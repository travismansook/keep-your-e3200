#!/usr/bin/env python3
"""Optional Linux kernel test in disposable namespaces, NOT the home network.

Requires root, iproute2, libpcap, Python 3.11+. Exercises the actual forwarder,
Linux raw-IP byte order, device binding, privilege drop, local delivery test,
and a simulated real router's OFFER/ACK/renewal. Does not alter host interfaces.
"""
import argparse
import os
from pathlib import Path
import pwd
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import forwarder as f

SERVER=socket.inet_aton('198.18.0.1')
OFFER=socket.inet_aton('198.18.0.50')


def dhcp(kind,mac,xid,ciaddr=f.ZERO):
    body=bytearray(240)
    body[:4]=bytes((2 if kind in (2,5) else 1,1,6,0))
    struct.pack_into('!I',body,4,xid)
    struct.pack_into('!H',body,10,0x8000)
    body[12:16]=ciaddr
    if body[0]==2:body[16:20]=OFFER
    body[28:34]=mac
    body[236:240]=f.COOKIE
    options=[(53,bytes((kind,))),(61,b'\x01'+mac)]
    if kind in (2,3,5):options.append((54,SERVER))
    if kind==3 and ciaddr==f.ZERO:options.append((50,OFFER))
    for code,value in options:body.extend(bytes((code,len(value)))+value)
    body.append(255)
    body.extend(b'\0'*max(0,300-len(body)))
    return bytes(body)


def wire(sock,mac,payload,response=False):
    sock.send(b'\xff'*6+mac+b'\x08\x00'+f.udp_ip(payload,SERVER if response else f.ZERO,f.BROADCAST,
                                                    67 if response else 68,68 if response else 67))


def role(name):
    interface='eth0' if name=='client' else 'wifi0'
    mac,_=f.interface_info(interface)
    with socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x0800)) as sock:
        sock.bind((interface,0))
        sock.settimeout(15 if name=='router' else 4)
        if name=='router':
            while True:
                packet=f.parse_frame(sock.recv(4096))
                parsed=f.parse_dhcp(packet['payload']) if packet else None
                if not parsed or parsed['op']!=1:continue
                if parsed['xid']==18:
                    assert parsed['ciaddr']==f.ZERO and parsed['values'].get(50)==OFFER, 'Renewal conversion failed'
                kind=2 if parsed['msg']==1 else 5
                wire(sock,mac,dhcp(kind,parsed['mac'],parsed['xid']),True)
        else:
            for request,expected,xid,ciaddr in ((1,2,17,f.ZERO),(3,5,17,f.ZERO),(3,5,18,OFFER)):
                wire(sock,mac,dhcp(request,mac,xid,ciaddr))
                end=time.monotonic()+4
                while time.monotonic()<end:
                    packet=f.parse_frame(sock.recv(4096))
                    parsed=f.parse_dhcp(packet['payload']) if packet else None
                    if parsed and parsed['op']==2 and parsed['msg']==expected and parsed['xid']==xid:
                        assert parsed['mac']==mac and parsed['values'].get(54)==SERVER
                        assert packet['src']==SERVER and packet['payload'][16:20]==OFFER
                        break
                else:raise AssertionError('No matching DHCP reply')
            print('PASS: Linux DHCP OFFER, ACK and renewal delivered from the simulated real router')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--role',choices=('client','router'))
    args=parser.parse_args()
    if sys.platform!='linux' or os.geteuid()!=0:parser.error('Run on Linux with sudo; it does not use home interfaces.')
    if args.role:
        role(args.role)
        return
    token=uuid.uuid4().hex[:6]
    names={k:'e3-'+k+'-'+token for k in ('h','r','c')}
    processes=[]
    made=[]
    def cmd(*args):subprocess.run(args,check=True,capture_output=True,text=True,timeout=10)
    def ipns(n,*args):cmd('ip','netns','exec',names[n],*args)
    with tempfile.TemporaryDirectory(prefix='e3200-kernel-test-') as temporary:
        base=Path(temporary)
        try:
            for ns in names.values():
                cmd('ip','netns','add',ns);made.append(ns)
            for n in names:ipns(n,'ip','link','set','lo','up')
            for other,target in [('r','wifi0'),('c','eth0')]:
                # Create both ends directly inside disposable namespaces: no
                # physical or host-namespace interfaces are reconfigured.
                ipns('h','ip','link','add',target,'type','veth','peer','name',target,'netns',names[other])
                for n in ('h',other):ipns(n,'ip','link','set',target,'up')
            ipns('h','ip','address','add','198.18.0.2/24','dev','wifi0')
            ipns('r','ip','address','add','198.18.0.1/24','dev','wifi0')
            ipns('h','ip','address','add','169.254.88.1/16','dev','eth0')
            nobody=pwd.getpwnam('nobody')
            lock=base/'forward.lock';lock.touch();os.chown(lock,nobody.pw_uid,nobody.pw_gid)
            with (base/'router.log').open('w') as router_log,(base/'forwarder.log').open('w') as helper_log:
                router=subprocess.Popen(['ip','netns','exec',names['r'],sys.executable,__file__,'--role','router'],stdout=router_log,stderr=subprocess.STDOUT)
                processes.append(router)
                helper=subprocess.Popen(['ip','netns','exec',names['h'],sys.executable,str(Path(__file__).resolve().parents[1]/'src/forwarder.py'),
                    '--ethernet','eth0','--wifi','wifi0','--server','198.18.0.1','--extender-mac','02:00:00:00:00:02',
                    '--uid',str(nobody.pw_uid),'--gid',str(nobody.pw_gid),'--lock-file',str(lock)],stdout=helper_log,stderr=subprocess.STDOUT)
                processes.append(helper)
                end=time.monotonic()+8
                while 'FORWARDER READY:' not in (base/'forwarder.log').read_text():
                    if helper.poll() is not None or time.monotonic()>end:
                        raise AssertionError('Forwarder startup failed:\n'+(base/'forwarder.log').read_text())
                    time.sleep(.05)
                subprocess.run(['ip','netns','exec',names['c'],sys.executable,__file__,'--role','client'],check=True,timeout=15)
                helper.send_signal(signal.SIGTERM)
                assert helper.wait(timeout=5)==0
                print((base/'forwarder.log').read_text())
        except Exception:
            for file in base.glob('*.log'):print(file.name+'\n'+file.read_text(),file=sys.stderr)
            raise
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=2)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
            for ns in reversed(made):subprocess.run(['ip','netns','delete',ns],capture_output=True)


if __name__=='__main__':main()

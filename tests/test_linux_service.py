"""Inert-process Linux supervisor tests; no DHCP, capture, or host changes."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]


def wait_for(check, timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if check():return
        time.sleep(.03)
    raise AssertionError('Timed out waiting for simulated Linux helper')


def alive(pid):
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False


class LinuxServiceTests(unittest.TestCase):
    def fixture(self, base, mode='full'):
        for name in ('state','runtime'):(base/name).mkdir()
        for role in ('E3200','Ethernet'):
            code='''import os,signal,sys,time
from pathlib import Path
base=Path(BASE)
role=ROLE
(base/(role+'.pid')).write_text(str(os.getpid()))
if (base/('fail-'+role)).exists():sys.exit(7)
signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
if role=='Ethernet' and (base/'unplugged').exists():sys.exit(75)
if role=='Ethernet' and (base/'slow-start').exists():time.sleep(.7)
print('dnsmasq: started, version inert' if role=='E3200' else 'FORWARDER READY: inert',flush=True)
while True:
 if role=='Ethernet' and (base/'unplugged').exists():sys.exit(75)
 time.sleep(.03)
'''.replace('BASE',repr(str(base))).replace('ROLE',repr(role))
            (base/(role+'.py')).write_text(code)
        wrapper=base/'run.py'
        wrapper.write_text('''import sys,subprocess,pwd,json
from pathlib import Path
sys.path.insert(0, SOURCE)
import linux_service as service
base=Path(BASE)
popen=subprocess.Popen
service.subprocess.run=lambda *args,**kwargs:subprocess.CompletedProcess(args,0)
def launch(args,**kwargs):
 role='E3200' if args[0]=='/usr/sbin/dnsmasq' else 'Ethernet'
 return popen([sys.executable,str(base/(role+'.py'))],**kwargs)
service.subprocess.Popen=launch
def identity(profile):
 if (base/'wifi-lost').exists():raise ValueError('Home Wi-Fi unavailable')
 return {'ip':'192.0.2.10'}
service.network.home_identity=identity
p=dict(version=1,mode=MODE,wifi_interface='wlan0',wifi_mac='02:00:00:00:00:10',
 ethernet_interface='eth0',ethernet_mac='02:00:00:00:00:11',gateway='192.0.2.1',subnet_mask='255.255.255.0',
 home_router_mac='02:00:00:00:00:01',extender_mac='02:00:00:00:00:02',extender_ip='192.0.2.250',
 lease_minutes=60,address_plan_confirmed=True)
if p['mode']=='compatibility':p.update(ethernet_interface=None,ethernet_mac=None)
raise SystemExit(service.supervise(p,pwd.getpwuid(__import__('os').getuid()),base/'state',base/'runtime'))
'''.replace('SOURCE',repr(str(ROOT/'src'))).replace('BASE',repr(str(base))).replace('MODE',repr(mode)))
        return wrapper

    def run_case(self, mode, action):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            wrapper=self.fixture(base,mode)
            if action=='failure':(base/'fail-Ethernet').touch()
            if action=='startup':(base/'slow-start').touch()
            output=base/'output.log'
            with output.open('w') as file:
                process=subprocess.Popen([sys.executable,str(wrapper)],stdout=file,stderr=subprocess.STDOUT,start_new_session=True)
                def status():
                    try:return json.loads((base/'state/status.json').read_text())['state']
                    except (OSError,ValueError):return None
                try:
                    if action=='failure':
                        self.assertEqual(process.wait(timeout=8),1,output.read_text())
                        self.assertEqual(status(),'error')
                    else:
                        if action=='startup':
                            wait_for(lambda:status()=='starting')
                            report=json.loads((base/'state/status.json').read_text())
                            self.assertIn('Home Wi-Fi is verified',report['detail'])
                        wait_for(lambda:status()==('ready' if mode=='full' else 'compatibility'))
                        dns=int((base/'E3200.pid').read_text())
                        if action=='dedup':
                            before=(base/'state/status.json').stat().st_mtime_ns
                            time.sleep(.7)
                            self.assertEqual((base/'state/status.json').stat().st_mtime_ns,before)
                            self.assertEqual(output.read_text().count('READY: Both helper components are running'),1)
                        if action=='cable':
                            old_bridge=int((base/'Ethernet.pid').read_text())
                            (base/'unplugged').touch()
                            wait_for(lambda:status()=='ethernet-wait')
                            self.assertTrue(alive(dns))
                            self.assertFalse(alive(old_bridge))
                            (base/'unplugged').unlink()
                            wait_for(lambda:status()=='ready',timeout=10)
                            self.assertEqual(dns,int((base/'E3200.pid').read_text()))
                        if action=='wifi':
                            (base/'wifi-lost').touch()
                            wait_for(lambda:status()=='paused')
                            self.assertFalse(alive(dns))
                            self.assertIsNone(process.poll())
                            (base/'wifi-lost').unlink()
                            wait_for(lambda:status()==('ready' if mode=='full' else 'compatibility'))
                            self.assertNotEqual(dns,int((base/'E3200.pid').read_text()))
                        process.send_signal(signal.SIGINT)
                        self.assertEqual(process.wait(timeout=6),0,output.read_text())
                        self.assertEqual(status(),'stopped')
                finally:
                    if process.poll() is None:
                        process.terminate();process.wait(timeout=6)
            for file in base.glob('*.pid'):
                self.assertFalse(alive(int(file.read_text())),file.name)
            if mode=='compatibility':self.assertFalse((base/'Ethernet.pid').exists())

    def test_full_stop_and_repeated_wifi_recovery(self):self.run_case('full','wifi')
    def test_compatibility_wifi_recovery_starts_no_forwarder(self):self.run_case('compatibility','wifi')
    def test_ethernet_reconnect_keeps_compatibility_alive(self):self.run_case('full','cable')
    def test_fatal_component_error_reaps_peer(self):self.run_case('full','failure')
    def test_unchanged_status_is_not_rewritten_or_logged_repeatedly(self):self.run_case('full','dedup')
    def test_slow_start_does_not_keep_claiming_wifi_is_still_being_checked(self):self.run_case('full','startup')


if __name__=='__main__':unittest.main()

"""Linux network discovery and interface-bound DHCP delivery.

Requires iproute2 and libpcap. No interface, routing, firewall, or sysctl changes.
"""
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess


def interface_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,14}', value) or value == 'lo':
        raise ValueError('Choose a physical Wi-Fi or Ethernet interface, such as wlan0 or eth0.')
    return value


def command(args, timeout=2):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Could not read the network connection.')
    return result.stdout


def ip_json(*args):
    return json.loads(command(['ip', '-j', *args]))


def snapshot(name):
    name = interface_name(name)
    rows = ip_json('address', 'show', 'dev', name)
    if len(rows) != 1:
        raise RuntimeError('Network interface is missing: ' + name)
    row = rows[0]
    addresses = [a for a in row.get('addr_info', []) if a.get('family') == 'inet']
    address = addresses[0] if addresses else None
    mac = row.get('address', '').lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac):
        raise RuntimeError('No Ethernet-format address on ' + name)
    return dict(device=name, mac=mac, active='LOWER_UP' in row.get('flags', []),
                ip=address['local'] if address else None,
                mask=str(ipaddress.IPv4Network('0.0.0.0/' + str(address['prefixlen'])).netmask) if address else None,
                wifi=(Path('/sys/class/net') / name / 'wireless').exists())


def connections():
    result = []
    for row in ip_json('link', 'show'):
        try:
            result.append(snapshot(row['ifname']))
        except (ValueError, RuntimeError):
            pass
    return result


def interface_info(name):
    info = snapshot(name)
    if not info['active']:
        raise RuntimeError('Network cable or Wi-Fi is disconnected: ' + name)
    return bytes.fromhex(info['mac'].replace(':', '')), info['ip']


def router_for(name):
    rows = ip_json('-4', 'route', 'show', 'default', 'dev', interface_name(name))
    gateways = {row['gateway'] for row in rows if row.get('gateway')}
    if len(gateways) != 1:
        raise ValueError('Wi-Fi needs exactly one IPv4 default gateway. Check Wi-Fi and any VPN.')
    return gateways.pop()


def home_identity(profile):
    info = snapshot(profile['wifi_interface'])
    if not info['wifi'] or not info['active'] or not info['ip']:
        raise ValueError('Home Wi-Fi is disconnected or has no IPv4 address.')
    if info['mac'] != profile['wifi_mac']:
        raise ValueError('The selected Wi-Fi adapter changed. Review Settings.')
    network = ipaddress.IPv4Network(profile['gateway'] + '/' + profile['subnet_mask'], strict=False)
    if (info['mask'] != profile['subnet_mask'] or ipaddress.IPv4Address(info['ip']) not in network
            or router_for(info['device']) != profile['gateway']):
        raise ValueError('This Wi-Fi connection does not match the configured home network.')
    def neighbor():
        for row in ip_json('neigh', 'show', 'to', profile['gateway'], 'dev', info['device']):
            if row.get('lladdr') and not set(row.get('state', [])).intersection({'FAILED', 'INCOMPLETE'}):
                return row['lladdr'].lower()
    mac = neighbor()
    if mac is None:
        try:
            subprocess.run(['ping', '-n', '-I', info['device'], '-c', '1', '-W', '1', profile['gateway']],
                           capture_output=True, timeout=1.5)
        except subprocess.TimeoutExpired:
            pass
        mac = neighbor()
    if mac is None or mac != profile['home_router_mac']:
        raise ValueError('The home router hardware address cannot be verified. Waiting for the home connection.')
    return info


class RawDelivery:
    """Linux raw IPv4 uses network byte order, unlike Darwin's raw-IP API."""
    def __init__(self, interface):
        self.interface = interface_name(interface)
        self.index = socket.if_nametoindex(interface)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        try:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_BINDTODEVICE', 25), interface.encode() + b'\0')
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except BaseException:
            self.sock.close()
            raise

    def send(self, payload, source, dest=b'\xff' * 4, sport=67, dport=68):
        from forwarder import udp_ip
        wire = udp_ip(payload, source, dest, sport, dport, secrets.randbits(16))
        if self.sock.sendto(wire, (socket.inet_ntoa(dest), 0)) != len(wire):
            raise RuntimeError('Incomplete Linux Ethernet delivery')

    def self_test(self, own_ip):
        if not own_ip:
            raise RuntimeError('Ethernet needs its link-local address first; wait for NetworkManager.')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_BINDTODEVICE', 25), self.interface.encode() + b'\0')
            receiver.setsockopt(socket.IPPROTO_IP, 8, 1)  # Linux IP_PKTINFO
            receiver.bind(('', 0))
            receiver.settimeout(1.5)
            nonce = b'DHCP-bridge-delivery-check:' + secrets.token_bytes(16)
            self.send(nonce, socket.inet_aton(own_ip), dport=receiver.getsockname()[1], sport=49153)
            data, controls, flags, _ = receiver.recvmsg(512, 512)
            indices = [struct.unpack_from('=I', value)[0] for level, kind, value in controls
                       if level == socket.IPPROTO_IP and kind == 8 and len(value) >= 12]
            if data != nonce or self.index not in indices or flags & getattr(socket, 'MSG_CTRUNC', 8):
                raise RuntimeError('Linux local Ethernet delivery/interface check failed')
        print('SELFTEST PASS: Linux Ethernet delivery reaches local UDP on the selected interface', flush=True)

    def close(self):
        self.sock.close()

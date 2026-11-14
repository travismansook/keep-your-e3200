"""Validated Linux settings and the narrowly scoped E3200 dnsmasq config."""
import ipaddress
import json
import os
from pathlib import Path
import tempfile
from configuration import address, normalize_mac
from linux_network import interface_name

CONFIG = Path('/etc/keep-your-e3200/profile.json')
STATE = Path('/var/lib/keep-your-e3200')
RUNTIME = Path('/run/keep-your-e3200')
UNIT = 'keep-your-e3200.service'
USER = 'e3200-helper'
VERSION = '0.1.0~preview3'
FIELDS = {'version', 'mode', 'wifi_interface', 'wifi_mac', 'ethernet_interface', 'ethernet_mac',
          'gateway', 'subnet_mask', 'home_router_mac', 'extender_mac', 'extender_ip',
          'lease_minutes', 'address_plan_confirmed'}
VENDOR = '00:00:0d:e9:21:04:06:38:38:30:33:35:35:05:10:47:30:30:30:30:30:30:30:30:30:30:30:30:30:30:30:06:05:47:33:31:30:30'


def validate(values):
    if (not isinstance(values, dict) or set(values) != FIELDS
            or type(values['version']) is not int or values['version'] != 1):
        raise ValueError('Saved Linux settings are incomplete. Open Setup again.')
    p = dict(values)
    if p['mode'] not in ('full', 'compatibility'):
        raise ValueError('Select Wi-Fi + Ethernet or Wi-Fi-only mode.')
    for field in ('wifi_interface',):
        p[field] = interface_name(p[field])
    for field in ('wifi_mac', 'home_router_mac', 'extender_mac'):
        p[field] = normalize_mac(p[field])
    if p['mode'] == 'full':
        p['ethernet_interface'] = interface_name(p['ethernet_interface'])
        p['ethernet_mac'] = normalize_mac(p['ethernet_mac'])
        if p['ethernet_interface'] == p['wifi_interface']:
            raise ValueError('Wi-Fi and Ethernet must be separate interfaces.')
    elif p['ethernet_interface'] is not None or p['ethernet_mac'] is not None:
        raise ValueError('Wi-Fi-only settings must not include an Ethernet adapter.')
    if p['extender_mac'] in (p['wifi_mac'], p['ethernet_mac'], p['home_router_mac']):
        raise ValueError('Use LAN1 MAC from the E3200 sticker, not an address from this computer or the router.')
    gateway = address(p['gateway'])
    extender = address(p['extender_ip'])
    network = ipaddress.IPv4Network(str(gateway) + '/' + p['subnet_mask'], strict=False)
    if not 8 <= network.prefixlen <= 29 or extender not in network or extender in (
            gateway, network.network_address, network.broadcast_address):
        raise ValueError('Choose an available E3200 IPv4 address on the home network.')
    if type(p['lease_minutes']) is not int or not 2 <= p['lease_minutes'] <= 525600:
        raise ValueError('Lease time must be from 2 minutes to 365 days.')
    if p['address_plan_confirmed'] is not True:
        raise ValueError('Confirm that the router reserves the chosen address for this E3200.')
    p.update(gateway=str(gateway), extender_ip=str(extender), subnet_mask=str(network.netmask))
    return p


def load(path=CONFIG):
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        raise ValueError('No saved setup yet. Choose Setup from Home or run keep-your-e3200 setup.')
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022 or path.stat().st_size > 16384:
        raise ValueError('The settings must be a small, root-owned file that other users cannot edit.')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('The settings contain a duplicate field.')
            result[key] = value
        return result
    return validate(json.loads(path.read_text(), object_pairs_hook=unique))


def atomic_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing to replace a symbolic link.')
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            os.fchmod(file.fileno(), 0o600)
            json.dump(value, file, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(path, values):
    atomic_json(path, validate(values))


def dnsmasq_config(profile, lease_file):
    p = validate(profile)
    network = ipaddress.IPv4Network(p['gateway'] + '/' + p['subnet_mask'], strict=False)
    return '\n'.join([
        '# E3200 only. The real router remains the allocator for all other clients.',
        'port=0', 'interface=' + p['wifi_interface'], 'bind-interfaces', 'except-interface=lo',
        'user=' + USER, 'group=' + USER,
        'dhcp-range=%s,static,%s,%dm' % (network.network_address, p['subnet_mask'], p['lease_minutes']),
        'dhcp-host=%s,%s,set:e3200' % (p['extender_mac'], p['extender_ip']),
        'dhcp-ignore=tag:!known',
        'dhcp-option=tag:e3200,option:router,' + p['gateway'],
        'dhcp-option=tag:e3200,option:dns-server,' + p['gateway'],
        'dhcp-option-force=tag:e3200,60,"ARCADYAN"',
        'dhcp-option-force=tag:e3200,125,' + VENDOR,
        'dhcp-leasefile=' + str(lease_file), 'log-dhcp', 'log-facility=-', ''])

"""Private configuration and read-only Mac connection discovery."""
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess

FIELDS = {'extender_mac', 'extender_ip', 'gateway', 'dns', 'subnet_mask',
          'ethernet_interface', 'ethernet_mac', 'wifi_interface',
          'lease_minutes', 'address_plan_confirmed'}


def normalize_mac(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{2}([:-][0-9a-fA-F]{2}){5}', value):
        raise ValueError('Use the six pairs on the device label, such as 02:00:00:00:00:02.')
    raw = bytes.fromhex(value.replace(':', '').replace('-', ''))
    if raw == b'\0' * 6 or raw[0] & 1:
        raise ValueError('That is not a usable device MAC address.')
    return raw.hex(':')


def address(value):
    if not isinstance(value, str):
        raise ValueError('Enter an IPv4 address using dots, such as 192.168.1.1.')
    try:
        ip = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise ValueError('Enter an IPv4 address using dots, such as 192.168.1.1.') from exc
    if ip.is_unspecified or ip.is_loopback or ip.is_link_local or ip.is_multicast or int(ip) >= 0xf0000000:
        raise ValueError('Use an ordinary address on your home network.')
    return ip


def validate(profile):
    if not isinstance(profile, dict) or set(profile) != FIELDS:
        raise ValueError('The saved settings are incomplete. Run the helper with --setup.')
    result = dict(profile)
    for key in ('extender_mac', 'ethernet_mac'):
        result[key] = normalize_mac(result[key])
    if result['extender_mac'] == result['ethernet_mac']:
        raise ValueError('The E3200 and your Mac adapter must have different MAC addresses.')
    for key in ('ethernet_interface', 'wifi_interface'):
        if not isinstance(result[key], str) or not re.fullmatch(r'en[0-9]+', result[key]):
            raise ValueError('Choose a physical Ethernet or Wi-Fi connection from setup.')
    if result['ethernet_interface'] == result['wifi_interface']:
        raise ValueError('Ethernet and Wi-Fi must be two different connections.')
    gateway, extender, dns = (address(result[key]) for key in ('gateway', 'extender_ip', 'dns'))
    try:
        network = ipaddress.IPv4Network(str(gateway) + '/' + result['subnet_mask'], strict=False)
    except (ValueError, TypeError) as exc:
        raise ValueError('The home network subnet mask is invalid.') from exc
    if not 8 <= network.prefixlen <= 29:
        raise ValueError('This preview supports ordinary home subnets from /8 to /29.')
    if extender not in network or extender in (network.network_address, network.broadcast_address, gateway):
        raise ValueError('Choose a different usable E3200 address on the same home network as the router.')
    minutes = result['lease_minutes']
    if type(minutes) is not int or not 2 <= minutes <= 525600:
        raise ValueError('The lease must be between 2 minutes and 365 days.')
    if result['address_plan_confirmed'] is not True:
        raise ValueError('Check the chosen E3200 address on your router before starting.')
    result.update(gateway=str(gateway), extender_ip=str(extender), dns=str(dns),
                  subnet_mask=str(network.netmask))
    return result


def load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid() or path.stat().st_size > 16384:
        raise ValueError('The private settings file has an unexpected type or owner.')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('The settings contain a duplicate field.')
            result[key] = value
        return result
    return validate(json.loads(path.read_text(), object_pairs_hook=unique))


def save(path, profile):
    path = Path(path)
    profile = validate(profile)
    if path.parent.is_symlink() or not path.parent.is_dir() or path.parent.stat().st_uid != os.getuid():
        raise ValueError('Use the private settings folder created by this helper.')
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w') as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(profile, output, indent=2)
        output.write('\n')


def output(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=8)
    return result.stdout if result.returncode == 0 else ''


def connections():
    ports = output(['/usr/sbin/networksetup', '-listallhardwareports'])
    result = []
    for label, device in re.findall(r'Hardware Port: ([^\n]+)\nDevice: (en[0-9]+)', ports):
        details = output(['/sbin/ifconfig', device])
        mac = re.search(r'\bether ([0-9a-fA-F:]{17})', details)
        ip = re.search(r'\binet ([0-9.]+) netmask (0x[0-9a-fA-F]+|[0-9.]+)', details)
        mask = None
        if ip:
            mask = str(ipaddress.IPv4Address(int(ip[2], 16))) if ip[2].startswith('0x') else ip[2]
        if mac:
            result.append(dict(label=label.strip(), device=device, mac=normalize_mac(mac[1]),
                               ip=ip[1] if ip else None, mask=mask,
                               active='status: active' in details,
                               wifi=label.strip().lower() in ('wi-fi', 'airport')))
    return result


def router_for(wifi):
    text = output(['/usr/sbin/ipconfig', 'getoption', wifi, 'router'])
    for value in text.split():
        try:
            return str(address(value))
        except ValueError:
            pass
    text = output(['/sbin/route', '-n', 'get', '-ifscope', wifi, 'default'])
    match = re.search(r'gateway:\s*([0-9.]+)', text)
    return str(address(match[1])) if match else None


def runtime_values(profile, items=None, router=None):
    profile = validate(profile)
    found = {item['device']: item for item in (connections() if items is None else items)}
    wired = found.get(profile['ethernet_interface'])
    wifi = found.get(profile['wifi_interface'])
    if not wired or not wired['active'] or wired['wifi'] or wired['mac'] != profile['ethernet_mac']:
        raise ValueError('Reconnect the Ethernet adapter selected in setup, or run --setup to choose another.')
    if not wifi or not wifi['active'] or not wifi['wifi'] or not wifi['ip']:
        raise ValueError('Connect the Mac to your home Wi-Fi as well as Ethernet.')
    ip = address(wifi['ip'])
    network = ipaddress.IPv4Network(profile['gateway'] + '/' + profile['subnet_mask'], strict=False)
    actual_router = router_for(wifi['device']) if router is None else router
    if ip not in network or wifi['mask'] != profile['subnet_mask'] or actual_router != profile['gateway']:
        raise ValueError('The Wi-Fi network differs from setup. Reconnect to home Wi-Fi or run --setup.')
    if str(ip) == profile['extender_ip'] or wired['ip'] == profile['extender_ip']:
        raise ValueError('The selected E3200 address is already used by this Mac. Choose another address in setup.')
    return dict(profile, wifi_ip=str(ip), network=str(network.network_address),
                subnet_hex=hex(int(network.netmask)))


def example():
    # Documentation-only values used by offline checks, never a real network profile.
    return validate(dict(extender_mac='02:00:00:00:00:02', extender_ip='192.0.2.250',
                         gateway='192.0.2.1', dns='192.0.2.1', subnet_mask='255.255.255.0',
                         ethernet_interface='en90', ethernet_mac='02:00:00:00:00:04',
                         wifi_interface='en91', lease_minutes=60, address_plan_confirmed=True))

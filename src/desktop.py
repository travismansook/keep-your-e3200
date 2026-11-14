#!/usr/bin/env python3
"""Guided entry point; native downloads also dispatch their bundled workers."""
import argparse
import fcntl
import gzip
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import readline
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

import configuration as config
import forwarder
import combined_worker

VERSION = '0.3.0'
STATE = Path.home() / 'Library/Application Support/E3200 CHR30A Helper'
RESOURCE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1] / 'build/package'))
FILES = {'launcher.command': 0o700, 'forwarder.py': 0o600,
         'combined_worker.py': 0o600, 'configuration.py': 0o600, 'dnsmasq': 0o700}


def internal(args):
    if args and Path(args[0]).name in ('forwarder.py', 'combined_worker.py'):
        name = Path(args[0]).name
        sys.argv = args
        result = forwarder.main() if name == 'forwarder.py' else combined_worker.main()
        return result or 0
    if args and args[0] == '--check-lock':
        if len(args) != 2:
            raise ValueError('A lock path is required.')
        fd = os.open(args[1], os.O_RDWR | os.O_NOFOLLOW)
        try:
            if os.fstat(fd).st_uid != os.getuid():
                raise ValueError('The forwarding lock has an unexpected owner.')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('A forwarding helper is already running. Stop its window with Ctrl+C.') from exc
        finally:
            os.close(fd)
        return 0
    return None


def private_folder(path):
    if path.is_symlink() or (path.exists() and (not path.is_dir() or path.stat().st_uid != os.getuid())):
        raise ValueError('The private data folder has an unexpected type or owner.')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def styled(text, color='36'):
    # Keep redirected output and plain terminals free of escape sequences.
    if sys.stdout.isatty() and os.environ.get('TERM') != 'dumb' and 'NO_COLOR' not in os.environ:
        return '\033[' + color + 'm' + text + '\033[0m'
    return text


def say(text=''):
    width = min(74, max(36, shutil.get_terminal_size(fallback=(80, 24)).columns - 4))
    print(textwrap.fill(text, width=width, initial_indent='  ', subsequent_indent='  ')
          if text else '')


def section(title, subtitle=None):
    rule = '─' * min(64, max(24, shutil.get_terminal_size(fallback=(80, 24)).columns - 4))
    print()
    print(styled('  ' + rule, '36'))
    if subtitle:
        say(styled(subtitle, '2'))
    say(styled(title, '1;36'))
    print(styled('  ' + rule, '36'))
    print()


def option(number, title, description):
    say(styled(str(number) + '  ' + title, '1'))
    say(description)
    print()


def ask(label, default=None):
    prompt = label + (' [' + str(default) + ']' if default is not None else '')
    # Keep the question outside the editable line. A plain input prompt also
    # gives libedit an accurate cursor boundary (ANSI colors count as bytes).
    print(styled('  ' + prompt + ':', '1;36'))
    readline.set_auto_history(False)
    answer = input('  > ').strip()
    return answer or default


class SetupCanceled(Exception):
    pass


def ask_value(label, check, default=None, help_text=None, allow_cancel=False):
    while True:
        value = ask(label, default)
        if allow_cancel and isinstance(value, str) and value.casefold() == 'cancel':
            raise SetupCanceled()
        if value == '?' and help_text:
            section('Reserve an address · Step-by-step guide')
            for paragraph in help_text:
                say(paragraph)
                print()
            continue
        try:
            return check(value)
        except (ValueError, TypeError) as exc:
            say(styled(str(exc), '33'))
            print()


def ask_yes_no(label, allow_cancel=False):
    def answer(value):
        word = value.casefold() if isinstance(value, str) else ''
        if word not in ('yes', 'no'):
            raise ValueError('Please type yes to confirm, or no to cancel, then press Return.')
        return word == 'yes'
    return ask_value(label, answer, allow_cancel=allow_cancel)


def confirm_address():
    return ask_yes_no('Address checked and protected? Type yes or no', allow_cancel=True)


def choose_mode(allow_back=False):
    section('KEEP YOUR E3200', VERSION + ' · CHR30A compatibility helper')
    say('Keep your extender useful. Choose how this Mac will help.')
    print()
    option(1, 'Wi-Fi + Ethernet · Recommended',
           'E3200 compatibility + automatic IPv4 for Ethernet devices. '
           'Connect this Mac to home Wi-Fi and by cable to the E3200.')
    option(2, 'Wi-Fi only',
           'E3200 compatibility only. No Mac Ethernet cable needed. '
           'This mode does not fix missing IPv4 for Ethernet devices.')
    say('Type 1 or 2, then press Return (Enter). A choice is required.')
    say('Type back to return to Home.' if allow_back else 'Type cancel to quit without starting.')
    print()
    def choice(value):
        if isinstance(value, str) and (value.casefold() == 'cancel' or (allow_back and value.casefold() == 'back')):
            return None
        if value not in ('1', '2'):
            raise ValueError('Please type 1 or 2, then press Return. Nothing has been selected.')
        return 'full' if value == '1' else 'compatibility'
    return ask_value('Choose 1 or 2', choice)


def menu_choice(label, allowed):
    def check(value):
        if value not in allowed:
            raise ValueError('Please type ' + ', '.join(allowed) + ', then press Return.')
        return value
    return ask_value(label, check)


def lease_label(minutes):
    return {60: '1 hour', 1440: '1 day', 525600: '1 year (365 days)'}.get(minutes, str(minutes) + ' minutes')


def failure_menu(message):
    section('Action needed')
    say(message)
    say('Read the details above. Correct the problem, then retry or return Home to check Settings.')
    option(1, 'Retry', 'Try the same connection mode again.')
    option(2, 'Home', 'Review or change your setup.')
    option(3, 'Quit', 'Close the launcher.')
    return menu_choice('Choose 1, 2 or 3', ('1', '2', '3'))


def return_to_settings():
    print()
    ask('Press Return to return to Settings')


def review_settings(profile):
    section('Saved settings')
    for label, value in [
        ('Mode', 'Wi-Fi + Ethernet' if profile['mode'] == 'full' else 'Wi-Fi only'),
        ('E3200 address', profile['extender_ip']), ('E3200 LAN1 MAC', profile['extender_mac']),
        ('Main router', profile['gateway']), ('DNS', profile['dns']), ('Subnet mask', profile['subnet_mask']),
        ('Mac Wi-Fi', profile['wifi_interface']),
        ('Mac Ethernet', profile['ethernet_interface'] if profile['mode'] == 'full' else 'not used in this mode'),
        ('E3200 lease offered', lease_label(profile['lease_minutes']) + ' (' + str(profile['lease_minutes']) + ' minutes)')]:
        say(label + ': ' + str(value))
    print()
    say('These are saved settings, not a live connection or accepted-lease check.')
    say('Ordinary device leases are controlled by the main router.')
    return_to_settings()


def settings_menu(profile):
    while True:
        section('Settings')
        say('Changes apply the next time you start the helper. Stop any running copy first.')
        print()
        option(1, 'Review current settings', 'Show the saved addresses, connections and lease duration.')
        option(2, 'Change lease duration', 'Keep all your other saved settings.')
        option(3, 'Run full setup again', 'Choose connections and enter the E3200 details again.')
        option(4, 'Back', 'Return to the main menu.')
        choice = menu_choice('Choose 1, 2, 3 or 4', ('1', '2', '3', '4'))
        if choice == '4':
            return profile
        if choice == '1':
            review_settings(profile)
        elif choice == '2':
            section('Change E3200 lease duration')
            say('Current duration: ' + lease_label(profile['lease_minutes']) + '.')
            say('This changes future offers after the helper is restarted. It does not immediately '
                'change the expiry of a lease the E3200 already accepted. Other devices still '
                'get their lease durations from the main router.')
            print()
            option(1, 'One hour', '60 minutes')
            option(2, 'One day', '1,440 minutes')
            option(3, 'One year', '525,600 minutes')
            option(4, 'Cancel', 'Keep the current duration.')
            lease = menu_choice('Choose 1, 2, 3 or 4', ('1', '2', '3', '4'))
            if lease == '4':
                say('Canceled. Your lease duration has not changed.')
            else:
                minutes = {'1': 60, '2': 1440, '3': 525600}[lease]
                if minutes == profile['lease_minutes']:
                    say('Already set to ' + lease_label(minutes) + '. No changes were made.')
                else:
                    section('Confirm lease change')
                    say('Current: ' + lease_label(profile['lease_minutes']))
                    say('New:     ' + lease_label(minutes))
                    say('All other settings will stay the same. This applies to future offers after restarting.')
                    if ask_yes_no('Save this change? Type yes or no'):
                        updated = config.validate(dict(profile, lease_minutes=minutes))
                        try:
                            config.save(STATE / 'profile.json', updated)
                        except OSError as exc:
                            say('Could not save the change. Your previous settings are unchanged.')
                            say('Details: ' + str(exc))
                        else:
                            profile = updated
                            say('Saved. E3200 lease duration: ' + lease_label(minutes) + '.')
                    else:
                        say('Canceled. Your lease duration has not changed.')
            return_to_settings()
        else:
            mode = choose_mode(allow_back=True)
            if mode is None:
                continue
            try:
                updated = setup(mode, profile)
            except (ValueError, OSError) as exc:
                say('Could not complete setup: ' + str(exc))
                updated = None
            if updated is not None:
                profile = updated
            return_to_settings()


def saved_menu(profile):
    while True:
        section('KEEP YOUR E3200', VERSION)
        option(1, 'Start helper', 'Choose Wi-Fi + Ethernet or Wi-Fi only.')
        option(2, 'Settings', 'Review settings, change the lease, or run setup again.')
        option(3, 'Quit', 'Close without starting the helper.')
        option(4, 'Help and troubleshooting', 'Connection checklist, shortcuts and log location.')
        choice = menu_choice('Choose 1, 2, 3 or 4', ('1', '2', '3', '4'))
        if choice == '1':
            return profile
        if choice == '3':
            return None
        if choice == '4':
            section('Help and troubleshooting')
            say('1. Keep home Wi-Fi connected. Recommended mode also needs the Mac Ethernet cable to the E3200.')
            say('2. Keep the E3200 connected by coax to the CHR30A and its MoCA module.')
            say('3. Disconnect any VPN on this Mac before starting.')
            say('4. Ctrl+C while running stops this helper and returns Home.')
            say('5. Settings can review your setup or change the E3200 lease.')
            say('Logs and saved settings: ' + str(STATE))
            say('Finder: press Command+Shift+G and paste that folder path.')
            ask('Press Return to return Home')
            continue
        profile = settings_menu(profile)


def show_info(profile):
    minutes = profile['lease_minutes']
    if minutes == 525600:
        duration = '1 year (365 days)'
    elif minutes % 1440 == 0:
        days = minutes // 1440
        duration = str(days) + (' day' if days == 1 else ' days')
    elif minutes % 60 == 0:
        hours = minutes // 60
        duration = str(hours) + (' hour' if hours == 1 else ' hours')
    else:
        duration = str(minutes) + ' minutes'
    section('Your setup', 'REVIEW')
    say('Mode: ' + ('Wi-Fi + Ethernet · Recommended' if profile['mode'] == 'full' else 'Wi-Fi-only compatibility'))
    say('E3200 address: ' + profile['extender_ip'])
    say('E3200 LAN1 MAC: ' + profile['extender_mac'])
    say('Main router: ' + profile['gateway'])
    say('DNS: ' + profile['dns'])
    print()
    say('Mac Wi-Fi connection: ' + profile['wifi_interface'])
    say('Mac Ethernet connection: ' + (profile['ethernet_interface'] if profile['mode'] == 'full' else 'not required; Ethernet IPv4 fix is OFF'))
    print()
    say('E3200 lease offered: ' + duration + ' (' + str(minutes) + ' minutes)')
    say('Ordinary device leases: controlled by the main router')
    say('Run time: until you stop it with Ctrl+C')
    print()
    say('The lease above is configured; acceptance is confirmed in the E3200 DHCP log. '
        'Its settings page becomes available after it accepts its address.')
    print()
    section('Before starting · Mac VPN')
    say('If a VPN is running on this Mac, disconnect it before starting the helper. '
        'It can block the direct Wi-Fi check or access to your home network.')
    say('Keep the Mac VPN disconnected while relying on this workaround until '
        'your VPN settings have been tested with it. Reconnecting it may interrupt the helper.')
    say('This note is about the VPN on this Mac. The helper does not turn it off '
        'or change any VPN settings for you.')
    print()


def setup(mode='full', previous=None):
    try:
        return setup_questions(mode, previous)
    except SetupCanceled:
        section('Setup canceled')
        say('Saved settings are unchanged. No helper services were started.')
        return None


def setup_questions(mode='full', previous=None):
    section('Update saved setup' if previous else 'First-time setup', 'KEEP YOUR E3200')
    say('Type each answer, then press Return. When a question has a [default], '
        'press Return alone to accept it.')
    say('Take your time. This window waits while you look up the details.')
    say('Type cancel at any setup question to leave without saving.')
    print()
    say('Connect this Mac to your home Wi-Fi. Keep the E3200 connected to '
        'the main CHR30A by coax.')
    if mode == 'full':
        say('Also connect the Mac Ethernet cable directly to an Ethernet port on the E3200.')
    previous = previous or {}
    print()
    say('Setup reads your connections. It does not change your network settings.')
    items = config.connections()
    wifi = [item for item in items if item['wifi'] and item['active'] and item['ip']]
    wired = [item for item in items if not item['wifi'] and item['active']]
    if len(wifi) != 1 or (mode == 'full' and not wired):
        raise ValueError('Connect home Wi-Fi with working IPv4, and Ethernet if you selected the recommended mode.')
    wifi = wifi[0]
    config.address(wifi['ip'])
    network = ipaddress.IPv4Network(wifi['ip'] + '/' + wifi['mask'], strict=False)
    if not 8 <= network.prefixlen <= 29:
        raise ValueError('This preview needs a home Wi-Fi subnet from /8 to /29.')
    mac_addresses = {item['mac'] for item in items}
    local_addresses = {item.get('ip') for item in items}
    cable = None
    step_number = 0
    def step(title):
        nonlocal step_number
        step_number += 1
        section(title, 'STEP ' + str(step_number) + ' OF ' + ('5' if mode == 'full' else '4'))
    if mode == 'full':
        step('Choose your Ethernet connection')
        say('Select the Mac adapter whose cable goes to the E3200.')
        print()
        for number, item in enumerate(wired, 1):
            option(number, item['label'], 'Current address: ' + (item['ip'] or 'waiting for an address'))
        say('An address starting with 169.254 means Ethernet has no usable IPv4 yet. '
            'You can still select it; keep home Wi-Fi connected.')
        print()
        def choice(value):
            if value is None or not str(value).isdigit() or not 1 <= int(value) <= len(wired):
                raise ValueError('Choose one of the connection numbers above.')
            return wired[int(value) - 1]
        previous_number = next((str(index) for index, item in enumerate(wired, 1)
                                if item['mac'] == previous.get('ethernet_mac')), None)
        cable = ask_value('Which Ethernet connection leads to the E3200?', choice,
                          previous_number or ('1' if len(wired) == 1 else None), allow_cancel=True)
    step('Confirm your main router address')
    say('This is the address of your main CHR30A, usually 192.168.1.1. '
        'The default below comes from your Mac Wi-Fi connection.')
    print()
    say('To check it on your Mac:')
    say('Apple menu → System Settings → Wi-Fi → Details beside your home network → TCP/IP → Router.')
    print()
    say('Use the Router value. Press Return if the detected address is correct.')
    print()
    detected_router = config.router_for(wifi['device'])
    def router_address(value):
        address = config.address(value)
        if address not in network or address in (network.network_address, network.broadcast_address):
            raise ValueError('Use the Router address from this Mac home Wi-Fi connection; that address is outside its usable range.')
        if str(address) in local_addresses:
            raise ValueError('That address belongs to this Mac. Enter the Router value from Wi-Fi > Details > TCP/IP.')
        if detected_router and str(address) != detected_router:
            raise ValueError('This Mac home Wi-Fi reports Router ' + detected_router + '. Use that address, or reconnect to the correct home network.')
        return str(address)
    gateway = ask_value('Main CHR30A router address', router_address, detected_router, allow_cancel=True)
    step('Find the E3200 sticker')
    say('Look at the sticker on the BACK of your E3200.')
    print()
    say(styled('Under Serial#, find LAN1 MAC:', '1'))
    say('Enter the six pairs printed beside LAN1 MAC. Type only the address, not the label.')
    print()
    say('Example format: 02.00.00.00.00.AA (use your own sticker).')
    say('Dots, colons and hyphens all work. Uppercase and lowercase both work. '
        'The helper converts the address automatically.')
    print()
    say('Use LAN1 MAC, not the serial number, a Wi-Fi radio MAC or your Mac adapter MAC. '
        'You do not need to open the E3200 settings page to find it.')
    print()
    def extender_mac(value):
        normalized = config.normalize_mac(value)
        if normalized in mac_addresses:
            raise ValueError('That is a Mac adapter address. Copy LAN1 MAC from the sticker on the E3200.')
        return normalized
    mac = ask_value('E3200 LAN1 MAC', extender_mac, previous.get('extender_mac'), allow_cancel=True)
    say('Using LAN1 MAC: ' + mac)
    step('Reserve the E3200 settings-page address')
    say('This is the address you will use to open the extender settings in a browser.')
    say('Already reserved an address for THIS E3200? Reuse it.')
    print()
    say('Otherwise, leave this window open. In your browser:')
    say('1. Open https://' + gateway + ' and sign in to your main router.')
    say('2. Go to Network Settings → IPv4 Address Distribution → Connection List. '
        'You may need Advanced first.')
    say('3. Edit the entry for LAN1 MAC ' + mac + ', or choose Add static connection. '
        'Reserve an available address for this MAC, then Apply/save.')
    print()
    say('Enter that SAME address below. On a 192.168.1.x network, '
        '192.168.1.250 is an example; check it is allowed and available first.')
    print()
    say(styled('Need more help? Type ? below for the full reservation guide.', '1'))
    print()
    address_help = [
        'Open https://' + gateway + ' in a browser and sign in with your router administrator password. '
        'This may differ from your Wi-Fi password.',
        'Open Network Settings → IPv4 Address Distribution → Connection List. '
        'You may need Advanced first; names can vary with router software.',
        'Find the entry matching E3200 LAN1 MAC ' + mac + '. '
        'Reuse its existing reservation, or edit that entry to make it static. '
        'If there is no entry, choose Add static connection.',
        'For a new entry, use a name such as E3200, the LAN1 MAC above, and an available address '
        'allowed by your router. Check the device/reservation list and any manually configured devices '
        'to make sure the address does not belong to another device.',
        'To find the allowed range, open the edit/settings entry on IPv4 Address Distribution. '
        'Read Start IP Address and End IP Address. You do not need to change that range.',
        'If the router says outside DHCP range, choose a free address within its allowed range. '
        'If it says address/name already exists, check the existing entry instead of adding a duplicate.',
        'Apply/save the reservation. Return here and enter that exact address. '
        'An existing reservation for this E3200 is OK; an address used by another device is not.',
        'If you already excluded an address from automatic assignment for this E3200, '
        'you can reuse it after checking that no other device has it.'
    ]
    def extender_address(value):
        address = config.address(value)
        if address not in network or address in (network.network_address, network.broadcast_address):
            raise ValueError('Choose an available address on the same home network as your router, within its usable range.')
        if str(address) == gateway:
            raise ValueError('That is the main router address. Reserve a different address for the E3200.')
        if str(address) in local_addresses:
            raise ValueError('That address belongs to this Mac. Reserve a different address for the E3200.')
        return str(address)
    extender = ask_value('E3200 settings-page address', extender_address,
                         previous.get('extender_ip'), help_text=address_help, allow_cancel=True)
    print()
    say(styled('Check these match your router reservation:', '1'))
    say('E3200 address:  ' + extender)
    say('E3200 LAN1 MAC: ' + mac)
    print()
    say('The helper cannot check or create the router reservation for you. '
        'Confirm this exact address is reserved for this E3200 (or excluded from '
        'automatic assignment for it), and is not used by another device.')
    print()
    say('Type yes to confirm, or no to cancel. Uppercase and lowercase both work.')
    print()
    if not confirm_address():
        section('Setup canceled')
        say('Your saved settings are unchanged. No helper services were started.')
        return None
    step('Choose how long the E3200 keeps its address')
    say('A lease is how long the extender keeps an accepted address before it must renew it. '
        'It does not limit how long this helper runs.')
    print()
    option(1, 'One hour · Start here', 'Best for checking that address renewal works.')
    option(2, 'One day', 'A longer lease after initial testing.')
    option(3, 'One year · Advanced', 'A long lease; this still is not a permanent fix.')
    say('Other devices get their own lease lengths from the main router.')
    print()
    def lease(value):
        if value not in ('1', '2', '3'):
            raise ValueError('Choose 1, 2, or 3.')
        return {'1': 60, '2': 1440, '3': 525600}[value]
    previous_lease = {60: '1', 1440: '2', 525600: '3'}.get(previous.get('lease_minutes'), '1')
    minutes = ask_value('Lease option', lease, previous_lease, allow_cancel=True)
    profile = config.validate(dict(extender_mac=mac, extender_ip=extender, gateway=gateway,
                                  dns=gateway, subnet_mask=wifi['mask'],
                                  mode=mode, ethernet_interface=cable['device'] if cable else previous.get('ethernet_interface'),
                                  ethernet_mac=cable['mac'] if cable else previous.get('ethernet_mac'),
                                  wifi_interface=wifi['device'], lease_minutes=minutes,
                                  address_plan_confirmed=True))
    config.runtime_values(profile, items, gateway)
    config.save(STATE / 'profile.json', profile)
    section('Settings saved')
    say('Your settings are saved privately on this Mac. Your router and devices were not reconfigured.')
    return profile


def unpack(destination):
    runtime = RESOURCE / 'runtime'
    manifest = json.loads((runtime / 'manifest.json').read_text())
    if set(manifest) != set(FILES):
        raise ValueError('The included program manifest is incomplete. Download the helper again.')
    for name, mode in FILES.items():
        data = (runtime / name).read_bytes()
        if name == 'dnsmasq':
            data = gzip.decompress(data)
        if hashlib.sha256(data).hexdigest() != manifest[name]:
            raise ValueError('An included program is damaged. Download the helper again.')
        target = destination / name
        with target.open('xb') as output:
            output.write(data)
        target.chmod(mode)
    return manifest


def environment(values, folder, state, manifest):
    runner = sys.executable
    if not getattr(sys, 'frozen', False):
        # Source workflow: use the same interpreter for every subprocess.
        runner_path = folder / 'python-runner'
        runner_path.write_text('#!/bin/bash\nexec ' + shlex.quote(sys.executable) + ' '
                               + shlex.quote(str(Path(__file__).resolve())) + ' "$@"\n')
        runner_path.chmod(0o700)
        runner = str(runner_path)
    mapping = dict(STATE_DIR=str(state), MODE=values.get('mode', 'full'), ETHERNET=values['ethernet_interface'] or '',
                   ETHERNET_MAC=values['ethernet_mac'] or '', SERVER=values['gateway'],
                   MAC=values['extender_mac'], IP=values['extender_ip'],
                   WIFI=values['wifi_interface'], WIFI_IP=values['wifi_ip'],
                   SUBNET_MASK=values['subnet_mask'], SUBNET_HEX=values['subnet_hex'],
                   NETWORK=values['network'], DNS=values['dns'], LEASE_MINUTES=str(values['lease_minutes']),
                   PYTHON=runner, ENGINE_SHA256=manifest['dnsmasq'], PORTABLE_PARENT_PID=str(os.getpid()))
    return dict(os.environ, **{'E3200_' + key: value for key, value in mapping.items()})


def run(profile, dry_run=False, self_test=False):
    values = (dict(profile, wifi_ip='192.0.2.10', network='192.0.2.0', subnet_hex='0xffffff00')
              if self_test else config.runtime_values(profile))
    child = None
    stopped = None
    def signal_child(signum, _frame):
        nonlocal stopped
        stopped = signum
        if child is not None and child.poll() is None:
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass
    old_handlers = {sig: signal.signal(sig, signal_child)
                    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        with tempfile.TemporaryDirectory(prefix='e3200-chr30a-') as temporary:
            folder = Path(temporary)
            manifest = unpack(folder)
            state = folder / 'offline-state' if self_test else STATE
            env = environment(values, folder, state, manifest)
            if stopped:
                return 128 + stopped
            args = ['/bin/bash', str(folder / 'launcher.command')]
            if dry_run or self_test:
                args.append('--dry-run')
            child = subprocess.Popen(args, env=env)
            if stopped and child.poll() is None:
                child.send_signal(stopped)
            result = child.wait()
            return 128 + stopped if stopped else (result if result >= 0 else 128 - result)
    finally:
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            child.wait()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


def stop():
    if not STATE.is_dir() or STATE.is_symlink() or STATE.stat().st_uid != os.getuid():
        print('No private helper session was found.')
        return 0
    active = []
    for folder in STATE.glob('run-*'):
        if (folder.is_symlink() or not folder.is_dir() or folder.stat().st_uid != os.getuid()
                or not (folder / 'supervisor.sh').is_file() or (folder / 'stopped').exists()):
            continue
        fd = os.open(folder / 'stop.request', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        active.append(folder)
    until = time.monotonic() + 12
    while active and time.monotonic() < until:
        if all((folder / 'stopped').is_file() for folder in active):
            print('The managed helper stopped.')
            return 0
        time.sleep(.1)
    if active:
        print('Stop requested; shutdown is not yet confirmed.', file=sys.stderr)
        return 1
    print('No active combined helper was found.')
    return 0


def main(args=None):
    args = sys.argv[1:] if args is None else args
    result = internal(args)
    if result is not None:
        return result
    parser = argparse.ArgumentParser(description='Keep Your E3200 — guided CHR30A compatibility and Ethernet helper for Mac.')
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--mode', choices=('full', 'compatibility'), help='full helper or Wi-Fi-only compatibility')
    parser.add_argument('--setup', action='store_true', help='change saved settings')
    parser.add_argument('--settings', action='store_true', help='open the saved settings menu')
    parser.add_argument('--stop', action='store_true', help='stop both managed components')
    parser.add_argument('--self-test', action='store_true', help='offline checks only; no network changes')
    parser.add_argument('--dry-run', action='store_true', help='validate saved settings without starting a service')
    parser.add_argument('--licenses', action='store_true', help='show included license notices')
    parser.add_argument('--extract-source', metavar='NEW_FOLDER', help='export included licenses and dnsmasq source')
    selected = parser.parse_args(args)
    if selected.licenses:
        print((RESOURCE / 'licenses/THIRD-PARTY-NOTICES.md').read_text())
        return 0
    if selected.extract_source:
        target = Path(selected.extract_source).expanduser()
        target.mkdir(mode=0o700, parents=False, exist_ok=False)
        for item in (RESOURCE / 'licenses').iterdir():
            if item.is_file() and not item.is_symlink():
                shutil.copyfile(item, target / item.name)
        print('Included licenses and corresponding source exported to ' + str(target))
        return 0
    if sys.platform != 'darwin':
        raise ValueError('This is the Mac launcher. Use the separate Linux/Pi installer on Linux; Windows support is planned.')
    if selected.self_test:
        profile = dict(config.example(), mode=selected.mode or 'full')
        if profile['mode'] == 'compatibility':
            profile.update(ethernet_interface=None, ethernet_mac=None)
        return run(config.validate(profile), self_test=True)
    if selected.stop:
        return stop()
    if os.geteuid() == 0:
        raise ValueError('Open the launcher as your normal Mac user. It will request administrator access when needed.')
    private_folder(STATE)
    if selected.dry_run and not (STATE / 'profile.json').exists():
        raise ValueError('Run first-time setup before validating saved settings, or use --self-test for offline checks.')
    while True:
        try:
            profile = config.load(STATE / 'profile.json') if (STATE / 'profile.json').exists() else None
        except (ValueError, OSError) as exc:
            if selected.dry_run or not sys.stdin.isatty():
                raise
            section('Could not read saved settings')
            say(str(exc))
            say('Your existing file will be kept until you complete setup again.')
            option(1, 'Run setup again', 'Enter and confirm the settings before replacing the file.')
            option(2, 'Quit', 'Leave the existing file unchanged.')
            if menu_choice('Choose 1 or 2', ('1', '2')) == '2':
                return 1
            selected.setup = True
            selected.settings = False
            profile = None
        if selected.settings:
            if selected.dry_run:
                raise ValueError('Settings cannot be changed during a dry run. Open --settings separately.')
            if profile is None:
                print('No saved settings yet. Open the launcher to complete first-time setup.')
            else:
                settings_menu(profile)
            return 0
        if profile is not None and not selected.setup and not selected.dry_run and selected.mode is None and sys.stdin.isatty():
            profile = saved_menu(profile)
            if profile is None:
                return 0
        mode = selected.mode or (profile['mode'] if profile else 'full')
        if not selected.dry_run and selected.mode is None and sys.stdin.isatty():
            mode = choose_mode(allow_back=profile is not None)
            if mode is None:
                if profile is None:
                    return 0
                selected.setup = False
                selected.mode = None
                continue
        needs_setup = selected.setup or profile is None or (mode == 'full' and not profile['ethernet_interface'])
        if needs_setup and selected.dry_run:
            raise ValueError('Run --setup for this mode before validating saved settings.')
        if needs_setup:
            try:
                profile = setup(mode, profile)
            except (ValueError, OSError) as exc:
                if selected.dry_run or not sys.stdin.isatty():
                    raise
                action = failure_menu('Could not complete setup: ' + str(exc))
                if action == '3':
                    return 1
                selected.mode = mode if action == '1' else None
                selected.setup = action == '1'
                continue
            if profile is None:
                if (STATE / 'profile.json').exists() and sys.stdin.isatty() and selected.mode is None:
                    selected.setup = False
                    continue
                return 0
        else:
            profile = config.validate(dict(profile, mode=mode))
            if not selected.dry_run:
                config.save(STATE / 'profile.json', profile)
            print('\nKEEP YOUR E3200\nUsing your saved settings. Use --setup to change them.\n')
        show_info(profile)
        if mode == 'full':
            print('Full helper: keep home Wi-Fi connected. If Ethernet disconnects, reconnect the same adapter; forwarding retries automatically.')
        else:
            print('Wi-Fi-only compatibility: keep the Mac awake and connected to home Wi-Fi.')
            print('The Ethernet IPv4 fix is OFF. This mode answers only the E3200, not ordinary devices.')
        print('Leave this window open. Ctrl+C — stop helper and return Home.\n')
        if not selected.dry_run:
            say('If asked for Password, enter your Mac login password and press Return. '
                'Terminal does not show characters while you type it.')
        try:
            result = run(profile, dry_run=selected.dry_run)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            if selected.dry_run or not sys.stdin.isatty():
                raise
            say('Could not start: ' + str(exc))
            result = 1
        if result == 130 and not selected.dry_run and sys.stdin.isatty():
            print('\nHelper stopped. Returning Home.\n')
            selected.setup = False
            selected.settings = False
            selected.mode = None
            continue
        if result == 1 and not selected.dry_run and sys.stdin.isatty():
            action = failure_menu('The helper could not start or stopped with an error.')
            if action != '3':
                selected.mode = mode if action == '1' else None
                selected.setup = False
                continue
        return result



if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except EOFError:
        print('\nInput closed. The launcher has stopped.', file=sys.stderr, flush=True)
        raise SystemExit(1)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('\nStopped: ' + str(exc), file=sys.stderr, flush=True)
        if sys.stdin.isatty():
            try:
                input('Press Return to close. ')
            except (EOFError, KeyboardInterrupt):
                pass
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)

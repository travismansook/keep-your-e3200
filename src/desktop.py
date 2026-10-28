#!/usr/bin/env python3
"""Guided entry point; native downloads also dispatch their bundled workers."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import configuration as config
import forwarder
import combined_worker

VERSION = '0.2.0'
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


def ask(label, default=None):
    answer = input(label + (' [' + str(default) + ']' if default is not None else '') + ': ').strip()
    return answer or default


def ask_value(label, check, default=None):
    while True:
        value = ask(label, default)
        try:
            return check(value)
        except (ValueError, TypeError) as exc:
            print('  ' + str(exc))


def choose_mode():
    print('\n1. Wi-Fi + Ethernet — Recommended (compatibility + Ethernet IPv4 fix)')
    print('2. Wi-Fi only — E3200 compatibility (no Ethernet IPv4 fix)')
    def choice(value):
        if value not in ('1', '2'):
            raise ValueError('Choose 1 or 2.')
        return 'full' if value == '1' else 'compatibility'
    return ask_value('Choose a mode', choice, '1')


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
    print('\nYour setup')
    print('  Mode: ' + ('Wi-Fi + Ethernet — Recommended' if profile['mode'] == 'full' else 'Wi-Fi-only compatibility'))
    print('  E3200 address: ' + profile['extender_ip'] + ' (settings page after its lease is accepted)')
    print('  E3200 MAC: ' + profile['extender_mac'])
    print('  Main router: ' + profile['gateway'])
    print('  DNS: ' + profile['dns'])
    print('  Mac Wi-Fi connection: ' + profile['wifi_interface'])
    print('  Mac Ethernet connection: ' + (profile['ethernet_interface'] if profile['mode'] == 'full' else 'not required; Ethernet IPv4 fix is OFF'))
    print('  E3200 lease offered: ' + duration + ' (' + str(minutes) + ' minutes)')
    print('  Ordinary device leases: controlled by the main router')
    print('  Run time: until you stop it with Ctrl+C')
    print('  The lease above is configured; acceptance is confirmed in the E3200 DHCP log.\n')


def setup(mode='full', previous=None):
    print('\nKEEP YOUR E3200 · First-time setup\n')
    print('Connect this Mac to your home Wi-Fi. The E3200 still needs its coax connection.')
    if mode == 'full':
        print('Also plug the Mac Ethernet cable directly into an Ethernet port on the E3200.')
    previous = previous or {}
    print('The helper reads these connections; it does not change your network settings.\n')
    items = config.connections()
    wifi = [item for item in items if item['wifi'] and item['active'] and item['ip']]
    wired = [item for item in items if not item['wifi'] and item['active']]
    if len(wifi) != 1 or (mode == 'full' and not wired):
        raise ValueError('Connect home Wi-Fi with working IPv4, and Ethernet if you selected the recommended mode.')
    wifi = wifi[0]
    cable = None
    if mode == 'full':
        for number, item in enumerate(wired, 1):
            print(str(number) + '. ' + item['label'] + ' — ' + (item['ip'] or 'waiting for an address'))
        def choice(value):
            if value is None or not str(value).isdigit() or not 1 <= int(value) <= len(wired):
                raise ValueError('Choose one of the connection numbers above.')
            return wired[int(value) - 1]
        cable = ask_value('Which Ethernet connection leads to the E3200?', choice, '1' if len(wired) == 1 else None)
    gateway = ask_value('Main router address', lambda value: str(config.address(value)), config.router_for(wifi['device']))
    print('\nFind the E3200 MAC address on its label or settings page. This identifies the extender, not the Mac adapter.')
    mac = ask_value('E3200 MAC address', config.normalize_mac, previous.get('extender_mac'))
    extender = ask_value('Unused address set aside for the E3200 on your router', lambda value: str(config.address(value)), previous.get('extender_ip'))
    print('\nBefore starting, check your router: this address must be reserved for this E3200,')
    print('or excluded from automatic assignment, and must not be manually used by another device.')
    if ask('Have you checked and protected that address? Type YES') != 'YES':
        raise ValueError('Setup stopped. Check the address plan using the setup guide before trying again.')
    print('\nE3200 lease length: 1. One hour (start here)  2. One day  3. One year (advanced)')
    def lease(value):
        if value not in ('1', '2', '3'):
            raise ValueError('Choose 1, 2, or 3.')
        return {'1': 60, '2': 1440, '3': 525600}[value]
    minutes = ask_value('Lease option', lease, '1')
    profile = config.validate(dict(extender_mac=mac, extender_ip=extender, gateway=gateway,
                                  dns=gateway, subnet_mask=wifi['mask'],
                                  mode=mode, ethernet_interface=cable['device'] if cable else previous.get('ethernet_interface'),
                                  ethernet_mac=cable['mac'] if cable else previous.get('ethernet_mac'),
                                  wifi_interface=wifi['device'], lease_minutes=minutes,
                                  address_plan_confirmed=True))
    config.runtime_values(profile, items, gateway)
    config.save(STATE / 'profile.json', profile)
    print('\nSettings saved privately on this Mac. Your router and devices were not reconfigured.\n')
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
            return result if result >= 0 else 128 - result
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
        raise ValueError('This combined release runs on macOS. Windows and Linux versions are planned.')
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
    profile = config.load(STATE / 'profile.json') if (STATE / 'profile.json').exists() else None
    mode = selected.mode or (profile['mode'] if profile else 'full')
    if not selected.dry_run and selected.mode is None and sys.stdin.isatty():
        mode = choose_mode()
    needs_setup = selected.setup or profile is None or (mode == 'full' and not profile['ethernet_interface'])
    if needs_setup and selected.dry_run:
        raise ValueError('Run --setup for this mode before validating saved settings.')
    if needs_setup:
        profile = setup(mode, profile)
    else:
        profile = config.validate(dict(profile, mode=mode))
        if not selected.dry_run:
            config.save(STATE / 'profile.json', profile)
        print('\nKEEP YOUR E3200\nUsing your saved settings. Use --setup to change them.\n')
    show_info(profile)
    if mode == 'full':
        print('Full helper: keep the Mac awake with Wi-Fi and Ethernet connected.')
    else:
        print('Wi-Fi-only compatibility: keep the Mac awake and connected to home Wi-Fi.')
        print('The Ethernet IPv4 fix is OFF. This mode answers only the E3200, not ordinary devices.')
    print('Leave this window open. Ctrl+C stops the selected helper mode.\n')
    return run(profile, dry_run=selected.dry_run)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError, EOFError) as exc:
        print('\nStopped: ' + str(exc), file=sys.stderr, flush=True)
        if sys.stdin.isatty():
            try:
                input('Press Return to close. ')
            except (EOFError, KeyboardInterrupt):
                pass
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)

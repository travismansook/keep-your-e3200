#!/usr/bin/env python3
"""Beginner-oriented Linux setup, service controls and diagnostics."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent))
import linux_config as config
import linux_network as network
from configuration import address, normalize_mac

try:
    import readline  # Enable normal arrow-key and backspace editing in input().
except ImportError:
    pass

NM_NAME = 'Keep Your E3200 Ethernet'


class Cancelled(Exception):
    pass


def section(title):
    print('\n' + '=' * 58 + '\n  ' + title + '\n' + '=' * 58)


def ask(label, check=lambda value: value, default=None):
    while True:
        print('\n' + label + (' [' + str(default) + ']' if default is not None else '') + ':')
        value = input('  > ').strip()
        if value.casefold() == 'cancel':
            raise Cancelled()
        if not value and default is not None:
            value = str(default)
        try:
            return check(value)
        except (ValueError, TypeError) as exc:
            print('  ' + str(exc))


def choice(value, allowed):
    if value not in allowed:
        raise ValueError('Please enter ' + ', '.join(allowed) + '. A choice is required.')
    return value


def yes(label):
    return ask(label + ' (yes/no)', lambda value: choice(value.casefold(), ('yes', 'no', 'y', 'n'))) in ('yes', 'y')


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def active():
    return subprocess.run(['systemctl', 'is-active', '--quiet', config.UNIT]).returncode == 0


def lease(value):
    if not value.isdecimal() or not 2 <= int(value) <= 525600:
        raise ValueError('Enter minutes from 2 to 525600 (one year).')
    return int(value)


def choose_adapter(items, label, previous_mac=None):
    if not items:
        raise ValueError('No ' + label + ' adapter is available. Check the Pi connections and retry.')
    for index, item in enumerate(items, 1):
        print('  %d. %s — %s — %s' % (index, item['device'], item['ip'] or 'no IPv4 yet', item['mac']))
    default = next((str(i) for i, item in enumerate(items, 1) if item['mac'] == previous_mac), None)
    selected = ask('Choose the ' + label + ' connection number',
                   lambda value: int(choice(value, tuple(str(n) for n in range(1, len(items)+1)))), default)
    return items[selected - 1]


def find_router_mac(wifi, gateway):
    def get():
        for item in network.ip_json('neigh', 'show', 'to', gateway, 'dev', wifi['device']):
            if item.get('lladdr') and not set(item.get('state', [])).intersection({'INCOMPLETE', 'FAILED'}):
                return normalize_mac(item['lladdr'])
    mac = get()
    if mac is None:
        try:
            subprocess.run(['ping', '-n', '-I', wifi['device'], '-c', '1', '-W', '1', gateway],
                           capture_output=True, timeout=1.5)
        except subprocess.TimeoutExpired:
            pass
        mac = get()
    if mac is None:
        raise ValueError('The router hardware address is not available on Wi-Fi yet. Wait a moment and retry.')
    return mac


def setup():
    if active():
        raise ValueError('Stop the Pi helper from Home before changing its setup. The current setup was kept.')
    section('KEEP YOUR E3200 · Linux setup')
    print('Type cancel at any question to leave the saved setup unchanged.')
    print('A value in [brackets] is saved or suggested; press Return to keep it.')
    previous = {}
    if config.CONFIG.exists():
        try:
            previous = config.load()
            print('Your saved details are offered below. Changes are saved only after confirmation.')
        except (ValueError, OSError):
            print('The saved setup could not be read. Enter a replacement, or type cancel to keep the file.')
    print('Keep the Pi on home Wi-Fi. The E3200 still needs its coax connection.')
    print('Disconnect a VPN on the Pi before setup. Do not configure Wi-Fi through this helper.')
    print('\n1. Wi-Fi + Ethernet — recommended\n2. Wi-Fi-only compatibility — no Ethernet IPv4 fix')
    mode = {'1':'full', '2':'compatibility'}[ask('Choose 1 or 2', lambda v: choice(v, ('1','2')))]
    items = network.connections()
    wifi = choose_adapter([item for item in items if item['wifi'] and item['active'] and item['ip']], 'Wi-Fi', previous.get('wifi_mac'))
    gateway = network.router_for(wifi['device'])
    subnet = ipaddress.IPv4Network(wifi['ip'] + '/' + wifi['mask'], strict=False)
    print('\nDetected router:', gateway, ' | Wi-Fi address:', wifi['ip'])
    if not yes('Is this your home network with the CHR30A and E3200?'):
        raise Cancelled()
    ethernet = choose_adapter([item for item in items if not item['wifi']], 'Ethernet', previous.get('ethernet_mac')) if mode == 'full' else None
    print('\nLook at the BACK of the E3200. Under Serial#, find LAN1 MAC.')
    print('Enter only the address. Dots, colons, hyphens, uppercase and lowercase all work.')
    def extender_mac(value):
        mac = normalize_mac(value)
        if mac in {item['mac'] for item in items}:
            raise ValueError('That is this computer. Enter the E3200 LAN1 MAC from its sticker.')
        return mac
    mac = ask('E3200 LAN1 MAC', extender_mac, previous.get('extender_mac'))
    print('\nReserve an unused address in your CHR30A for that MAC first.')
    print('Open https://' + gateway + ' → Network Settings → IPv4 Address Distribution → Connection List.')
    print('The chosen address must be reserved for the E3200 or excluded from automatic assignment.')
    print('Use the same existing reservation as your Mac helper; do not create a duplicate.')
    print('If the router rejects an address outside its DHCP range, choose an allowed, unused one.')
    def extender_ip(value):
        result = address(value)
        if result not in subnet or result in (subnet.network_address, subnet.broadcast_address, address(gateway)):
            raise ValueError('Choose a different usable address on ' + str(subnet) + '.')
        if str(result) in {item['ip'] for item in items}:
            raise ValueError('This computer already uses that address. Choose a different one.')
        return str(result)
    old_ip = previous.get('extender_ip')
    if old_ip is not None:
        try:
            extender_ip(old_ip)
        except ValueError:
            old_ip = None
    ip = ask('E3200 reserved IPv4 address', extender_ip, old_ip)
    if not yes('Have you checked that this address is reserved/protected for this E3200 and unused by any other device?'):
        raise Cancelled()
    print('\nLease offered to the E3200: 60 = one hour; 1440 = one day; 525600 = one year.')
    print('Ordinary clients still receive their lease durations from the CHR30A.')
    minutes = ask('E3200 lease duration in minutes', lease, previous.get('lease_minutes', 525600))
    profile = config.validate(dict(version=1, mode=mode, wifi_interface=wifi['device'], wifi_mac=wifi['mac'],
            ethernet_interface=ethernet['device'] if ethernet else None, ethernet_mac=ethernet['mac'] if ethernet else None,
            gateway=gateway, subnet_mask=wifi['mask'], home_router_mac=find_router_mac(wifi, gateway),
            extender_mac=mac, extender_ip=ip, lease_minutes=minutes, address_plan_confirmed=True))
    review(profile)
    if not yes('Save these settings?'):
        raise Cancelled()
    config.save(config.CONFIG, profile)
    print('\nSaved. No DHCP service was started and no router settings were changed.')
    if ethernet:
        print('Next: prepare the Pi Ethernet profile from Home, then connect its cable to the E3200.')
    print('Stop the old Mac helper before starting this Pi helper. Use only one compatibility helper at a time.')


def lease_label(minutes):
    if minutes == 525600:
        return '525600 minutes (365 days / 1 year)'
    parts = []
    days, remainder = divmod(minutes, 1440)
    hours, remaining_minutes = divmod(remainder, 60)
    for amount, unit in ((days, 'day'), (hours, 'hour'), (remaining_minutes, 'minute')):
        if amount:
            parts.append(str(amount) + ' ' + unit + ('s' if amount != 1 else ''))
    return str(minutes) + ' minutes (' + ', '.join(parts) + ')'


def review(profile=None):
    p = profile or config.load()
    section('Saved settings — not a live connectivity or lease check')
    mode = 'Wi-Fi + Ethernet' if p['mode'] == 'full' else 'Wi-Fi-only compatibility'
    for label, value in [('Mode',mode), ('Pi Wi-Fi connection',p['wifi_interface']), ('Pi Ethernet connection',p['ethernet_interface'] or 'not used'),
                         ('Main router IPv4',p['gateway']), ('E3200 LAN1 MAC',p['extender_mac']), ('E3200 settings-page IPv4',p['extender_ip']),
                         ('E3200 lease offered',lease_label(p['lease_minutes']))]:
        print('  ' + label + ': ' + value)
    print('  The CHR30A controls ordinary client leases. Readiness does not confirm every client has internet.')


def ethernet_profile():
    p = config.load()
    if p['mode'] != 'full':
        raise ValueError('Ethernet is not used in Wi-Fi-only mode.')
    if active():
        raise ValueError('Stop the Pi helper before preparing its Ethernet connection.')
    section('Prepare only the Pi Ethernet connection')
    print('This creates a NetworkManager profile for ' + p['ethernet_interface'] + '.')
    print('It gives the Pi a local-only Ethernet address and keeps internet/SSH on Wi-Fi.')
    print('It does not change Wi-Fi, assign addresses to other devices, share internet, or configure NAT.')
    print('The existing Ethernet profiles are retained. Run this while connected by Wi-Fi, not Ethernet SSH.')
    if not yes('Create/activate this Ethernet profile?'):
        return
    rows = network.command(['nmcli', '-t', '-f', 'UUID,NAME', 'connection', 'show']).splitlines()
    matches = [line.split(':',1)[0] for line in rows if line.partition(':')[2] == NM_NAME]
    if matches:
        raise ValueError('The dedicated Ethernet profile already exists. Use Diagnose to check it. '
                         'If you changed adapters, use Restore previous Ethernet use, then Prepare Pi Ethernet profile again. '
                         'The existing profile was kept.')
    identifier = str(uuid.uuid4())
    run(['nmcli', 'connection', 'add', 'type', 'ethernet', 'ifname', p['ethernet_interface'],
         'con-name', NM_NAME, 'connection.uuid', identifier, '802-3-ethernet.mac-address', p['ethernet_mac'],
         'connection.autoconnect', 'yes', 'connection.autoconnect-priority', '100',
         'ipv4.method', 'link-local', 'ipv4.never-default', 'yes',
         'ipv6.method', 'link-local', 'ipv6.never-default', 'yes'])
    result = subprocess.run(['nmcli', '--wait', '10', 'connection', 'up', 'uuid', identifier])
    if result.returncode:
        print('Profile saved, but not active yet. Connect the cable; NetworkManager should activate it automatically.')
    else:
        print('Dedicated Ethernet profile is active. You can now start the helper.')
    print('To undo this profile later: keep-your-e3200 restore-ethernet')


def restore_ethernet():
    if active():
        raise ValueError('Stop the helper before restoring Ethernet.')
    print('This removes only the dedicated Keep Your E3200 Ethernet profile. Other profiles are kept.')
    if yes('Remove that profile?'):
        run(['nmcli', 'connection', 'delete', 'id', NM_NAME])
        print('Removed. Reconnect Ethernet or choose your previous connection profile in NetworkManager.')


def change_lease():
    if active():
        raise ValueError('Stop the Pi helper first, then change the offered lease and start again.')
    p = config.load()
    minutes = ask('New E3200 lease duration in minutes', lease, p['lease_minutes'])
    if minutes == p['lease_minutes']:
        print('No change.')
        return
    print('Change:', lease_label(p['lease_minutes']), '→', lease_label(minutes))
    print('This affects future offers after restarting, not the expiry of an already accepted lease.')
    if yes('Save this change?'):
        config.save(config.CONFIG, dict(p, lease_minutes=minutes))
        print('Saved. Start the helper when ready.')
    else:
        print('Cancelled; the saved lease duration is unchanged.')


def show_status():
    running = active()
    section('Helper status')
    boot = subprocess.run(['systemctl', 'is-enabled', '--quiet', config.UNIT]).returncode == 0
    print('  Background service:', 'active' if running else 'not active')
    print('  Start after reboot:', 'enabled' if boot else 'disabled')
    path = config.STATE / 'status.json'
    if path.exists():
        try:
            value = json.loads(path.read_text())
            if (not isinstance(value, dict) or any(not isinstance(value.get(key), str)
                    for key in ('title', 'detail', 'action')) or type(value.get('pid')) is not int):
                raise ValueError('Incomplete runtime report')
        except (ValueError, OSError) as exc:
            print('  The runtime report could not be read:', exc)
            print('  Component readiness is unknown. Open live logs to check the current service.')
            return
        pid = subprocess.run(['systemctl', 'show', '-p', 'MainPID', '--value', config.UNIT],
                             capture_output=True, text=True)
        current = running and pid.returncode == 0 and pid.stdout.strip() == str(value.get('pid'))
        print('  ' + ('Current report: ' if current else 'Last report (not current): ') + value['title'])
        print('  ' + value['detail'])
        print('  What to do: ' + value['action'])
        if not running:
            print('  The service is not active. Do not rely on an older ready report.')
        elif not current:
            print('  The service has a different process now. Wait for its fresh startup report; the old READY does not apply.')
    elif running:
        print('  Startup is in progress; the first component report is not available yet.')
        print('  What to do: Wait a few seconds, then check Status again. If it persists, open live logs.')
    elif config.CONFIG.exists():
        print('  No runtime report yet. Your saved setup is available.')
        print('  What to do: Choose Start helper, then check Status for component readiness.')
    else:
        print('  No saved setup yet. Choose Setup from Home before starting the helper.')


def diagnose():
    p = config.load()
    section('Read-only connection checks')
    info = network.home_identity(p)
    print('Home Wi-Fi router identity verified.')
    print('Main router IPv4:', p['gateway'])
    print("This Pi's Wi-Fi IPv4:", info['ip'])
    if p['mode'] == 'full':
        try:
            wired = network.snapshot(p['ethernet_interface'])
            print("This Pi's Ethernet:", wired['device'], 'link up' if wired['active'] else 'link down', wired['ip'] or 'no IPv4 yet')
            if wired['mac'] != p['ethernet_mac']:
                print('ACTION: This is a different Ethernet adapter. Review Setup.')
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            print('Ethernet is unavailable:', exc)
            print('ACTION: Reconnect the selected adapter, or use Setup to choose another.')
        print('A local-only 169.254.x.x address on the Pi Ethernet connection is expected for this helper.')
        print('Ethernet should use the dedicated link-local profile; Wi-Fi remains the Pi internet connection.')
        print('Other wired devices should receive their normal home-network IPv4 addresses from the CHR30A.')
    print('This does not start capture, send DHCP, or change settings. Router identity checks may send one ping.')
    print('Kernel:', os.uname().release)
    if shutil.which('vcgencmd'):
        print('Pi power/thermal flags:', network.command(['vcgencmd', 'get_throttled']).strip())
    print(network.command(['df', '-h', str(config.STATE)]).strip())


def view_logs(follow=False):
    section('Live logs' if follow else 'Recent detailed logs')
    if follow:
        print('New entries appear as they happen. Press Ctrl+C to close this viewer.')
        print('Closing the viewer keeps the background helper in its current state.', flush=True)
    try:
        run(['journalctl', '-u', config.UNIT, '-n', '60', '--no-pager',
             *(['--follow'] if follow else [])])
    except KeyboardInterrupt:
        if not follow:
            raise
    except subprocess.CalledProcessError as exc:
        if not follow or exc.returncode not in (-signal.SIGINT, 128 + signal.SIGINT):
            raise
    if follow:
        print('\nLive log viewer closed.')


def stop():
    run(['systemctl', 'stop', config.UNIT])
    print('Helper stopped. Saved settings and accepted device leases were kept.')


def set_boot(enabled):
    run(['systemctl', 'enable' if enabled else 'disable', config.UNIT])
    if enabled:
        print('Automatic startup is enabled for future Pi reboots.')
        print('To run the helper now, choose Start helper. Check Status for readiness.')
    else:
        print('Automatic startup is disabled. This leaves the current helper running if it was already started.')
        print('Choose Stop helper if you also want to stop it now.')


def menu():
    while True:
        section('KEEP YOUR E3200 · Linux ' + config.VERSION)
        print('1. Start background helper\n2. Stop helper\n3. Status\n4. Setup / replace settings\n'
              '5. Review settings\n6. Change lease duration\n7. Start automatically after reboot\n'
              '8. Disable automatic startup\n9. View recent detailed logs\n10. Diagnose connections\n'
              '11. Prepare Pi Ethernet profile\n12. Restore previous Ethernet use\n'
              '13. View live logs (Ctrl+C returns Home)\n0. Quit')
        try:
            value = ask('Choose a number', lambda v: choice(v, tuple(str(n) for n in range(14))))
            if value == '0':
                print('Closing this menu does not stop an already running background service.')
                return
            actions = {'1':start, '2':stop, '3':show_status, '4':setup,
                       '5':review, '6':change_lease, '7':lambda:set_boot(True),
                       '8':lambda:set_boot(False),
                       '9':view_logs,
                       '10':diagnose, '11':ethernet_profile, '12':restore_ethernet,
                       '13':lambda:view_logs(follow=True)}
            actions[value]()
            if value == '13':
                print('Returning Home.')
                continue
        except (Cancelled, KeyboardInterrupt):
            print('\nCancelled. Returning Home.')
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            print('\nAction needed:', exc)
        try:
            input('\nPress Return to go Home. ')
        except (KeyboardInterrupt, EOFError):
            return


def start():
    p = config.load()
    network.home_identity(p)
    print('Stop the Mac compatibility helper before running the Pi helper. Only one should be active.')
    run(['systemctl', 'reset-failed', config.UNIT])
    run(['systemctl', 'start', config.UNIT])
    print('Service start requested. Check Status: active is not the same as components ready.')
    show_status()


def main(args=None):
    parser = argparse.ArgumentParser(description='Keep Your E3200 — Linux/Pi preview')
    parser.add_argument('action', nargs='?', default='menu', choices=('menu','setup','review','lease','start','stop',
          'status','enable','disable','logs','diagnose','prepare-ethernet','restore-ethernet','version'))
    parser.add_argument('--follow', action='store_true', help='follow logs; Ctrl+C closes the viewer, not the service')
    selected = parser.parse_args(args)
    if selected.follow and selected.action != 'logs':
        parser.error('--follow is available with logs. Use: keep-your-e3200 logs --follow')
    if selected.action == 'version':
        print(config.VERSION)
        return 0
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('Use the Linux launcher on Linux; it requests administrator access when needed.')
    if selected.action == 'logs':
        view_logs(follow=selected.follow)
    else:
        actions = dict(menu=menu, setup=setup, review=review, lease=change_lease, start=start,
                       stop=stop, status=show_status,
                       enable=lambda:set_boot(True),
                       disable=lambda:set_boot(False), diagnose=diagnose,
                       **{'prepare-ethernet':ethernet_profile, 'restore-ethernet':restore_ethernet})
        actions[selected.action]()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Cancelled, KeyboardInterrupt, EOFError):
        print('\nCancelled. Existing settings were kept unless a save was already confirmed.')
        sys.exit(0)
    except Exception as exc:
        print('Action needed:', exc, file=sys.stderr)
        sys.exit(1)

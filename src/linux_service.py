#!/usr/bin/env python3
"""Pi/Linux supervisor. Recovers Wi-Fi/cable loss; systemd owns final cleanup."""
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import pwd
import selectors
import signal
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
import linux_config as config
import linux_network as network


def supervise(profile, account, state=config.STATE, runtime=config.RUNTIME):
    state, runtime = Path(state), Path(runtime)
    # The lease-writing account needs traversal, not access to private status/log
    # files. systemd creates this directory before the supervisor starts.
    os.chown(state, os.getuid(), account.pw_gid)
    state.chmod(0o710)
    logger = logging.getLogger('keep-your-e3200')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s %(message)s')
        for handler in (logging.StreamHandler(sys.stdout), RotatingFileHandler(
                state / 'helper.log', maxBytes=2*1024*1024, backupCount=2)):
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    stopped = [False]
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, lambda *_: stopped.__setitem__(0, True))
    children, buffers = {}, {}
    ready = set()
    selector = selectors.DefaultSelector()
    previous = None
    wifi_ip = None
    last_check = 0
    bridge_retry = 0
    boot_clock = (lambda: time.clock_gettime(time.CLOCK_BOOTTIME)) if hasattr(time, 'CLOCK_BOOTTIME') else time.monotonic
    last_tick = boot_clock()
    lock = os.open(runtime / 'service.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lease_dir = state / 'leases'
    lease_dir.mkdir(exist_ok=True, mode=0o700)
    if lease_dir.is_symlink():
        raise ValueError('The lease folder must not be a symbolic link.')
    os.chown(lease_dir, account.pw_uid, account.pw_gid)
    dns_conf = runtime / 'dnsmasq.conf'
    dns_conf.write_text(config.dnsmasq_config(profile, lease_dir / 'e3200.leases'))
    dns_conf.chmod(0o600)
    subprocess.run(['/usr/sbin/dnsmasq', '--test', '--conf-file=' + str(dns_conf)], check=True)

    def status(kind, title, detail, action):
        nonlocal previous
        value = dict(state=kind, title=title, detail=detail, action=action)
        if value == previous:
            return
        previous = value.copy()
        value.update(time=time.time(), pid=os.getpid())
        config.atomic_json(state / 'status.json', value)
        logger.info('%s: %s\n  %s\n  What to do: %s', kind.upper(), title, detail, action)

    def emit(label, data):
        data = buffers.get(label, b'') + data
        lines = data.split(b'\n')
        buffers[label] = lines.pop()
        for line in lines:
            text = line.decode('utf-8', 'replace')
            logger.info('[%s] %s', label, text)
            if label == 'E3200' and 'started, version' in text:
                ready.add(label)
            elif label == 'Ethernet' and 'FORWARDER READY:' in text:
                ready.add(label)

    def drain(timeout):
        for key, _ in selector.select(timeout):
            data = os.read(key.fileobj.fileno(), 65536)
            if data:
                emit(key.data, data)
            else:
                selector.unregister(key.fileobj)

    def launch(label, args):
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True, bufsize=0,
                                   env=dict(PATH='/usr/sbin:/usr/bin:/sbin:/bin', PYTHONNOUSERSITE='1', PYTHONUNBUFFERED='1'))
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ, label)
        children[label] = (process, time.monotonic())
        ready.discard(label)
        logger.info('Starting %s component', label)

    def retire(label):
        process, _ = children.pop(label)
        try:
            while True:
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    break
                emit(label, data)
        except BlockingIOError:
            pass
        try:
            selector.unregister(process.stdout)
        except KeyError:
            pass
        if buffers.get(label):
            emit(label, b'\n')
        buffers.pop(label, None)
        process.stdout.close()
        process.wait(timeout=1)
        ready.discard(label)

    def stop_all():
        for process, _ in children.values():
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 2
        while any(p.poll() is None for p, _ in children.values()) and time.monotonic() < deadline:
            drain(.05)
        for label, (process, _) in list(children.items()):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=1)
            retire(label)

    def launch_bridge():
        launch('Ethernet', [sys.executable, str(Path(__file__).with_name('forwarder.py')),
               '--wifi', profile['wifi_interface'], '--ethernet', profile['ethernet_interface'],
               '--ethernet-mac', profile['ethernet_mac'], '--server', profile['gateway'],
               '--extender-mac', profile['extender_mac'], '--uid', str(account.pw_uid),
               '--gid', str(account.pw_gid), '--lock-file', str(runtime / 'forwarder.lock')])

    bridge_lock = runtime / 'forwarder.lock'
    fd = os.open(bridge_lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    os.fchown(fd, account.pw_uid, account.pw_gid)
    os.close(fd)
    result = 0
    try:
        status('waiting', 'Checking home Wi-Fi', 'No component is ready yet.',
               'Keep the Pi on home Wi-Fi. Startup and reconnection checks retry automatically.')
        while not stopped[0]:
            now = time.monotonic()
            tick = boot_clock()
            if tick - last_tick > 15:
                stop_all()
                wifi_ip = None
                last_check = 0
                status('paused', 'Rechecking after an interruption', 'Old component connections were closed.',
                       'Wait while home Wi-Fi is verified. The helper will resume automatically.')
            last_tick = tick
            if now - last_check >= 2:
                last_check = now
                try:
                    current = network.home_identity(profile)
                except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
                    stop_all()
                    wifi_ip = None
                    status('paused', 'Waiting for home Wi-Fi', str(exc) + ' Neither component is assisting.',
                           'Reconnect to the configured home Wi-Fi. Retrying automatically; review Setup if the router changed.')
                    drain(.1)
                    continue
                if stopped[0]:
                    break
                if wifi_ip != current['ip']:
                    stop_all()
                    wifi_ip = current['ip']
                    bridge_retry = 0
                if 'E3200' not in children:
                    launch('E3200', ['/usr/sbin/dnsmasq', '--keep-in-foreground',
                                      '--conf-file=' + str(dns_conf), '--pid-file='])
                if profile['mode'] == 'full' and 'Ethernet' not in children and now >= bridge_retry:
                    launch_bridge()
            # A previous Wi-Fi failure must not restart any components between checks.
            if wifi_ip is None:
                drain(.1)
                continue
            drain(.1)
            if stopped[0]:
                break
            for label, (process, began) in list(children.items()):
                code = process.poll()
                if code is not None:
                    retire(label)
                    if label == 'Ethernet' and code == 75:
                        bridge_retry = time.monotonic() + 5
                    else:
                        raise RuntimeError('%s component exited (%s). Read the detailed log above.' % (label, code))
                elif label not in ready and time.monotonic() - began > 20:
                    raise RuntimeError(label + ' did not become ready within 20 seconds.')
            if 'E3200' in ready and profile['mode'] == 'compatibility':
                status('compatibility', 'Wi-Fi-only compatibility is running',
                       'Ethernet IPv4 forwarding is OFF. Component readiness does not confirm an accepted extender lease.',
                       'Keep the Pi powered and connected. Check the E3200 page to verify its lease.')
            elif {'E3200', 'Ethernet'} <= ready:
                status('ready', 'Both helper components are running',
                       'The router supplies ordinary device leases. Readiness does not prove every client has internet.',
                       'Keep the Pi powered with Wi-Fi and Ethernet connected. You may close SSH; the service keeps running.')
            elif 'E3200' in ready and 'Ethernet' not in children:
                status('ethernet-wait', 'Compatibility is running; Ethernet is waiting',
                       'The E3200 compatibility component remains active. Ethernet forwarding is paused.',
                       'Connect the selected cable to the E3200. NetworkManager may need a moment to assign the Pi a link-local address. Retrying every 5 seconds.')
            elif 'E3200' in ready:
                status('starting', 'Compatibility is running; Ethernet is starting',
                       'Home Wi-Fi is verified. The Ethernet component is checking its connection and reply delivery.',
                       'Wait for the next report. If startup fails, open live logs for the reason and next step.')
            else:
                status('starting', 'Starting helper components',
                       'Home Wi-Fi is verified. The compatibility component is not ready yet.',
                       'Wait for the next report. If startup fails, open live logs for the reason and next step.')
    except Exception as exc:
        stop_all()
        result = 1
        status('error', 'Helper stopped with an error', str(exc),
               'Run keep-your-e3200 logs. Check cables, Wi-Fi and other DHCP services. systemd retries after 10 seconds, but can stop retrying after repeated errors. Check Status.')
    finally:
        stop_all()
        if result == 0:
            status('stopped', 'Helper stopped', 'The compatibility and forwarding processes have exited.',
                   'Existing leases were not erased. Use Start when ready.')
        selector.close()
        os.close(lock)
    return result


def main():
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('Start this service through the Linux launcher on Linux.')
    return supervise(config.load(), pwd.getpwnam(config.USER))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('Could not start the Linux helper:', exc, flush=True)
        sys.exit(1)

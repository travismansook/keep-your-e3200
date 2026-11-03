#!/usr/bin/env python3
"""Manage the two existing network components as one foreground helper.

No protocol or interface configuration changes live here. The outer, already
tested supervisor handles launcher death; this worker owns and reaps both
component process groups before it exits.
"""
import argparse
import os
import selectors
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('full', 'compatibility'), default='full')
    parser.add_argument('--dnsmasq', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--bridge', required=True)
    parser.add_argument('--lock-file', required=True)
    parser.add_argument('--uid', type=int, required=True)
    parser.add_argument('--gid', type=int, required=True)
    parser.add_argument('--ethernet-mac')
    for name in ('ethernet', 'wifi', 'server', 'extender-mac'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    if args.uid <= 0 or args.gid < 0:
        parser.error('A non-root runtime user is required')

    stopping = [False]
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: stopping.__setitem__(0, True))
    selector = selectors.DefaultSelector()
    children = []
    buffers = {}
    bridge_ready = args.mode == 'compatibility'
    extender_ready = False
    announced = False
    status = 0
    started = time.monotonic()
    retry_at = None

    def launch_bridge():
        command = [sys.executable, args.bridge, '--ethernet', args.ethernet,
                   '--wifi', args.wifi, '--server', args.server,
                   '--extender-mac', args.extender_mac,
                   '--uid', str(args.uid), '--gid', str(args.gid),
                   '--lock-file', args.lock_file]
        if args.ethernet_mac:
            command.extend(['--ethernet-mac', args.ethernet_mac])
        launch('Ethernet', command)

    def emit(label, data, final=False):
        nonlocal bridge_ready, extender_ready
        data = buffers.get(label, b'') + data
        lines = data.split(b'\n')
        buffers[label] = lines.pop()
        if final and buffers[label]:
            lines.append(buffers.pop(label))
        for raw in lines:
            line = raw.decode('utf-8', 'replace')
            print('[%s] %s' % (label, line), flush=True)
            if label == 'Ethernet' and 'FORWARDER READY:' in line:
                if announced and not bridge_ready:
                    print('Ethernet reconnected. Automatic IPv4 forwarding resumed.', flush=True)
                bridge_ready = True
            if label == 'E3200' and 'started, version' in line:
                extender_ready = True

    def launch(label, command):
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   start_new_session=True, bufsize=0)
        children.append((label, process))
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ, label)
        print('Starting %s component...' % label, flush=True)

    def drain(timeout):
        for key, _ in selector.select(timeout):
            data = os.read(key.fileobj.fileno(), 65536)
            if data:
                emit(key.data, data)
            else:
                selector.unregister(key.fileobj)
                emit(key.data, b'', final=True)

    def stop_children():
        # Signal both groups first; use one shared deadline under the outer
        # supervisor's four-second fallback, including a stubborn child.
        for _, process in children:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 2
        while any(p.poll() is None for _, p in children) and time.monotonic() < deadline:
            drain(.05)
        for _, process in children:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=.5)
        drain_deadline = time.monotonic() + .3
        while selector.get_map() and time.monotonic() < drain_deadline:
            drain(.03)
        # A component should not leave other descendants holding its log
        # descriptor. Do not let such a descriptor block shutdown indefinitely.
        for key in list(selector.get_map().values()):
            selector.unregister(key.fileobj)
            emit(key.data, b'', final=True)
        for _, process in children:
            process.stdout.close()
        print('Both components stopped.' if args.mode == 'full' else 'E3200 compatibility stopped.', flush=True)

    def retire(label, process):
        # A reconnecting child has exited. Drain and close its old descriptor
        # before reusing the label; retain only current children and buffers.
        for _ in range(128):
            try:
                data = os.read(process.stdout.fileno(), 65536)
            except BlockingIOError:
                break
            if not data:
                break
            emit(label, data)
        try:
            selector.unregister(process.stdout)
        except KeyError:
            pass
        emit(label, b'', final=True)
        buffers.pop(label, None)
        process.stdout.close()
        process.wait()
        children.remove((label, process))

    try:
        if not stopping[0] and args.mode == 'full':
            launch_bridge()
        if not stopping[0] and args.mode == 'compatibility':
            launch('E3200', [args.dnsmasq, '--keep-in-foreground', '--conf-file=' + args.config, '--pid-file='])
        while not stopping[0]:
            drain(.1)
            for label, process in list(children):
                result = process.poll()
                if result is not None:
                    if label == 'Ethernet' and result == 75:
                        retire(label, process)
                        bridge_ready = False
                        retry_at = time.monotonic() + 3
                        print('Ethernet is paused. Reconnect the same adapter and cable; retrying automatically every 3 seconds.', flush=True)
                        if extender_ready and any(label == 'E3200' and child.poll() is None for label, child in children):
                            print('E3200 compatibility is still running over Wi-Fi.', flush=True)
                        else:
                            print('E3200 compatibility will start after Ethernet is ready.', flush=True)
                        print('It may take a few moments for macOS to recognize the adapter. '
                              'Keep this window open and home Wi-Fi connected. '
                              'If it does not reconnect, check the cable and adapter, then try restarting the helper. '
                              'Ctrl+C stops the helper.', flush=True)
                        continue
                    print('%s component exited (%s); stopping the combined helper.'
                          % (label, result), flush=True)
                    status = 1
                    stopping[0] = True
                    break
            if stopping[0]:
                break
            if retry_at is not None and time.monotonic() >= retry_at:
                retry_at = None
                started = time.monotonic()
                launch_bridge()
            # The bridge's self-test and exclusive lock must pass before any
            # extender service starts. Existing forwarding code is unchanged.
            if args.mode == 'full' and bridge_ready and len(children) == 1:
                launch('E3200', [args.dnsmasq, '--keep-in-foreground',
                                  '--conf-file=' + args.config, '--pid-file='])
            if bridge_ready and extender_ready and not announced:
                announced = True
                print('READY: E3200 and Ethernet helpers are running. Ctrl+C stops both and returns Home.' if args.mode == 'full' else 'READY: Wi-Fi-only E3200 compatibility is running. Ethernet IPv4 fix is OFF. Ctrl+C stops it and returns Home.', flush=True)
            if not announced and retry_at is None and time.monotonic() - started > 20:
                print('Startup did not complete; stopping both components.', flush=True)
                status = 1
                break
    except Exception as exc:
        print('Combined helper error: %s' % exc, flush=True)
        status = 1
    finally:
        stop_children()
        selector.close()
    return status


if __name__ == '__main__':
    sys.exit(main())

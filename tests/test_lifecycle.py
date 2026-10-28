"""Inert child processes only; these tests never start packet capture or DHCP."""
from pathlib import Path
import os
import itertools
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / 'src/combined_worker.py'
MOCK = '''import os,signal,sys,time
from pathlib import Path
role=ROLE
d=Path(os.environ['E3200_TEST_DIRECTORY'])
(d/(role+'.pid')).write_text(str(os.getpid()))
mode=os.environ.get('E3200_TEST_MODE','normal')
if mode=='fail-'+role:sys.exit(7)
print('FORWARDER READY: mock' if role=='bridge' else 'dnsmasq: started, version mock',flush=True)
if mode=='stubborn':signal.signal(signal.SIGTERM,signal.SIG_IGN)
else:signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
while True:time.sleep(.03)
'''


def wait_for(check, timeout=7):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.03)
    raise AssertionError('Timed out waiting for an inert test process')


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='e3200-offline-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def fixture(self, name, mode='normal'):
        d = self.base / name
        d.mkdir()
        bridge = d / 'mock_forwarder.py'
        bridge.write_text(MOCK.replace('ROLE', repr('bridge')))
        dns = d / 'mock_dnsmasq'
        dns.write_text('#!' + sys.executable + '\n' + MOCK.replace('ROLE', repr('dnsmasq')))
        dns.chmod(0o700)
        config = d / 'config.conf'
        config.touch()
        env = dict(os.environ, E3200_TEST_DIRECTORY=str(d), E3200_TEST_MODE=mode)
        args = [sys.executable, str(WORKER), '--dnsmasq', str(dns), '--config', str(config),
                '--bridge', str(bridge), '--lock-file', str(d / 'lock'),
                '--uid', str(os.getuid()), '--gid', str(os.getgid()), '--ethernet', 'en90',
                '--wifi', 'en91', '--server', '192.0.2.1', '--extender-mac', '02:00:00:00:00:02']
        return d, env, args

    def gone(self, d):
        for file in d.glob('*.pid'):
            self.assertFalse(alive(int(file.read_text())), 'Retained process: ' + file.name)

    def direct(self, name, mode='normal', signum=None, kill_role=None):
        d, env, args = self.fixture(name, mode)
        logpath = d / 'output.log'
        with logpath.open('w') as log:
            process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env)
            try:
                if mode.startswith('fail-'):
                    self.assertEqual(process.wait(timeout=7), 1)
                    if mode == 'fail-bridge':
                        self.assertFalse((d / 'dnsmasq.pid').exists())
                else:
                    wait_for(lambda: 'READY: E3200 and Ethernet helpers are running.' in logpath.read_text())
                    if kill_role:
                        os.kill(int((d / (kill_role + '.pid')).read_text()), signal.SIGTERM)
                    else:
                        process.send_signal(signum or signal.SIGTERM)
                    self.assertEqual(process.wait(timeout=5), 1 if kill_role else 0, logpath.read_text())
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
        self.gone(d)

    def test_stop_signals(self):
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=sig):
                self.direct('signal-' + str(sig), signum=sig)

    def test_startup_failures(self):
        self.direct('bridge-fails', mode='fail-bridge')
        self.direct('extender-fails', mode='fail-dnsmasq')

    def test_component_death_stops_peer(self):
        self.direct('bridge-exits', kill_role='bridge')
        self.direct('extender-exits', kill_role='dnsmasq')

    def test_stubborn_children_are_reaped(self):
        self.direct('stubborn', mode='stubborn')

    def test_compatibility_never_starts_forwarder_and_shuts_down(self):
        cases = [('normal', signal.SIGINT), ('normal', signal.SIGTERM),
                 ('normal', signal.SIGHUP), ('stubborn', signal.SIGTERM),
                 ('fail-dnsmasq', None), ('dies', None)]
        for number, (mode, sig) in enumerate(cases):
            with self.subTest(mode=mode, signal=sig):
                d, env, args = self.fixture('compat-' + str(number), mode)
                args.extend(['--mode', 'compatibility'])
                logpath = d / 'output.log'
                with logpath.open('w') as log:
                    process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env)
                    try:
                        if mode == 'fail-dnsmasq':
                            self.assertEqual(process.wait(timeout=7), 1)
                        else:
                            wait_for(lambda: 'READY: Wi-Fi-only' in logpath.read_text())
                            self.assertFalse((d / 'bridge.pid').exists())
                            if mode == 'dies':
                                os.kill(int((d / 'dnsmasq.pid').read_text()), signal.SIGTERM)
                            else:
                                process.send_signal(sig)
                            self.assertEqual(process.wait(timeout=5), 1 if mode == 'dies' else 0, logpath.read_text())
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            process.wait(timeout=5)
                self.assertFalse((d / 'bridge.pid').exists())
                self.gone(d)

    @unittest.skipUnless(sys.platform == 'darwin', 'Darwin parent watcher')
    def test_supervisor_parent_death_stop_request_and_terminal_interrupt(self):
        for helper_mode, action in itertools.product(('full', 'compatibility'), ('parent-death', 'stop-request', 'terminal-interrupt')):
            with self.subTest(mode=helper_mode, action=action):
                d, env, args = self.fixture(helper_mode + '-' + action)
                args.extend(['--mode', helper_mode])
                state = d / 'state'
                state.mkdir()
                sudo = d / 'sudo-shim'
                sudo.write_text('#!/bin/bash\n[ "$1" != -v ] || exit 0\n[ "$1" != -n ] || shift\nexec "$@"\n')
                sudo.chmod(0o700)
                watcher = d / 'watch-shim'
                watcher.write_text('#!' + sys.executable + '\n' + '''import select,sys
pid=int(sys.argv[sys.argv.index('-w')+1])
k=select.kqueue()
try:k.control([select.kevent(pid,filter=select.KQ_FILTER_PROC,flags=select.KQ_EV_ADD|select.KQ_EV_ENABLE,fflags=select.KQ_NOTE_EXIT)],1,None)
except ProcessLookupError:pass
''')
                watcher.chmod(0o700)
                source = (ROOT / 'src/launcher.template.command').read_text()
                prefix = source[:source.index('\nE3200_MAC=')]
                prefix = prefix.replace('/usr/bin/sudo', str(sudo)).replace('/usr/bin/caffeinate', str(watcher))
                env.update(E3200_STATE_DIR=str(state), E3200_ETHERNET='en90', E3200_SERVER='192.0.2.1',
                           E3200_ETHERNET_MAC='02:00:00:00:00:04')
                launcher = d / 'launcher.command'
                launcher.write_text(prefix + '\nRUN_ID=test\nrun_managed "$STATE_DIR/test.log" '
                                    + ' '.join(shlex.quote(arg) for arg in args) + '\n')
                with (d / 'outer.log').open('w') as log:
                    process = subprocess.Popen(['/bin/bash', str(launcher)], stdout=log,
                                               stderr=subprocess.STDOUT, env=env, start_new_session=True)
                    try:
                        wait_for(lambda: (state / 'test.log').exists() and 'READY:' in (state / 'test.log').read_text())
                        runtime = next(state.glob('run-*'))
                        if action == 'parent-death':
                            process.kill()
                        elif action == 'stop-request':
                            (runtime / 'stop.request').touch()
                        else:
                            os.killpg(process.pid, signal.SIGINT)
                        process.wait(timeout=10)
                        wait_for(lambda: (runtime / 'stopped').exists())
                        self.gone(d)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                            process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()

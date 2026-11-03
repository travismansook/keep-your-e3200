"""Exercise real terminal editing rather than mocking Python's input()."""
import os
import json
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TerminalInputTests(unittest.TestCase):
    def test_full_terminal_wizard_retries_then_accepts_lowercase_yes(self):
        # Fake only discovery and service startup. The real menu, readline,
        # questions, validation, confirmation and profile save all execute.
        script = """
import json, sys
from pathlib import Path
sys.path.insert(0, 'src')
import desktop
desktop.STATE = Path(sys.argv[1])
desktop.sys.platform = 'darwin'
desktop.os.geteuid = lambda: 501
desktop.config.connections = lambda: [
    dict(device='en91', label='Wi-Fi', mac='02:00:00:00:00:06', active=True,
         wifi=True, ip='192.0.2.10', mask='255.255.255.0'),
    dict(device='en90', label='USB Ethernet 1', mac='02:00:00:00:00:04', active=True,
         wifi=False, ip='169.254.1.10', mask='255.255.0.0'),
    dict(device='en92', label='USB Ethernet 2', mac='02:00:00:00:00:08', active=True,
         wifi=False, ip='169.254.1.11', mask='255.255.0.0')]
desktop.config.router_for = lambda _: '192.0.2.1'
desktop.run = lambda profile, **kwargs: (print('TEST_RUN=' + json.dumps(profile), flush=True) or 0)
raise SystemExit(desktop.main(['--setup']))
"""
        with tempfile.TemporaryDirectory() as directory:
            master, slave = pty.openpty()
            child = subprocess.Popen(
                [sys.executable, '-c', script, directory], cwd=ROOT,
                stdin=slave, stdout=slave, stderr=slave,
                env=dict(os.environ, TERM='xterm-256color', NO_COLOR='1'))
            os.close(slave)

            def read_prompt():
                data = b''
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if select.select([master], [], [], .02)[0]:
                        try:
                            chunk = os.read(master, 65536)
                        except OSError:
                            break
                        if not chunk:
                            break
                        data += chunk
                        if data.endswith(b'  > '):
                            break
                return data

            try:
                self.assertIn(b'Choose 1 or 2', read_prompt())
                rounds = [
                    ('', b'Nothing has been selected.'),
                    ('1', b'Which Ethernet connection'),
                    ('', b'Choose one of the connection numbers'),
                    ('2', b'Main CHR30A router address'),
                    ('', b'E3200 LAN1 MAC'),
                    ('02.00.00.00.00.AA', b'E3200 settings-page address'),
                    ('192.0.2.1', b'That is the main router address.'),
                    ('192.0.2.250', b'Address checked and protected?'),
                    ('', b'Please type yes to confirm, or no to cancel'),
                    ('maybe', b'Please type yes to confirm, or no to cancel'),
                    ('yes', b'Lease option')]
                for answer, expected in rounds:
                    with self.subTest(answer=answer, expected=expected):
                        os.write(master, answer.encode() + b'\n')
                        self.assertIn(expected, read_prompt())
                        self.assertFalse((Path(directory) / 'profile.json').exists())
                os.write(master, b'2\n')
                output = read_prompt()
                self.assertIn(b'TEST_RUN=', output)
                self.assertNotIn(b'Traceback', output)
                self.assertEqual(child.wait(timeout=3), 0)
                profile = json.loads((Path(directory) / 'profile.json').read_text())
                self.assertEqual(profile['extender_mac'], '02:00:00:00:00:aa')
                self.assertEqual(profile['lease_minutes'], 1440)
                self.assertEqual(profile['ethernet_interface'], 'en92')
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
                os.close(master)

    def test_backspace_stops_at_empty_answer_and_still_edits_typed_text(self):
        master, slave = pty.openpty()
        script = (
            "import sys; sys.path.insert(0, 'src'); import desktop; "
            "answer = desktop.ask('E3200 LAN1 MAC'); "
            "print('ANSWER=' + repr(answer), flush=True)"
        )
        child = subprocess.Popen(
            [sys.executable, '-c', script], cwd=ROOT,
            stdin=slave, stdout=slave, stderr=slave,
            env=dict(os.environ, TERM='xterm-256color', NO_COLOR='1'))
        os.close(slave)

        def read_until(marker=None, timeout=.25):
            data = b''
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if select.select([master], [], [], .02)[0]:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    data += chunk
                    if marker and marker in data:
                        break
            return data

        try:
            initial = read_until(b'  > ', 3)
            self.assertIn(b'E3200 LAN1 MAC:\r\n  > ', initial)
            # Erasing beyond the start of an empty answer must not erase the
            # input indicator or move the cursor back toward the label.
            os.write(master, b'\x7f' * 30)
            at_start = read_until()
            self.assertNotIn(b'\x08', at_start)
            self.assertNotIn(b'\x1b', at_start)
            self.assertNotIn(b'\x7f', at_start)
            # Normal corrections still work, including the sticker's dots.
            os.write(master, b'02.00.00.AA' + b'\x7f\x7f' + b'BB\n')
            result = read_until(b"ANSWER='02.00.00.BB'", 3)
            self.assertIn(b"ANSWER='02.00.00.BB'", result)
            self.assertEqual(child.wait(timeout=3), 0)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
            os.close(master)


if __name__ == '__main__':
    unittest.main()

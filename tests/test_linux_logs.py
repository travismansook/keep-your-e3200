"""Log viewer navigation, including a real foreground-terminal Ctrl+C."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import linux_app as app


class LinuxLogTests(unittest.TestCase):
    def test_live_viewer_handles_interrupt_without_controlling_the_service(self):
        results = [KeyboardInterrupt(),
                   subprocess.CalledProcessError(-signal.SIGINT, ['journalctl']),
                   subprocess.CalledProcessError(128 + signal.SIGINT, ['journalctl'])]
        for result in results:
            with self.subTest(result=result), patch.object(app, 'run', side_effect=result) as run, \
                    redirect_stdout(io.StringIO()) as output:
                app.view_logs(follow=True)
                self.assertEqual(run.call_count, 1)
                command = run.call_args.args[0]
                self.assertEqual(command[0], 'journalctl')
                self.assertIn('--follow', command)
                self.assertIn('Live log viewer closed', output.getvalue())

    def test_live_viewer_does_not_hide_an_actual_journal_error(self):
        with patch.object(app, 'run', side_effect=subprocess.CalledProcessError(1, ['journalctl'])), \
                redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            app.view_logs(follow=True)

    def test_recent_logs_remain_a_one_time_view(self):
        with patch.object(app, 'run') as run, redirect_stdout(io.StringIO()):
            app.view_logs()
            self.assertNotIn('--follow', run.call_args.args[0])
            self.assertIn('--no-pager', run.call_args.args[0])

    def test_live_option_returns_home_without_an_extra_return_key(self):
        with patch('builtins.input', side_effect=['13', '0']), \
                patch.object(app, 'run', side_effect=KeyboardInterrupt()) as run, \
                redirect_stdout(io.StringIO()) as output:
            app.menu()
            self.assertEqual(run.call_count, 1)
            self.assertIn('13. View live logs', output.getvalue())
            self.assertIn('Returning Home.', output.getvalue())
            self.assertNotIn('Press Return to go Home.', output.getvalue())

    def test_real_terminal_ctrl_c_reaps_viewer_and_keeps_menu_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            viewer = Path(directory) / 'viewer.py'
            viewer.write_text("""import os, signal, time
signal.signal(signal.SIGINT, lambda *_: os._exit(130))
print('TEST_JOURNAL_READY:' + str(os.getpid()), flush=True)
while True:
    time.sleep(.02)
""")
            harness = """import subprocess, sys
sys.path.insert(0, SOURCE)
import linux_app as app
def run(command, **kwargs):
    if command[0] != 'journalctl':
        raise AssertionError('Unexpected service control: ' + repr(command))
    return subprocess.run([sys.executable, sys.argv[1]], check=True)
app.run = run
app.menu()
""".replace('SOURCE', repr(str(ROOT / 'src')))
            pid, master = pty.fork()
            if pid == 0:
                os.execve(sys.executable, [sys.executable, '-c', harness, str(viewer)],
                          dict(os.environ, TERM='xterm-256color'))
            transcript = bytearray()
            reaped = False

            def read_until(marker, timeout=6):
                data = bytearray()
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if select.select([master], [], [], .03)[0]:
                        try:
                            chunk = os.read(master, 65536)
                        except OSError:
                            break
                        if not chunk:
                            break
                        data.extend(chunk)
                        transcript.extend(chunk)
                        if marker in data:
                            return bytes(data)
                self.fail('Terminal did not show ' + repr(marker) + ': ' + transcript.decode(errors='replace'))

            try:
                self.assertIn(b'13. View live logs', read_until(b'  > '))
                os.write(master, b'13\n')
                ready = read_until(b'TEST_JOURNAL_READY:')
                if not ready.rstrip().split(b'TEST_JOURNAL_READY:')[-1].isdigit():
                    ready += read_until(b'\r\n')
                viewer_pid = int(ready.split(b'TEST_JOURNAL_READY:')[-1].split()[0])
                os.write(master, b'\x03')
                returned = read_until(b'  > ')
                self.assertIn(b'Returning Home.', returned)
                self.assertNotIn(b'Press Return to go Home.', returned)
                self.assertNotIn(b'Traceback', returned)
                with self.assertRaises(ProcessLookupError):
                    os.kill(viewer_pid, 0)
                os.write(master, b'0\n')
                read_until(b'Closing this menu does not stop')
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    result, status = os.waitpid(pid, os.WNOHANG)
                    if result:
                        reaped = True
                        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                        break
                    time.sleep(.02)
                self.assertTrue(reaped, transcript.decode(errors='replace'))
            finally:
                if not reaped:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)
                os.close(master)


if __name__ == '__main__':
    unittest.main()

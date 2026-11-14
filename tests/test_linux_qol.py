"""Pi menu/settings regressions. Network and service commands are replaced."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import linux_app as app
import linux_config as config
from test_linux import profile, wifi


class LinuxQualityOfLifeTests(unittest.TestCase):
    def test_blank_or_invalid_mode_does_not_start_setup_with_a_default_choice(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'CONFIG', Path(directory) / 'profile.json'), \
                patch.object(app, 'active', return_value=False), patch.object(app.network, 'connections') as discover, \
                patch.object(config, 'save') as save, patch('builtins.input', side_effect=['', 'bad', 'cancel']), \
                redirect_stdout(io.StringIO()) as output, self.assertRaises(app.Cancelled):
            app.setup()
        discover.assert_not_called()
        save.assert_not_called()
        self.assertIn('A choice is required', output.getvalue())

    def test_reconfigure_offers_saved_details_and_preserves_custom_lease(self):
        previous = dict(profile(), lease_minutes=60)
        ethernet = dict(device='eth0', mac=previous['ethernet_mac'], wifi=False, active=False, ip=None, mask=None)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            path.write_text('original setup')
            with patch.object(config, 'CONFIG', path), patch.object(config, 'load', return_value=previous), \
                    patch.object(config, 'save') as save, patch.object(app, 'active', return_value=False), \
                    patch.object(app.network, 'connections', return_value=[wifi(), ethernet]), \
                    patch.object(app.network, 'router_for', return_value=previous['gateway']), \
                    patch.object(app, 'find_router_mac', return_value=previous['home_router_mac']), \
                    patch('builtins.input', side_effect=['1', '', 'yes', '', '', '', 'yes', '', 'yes']), \
                    redirect_stdout(io.StringIO()):
                app.setup()
                self.assertEqual(save.call_args.args[1], previous)
                self.assertEqual(path.read_text(), 'original setup')

    def test_cancel_during_reconfigure_does_not_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            path.write_text('original setup')
            with patch.object(config, 'CONFIG', path), patch.object(config, 'load', return_value=profile()), \
                    patch.object(config, 'save') as save, patch.object(app, 'active', return_value=False), \
                    patch('builtins.input', side_effect=['cancel']), redirect_stdout(io.StringIO()), \
                    self.assertRaises(app.Cancelled):
                app.setup()
            save.assert_not_called()
            self.assertEqual(path.read_text(), 'original setup')

    def test_initial_status_does_not_tell_running_service_to_repeat_setup(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'STATE', Path(directory)), \
                patch.object(app, 'active', return_value=True), \
                patch.object(app.subprocess, 'run', return_value=Mock(returncode=0)), \
                redirect_stdout(io.StringIO()) as output:
            app.show_status()
            self.assertIn('Startup is in progress', output.getvalue())
            self.assertNotIn('Complete Setup', output.getvalue())

    def test_missing_setup_has_a_clear_next_step(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'No saved setup yet'):
                config.load(Path(directory) / 'missing.json')

    def test_status_handles_damaged_or_incomplete_runtime_report(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            for value in ('{broken', '{}', '[]', json.dumps(dict(title='READY', detail='old', action='old'))):
                (state / 'status.json').write_text(value)
                with self.subTest(value=value), patch.object(config, 'STATE', state), \
                        patch.object(app, 'active', return_value=True), \
                        patch.object(app.subprocess, 'run', return_value=Mock(returncode=0)), \
                        redirect_stdout(io.StringIO()) as output:
                    app.show_status()
                    self.assertIn('Component readiness is unknown', output.getvalue())
                    self.assertNotIn('Current report:', output.getvalue())

    def test_diagnose_labels_router_and_pi_and_survives_missing_ethernet(self):
        for wired in (dict(device='eth0', mac=profile()['ethernet_mac'], active=True, ip='169.254.10.20'),
                      RuntimeError('Network interface is missing: eth0')):
            with self.subTest(wired=wired), patch.object(config, 'load', return_value=profile()), \
                    patch.object(app.network, 'home_identity', return_value=wifi()), \
                    patch.object(app.network, 'snapshot', side_effect=[wired]), \
                    patch.object(app.network, 'command', return_value='Disk space report'), \
                    patch.object(app.shutil, 'which', return_value=None), redirect_stdout(io.StringIO()) as output:
                app.diagnose()
                text = output.getvalue()
                self.assertIn('Main router IPv4: 192.0.2.1', text)
                self.assertIn("This Pi's Wi-Fi IPv4: 192.0.2.10", text)
                self.assertIn('169.254.x.x', text)
                self.assertIn('Disk space report', text)
                if isinstance(wired, Exception):
                    self.assertIn('Reconnect the selected adapter', text)

    def test_boot_preferences_do_not_implicitly_start_or_stop_service(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled), patch.object(app, 'run') as run, redirect_stdout(io.StringIO()) as output:
                app.set_boot(enabled)
                run.assert_called_once_with(['systemctl', 'enable' if enabled else 'disable', config.UNIT])
                self.assertIn('future Pi reboots' if enabled else 'leaves the current helper running', output.getvalue())

    def test_manual_start_clears_old_failure_limit_before_starting(self):
        with patch.object(config, 'load', return_value=profile()), patch.object(app.network, 'home_identity'), \
                patch.object(app, 'show_status'), patch.object(app, 'run') as run, redirect_stdout(io.StringIO()):
            app.start()
            self.assertEqual([call.args[0][1] for call in run.call_args_list], ['reset-failed', 'start'])

    def test_confirmation_aliases_and_invalid_follow_flag(self):
        for answer, expected in (('y', True), ('YES', True), ('N', False), ('no', False)):
            with self.subTest(answer=answer), patch('builtins.input', return_value=answer), redirect_stdout(io.StringIO()):
                self.assertEqual(app.yes('Continue?'), expected)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
            app.main(['status', '--follow'])
        self.assertEqual(result.exception.code, 2)

    def test_saved_review_displays_human_readable_lease(self):
        with redirect_stdout(io.StringIO()) as output:
            app.review(profile())
        self.assertIn('365 days / 1 year', output.getvalue())
        self.assertIn('E3200 settings-page IPv4', output.getvalue())

    def test_terminal_backspace_and_arrow_key_editing(self):
        master, slave = pty.openpty()
        script = ("import sys; sys.path.insert(0, 'src'); import linux_app as app; "
                  "print('ANSWER=' + repr(app.ask('Edit test')), flush=True)")
        child = subprocess.Popen([sys.executable, '-c', script],
                cwd=Path(__file__).resolve().parents[1], stdin=slave, stdout=slave, stderr=slave,
                env=dict(os.environ, TERM='xterm-256color'))
        os.close(slave)

        def read_until(marker):
            data = bytearray()
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if select.select([master], [], [], .03)[0]:
                    try:
                        part = os.read(master, 65536)
                    except OSError:
                        break
                    if not part:
                        break
                    data.extend(part)
                    if marker in data:
                        return bytes(data)
            self.fail(data.decode(errors='replace'))

        try:
            read_until(b'  > ')
            os.write(master, b'\x7f' * 10 + b'abx\x1b[D\x7fc\x1b[C\n')
            self.assertIn(b"ANSWER='acx'", read_until(b"ANSWER='acx'"))
            self.assertEqual(child.wait(timeout=4), 0)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
            os.close(master)


if __name__ == '__main__':
    unittest.main()

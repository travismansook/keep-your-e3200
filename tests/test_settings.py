from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import configuration as config
import desktop


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.path = self.state / 'profile.json'
        self.original = config.example()
        config.save(self.path, self.original)
        self.before = self.path.read_bytes()

    def menu(self, answers):
        with patch.object(desktop, 'STATE', self.state), patch('builtins.input', side_effect=answers), \
             patch.object(config, 'connections', side_effect=AssertionError('Settings must not discover interfaces')), \
             patch.object(desktop, 'run', side_effect=AssertionError('Settings must not start services')), \
             redirect_stdout(io.StringIO()):
            return desktop.settings_menu(self.original)

    def test_lease_change_retries_invalid_answers_and_only_changes_duration(self):
        result = self.menu(['2', '', 'bad', '0', '3', '', 'bad', 'YeS', '', '4'])
        expected = dict(self.original, lease_minutes=525600)
        self.assertEqual(result, expected)
        self.assertEqual(config.load(self.path), expected)

    def test_review_and_cancel_never_modify_the_profile(self):
        for answers in (['1', '', '4'], ['2', '4', '', '4'], ['', 'bad', '4'], ['2', '2', 'no', '', '4'], ['2', '1', '', '4']):
            with self.subTest(answers=answers):
                self.assertEqual(self.menu(answers), self.original)
                self.assertEqual(self.path.read_bytes(), self.before)

    def test_eof_and_interrupt_before_saving_preserve_settings(self):
        for error in (EOFError, KeyboardInterrupt):
            for prefix in ([], ['2'], ['2', '2']):
                with self.subTest(error=error, prefix=prefix), self.assertRaises(error):
                    self.menu(prefix + [error()])
                self.assertEqual(self.path.read_bytes(), self.before)

    def test_full_setup_reuses_profile_and_mode_menu(self):
        updated = dict(self.original, mode='compatibility')
        with patch.object(desktop, 'setup', return_value=updated) as setup:
            self.assertEqual(self.menu(['3', '2', '', '4']), updated)
            setup.assert_called_once_with('compatibility', self.original)

    def test_start_uses_new_lease_and_quit_does_not_run(self):
        for answers, expected_calls in ((['2', '2', '2', 'yes', '', '4', '1', '1'], 1), (['3'], 0)):
            with self.subTest(answers=answers), patch.object(desktop, 'STATE', self.state), \
                 patch.object(desktop.sys, 'platform', 'darwin'), \
                 patch.object(desktop.sys.stdin, 'isatty', return_value=True), \
                 patch.object(desktop.os, 'geteuid', return_value=501), \
                 patch('builtins.input', side_effect=answers), patch.object(desktop, 'run', return_value=0) as run, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(desktop.main([]), 0)
                self.assertEqual(run.call_count, expected_calls)
                if expected_calls:
                    self.assertEqual(run.call_args.args[0]['lease_minutes'], 1440)

    def test_settings_cannot_write_during_dry_run(self):
        with patch.object(desktop, 'STATE', self.state), patch.object(desktop.sys, 'platform', 'darwin'), \
             patch.object(desktop.os, 'geteuid', return_value=501), \
             patch('builtins.input', side_effect=AssertionError('Dry run must not prompt')):
            with self.assertRaises(ValueError):
                desktop.main(['--settings', '--dry-run'])
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_review_waits_with_saved_values_visible(self):
        output = io.StringIO()
        def dismiss(prompt):
            text = output.getvalue()
            self.assertIn('Saved settings', text)
            self.assertIn(self.original['extender_ip'], text)
            self.assertIn(self.original['extender_mac'], text)
            self.assertIn('1 hour', text)
            self.assertNotIn('Mac VPN', text)
            self.assertLessEqual(len(text.splitlines()), 24)
            return ''
        with patch('builtins.input', side_effect=dismiss), redirect_stdout(output):
            desktop.review_settings(self.original)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_selection_does_not_save_until_yes(self):
        answers = iter(['2', '2', '', 'no', '', '4'])
        def answer(_):
            self.assertEqual(self.path.read_bytes(), self.before)
            return next(answers)
        with patch.object(desktop, 'STATE', self.state), patch('builtins.input', side_effect=answer), \
             patch.object(config, 'save') as save, redirect_stdout(io.StringIO()):
            self.assertEqual(desktop.settings_menu(self.original), self.original)
            save.assert_not_called()

    def test_failed_save_stays_in_settings_without_false_success(self):
        with patch.object(config.os, 'replace', side_effect=OSError('disk full')):
            result = self.menu(['2', '2', 'yes', '', '4'])
        self.assertEqual(result, self.original)
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(list(self.state.glob('.profile-*')), [])

    def test_stopped_session_returns_home_and_can_quit_without_restarting(self):
        with patch.object(desktop, 'STATE', self.state), patch.object(desktop.sys, 'platform', 'darwin'), \
             patch.object(desktop.sys.stdin, 'isatty', return_value=True), \
             patch.object(desktop.os, 'geteuid', return_value=501), \
             patch('builtins.input', side_effect=['1', '1', '3']), \
             patch.object(desktop, 'run', return_value=130) as run, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(desktop.main([]), 0)
            run.assert_called_once()
            self.assertIn('Helper stopped. Returning Home.', output.getvalue())


if __name__ == '__main__':
    unittest.main()

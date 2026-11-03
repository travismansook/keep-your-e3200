"""Launcher navigation and recovery, with all live networking replaced."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import desktop
import configuration as config
from test_setup_validation import connections


class QualityOfLifeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.path = self.state / 'profile.json'
        self.profile = dict(config.example(), lease_minutes=525600)
        config.save(self.path, self.profile)
        self.before = self.path.read_bytes()

    def launch(self, answers, results=(0,), args=None):
        with patch.object(desktop, 'STATE', self.state), \
             patch.object(desktop.sys, 'platform', 'darwin'), \
             patch.object(desktop.sys.stdin, 'isatty', return_value=True), \
             patch.object(desktop.os, 'geteuid', return_value=501), \
             patch('builtins.input', side_effect=answers), \
             patch.object(desktop, 'run', side_effect=results) as run, redirect_stdout(io.StringIO()) as output:
            status = desktop.main(args or [])
        return status, run.call_count, output.getvalue()

    def test_mode_back_and_help_do_not_start_services(self):
        for answers in (['1', 'back', '3'], ['4', '', '3']):
            with self.subTest(answers=answers):
                status, calls, _ = self.launch(answers)
                self.assertEqual((status, calls), (0, 0))
                self.assertEqual(self.path.read_bytes(), self.before)

    def test_failure_can_retry_or_return_home(self):
        for failure in (1, ValueError('home Wi-Fi changed')):
            with self.subTest(failure=failure):
                status, calls, text = self.launch(['1', '1', '', 'bad', '1'], (failure, 0))
                self.assertEqual((status, calls), (0, 2))
                self.assertIn('Action needed', text)
                status, calls, _ = self.launch(['1', '1', '2', '3'], (failure,))
                self.assertEqual((status, calls), (0, 1))

    def test_corrupt_profile_quit_preserves_original_file(self):
        self.path.write_text('{broken json')
        status, calls, text = self.launch(['2'])
        self.assertEqual((status, calls), (1, 0))
        self.assertIn('Could not read saved settings', text)
        self.assertEqual(self.path.read_text(), '{broken json')

    def test_cancel_at_each_setup_question_preserves_settings(self):
        valid = ['1', '', '02.00.00.00.00.AA', '192.0.2.250', 'yes', '3']
        for index in range(len(valid)):
            with self.subTest(question=index), patch.object(desktop, 'STATE', self.state), \
                 patch.object(config, 'connections', side_effect=connections), \
                 patch.object(config, 'router_for', return_value='192.0.2.1'), \
                 patch('builtins.input', side_effect=valid[:index] + ['CaNcEl']), redirect_stdout(io.StringIO()):
                self.assertIsNone(desktop.setup('full', self.profile))
                self.assertEqual(self.path.read_bytes(), self.before)

    def test_full_setup_keeps_existing_lease_and_adapter_default(self):
        previous = dict(self.profile, ethernet_interface='en92', ethernet_mac='02:00:00:00:00:08')
        with patch.object(desktop, 'STATE', self.state), \
             patch.object(config, 'connections', side_effect=connections), \
             patch.object(config, 'router_for', return_value='192.0.2.1'), \
             patch('builtins.input', side_effect=['', '', '', '', 'yes', '']), redirect_stdout(io.StringIO()):
            result = desktop.setup('full', previous)
        self.assertEqual(result['ethernet_interface'], 'en92')
        self.assertEqual(result['lease_minutes'], 525600)

    def test_narrow_terminal_dividers_do_not_overflow(self):
        with patch.dict(os.environ, {'COLUMNS': '40', 'LINES': '24', 'NO_COLOR': '1'}), redirect_stdout(io.StringIO()) as output:
            desktop.section('Settings')
        self.assertTrue(all(len(line) <= 40 for line in output.getvalue().splitlines()))


if __name__ == '__main__':
    unittest.main()

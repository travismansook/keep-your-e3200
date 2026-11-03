"""Drive the complete wizard with malformed input; never start live helpers."""
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


def connections():
    return [
        dict(device='en91', label='Wi-Fi', mac='02:00:00:00:00:06',
             active=True, wifi=True, ip='192.0.2.10', mask='255.255.255.0'),
        dict(device='en90', label='USB Ethernet 1', mac='02:00:00:00:00:04',
             active=True, wifi=False, ip='169.254.10.10', mask='255.255.0.0'),
        dict(device='en92', label='USB Ethernet 2', mac='02:00:00:00:00:08',
             active=True, wifi=False, ip='192.0.2.11', mask='255.255.255.0')]


class SetupValidationTests(unittest.TestCase):
    def exercise(self, answers, mode='compatibility', previous=False, failure=None):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            path = state / 'profile.json'
            if previous:
                config.save(path, config.example())
            before = path.read_bytes() if path.exists() else None
            with patch.object(desktop, 'STATE', state), \
                 patch.object(desktop.sys, 'platform', 'darwin'), \
                 patch.object(desktop.os, 'geteuid', return_value=501), \
                 patch.object(config, 'connections', side_effect=connections), \
                 patch.object(config, 'router_for', return_value='192.0.2.1'), \
                 patch('builtins.input', side_effect=answers) as read, \
                 patch.object(desktop, 'run', return_value=0) as run, \
                 redirect_stdout(io.StringIO()) as out:
                if failure:
                    with self.assertRaises(failure):
                        desktop.main(['--setup', '--mode', mode])
                else:
                    self.assertEqual(desktop.main(['--setup', '--mode', mode]), 0)
            after = path.read_bytes() if path.exists() else None
            if run.called:
                result = config.load(path)
                self.assertEqual(run.call_count, 1)
            else:
                self.assertEqual(after, before, 'Cancellation changed saved settings')
                result = None
            return result, out.getvalue(), read.call_count

    def test_confirmation_retries_blank_and_invalid_and_accepts_yes_in_any_case(self):
        for yes in ('yes', 'YES', 'YeS', ' yes '):
            answers = ['', '02.00.00.00.00.AA', '192.0.2.250', '', '  ', 'true', 'y', '1', yes, '']
            with self.subTest(yes=yes):
                profile, text, count = self.exercise(answers)
                self.assertEqual(profile['extender_mac'], '02:00:00:00:00:aa')
                self.assertEqual(profile['lease_minutes'], 60)
                self.assertEqual(count, len(answers))
                self.assertIn('Please type yes to confirm, or no to cancel', text)

    def test_no_cancels_without_starting_or_overwriting_settings(self):
        for previous in (False, True):
            for no in ('no', 'NO', 'nO', ' No '):
                with self.subTest(previous=previous, no=no):
                    profile, text, _ = self.exercise(
                        ['', '02.00.00.00.00.AA', '192.0.2.250', no], previous=previous)
                    self.assertIsNone(profile)
                    self.assertIn('Setup canceled', text)

    def test_every_prompt_retries_bad_values_before_running(self):
        for mode in ('full', 'compatibility'):
            answers = ([] if mode == 'compatibility' else ['', '0', '3', 'two', '2'])
            answers += [
                # Router: malformed, IPv6, self-assigned, network/broadcast,
                # different subnet, Mac address, then a wrong detected router.
                'bad', '::1', '169.254.1.1', '192.0.2.0', '192.0.2.255',
                '192.0.3.1', '192.0.2.10', '192.0.2.2', '',
                # MAC: required, malformed, group/zero and Mac adapter values.
                '', 'bad', 'ff.ff.ff.ff.ff.ff', '00.00.00.00.00.00',
                '02.00.00.00.00.06', '02.00.00.00.00.04', '02.00.00.00.00.AA',
                # E3200 IP: required, malformed, router, reserved endpoints,
                # different subnet, and both of the Mac's usable addresses.
                '', 'bad', '::1', '192.0.2.1', '192.0.2.0', '192.0.2.255',
                '192.0.3.250', '192.0.2.10', '192.0.2.11', '?', '192.0.2.250',
                # Confirmation is required, case insensitive, and retried.
                '', '1', 'sure', 'yes',
                # Lease menu keeps its explicit one-hour default.
                '0', '4', 'one', '2'
            ]
            with self.subTest(mode=mode):
                profile, text, count = self.exercise(answers, mode=mode)
                self.assertEqual(count, len(answers))
                self.assertEqual(profile['mode'], mode)
                self.assertEqual(profile['lease_minutes'], 1440)
                self.assertEqual(profile['extender_ip'], '192.0.2.250')
                self.assertIn('Start IP Address', text)
                if mode == 'full':
                    self.assertEqual(profile['ethernet_interface'], 'en92')

    def test_eof_and_ctrl_c_at_every_question_never_save_or_run(self):
        for mode in ('full', 'compatibility'):
            valid = (['1'] if mode == 'full' else []) + [
                '', '02.00.00.00.00.AA', '192.0.2.250', 'yes', '1']
            for previous in (False, True):
                for error in (EOFError, KeyboardInterrupt):
                    for index in range(len(valid)):
                        with self.subTest(mode=mode, previous=previous, error=error, question=index):
                            profile, _, _ = self.exercise(valid[:index] + [error()], mode=mode,
                                                          previous=previous, failure=error)
                            self.assertIsNone(profile)

    def test_saved_defaults_remain_usable_after_explicit_mode_choice(self):
        for mode in ('full', 'compatibility'):
            answers = (['1'] if mode == 'full' else []) + ['', '', '', 'yes', '']
            with self.subTest(mode=mode):
                profile, _, _ = self.exercise(answers, mode=mode, previous=True)
                self.assertEqual(profile['extender_ip'], config.example()['extender_ip'])
                self.assertEqual(profile['extender_mac'], config.example()['extender_mac'])
                self.assertEqual(profile['lease_minutes'], 60)


if __name__ == '__main__':
    unittest.main()

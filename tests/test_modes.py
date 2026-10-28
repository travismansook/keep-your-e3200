"""Mode boundaries and guided setup; no real network discovery or services."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import configuration as config
import desktop


def wifi():
    return dict(device='en91', label='Wi-Fi', mac='02:00:00:00:00:06', active=True,
                wifi=True, ip='192.0.2.10', mask='255.255.255.0')


class ModeTests(unittest.TestCase):
    def compatible(self):
        return config.validate(dict(config.example(), mode='compatibility',
                                    ethernet_interface=None, ethernet_mac=None))

    def test_info_distinguishes_offered_extender_lease_and_router_leases(self):
        for mode in ('full', 'compatibility'):
            with self.subTest(mode=mode), redirect_stdout(io.StringIO()) as out:
                desktop.show_info(config.validate(dict(config.example(), mode=mode, lease_minutes=525600)))
                text = out.getvalue()
                self.assertIn('1 year (365 days) (525600 minutes)', text)
                self.assertIn('E3200 lease offered:', text)
                self.assertIn('Ordinary device leases: controlled by the main router', text)
                self.assertIn('acceptance is confirmed', text)
                if mode == 'compatibility':
                    self.assertIn('Ethernet IPv4 fix is OFF', text)

    def test_legacy_profile_defaults_to_full(self):
        profile = config.example()
        profile.pop('mode')
        self.assertEqual(config.validate(profile)['mode'], 'full')

    def test_only_compatibility_allows_missing_adapter(self):
        profile = self.compatible()
        self.assertEqual(config.runtime_values(profile, [wifi()], '192.0.2.1')['wifi_ip'], '192.0.2.10')
        for values in (dict(profile, mode='full'), dict(profile, mode='unknown'),
                       dict(profile, ethernet_mac='02:00:00:00:00:04')):
            with self.assertRaises(ValueError):
                config.validate(values)
        with self.assertRaises(ValueError):
            config.runtime_values(config.example(), [wifi()], '192.0.2.1')
        with self.assertRaises(ValueError):
            config.runtime_values(profile, [], '192.0.2.1')
        with self.assertRaises(ValueError):
            config.runtime_values(profile, [dict(wifi(), ip='192.0.3.10')], '192.0.2.1')

    def test_first_setup_without_any_ethernet_hardware(self):
        questions = []
        answers = iter(['', '02:00:00:00:00:02', '192.0.2.250', 'YES', ''])
        def respond(question):
            questions.append(question)
            return next(answers)
        with tempfile.TemporaryDirectory() as directory, patch.object(desktop, 'STATE', Path(directory)), \
             patch.object(config, 'connections', return_value=[wifi()]), \
             patch.object(config, 'router_for', return_value='192.0.2.1'), \
             patch('builtins.input', side_effect=respond), redirect_stdout(io.StringIO()):
            profile = desktop.setup('compatibility')
            self.assertIsNone(profile['ethernet_interface'])
            self.assertEqual(config.load(Path(directory) / 'profile.json')['mode'], 'compatibility')
        self.assertFalse(any('Which Ethernet' in q for q in questions))

    def test_recommended_menu_is_default_and_saved_settings_are_reused(self):
        with patch('builtins.input', return_value=''), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(desktop.choose_mode(), 'full')
            self.assertIn('Recommended', out.getvalue())
        with tempfile.TemporaryDirectory() as directory, patch.object(desktop, 'STATE', Path(directory)), \
             patch.object(desktop.sys, 'platform', 'darwin'), patch.object(desktop.sys.stdin, 'isatty', return_value=True), \
             patch('builtins.input', return_value='2'), patch.object(desktop, 'run', return_value=0) as run, \
             patch.object(desktop, 'setup') as setup, redirect_stdout(io.StringIO()):
            old = config.example()
            old.pop('mode')
            (Path(directory) / 'profile.json').write_text(json.dumps(old))
            self.assertEqual(desktop.main([]), 0)
            setup.assert_not_called()
            used = run.call_args.args[0]
            self.assertEqual(used['mode'], 'compatibility')
            self.assertEqual(used['extender_ip'], old['extender_ip'])
            self.assertEqual(used['ethernet_mac'], old['ethernet_mac'])

    def test_wifi_first_user_must_choose_adapter_before_full_mode(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(desktop, 'STATE', Path(directory)), \
             patch.object(desktop.sys, 'platform', 'darwin'), patch.object(desktop.sys.stdin, 'isatty', return_value=True), \
             patch('builtins.input', return_value=''), patch.object(desktop, 'run', return_value=0), \
             patch.object(desktop, 'setup', return_value=config.example()) as setup, redirect_stdout(io.StringIO()):
            profile = self.compatible()
            config.save(Path(directory) / 'profile.json', profile)
            desktop.main([])
            setup.assert_called_once_with('full', profile)

    def test_dry_run_never_invokes_setup_or_saves_a_mode_change(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(desktop, 'STATE', Path(directory)), \
             patch.object(desktop.sys, 'platform', 'darwin'), patch.object(desktop, 'setup') as setup:
            path = Path(directory) / 'profile.json'
            config.save(path, self.compatible())
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                desktop.main(['--dry-run', '--mode', 'full'])
            setup.assert_not_called()
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

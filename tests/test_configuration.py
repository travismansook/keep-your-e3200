from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import configuration as c


class ConfigurationTests(unittest.TestCase):
    def test_example_validates_and_normalizes(self):
        profile = c.example()
        self.assertEqual(c.validate(profile), profile)
        self.assertEqual(c.normalize_mac('02-00-00-00-00-AA'), '02:00:00:00:00:aa')

    def test_invalid_identity_and_network_values(self):
        for field, value in [('extender_mac', 'ff:ff:ff:ff:ff:ff'),
                             ('extender_mac', '00:00:00:00:00:00'),
                             ('extender_ip', '192.0.2.1'), ('extender_ip', '192.0.2.255'),
                             ('extender_ip', '192.0.3.250'), ('gateway', '169.254.1.1'),
                             ('dns', '127.0.0.1'), ('subnet_mask', '255.0.255.0'),
                             ('ethernet_interface', 'en90; reboot'), ('lease_minutes', True),
                             ('lease_minutes', 0), ('lease_minutes', 525601),
                             ('address_plan_confirmed', False)]:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    c.validate(dict(c.example(), **{field: value}))

    def test_missing_unknown_and_same_connection(self):
        with self.assertRaises(ValueError):
            c.validate(dict(c.example(), extra='ignored'))
        profile = c.example()
        del profile['dns']
        with self.assertRaises(ValueError):
            c.validate(profile)
        for change in ({'wifi_interface': 'en90'}, {'extender_mac': c.example()['ethernet_mac']}):
            with self.assertRaises(ValueError):
                c.validate(dict(c.example(), **change))

    def test_private_roundtrip_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            c.save(path, c.example())
            self.assertEqual(c.load(path), c.example())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                c.load(link)
            with self.assertRaises(OSError):
                c.save(link, c.example())

    def test_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            text = json.dumps(c.example()).replace('"lease_minutes": 60', '"lease_minutes": 60, "lease_minutes": 1440')
            path.write_text(text)
            with self.assertRaises(ValueError):
                c.load(path)

    def links(self):
        profile = c.example()
        return [dict(device='en90', mac=profile['ethernet_mac'], active=True, wifi=False,
                     ip='169.254.10.10', mask='255.255.0.0'),
                dict(device='en91', mac='02:00:00:00:00:06', active=True, wifi=True,
                     ip='192.0.2.10', mask='255.255.255.0')]

    def test_runtime_accepts_self_assigned_wired_address(self):
        values = c.runtime_values(c.example(), self.links(), router='192.0.2.1')
        self.assertEqual(values['wifi_ip'], '192.0.2.10')
        self.assertEqual(values['network'], '192.0.2.0')
        self.assertEqual(values['subnet_hex'], '0xffffff00')

    def test_rejects_wrong_adapter_network_and_address_conflict(self):
        cases = [(0, 'active', False), (0, 'mac', '02:00:00:00:00:08'),
                 (0, 'wifi', True), (1, 'active', False), (1, 'ip', '169.254.1.2'),
                 (1, 'ip', '192.0.3.10'), (1, 'mask', '255.255.0.0'),
                 (1, 'ip', '192.0.2.250'), (0, 'ip', '192.0.2.250')]
        for index, field, value in cases:
            with self.subTest(field=field, value=value):
                links = self.links()
                links[index][field] = value
                with self.assertRaises(ValueError):
                    c.runtime_values(c.example(), links, router='192.0.2.1')
        with self.assertRaises(ValueError):
            c.runtime_values(c.example(), self.links(), router='192.0.2.2')


if __name__ == '__main__':
    unittest.main()

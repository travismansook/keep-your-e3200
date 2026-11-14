"""Run update scripts with isolated paths and fake OS/package commands."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LinuxUpdateTests(unittest.TestCase):
    def executable(self, folder, name, body):
        path = folder / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)

    def fixture(self, base):
        tools = base / 'bin'
        tools.mkdir()
        cache = base / 'cache'
        cache.mkdir()
        (cache / 'current.deb').write_bytes(b'previous installed package')
        release = base / 'release'
        (release / 'linux').mkdir(parents=True)
        installer = release / 'linux/install.sh'
        installer.write_text((ROOT / 'linux/install.sh').read_text().replace('/var/cache/keep-your-e3200', str(cache)))
        package = release / 'keep-your-e3200_0.1.0~preview2_all.deb'
        package.write_bytes(b'new package for simulated apt')
        (release / 'keep-your-e3200_0.1.0~preview1_all.deb').write_bytes(b'old extracted download')
        manifest = release / 'linux/SHA256SUMS'
        manifest.write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' +
                                  str(path.relative_to(release)) + '\n' for path in (installer, package)))
        self.executable(tools, 'uname', "print('Linux')\n")
        self.executable(tools, 'id', "print('0')\n")
        self.executable(tools, 'nmcli', 'raise SystemExit(0)\n')
        self.executable(tools, 'systemctl', 'raise SystemExit(0)\n')
        self.executable(tools, 'apt-get', """import json, os, sys
with open(os.environ['TEST_ACTIONS'], 'a') as file:
    file.write(json.dumps(sys.argv[1:]) + '\\n')
""")
        self.executable(tools, 'sha256sum', """import hashlib, pathlib, sys
for row in pathlib.Path(sys.argv[2]).read_text().splitlines():
    digest, name = row.split('  ', 1)
    if hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest() != digest:
        raise SystemExit(1)
""")
        actions = base / 'actions.jsonl'
        env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], TEST_ACTIONS=str(actions))
        return installer, package, cache, actions, env

    def test_update_selects_manifest_package_when_old_download_is_still_present(self):
        with tempfile.TemporaryDirectory() as directory:
            installer, package, cache, actions, env = self.fixture(Path(directory))
            result = subprocess.run(['/bin/sh', str(installer), '--update'], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = [json.loads(line) for line in actions.read_text().splitlines()]
            self.assertEqual(calls, [['update'], ['install', '-y', str(package)]])
            self.assertEqual((cache / 'current.deb').read_bytes(), package.read_bytes())
            self.assertEqual((cache / 'previous.deb').read_bytes(), b'previous installed package')

    def test_checksum_failure_does_not_install_or_replace_cached_package(self):
        with tempfile.TemporaryDirectory() as directory:
            installer, package, cache, actions, env = self.fixture(Path(directory))
            package.write_bytes(b'corrupted download')
            result = subprocess.run(['/bin/sh', str(installer), '--update'], env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(actions.exists())
            self.assertEqual((cache / 'current.deb').read_bytes(), b'previous installed package')

    def test_upgrade_forgets_old_restart_marker_when_service_is_now_stopped(self):
        for running in (False, True):
            with self.subTest(running=running), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                tools = base / 'bin'
                tools.mkdir()
                marker = base / 'restart-marker'
                marker.touch()
                script = base / 'prerm'
                script.write_text((ROOT / 'linux/prerm').read_text().replace('/run/keep-your-e3200-upgrade-active', str(marker)))
                self.executable(tools, 'systemctl', """import os, sys
if sys.argv[1] == 'is-active':
    raise SystemExit(0 if os.environ['TEST_RUNNING'] == '1' else 3)
raise SystemExit(0)
""")
                result = subprocess.run(['/bin/sh', str(script), 'upgrade'],
                        env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], TEST_RUNNING=str(int(running))),
                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(marker.exists(), running)


if __name__ == '__main__':
    unittest.main()

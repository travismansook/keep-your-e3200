"""Validate Debian archives/upgrade scripts without apt or a Linux host."""
import gzip
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('linux_builder',ROOT/'packaging/build_linux.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def members(data):
    assert data[:8]==b'!<arch>\n'
    result={};pos=8
    while pos<len(data):
        header=data[pos:pos+60];assert header[58:60]==b'`\n'
        name=header[:16].decode().strip().rstrip('/')
        size=int(header[48:58]);pos+=60
        result[name]=data[pos:pos+size];pos+=size+(size%2)
    return result


class LinuxPackageTests(unittest.TestCase):
    def test_deb_contents_and_preview_bundle_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            package,bundle=builder.build(directory)
            chunks=members(package.read_bytes())
            self.assertEqual(chunks['debian-binary'],b'2.0\n')
            with tarfile.open(fileobj=io.BytesIO(chunks['control.tar.gz']),mode='r:gz') as control:
                text=control.extractfile('control').read().decode()
                self.assertIn('Architecture: all',text)
                self.assertIn('Version: '+builder.linux_config.VERSION,text)
                for name in ('preinst','postinst','prerm','postrm'):
                    self.assertEqual(control.getmember(name).mode,0o755)
                sums=control.extractfile('md5sums').read().decode().splitlines()
            with tarfile.open(fileobj=io.BytesIO(chunks['data.tar.gz']),mode='r:gz') as archive:
                names=archive.getnames()
                self.assertNotIn('etc/keep-your-e3200/profile.json',names)
                self.assertFalse(any(name.endswith('.leases') for name in names))
                self.assertIn('usr/lib/systemd/system/keep-your-e3200.service',names)
                self.assertEqual(archive.getmember('usr/bin/keep-your-e3200').mode,0o755)
                for row in sums:
                    digest,name=row.split('  ',1)
                    self.assertEqual(hashlib.md5(archive.extractfile(name).read()).hexdigest(),digest)
            with tarfile.open(bundle,'r:gz') as archive:
                prefix='Keep-Your-E3200-Linux-Preview/'
                for row in archive.extractfile(prefix+'linux/SHA256SUMS').read().decode().splitlines():
                    digest,name=row.split('  ',1)
                    self.assertEqual(hashlib.sha256(archive.extractfile(prefix+name).read()).hexdigest(),digest)
                self.assertIn(prefix+package.name,archive.getnames())

    def test_first_install_is_stopped_and_upgrade_remembers_active_state(self):
        before=(ROOT/'linux/prerm').read_text()
        after=(ROOT/'linux/postinst').read_text()
        self.assertIn('upgrade)',before)
        self.assertIn('is-active --quiet',before)
        self.assertIn('keep-your-e3200-upgrade-active',before)
        self.assertIn('if [ -f /run/keep-your-e3200-upgrade-active ]',after)
        self.assertNotIn('systemctl enable',after)
        self.assertIn('No service was started or enabled automatically',after)
        self.assertNotIn('profile.json',after)

    def test_installer_handles_updates_without_compiler_and_retains_previous_package(self):
        text=(ROOT/'linux/install.sh').read_text()
        self.assertIn('--update',text)
        self.assertIn('apt-get install -y "$PACKAGE"',text)
        self.assertIn('previous.deb',text)
        self.assertNotIn('gcc',text)
        self.assertNotIn('make ',text)
        self.assertIn('sha256sum --check',text)


if __name__=='__main__':unittest.main()

from pathlib import Path
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import desktop


class PackagingTests(unittest.TestCase):
    def package(self, root):
        runtime = root / 'runtime'
        runtime.mkdir()
        contents = {name: (b'\xcf\xfa\xed\xfe' + b'test engine' if name == 'dnsmasq'
                           else name.encode()) for name in desktop.FILES}
        manifest = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
        for name, data in contents.items():
            (runtime / name).write_bytes(gzip.compress(data, mtime=0) if name == 'dnsmasq' else data)
        (runtime / 'manifest.json').write_text(json.dumps(manifest))
        return runtime, contents

    def test_engine_roundtrip_preserves_original_integrity_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, contents = self.package(root)
            output = root / 'output'
            output.mkdir()
            with patch.object(desktop, 'RESOURCE', root):
                desktop.unpack(output)
            for name, data in contents.items():
                self.assertEqual((output / name).read_bytes(), data)
                self.assertEqual((output / name).stat().st_mode & 0o777, desktop.FILES[name])

    def test_changed_engine_is_rejected_after_decompression(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, _ = self.package(root)
            (runtime / 'dnsmasq').write_bytes(gzip.compress(b'changed engine', mtime=0))
            output = root / 'output'
            output.mkdir()
            with patch.object(desktop, 'RESOURCE', root), self.assertRaisesRegex(ValueError, 'damaged'):
                desktop.unpack(output)


if __name__ == '__main__':
    unittest.main()

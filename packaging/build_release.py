"""Build and offline-test a native, one-file Mac download. Never start DHCP."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'build/dnsmasq-2.93-macos-relay-source.tar.gz'


def run(args, **kwargs):
    subprocess.run([str(item) for item in args], check=True, **kwargs)


def prepare():
    source_info = json.loads((ROOT / 'third_party/SOURCE.json').read_text())
    patch = ROOT / 'third_party/macos-relay.patch'
    if hashlib.sha256(patch.read_bytes()).hexdigest() != source_info['patch_sha256']:
        raise ValueError('The reviewed patch does not match its pinned checksum.')
    upstream = ROOT / 'build/dnsmasq-2.93-upstream.tar.gz'
    upstream.parent.mkdir(parents=True, exist_ok=True)
    if not upstream.exists():
        run(['/usr/bin/curl', '--fail', '--location', '--connect-timeout', '15', '--max-time', '120',
             '--proto', '=https', '--output', upstream, source_info['upstream']])
    if hashlib.sha256(upstream.read_bytes()).hexdigest() != source_info['upstream_sha256']:
        raise ValueError('The official source download does not match the pinned checksum.')
    extracted = ROOT / 'build/engine-source'
    if extracted.is_symlink():
        raise ValueError('The source build folder must not be a symbolic link.')
    if extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True)
    with tarfile.open(upstream) as archive:
        for member in archive.getmembers():
            if not (member.isfile() or member.isdir()):
                raise ValueError('Unexpected entry in official source archive')
            if not (extracted / member.name).resolve().is_relative_to(extracted.resolve()):
                raise ValueError('Source archive path escapes the build directory')
        archive.extractall(extracted, filter='data')
    source = extracted / 'dnsmasq-2.93'
    run(['/usr/bin/patch', '-p1', '-i', patch], cwd=source)
    # Archive the complete modified source before compilation adds build products.
    with tarfile.open(ARCHIVE, 'w:gz') as archive:
        archive.add(source, arcname='dnsmasq-2.93-macos-relay')
    env = dict(os.environ, MACOSX_DEPLOYMENT_TARGET='15.0')
    run(['make', '-j2', 'COPTS=-DNO_GETTEXT -DNO_LUA -DNO_DBUS -DNO_UBUS -DNO_IDN -DNO_DNSSEC',
         'CFLAGS=-O2 -D__APPLE_USE_RFC_3542'], cwd=source, env=env)
    engine = source / 'src/dnsmasq'
    package = ROOT / 'build/package'
    runtime = package / 'runtime'
    notices = package / 'licenses'
    runtime.mkdir(parents=True, exist_ok=True)
    notices.mkdir(parents=True, exist_ok=True)
    for filename in ('forwarder.py', 'combined_worker.py', 'configuration.py'):
        shutil.copyfile(ROOT / 'src' / filename, runtime / filename)
    shutil.copyfile(ROOT / 'src/launcher.template.command', runtime / 'launcher.command')
    shutil.copyfile(engine, runtime / 'dnsmasq')
    (runtime / 'dnsmasq').chmod(0o755)
    manifest = {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                for file in runtime.iterdir() if file.is_file() and file.name != 'manifest.json'}
    (runtime / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # Keep the engine opaque to the freezer: its Mach-O rewriting/signing would
    # otherwise change the bytes after the integrity manifest was calculated.
    # The launcher decompresses it and verifies the original hash before use.
    (runtime / 'dnsmasq').write_bytes(gzip.compress((runtime / 'dnsmasq').read_bytes(), mtime=0))
    for origin, name in ((ROOT / 'LICENSE', 'Project-LICENSE.txt'),
                         (ROOT / 'THIRD-PARTY-NOTICES.md', 'THIRD-PARTY-NOTICES.md'),
                         (ARCHIVE, ARCHIVE.name),
                         (ROOT / 'third_party/dnsmasq-COPYING', 'dnsmasq-COPYING'),
                         (ROOT / 'third_party/SOURCE.json', 'SOURCE.json'),
                         (patch, 'macos-relay.patch')):
        shutil.copyfile(origin, notices / name)
    (notices / 'BUILD.json').write_text(json.dumps(dict(
        version=(ROOT / 'VERSION').read_text().strip(), source_commit=os.environ.get('GITHUB_SHA', 'local'),
        python=platform.python_version(), architecture=platform.machine(),
        engine_sha256=manifest['dnsmasq'],
        corresponding_source_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()), indent=2) + '\n')
    return package


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('Native Mac downloads must be built on macOS.')
    os.chdir(ROOT)
    os.environ.setdefault('PYINSTALLER_CONFIG_DIR', str(ROOT / 'build/pyinstaller-cache'))
    package = prepare()
    run([sys.executable, ROOT / 'src/desktop.py', '--self-test'])
    if args.prepare_only:
        return
    import importlib.metadata
    import sysconfig
    notices = package / 'licenses'
    python_license = next((path for path in (
        Path(sys.base_prefix) / 'LICENSE.txt', Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt') if path.is_file()), None)
    if python_license is None:
        raise RuntimeError('The Python runtime license is required in the downloadable program.')
    shutil.copyfile(python_license, notices / 'Python-LICENSE.txt')
    dist = importlib.metadata.distribution('pyinstaller')
    for entry in dist.files or []:
        if entry.name.lower().startswith(('license', 'copying')) and dist.locate_file(entry).is_file():
            shutil.copyfile(dist.locate_file(entry), notices / ('PyInstaller-' + entry.name))
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
         '--name', 'KeepYourE3200', '--distpath', 'build/native', '--workpath', 'build/freeze',
         '--specpath', 'build/spec', '--add-data', str(package / 'runtime') + ':runtime',
         '--add-data', str(notices) + ':licenses', ROOT / 'src/desktop.py'])
    binary = ROOT / 'build/native/KeepYourE3200'
    run([binary, '--self-test'])
    run([binary, '--version'])
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    label = 'AppleSilicon' if platform.machine() == 'arm64' else 'Intel'
    target = release / ('Keep-Your-E3200-macOS-' + label + '.zip')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        info = zipfile.ZipInfo('Keep Your E3200.command')
        info.create_system = 3
        info.external_attr = 0o100755 << 16
        output.writestr(info, binary.read_bytes())
    print('Built and offline-tested:', target)


if __name__ == '__main__':
    main()

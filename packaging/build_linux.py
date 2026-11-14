"""Build a small Architecture: all .deb and a ready-to-copy preview bundle.

Pure packaging: works on macOS; does not execute Linux, apt, or a DHCP service.
No third-party Python modules required.
"""
import gzip
import hashlib
import importlib.util
import io
from pathlib import Path, PurePosixPath
import tarfile
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import linux_config
FILES=['configuration.py','forwarder.py','linux_network.py','linux_config.py','linux_service.py','linux_app.py']


def tar_bytes(entries):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        folders = {str(parent) for name,_,_ in entries for parent in PurePosixPath(name).parents if str(parent) != '.'}
        for folder in sorted(folders, key=lambda name: (name.count('/'),name)):
            info=tarfile.TarInfo(folder)
            info.type=tarfile.DIRTYPE;info.mode=0o755;info.mtime=0;info.uid=info.gid=0
            info.uname=info.gname='root'
            archive.addfile(info)
        for name,data,mode in sorted(entries):
            info=tarfile.TarInfo(name)
            info.size=len(data);info.mode=mode;info.mtime=0;info.uid=info.gid=0
            info.uname=info.gname='root'
            archive.addfile(info,io.BytesIO(data))
    return gzip.compress(stream.getvalue(),mtime=0)


def ar_member(name,data):
    header=('%-16s%-12s%-6s%-6s%-8s%-10s`\n' % (name+'/',0,0,0,'100644',len(data))).encode('ascii')
    assert len(header)==60
    return header+data+(b'\n' if len(data)%2 else b'')


def build(output=None):
    output=Path(output or ROOT/'release/linux')
    output.mkdir(parents=True,exist_ok=True)
    data=[('opt/keep-your-e3200/src/'+name,(ROOT/'src'/name).read_bytes(),0o644) for name in FILES]
    data.extend([
        ('opt/keep-your-e3200/LICENSE',(ROOT/'LICENSE').read_bytes(),0o644),
        ('opt/keep-your-e3200/README.md',(ROOT/'linux/README.md').read_bytes(),0o644),
        ('opt/keep-your-e3200/VALIDATION.md',(ROOT/'linux/VALIDATION.md').read_bytes(),0o644),
        ('opt/keep-your-e3200/RELEASE_NOTES.md',(ROOT/'linux/RELEASE_NOTES.md').read_bytes(),0o644),
        ('opt/keep-your-e3200/THIRD-PARTY-NOTICES.md',(ROOT/'THIRD-PARTY-NOTICES.md').read_bytes(),0o644),
        ('usr/bin/keep-your-e3200',(ROOT/'linux/keep-your-e3200').read_bytes(),0o755),
        ('usr/lib/systemd/system/keep-your-e3200.service',(ROOT/'linux/keep-your-e3200.service').read_bytes(),0o644),
        ('usr/share/doc/keep-your-e3200/copyright',(ROOT/'LICENSE').read_bytes(),0o644)])
    version=linux_config.VERSION
    control=('Package: keep-your-e3200\nVersion: '+version+'\nArchitecture: all\n'
             'Maintainer: Travis Mansook\nSection: net\nPriority: optional\n'
             'Depends: python3 (>= 3.11), dnsmasq-base, libpcap0.8 | libpcap0.8t64, iproute2, iputils-ping, network-manager, adduser, systemd\n'
             'Homepage: https://github.com/travismansook/keep-your-e3200\n'
             'Description: E3200 compatibility and Ethernet DHCP helper for Linux\n'
             ' A foreground supervisor managed by systemd. The real router remains\n'
             ' the address allocator for ordinary clients. Initial installation does\n'
             ' not start or enable the service. Preview; broader field testing remains.\n').encode()
    controls=[('control',control,0o644),('md5sums',''.join(hashlib.md5(body).hexdigest()+'  '+name+'\n' for name,body,_ in data).encode(),0o644)]
    controls.extend((name,(ROOT/'linux'/name).read_bytes(),0o755) for name in ('preinst','postinst','prerm','postrm'))
    package=output/('keep-your-e3200_'+version+'_all.deb')
    package.write_bytes(b'!<arch>\n'+ar_member('debian-binary',b'2.0\n')+
                        ar_member('control.tar.gz',tar_bytes(controls))+ar_member('data.tar.gz',tar_bytes(data)))
    bundle=[(name,(ROOT/name).read_bytes(),0o644) for name in
            ['LICENSE','THIRD-PARTY-NOTICES.md','linux/README.md','linux/RELEASE_NOTES.md','linux/VALIDATION.md','linux/RELEASING.md','linux/keep-your-e3200.service','linux/test_network_namespace.py',
             'tests/test_linux.py','tests/test_linux_logs.py','tests/test_linux_qol.py','tests/test_linux_service.py','tests/test_forwarder.py','src/launcher.template.command']+
            ['src/'+name for name in FILES]]
    bundle.extend((name,(ROOT/name).read_bytes(),0o755) for name in
                  ('linux/install.sh','linux/keep-your-e3200','linux/preinst','linux/postinst','linux/prerm','linux/postrm'))
    bundle.append((package.name,package.read_bytes(),0o644))
    sums=''.join(hashlib.sha256(body).hexdigest()+'  '+name+'\n' for name,body,_ in sorted(bundle))
    bundle.append(('linux/SHA256SUMS',sums.encode(),0o644))
    target=output/'Keep-Your-E3200-Linux-Preview.tar.gz'
    target.write_bytes(tar_bytes([('Keep-Your-E3200-Linux-Preview/'+name,body,mode) for name,body,mode in bundle]))
    (output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n' for path in (package,target)))
    print(package);print(target)
    return package,target


if __name__=='__main__':build()

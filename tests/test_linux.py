"""Linux unit tests: mocked system calls, no host network changes."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, call
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import linux_app as app
import linux_config as config
import linux_network as network
import forwarder


def profile(mode='full'):
    return dict(version=1, mode=mode, wifi_interface='wlan0', wifi_mac='02:00:00:00:00:10',
                ethernet_interface='eth0' if mode == 'full' else None,
                ethernet_mac='02:00:00:00:00:11' if mode == 'full' else None,
                gateway='192.0.2.1', subnet_mask='255.255.255.0', home_router_mac='02:00:00:00:00:01',
                extender_mac='02:00:00:00:00:02', extender_ip='192.0.2.250', lease_minutes=525600,
                address_plan_confirmed=True)


def wifi():
    return dict(device='wlan0', mac='02:00:00:00:00:10', wifi=True, active=True,
                ip='192.0.2.10', mask='255.255.255.0')


class LinuxConfigTests(unittest.TestCase):
    def test_both_modes_and_mac_normalization(self):
        for mode in ('full', 'compatibility'):
            self.assertEqual(config.validate(dict(profile(mode), extender_mac='02.00.00.00.00.AA'))['extender_mac'], '02:00:00:00:00:aa')

    def test_rejects_injection_and_wrong_network_identity(self):
        for change in ({'wifi_interface':'wlan0\nport=53'}, {'gateway':'127.0.0.1'},
                       {'lease_minutes':True}, {'extender_ip':'192.0.3.250'}, {'extender_ip':'192.0.2.1'},
                       {'home_router_mac':'ff:ff:ff:ff:ff:ff'}, {'ethernet_interface':'wlan0'},
                       {'extender_mac':'02:00:00:00:00:11'}, {'lease_minutes':0}, {'address_plan_confirmed':False}, {'version':2}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                config.validate(dict(profile(), **change))

    def test_dnsmasq_only_serves_one_known_extender(self):
        text = config.dnsmasq_config(profile(), '/var/lib/keep-your-e3200/leases/e3200.leases')
        for expected in ('port=0\n','dhcp-ignore=tag:!known\n','192.0.2.0,static,255.255.255.0,525600m',
                         'dhcp-host=02:00:00:00:00:02,192.0.2.250,set:e3200','interface=wlan0\n','60,"ARCADYAN"'):
            self.assertIn(expected,text)
        template = (Path(__file__).resolve().parents[1] / 'src/launcher.template.command').read_text()
        self.assertIn('OPT125="' + config.VENDOR + '"',template)
        self.assertNotIn('dhcp-relay=',text)

    def test_atomic_save_preserves_previous_file_on_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            config.save(path,profile())
            before = path.read_bytes()
            with patch.object(config.os,'replace',side_effect=OSError('disk full')),self.assertRaises(OSError):
                config.save(path,dict(profile(),lease_minutes=60))
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(Path(directory).iterdir()),[path])
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_blank_input_retries_and_yes_is_case_insensitive(self):
        with patch('builtins.input',side_effect=['','bad','YeS']),redirect_stdout(io.StringIO()) as output:
            self.assertTrue(app.yes('Continue?'))
            self.assertIn('A choice is required',output.getvalue())

    def test_lease_change_requires_confirmation(self):
        for answer,expected in [('no',0),('YES',1)]:
            with patch.object(app,'active',return_value=False),patch.object(config,'load',return_value=profile()), \
                 patch.object(config,'save') as save,patch('builtins.input',side_effect=['60',answer]),redirect_stdout(io.StringIO()):
                app.change_lease()
                self.assertEqual(save.call_count,expected)
                if expected:self.assertEqual(save.call_args.args[1]['lease_minutes'],60)

    def test_status_does_not_present_old_ready_as_current_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)
            (state/'status.json').write_text(json.dumps(dict(pid=100,title='Both components ready',detail='Old report',action='Old action')))
            from subprocess import CompletedProcess
            with patch.object(config,'STATE',state),patch.object(app,'active',return_value=True), \
                 patch.object(app.subprocess,'run',side_effect=[CompletedProcess([],0),CompletedProcess([],0,stdout='200\n')]), \
                 redirect_stdout(io.StringIO()) as output:
                app.show_status()
                self.assertIn('Last report (not current)',output.getvalue())
                self.assertIn('old READY does not apply',output.getvalue())
                self.assertNotIn('Current report:',output.getvalue())

    def test_network_profile_is_local_only_and_scoped_to_adapter(self):
        with patch.object(config,'load',return_value=profile()),patch.object(app,'active',return_value=False), \
             patch.object(network,'command',return_value=''),patch.object(app,'yes',return_value=True), \
             patch.object(app,'run') as run,patch.object(app.subprocess,'run',return_value=Mock(returncode=0)),redirect_stdout(io.StringIO()):
            app.ethernet_profile()
            args = run.call_args.args[0]
            for key,value in [('ipv4.method','link-local'),('ipv4.never-default','yes'),('ipv6.method','link-local'),
                              ('ifname','eth0'),('802-3-ethernet.mac-address','02:00:00:00:00:11')]:
                self.assertEqual(args[args.index(key)+1],value)
            self.assertNotIn('shared',args)
            self.assertNotIn('wlan0',args)


class LinuxNetworkTests(unittest.TestCase):
    def test_wrong_router_even_at_same_private_address_is_rejected(self):
        with patch.object(network,'snapshot',return_value=wifi()),patch.object(network,'router_for',return_value='192.0.2.1'), \
             patch.object(network,'ip_json',return_value=[{'lladdr':'02:00:00:00:00:ff','state':['REACHABLE']}]):
            with self.assertRaisesRegex(ValueError,'hardware address'):network.home_identity(profile())

    def test_missing_neighbor_refreshes_without_requiring_ping_reply(self):
        with patch.object(network,'snapshot',return_value=wifi()),patch.object(network,'router_for',return_value='192.0.2.1'), \
             patch.object(network,'ip_json',side_effect=[[],[{'lladdr':'02:00:00:00:00:01','state':['STALE']}]]), \
             patch.object(network.subprocess,'run',return_value=Mock(returncode=1)) as ping:
            self.assertEqual(network.home_identity(profile())['ip'],'192.0.2.10')
            self.assertIn('wlan0',ping.call_args.args[0])

    def test_snapshot_accepts_linux_names_and_requires_real_link_state(self):
        row = dict(address='02:00:00:00:00:10',flags=['UP','LOWER_UP'],addr_info=[{'family':'inet','local':'169.254.88.1','prefixlen':16}])
        with patch.object(network,'ip_json',return_value=[row]):
            info=network.snapshot('enp2s0')
            self.assertEqual(info['mask'],'255.255.0.0')
            self.assertTrue(info['active'])
        for name in ('lo','../eth0','x'*16,'eth0;reboot'):
            with self.assertRaises(ValueError):network.interface_name(name)

    def test_raw_delivery_uses_network_order_and_interface_binding(self):
        sock=Mock()
        sock.sendto.side_effect=lambda wire,target:len(wire)
        with patch.object(network.socket,'socket',return_value=sock),patch.object(network.socket,'if_nametoindex',return_value=7):
            delivery=network.RawDelivery('eth0')
            delivery.send(b'hello',socket.inet_aton('192.0.2.1'))
        wire=sock.sendto.call_args.args[0]
        self.assertEqual(struct.unpack_from('!H',wire,2)[0],len(wire))
        self.assertEqual(forwarder.checksum(wire[:20]),0)
        self.assertIn(call(socket.SOL_SOCKET,getattr(socket,'SO_BINDTODEVICE',25),b'eth0\0'),sock.setsockopt.call_args_list)
        self.assertNotIn(call(socket.IPPROTO_IP,25,7),sock.setsockopt.call_args_list)

    def test_delivery_self_test_rejects_wrong_interface(self):
        delivery=object.__new__(network.RawDelivery)
        delivery.interface,delivery.index='eth0',7
        receiver=Mock()
        receiver.__enter__=Mock(return_value=receiver)
        receiver.__exit__=Mock(return_value=None)
        receiver.getsockname.return_value=('',12345)
        receiver.recvmsg.return_value=(b'DHCP-bridge-delivery-check:'+b'a'*16,[(socket.IPPROTO_IP,8,struct.pack('=I4s4s',99,b'\0'*4,b'\0'*4))],0,('',0))
        with patch.object(network.socket,'socket',return_value=receiver),patch.object(network.secrets,'token_bytes',return_value=b'a'*16),patch.object(delivery,'send'):
            with self.assertRaisesRegex(RuntimeError,'interface check failed'):delivery.self_test('169.254.88.1')

    def test_systemd_cleanup_and_installer_do_not_auto_start(self):
        root=Path(__file__).resolve().parents[1]
        unit=(root/'linux/keep-your-e3200.service').read_text()
        for value in ('KillMode=control-group','Restart=on-failure','ProtectSystem=strict','AF_PACKET','AF_NETLINK'):
            self.assertIn(value,unit)
        installer=(root/'linux/install.sh').read_text()
        self.assertNotIn('systemctl enable',installer)
        self.assertNotIn('systemctl start',installer)


if __name__=='__main__':unittest.main()

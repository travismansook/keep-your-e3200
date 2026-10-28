import importlib.util
from pathlib import Path
import socket
import struct
import unittest

path = Path(__file__).resolve().parents[1] / 'src/forwarder.py'
spec = importlib.util.spec_from_file_location('bridge', path)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
SERVER = socket.inet_aton('192.168.1.1')
EXTENDER = bytes.fromhex('020000000002')
CLIENT = bytes.fromhex('020000000010')
OTHER = bytes.fromhex('020000000017')
WIFI = bytes.fromhex('020000000012')


def message(kind=1, mac=CLIENT, xid=17, ciaddr=b.ZERO, server=None, extra=()):
    body = bytearray(240)
    body[0:4] = bytes((2 if kind in (2, 5, 6) else 1, 1, 6, 0))
    struct.pack_into('!I', body, 4, xid)
    body[12:16] = ciaddr
    body[16:20] = socket.inet_aton('192.168.1.6') if body[0] == 2 else b.ZERO
    body[28:34] = mac
    body[236:240] = b.COOKIE
    options = [(53, bytes((kind,))), (61, b'\x01' + mac), (12, b'offline-test')]
    if server is not None:
        options.append((54, server))
    options.extend(extra)
    for code, value in options:
        body.extend(bytes((code, len(value))) + value)
    body.append(255)
    body.extend(b'\0' * max(0, 300 - len(body)))
    return bytes(body)


def packet(payload, response=False, source=None):
    parsed = b.parse_dhcp(payload)
    mac = bytes.fromhex('020000000001') if response else parsed['mac']
    wire = b.udp_ip(payload, source or (SERVER if response else b.ZERO),
                    b.BROADCAST, 67 if response else 68, 68 if response else 67)
    return b.parse_frame(b'\xff' * 6 + mac + b'\x08\x00' + wire)


class BridgeTests(unittest.TestCase):
    def test_handshake_uses_real_router_and_preserves_identity(self):
        g = b.Gate(SERVER, EXTENDER)
        original = message()
        parsed, forwarded, converted = g.request(packet(original), 0)
        self.assertFalse(converted)
        f = b.parse_dhcp(forwarded)
        self.assertEqual((f['mac'], f['xid'], f['values'][61]),
                         (CLIENT, 17, b.parse_dhcp(original)['values'][61]))
        self.assertEqual(struct.unpack_from('!H', forwarded, 10)[0], 0x8000)
        offer = message(2, server=SERVER)
        self.assertEqual(g.reply(packet(offer, True), .1)[1], offer)
        request = message(3, server=SERVER, extra=[(50, socket.inet_aton('192.168.1.6'))])
        self.assertIsNotNone(g.request(packet(request), .2))
        ack = message(5, server=SERVER)
        self.assertEqual(g.reply(packet(ack, True), .3)[1], ack)

    def test_new_client_needs_no_mapping(self):
        self.assertIsNotNone(b.Gate(SERVER, EXTENDER).request(packet(message(mac=OTHER)), 0))

    def test_extender_is_never_forwarded(self):
        self.assertIsNone(b.Gate(SERVER, EXTENDER).request(packet(message(mac=EXTENDER)), 0))
        for vendor in b.DETECTOR_CLASSES:
            alternate_port = bytes.fromhex('020000000003')
            self.assertIsNone(b.Gate(SERVER, EXTENDER).request(
                packet(message(mac=alternate_port, extra=[(60, vendor)])), 0))

    def test_wrong_server_and_unsolicited_replies_rejected(self):
        g = b.Gate(SERVER, EXTENDER)
        ack = message(5, server=SERVER)
        self.assertIsNone(g.reply(packet(ack, True), 0))
        g.request(packet(message()), .1)
        wrong = socket.inet_aton('192.168.1.8')
        self.assertIsNone(g.reply(packet(message(5, server=wrong), True), .2))
        self.assertIsNone(g.reply(packet(ack, True, wrong), .2))
        self.assertIsNone(g.reply(packet(message(5, xid=18, server=SERVER), True), .2))
        self.assertIsNone(g.reply(packet(message(5, mac=OTHER, server=SERVER), True), .2))

    def test_expiry_and_duplicate_suppression(self):
        g = b.Gate(SERVER, EXTENDER)
        req = packet(message())
        self.assertIsNotNone(g.request(req, 0))
        self.assertIsNone(g.request(req, .1))
        ack = packet(message(5, server=SERVER), True)
        self.assertIsNotNone(g.reply(ack, .2))
        self.assertIsNone(g.reply(ack, .3))
        self.assertIsNone(g.reply(ack, 181))

    def test_renewal_preserves_ip_id_and_xid_in_broadcast_form(self):
        address = socket.inet_aton('192.168.1.6')
        original = message(3, ciaddr=address, server=SERVER)
        parsed, body, converted = b.prepare_request(original, SERVER, EXTENDER)
        forward = b.parse_dhcp(body)
        self.assertTrue(converted)
        self.assertEqual(forward['ciaddr'], b.ZERO)
        self.assertEqual(forward['values'][50], address)
        self.assertNotIn(54, forward['values'])
        self.assertEqual(forward['values'][61], parsed['values'][61])
        self.assertEqual(forward['xid'], parsed['xid'])

    def test_selected_other_server_not_hijacked(self):
        self.assertIsNone(b.prepare_request(message(3, server=socket.inet_aton('192.168.1.249')), SERVER, EXTENDER))

    def test_malformed_and_relayed_inputs_rejected(self):
        for payload in (b'', message()[:239], message()[:240] + b'\x35\xff\x01', message() * 6):
            self.assertIsNone(b.parse_dhcp(payload))
        payload = bytearray(message())
        payload[24:28] = SERVER
        self.assertIsNone(b.prepare_request(bytes(payload), SERVER, EXTENDER))
        payload = bytearray(message())
        payload[1] = 2
        self.assertIsNone(b.parse_dhcp(payload))

    def test_packet_checksums_and_fragment_guard(self):
        payload = message()
        wire = b.udp_ip(payload, b.ZERO, b.BROADCAST, 68, 67)
        self.assertEqual(b.checksum(wire[:20]), 0)
        pseudo = b.ZERO + b.BROADCAST + struct.pack('!BBH', 0, 17, len(wire) - 20)
        self.assertEqual(b.checksum(pseudo + wire[20:]), 0)
        frame = b'\xff' * 6 + CLIENT + b'\x08\x00' + wire
        self.assertEqual(b.parse_frame(frame)['payload'], payload)
        fragmented = bytearray(frame)
        struct.pack_into('!H', fragmented, 20, 0x2000)
        self.assertIsNone(b.parse_frame(fragmented))
        self.assertIsNone(b.parse_frame(frame[:-1]))

    def test_vlan_and_client_mac_validation(self):
        p = message()
        frame = b'\xff' * 6 + CLIENT + b'\x81\x00\x00\x01\x08\x00' + b.udp_ip(p, b.ZERO, b.BROADCAST, 68, 67)
        self.assertEqual(b.parse_frame(frame)['payload'], p)
        received = packet(p)
        received['srcmac'] = OTHER
        self.assertIsNone(b.Gate(SERVER, EXTENDER).request(received, 0))


if __name__ == '__main__':
    unittest.main()

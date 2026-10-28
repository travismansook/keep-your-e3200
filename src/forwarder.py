#!/usr/bin/env python3
"""Bounded DHCP broadcast proxy. No address allocator or interface changes.

Requests must first be observed on the client Ethernet. Only matching replies
from the specified real router may be forwarded. The E3200 is excluded.
"""
import argparse
import collections
import ctypes as C
import ctypes.util
import fcntl
import hashlib
import ipaddress
import os
import re
import secrets
import select
import signal
import socket
import struct
import subprocess
import sys
import time

COOKIE = b'\x63\x82\x53\x63'
BROADCAST = b'\xff' * 4
ZERO = b'\0' * 4
DETECTOR_CLASSES = (b'Mesh WLAN DHCP Detect', b'Verizon BHRx1 DHCP Detect')
NAMES = {1: 'DISCOVER', 2: 'OFFER', 3: 'REQUEST', 4: 'DECLINE',
         5: 'ACK', 6: 'NAK', 7: 'RELEASE', 8: 'INFORM'}
IP_BOUND_IF = 25
IP_RECVIF = 20


def log(message):
    print(time.strftime('%Y-%m-%d %H:%M:%S') + ' ' + message, flush=True)


def checksum(data):
    if len(data) % 2:
        data += b'\0'
    value = sum(struct.unpack('!%dH' % (len(data) // 2), data))
    while value >> 16:
        value = (value & 65535) + (value >> 16)
    return (~value) & 65535


def udp_ip(payload, source, dest, sport, dport, ident=0):
    length = 8 + len(payload)
    udp = struct.pack('!HHHH', sport, dport, length, 0) + payload
    pseudo = source + dest + struct.pack('!BBH', 0, 17, length)
    udp = udp[:6] + struct.pack('!H', checksum(pseudo + udp) or 65535) + udp[8:]
    header = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + length,
                         ident & 65535, 0, 64, 17, 0, source, dest)
    header = header[:10] + struct.pack('!H', checksum(header)) + header[12:]
    return header + udp


def parse_frame(frame):
    if len(frame) < 14:
        return None
    offset, proto = 14, struct.unpack_from('!H', frame, 12)[0]
    for _ in range(2):
        if proto not in (0x8100, 0x88a8):
            break
        if len(frame) < offset + 4:
            return None
        proto = struct.unpack_from('!H', frame, offset + 2)[0]
        offset += 4
    if proto != 0x0800 or len(frame) < offset + 20:
        return None
    ip = frame[offset:]
    ihl = (ip[0] & 15) * 4
    total = struct.unpack_from('!H', ip, 2)[0]
    if (ip[0] >> 4 != 4 or ihl < 20 or total < ihl + 8
            or total > len(ip) or ip[9] != 17
            or struct.unpack_from('!H', ip, 6)[0] & 0x3fff):
        return None
    sport, dport, length = struct.unpack_from('!HHH', ip, ihl)
    if length < 8 or ihl + length > total:
        return None
    payload = bytes(ip[ihl + 8:ihl + length])
    return dict(srcmac=frame[6:12], src=ip[12:16], dst=ip[16:20],
                sport=sport, dport=dport, payload=payload)


def parse_dhcp(payload):
    if (len(payload) < 241 or len(payload) > 1472 or payload[1:3] != b'\x01\x06'
            or payload[236:240] != COOKIE or payload[3] != 0):
        return None
    options, pos, ended = [], 240, False
    while pos < len(payload):
        code = payload[pos]
        pos += 1
        if code == 255:
            ended = True
            break
        if code == 0:
            continue
        if pos >= len(payload):
            return None
        size = payload[pos]
        pos += 1
        if pos + size > len(payload):
            return None
        options.append((code, bytes(payload[pos:pos + size])))
        pos += size
    if not ended:
        return None
    values = dict(options)
    msg = values.get(53, b'')
    if len(msg) != 1 or msg[0] not in NAMES:
        return None
    return dict(op=payload[0], msg=msg[0], xid=struct.unpack_from('!I', payload, 4)[0],
                mac=bytes(payload[28:34]), ciaddr=bytes(payload[12:16]),
                giaddr=bytes(payload[24:28]), options=options, values=values,
                key=(bytes(payload[4:8]), bytes(payload[28:34])))


def prepare_request(payload, server, extender):
    parsed = parse_dhcp(payload)
    if (not parsed or parsed['op'] != 1 or parsed['mac'] == extender
            or parsed['giaddr'] != ZERO or parsed['msg'] not in (1, 3, 4, 7, 8)):
        return None
    if parsed['values'].get(60) in DETECTOR_CLASSES:
        return None
    selected = parsed['values'].get(54)
    if selected is not None and selected != server:
        return None
    body = bytearray(payload[:240])
    struct.pack_into('!H', body, 10, struct.unpack_from('!H', body, 10)[0] | 0x8000)
    options = parsed['options']
    converted = parsed['msg'] == 3 and parsed['ciaddr'] != ZERO
    if converted:
        # INIT-REBOOT form preserves identity/XID and asks the same server to
        # confirm the current lease, but permits a broadcast acknowledgement.
        body[12:16] = ZERO
        options = [(code, value) for code, value in options if code not in (50, 54)]
        options.append((50, parsed['ciaddr']))
    for code, value in options:
        body.extend(bytes((code, len(value))) + value)
    body.append(255)
    if len(body) > 1472:
        return None
    if len(body) < 300:
        body.extend(b'\0' * (300 - len(body)))
    return parsed, bytes(body), converted


class Gate:
    def __init__(self, server, extender):
        self.server = server
        self.extender = extender
        self.pending = collections.OrderedDict()
        self.requests = {}
        self.replies = {}
        self.times = collections.deque()

    def expire(self, now):
        for key, until in list(self.pending.items()):
            if until < now:
                del self.pending[key]
        for cache in (self.requests, self.replies):
            for key, last in list(cache.items()):
                if now - last > 180:
                    del cache[key]
        while self.times and now - self.times[0] > 1:
            self.times.popleft()

    def request(self, packet, now):
        self.expire(now)
        if packet['sport'] != 68 or packet['dport'] != 67:
            return None
        prepared = prepare_request(packet['payload'], self.server, self.extender)
        if not prepared:
            return None
        parsed, body, converted = prepared
        if packet['srcmac'] != parsed['mac']:
            return None
        digest = hashlib.sha256(packet['payload']).digest()
        if now - self.requests.get(digest, -1000) < .4 or len(self.times) >= 32:
            return None
        self.requests[digest] = now
        self.times.append(now)
        self.pending[parsed['key']] = now + 180
        while len(self.pending) > 1024:
            self.pending.popitem(last=False)
        return parsed, body, converted

    def reply(self, packet, now):
        self.expire(now)
        parsed = parse_dhcp(packet['payload'])
        if (packet['sport'] != 67 or packet['dport'] != 68
                or packet['src'] != self.server or not parsed
                or parsed['op'] != 2 or parsed['msg'] not in (2, 5, 6)
                or parsed['mac'] == self.extender
                or parsed['values'].get(54) != self.server
                or parsed['key'] not in self.pending):
            return None
        digest = hashlib.sha256(packet['payload']).digest()
        if now - self.replies.get(digest, -1000) < .4:
            return None
        self.replies[digest] = now
        return parsed, packet['payload']


class Header(C.Structure):
    _fields_ = [('sec', C.c_long), ('usec', C.c_long),
                ('caplen', C.c_uint32), ('length', C.c_uint32)]


class Program(C.Structure):
    _fields_ = [('length', C.c_uint), ('instructions', C.c_void_p)]


def pcap_library():
    lib = C.CDLL(ctypes.util.find_library('pcap') or '/usr/lib/libpcap.A.dylib')
    signatures = {
        'pcap_create': (C.c_void_p, [C.c_char_p, C.c_char_p]),
        'pcap_open_dead': (C.c_void_p, [C.c_int, C.c_int]),
        'pcap_activate': (C.c_int, [C.c_void_p]),
        'pcap_set_snaplen': (C.c_int, [C.c_void_p, C.c_int]),
        'pcap_set_promisc': (C.c_int, [C.c_void_p, C.c_int]),
        'pcap_set_timeout': (C.c_int, [C.c_void_p, C.c_int]),
        'pcap_set_immediate_mode': (C.c_int, [C.c_void_p, C.c_int]),
        'pcap_setnonblock': (C.c_int, [C.c_void_p, C.c_int, C.c_char_p]),
        'pcap_datalink': (C.c_int, [C.c_void_p]),
        'pcap_compile': (C.c_int, [C.c_void_p, C.POINTER(Program), C.c_char_p, C.c_int, C.c_uint32]),
        'pcap_setfilter': (C.c_int, [C.c_void_p, C.POINTER(Program)]),
        'pcap_freecode': (None, [C.POINTER(Program)]),
        'pcap_get_selectable_fd': (C.c_int, [C.c_void_p]),
        'pcap_next_ex': (C.c_int, [C.c_void_p, C.POINTER(C.POINTER(Header)), C.POINTER(C.POINTER(C.c_ubyte))]),
        'pcap_inject': (C.c_ssize_t, [C.c_void_p, C.c_void_p, C.c_size_t]),
        'pcap_geterr': (C.c_char_p, [C.c_void_p]),
        'pcap_close': (None, [C.c_void_p]),
    }
    for name, (result, args) in signatures.items():
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
    return lib


class Capture:
    def __init__(self, lib, interface, expression):
        self.lib, self.handle = lib, None
        err = C.create_string_buffer(256)
        handle = lib.pcap_create(interface.encode(), err)
        if not handle:
            raise RuntimeError(err.value.decode())
        self.handle = handle
        try:
            for name, value in [('pcap_set_snaplen', 4096), ('pcap_set_promisc', 0),
                                ('pcap_set_timeout', 50), ('pcap_set_immediate_mode', 1)]:
                if getattr(lib, name)(handle, value) != 0:
                    raise RuntimeError(name + ' failed')
            if lib.pcap_activate(handle) < 0 or lib.pcap_datalink(handle) != 1:
                raise RuntimeError('Ethernet-format capture is unavailable on ' + interface)
            program = Program()
            if lib.pcap_compile(handle, C.byref(program), expression.encode(), 1, 0xffffffff) != 0:
                raise RuntimeError(lib.pcap_geterr(handle).decode())
            try:
                if lib.pcap_setfilter(handle, C.byref(program)) != 0:
                    raise RuntimeError('Could not set capture filter')
            finally:
                lib.pcap_freecode(C.byref(program))
            if lib.pcap_setnonblock(handle, 1, err) != 0:
                raise RuntimeError(err.value.decode())
            self.fd = lib.pcap_get_selectable_fd(handle)
            if self.fd < 0:
                raise RuntimeError('Capture descriptor is unavailable')
        except BaseException:
            self.close()
            raise

    def packets(self):
        for _ in range(128):
            header, data = C.POINTER(Header)(), C.POINTER(C.c_ubyte)()
            result = self.lib.pcap_next_ex(self.handle, C.byref(header), C.byref(data))
            if result == 0:
                return
            if result != 1:
                raise RuntimeError('Capture ended or interface disconnected')
            if header.contents.caplen <= 4096:
                yield C.string_at(data, header.contents.caplen)

    def inject(self, frame):
        buf = C.create_string_buffer(frame)
        if self.lib.pcap_inject(self.handle, buf, len(frame)) != len(frame):
            raise RuntimeError('Wi-Fi transmission failed: ' + self.lib.pcap_geterr(self.handle).decode())

    def close(self):
        if self.handle:
            self.lib.pcap_close(self.handle)
            self.handle = None


def interface_info(name):
    if not re.fullmatch(r'en[0-9]+', name):
        raise ValueError('Unsupported interface name')
    text = subprocess.check_output(['/sbin/ifconfig', name], text=True)
    mac = re.search(r'\bether ([0-9a-f:]{17})', text)
    address = re.search(r'\binet ([0-9.]+)', text)
    if not mac or 'status: active' not in text:
        raise RuntimeError('Interface is not active: ' + name)
    return bytes.fromhex(mac.group(1).replace(':', '')), address.group(1) if address else None


class RawDelivery:
    def __init__(self, interface):
        self.index = socket.if_nametoindex(interface)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        self.sock.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF, self.index)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def send(self, payload, source, dest=BROADCAST, sport=67, dport=68):
        wire = bytearray(udp_ip(payload, source, dest, sport, dport, secrets.randbits(16)))
        # Darwin raw IPv4 expects ip_len and ip_off in host order. The kernel
        # fills the IPv4 checksum; the UDP checksum above is already complete.
        struct.pack_into('=H', wire, 2, len(wire))
        struct.pack_into('=H', wire, 6, 0)
        wire[10:12] = b'\0\0'
        sent = self.sock.sendto(wire, (socket.inet_ntoa(dest), 0))
        if sent != len(wire):
            raise RuntimeError('Incomplete Ethernet delivery')

    def self_test(self, own_ip):
        # One small generic UDP broadcast, NOT DHCP. Verify local delivery and
        # interface metadata before forwarding any real DHCP messages.
        if not own_ip:
            raise RuntimeError('Wait for an Ethernet address, including self-assigned, then retry')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF, self.index)
            receiver.setsockopt(socket.IPPROTO_IP, IP_RECVIF, 1)
            receiver.bind(('', 0))
            receiver.settimeout(1.5)
            nonce = b'DHCP-bridge-delivery-check:' + secrets.token_bytes(16)
            self.send(nonce, socket.inet_aton(own_ip), dport=receiver.getsockname()[1], sport=49153)
            data, controls, _, _ = receiver.recvmsg(512, 512)
            indices = [struct.unpack_from('=H', value, 2)[0]
                       for level, kind, value in controls
                       if level == socket.IPPROTO_IP and kind == IP_RECVIF and len(value) >= 4]
            if data != nonce or self.index not in indices:
                raise RuntimeError('Local Ethernet delivery/interface check failed')
        log('SELFTEST PASS: Ethernet delivery reaches local UDP with the correct interface')

    def close(self):
        self.sock.close()


def filters(server):
    return ('udp src port 68 and udp dst port 67',
            'udp src port 67 and udp dst port 68 and src host ' + server)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ethernet')
    parser.add_argument('--wifi')
    parser.add_argument('--server', default='192.168.1.1')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--extender-mac')
    parser.add_argument('--uid', type=int, required=False)
    parser.add_argument('--gid', type=int, required=False)
    parser.add_argument('--lock-file')
    args = parser.parse_args()
    server = ipaddress.IPv4Address(args.server).packed
    lib = pcap_library()
    expressions = filters(args.server)
    if args.check_only:
        dead = lib.pcap_open_dead(1, 4096)
        if not dead:
            raise RuntimeError('Could not open offline capture compiler')
        try:
            for expression in expressions:
                program = Program()
                if lib.pcap_compile(dead, C.byref(program), expression.encode(), 1, 0xffffffff) != 0:
                    raise RuntimeError('Capture filter failed offline validation')
                lib.pcap_freecode(C.byref(program))
        finally:
            lib.pcap_close(dead)
        print('Offline checks passed. No captures, packet transmissions, or setting changes.', flush=True)
        return
    from configuration import normalize_mac
    if not args.ethernet or not args.wifi or not args.extender_mac:
        raise ValueError('Start the guided helper to select both connections and your extender')
    extender = bytes.fromhex(normalize_mac(args.extender_mac).replace(':', ''))
    if sys.platform != 'darwin' or os.geteuid() != 0:
        raise RuntimeError('Use the guided Mac launcher for the required capture permissions')
    if args.uid is None or args.uid <= 0 or args.gid is None or args.gid < 0:
        raise RuntimeError('A non-root runtime user must be provided')
    if not args.lock_file:
        raise RuntimeError('Use the guided launcher to provide a private lock file')
    lock_fd = os.open(args.lock_file, os.O_RDWR | os.O_NOFOLLOW)
    if os.fstat(lock_fd).st_uid != args.uid:
        os.close(lock_fd)
        raise RuntimeError('Forwarder lock ownership does not match the runtime user')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise RuntimeError('Another copy of this forwarder is already running')
    _, own_ip = interface_info(args.ethernet)
    wifi_mac, _ = interface_info(args.wifi)
    resources = []
    running = [True]
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: running.__setitem__(0, False))
    try:
        delivery = RawDelivery(args.ethernet)
        resources.append(delivery)
        delivery.self_test(own_ip)
        ethernet = Capture(lib, args.ethernet, expressions[0])
        resources.append(ethernet)
        wifi = Capture(lib, args.wifi, expressions[1])
        resources.append(wifi)
        os.setgroups([])
        os.setgid(args.gid)
        os.setuid(args.uid)
        gate = Gate(server, extender)
        log('FORWARDER READY: router assigns ordinary client leases; E3200 is excluded')
        counts = collections.Counter()
        while running[0]:
            readable, _, _ = select.select([ethernet.fd, wifi.fd], [], [], .2)
            for capture in (ethernet, wifi):
                if capture.fd not in readable:
                    continue
                for frame in capture.packets():
                    packet = parse_frame(frame)
                    if packet is None:
                        continue
                    now = time.monotonic()
                    if capture is ethernet:
                        request = gate.request(packet, now)
                        if request:
                            parsed, payload, converted = request
                            source = ZERO if parsed['msg'] in (1, 3, 4) else parsed['ciaddr']
                            outgoing = b'\xff' * 6 + wifi_mac + b'\x08\x00' + udp_ip(payload, source, BROADCAST, 68, 67)
                            wifi.inject(outgoing)
                            counts['requests'] += 1
                            log('REQUEST %s client %s xid %08x%s' %
                                (NAMES[parsed['msg']], parsed['mac'].hex(':'), parsed['xid'],
                                 ' renewal-in-broadcast-form' if converted else ''))
                    else:
                        reply = gate.reply(packet, now)
                        if reply:
                            parsed, payload = reply
                            delivery.send(payload, server)
                            counts['replies'] += 1
                            log('REPLY %s client %s xid %08x offered %s' %
                                (NAMES[parsed['msg']], parsed['mac'].hex(':'), parsed['xid'],
                                 socket.inet_ntoa(payload[16:20])))
        log('STOPPED: requests=%d router-replies=%d' % (counts['requests'], counts['replies']))
    finally:
        for resource in reversed(resources):
            resource.close()
        os.close(lock_fd)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        log('STOPPED WITH ERROR: ' + str(exc))
        sys.exit(1)

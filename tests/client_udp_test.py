#!/usr/bin/env python3
"""Exercise the real Linux client in a fresh network namespace, never the stand.

Run: sudo unshare --net python3 client_udp_test.py BINARY OUTPUT_DIRECTORY
The caller builds BINARY with ASan/UBSan. Malformed input must be logged and discarded without stopping the client.
A valid frame in each direction must still pass through the same process.
"""
import json
import os
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import time


def main():
    binary, destination = sys.argv[1:]
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    # Refuse a namespace with any connection to hardware.
    links = json.loads(subprocess.check_output(['ip', '-j', 'link']))
    assert {x['ifname'] for x in links} == {'lo'}, 'requires fresh unshare --net'
    subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
    subprocess.run(['ip', 'link', 'add', 'qcan0', 'type', 'vcan'], check=True)
    subprocess.run(['ip', 'link', 'set', 'qcan0', 'up'], check=True)
    subprocess.run(['ip', 'link', 'add', 'qcan1', 'type', 'vcan'], check=True)
    subprocess.run(['ip', 'link', 'set', 'qcan1', 'up'], check=True)
    results = []
    valid_lengths = list(range(9)) + [12, 16, 20, 24, 32, 48, 64]
    packets = [(f'valid-{n}', bytes([n + 5]) + struct.pack('<I', 0x1234567)
                + bytes(range(n)), True) for n in valid_lengths]
    valid_512_records = ([(0x1234500 + n, bytes([n]) * 64) for n in range(7)]
                         + [(0x1234567, bytes(range(24)))])
    valid_512 = b''.join(bytes([len(data) + 5]) + struct.pack('<I', can_id) + data
                         for can_id, data in valid_512_records)
    invalid_513_records = ([(0x1234500 + n, bytes([n]) * 64) for n in range(7)]
                           + [(0x1234567, bytes(range(20))), (0x1234568, b'')])
    invalid_513 = b''.join(bytes([len(data) + 5]) + struct.pack('<I', can_id) + data
                           for can_id, data in invalid_513_records)
    assert len(valid_512) == 512
    assert len(invalid_513) == 513
    packets += [('valid-512', valid_512, True), ('invalid-513', invalid_513, False)]
    packets += [('heartbeat', b'EHB1', True)]
    packets += [(f'oversize-{n}', bytes([n]) + struct.pack('<I', 0x1234567)
                 + bytes(n - 5), False) for n in [70, 71, 128, 255]]
    packets += [('empty', b'', False),
                ('noncanonical-payload-9', b'\x0e' + struct.pack('<I', 0x1234567) + bytes(9), False),
                ('noncanonical-payload-11', b'\x10' + struct.pack('<I', 0x1234567) + bytes(11), False),
                ('valid-prefix-malformed-tail', b'\x05' + struct.pack('<I', 0x1234567) + b'\x00', False),
                ('datagram-too-large', bytes(9000), False),
                ('network-outage', b'', False),
                ('classic-can', b'', False),
                ('unknown-source', b'', False),
                ('short-header', b'\x05\x00', False),
                ('zero-length', bytes(5), False),
                ('truncated', b'\x45' + bytes(10), False),
                ('disabled-bus', b'\x05' + struct.pack('<I', 1 << 29), False),
                ('invalid-bus', b'\x05' + struct.pack('<I', 7 << 29), False),
                ('classic-mode-rejects-fd', b'\x11' + struct.pack('<I', 0x1234567) + bytes(12), False),
                ('async-can-error', b'', False)]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, \
            socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as can, \
            socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as recovery_can:
        udp.bind(('127.0.0.2', 1555))
        can.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FD_FRAMES, 1)
        can.bind(('qcan0',))
        recovery_can.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FD_FRAMES, 1)
        recovery_can.bind(('qcan1',))
        for name, payload, valid in packets:
            while select.select([can], [], [], 0)[0]:
                can.recv(72)
            while select.select([recovery_can], [], [], 0)[0]:
                recovery_can.recv(72)
            with (out / (name + '.log')).open('w+') as log:
                env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:abort_on_error=1',
                           UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
                command = [binary, '--host-ip', '127.0.0.1', '--board', 'test',
                           '--device-ip', '127.0.0.2', '--period', '0', '--bus0', 'qcan0']
                if name == 'classic-mode-rejects-fd':
                    command.append('--classic-bus0')
                elif name == 'async-can-error':
                    command.extend(['--bus1', 'qcan1'])
                proc = subprocess.Popen(command, stdout=log, stderr=log, env=env)
                started_pid = proc.pid
                try:
                    # Wait for the actual UDP socket instead of a guessed startup delay.
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        if proc.poll() is not None:
                            raise RuntimeError(f'{name}: client exited at startup')
                        if ':0614 ' in Path('/proc/net/udp').read_text():
                            break
                        time.sleep(.01)
                    else:
                        raise TimeoutError('client did not bind UDP 1556')
                    if name == 'network-outage':
                        subprocess.run(['ip', 'route', 'add', 'unreachable', '127.0.0.2/32', 'table', 'local'], check=True)
                        can.send(struct.pack('=IBBBB64s', 0x81234567, 8, 1, 0, 0, b'expired!'))
                        time.sleep(.05)
                        subprocess.run(['ip', 'route', 'del', 'unreachable', '127.0.0.2/32', 'table', 'local'], check=True)
                    elif name == 'classic-can':
                        can.send(struct.pack('=IBBBB8s', 0x81234567, 8, 0, 0, 0, b'classic!'))
                        assert select.select([udp], [], [], 1)[0], 'classic frame not forwarded'
                        assert udp.recv(8192) == bytes([13]) + struct.pack('<I', 0x1234567) + b'classic!'
                        udp.sendto(b'', ('127.0.0.1', 1556))
                    elif name == 'unknown-source':
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as unknown:
                            unknown.bind(('127.0.0.3', 1555))
                            unknown.sendto(b'\x05' + bytes(4), ('127.0.0.1', 1556))
                    elif name == 'async-can-error':
                        subprocess.run(['ip', 'link', 'del', 'qcan0'], check=True)
                        deadline = time.monotonic() + 1
                        while time.monotonic() < deadline:
                            if proc.poll() is not None:
                                break
                            if 'SO_ERROR=' in Path(log.name).read_text():
                                break
                            time.sleep(.01)
                        else:
                            raise TimeoutError('async CAN error did not reach epoll')
                    else:
                        udp.sendto(payload, ('127.0.0.1', 1556))
                    if name == 'async-can-error':
                        probe = bytes([13]) + struct.pack('<I', (1 << 29) | 0x1234567) + b'continue'
                        udp.sendto(probe, ('127.0.0.1', 1556))
                        ready = select.select([recovery_can], [], [], 1)[0]
                        frame = recovery_can.recv(72) if ready else b''
                        incoming_ok = (len(frame) == 72 and frame[4] == 8
                                       and frame[8:16] == b'continue'
                                       and struct.unpack_from('<I', frame)[0] == 0x81234567)
                        recovery_can.send(struct.pack(
                            '=IBBBB64s', 0x81234567, 8, 1, 0, 0, b'outgoing'))
                        ready = select.select([udp], [], [], 1)[0]
                        response = udp.recv(8192) if ready else b''
                        outgoing_ok = (response == bytes([13])
                                       + struct.pack('<I', (1 << 29) | 0x1234567)
                                       + b'outgoing')
                        same_process = proc.pid == started_pid and proc.poll() is None
                        log.flush()
                        log.seek(0)
                        diagnostic = log.read()
                        passed = (incoming_ok and outgoing_ok and same_process
                                  and 'SO_ERROR=' in diagnostic
                                  and 'AddressSanitizer' not in diagnostic
                                  and 'runtime error:' not in diagnostic)
                    elif name == 'valid-512':
                        passed = True
                        for expected_can_id, expected_payload in valid_512_records:
                            ready = select.select([can], [], [], 1)[0]
                            frame = can.recv(72) if ready else b''
                            passed = (passed and len(frame) == 72
                                      and frame[4] == len(expected_payload)
                                      and frame[8:8 + frame[4]] == expected_payload
                                      and struct.unpack_from('<I', frame)[0]
                                      == (expected_can_id | 0x80000000))
                        passed = (passed and not select.select([can], [], [], .05)[0]
                                  and proc.poll() is None)
                    elif valid and name != 'heartbeat':
                        ready = select.select([can], [], [], 1)[0]
                        frame = can.recv(72) if ready else b''
                        passed = (len(frame) == 72 and frame[4] == len(payload) - 5
                                  and frame[8:8 + frame[4]] == payload[5:]
                                  and struct.unpack_from('<I', frame)[0] == 0x81234567)
                    elif valid:
                        passed = not select.select([can], [], [], .1)[0] and proc.poll() is None
                    else:
                        unexpected = bool(select.select([can], [], [], .05)[0])
                        if unexpected:
                            can.recv(72)
                        probe = bytes([13]) + struct.pack('<I', 0x1234567) + b'continue'
                        board_udp = udp
                        board_udp.sendto(probe, ('127.0.0.1', 1556))
                        ready = select.select([can], [], [], 1)[0]
                        frame = can.recv(72) if ready else b''
                        if name == 'classic-mode-rejects-fd':
                            incoming_ok = (len(frame) == 16 and frame[4] == 8 and frame[5] == 0
                                           and frame[8:16] == b'continue')
                            can.send(struct.pack('=IBBBB64s', 0x81234567, 12, 1, 0, 0, b'not-forwarded'))
                            fd_forwarded = bool(select.select([board_udp], [], [], .1)[0])
                            if fd_forwarded:
                                board_udp.recv(8192)
                            can.send(struct.pack('=IBBBB8s', 0x81234567, 8, 0, 0, 0, b'outgoing'))
                        else:
                            incoming_ok = len(frame) == 72 and frame[8:16] == b'continue'
                            fd_forwarded = False
                            can.send(struct.pack('=IBBBB64s', 0x81234567, 8, 1, 0, 0, b'outgoing'))
                        ready = select.select([board_udp], [], [], 1)[0]
                        response = board_udp.recv(8192) if ready else b''
                        outgoing_ok = (not fd_forwarded and response == bytes([13])
                                       + struct.pack('<I', 0x1234567) + b'outgoing')
                        same_process = proc.pid == started_pid and proc.poll() is None
                        log.flush()
                        log.seek(0)
                        diagnostic = log.read()
                        expected_diagnostic = 'runtime drops='
                        passed = (not unexpected and incoming_ok and outgoing_ok and same_process
                                  and expected_diagnostic in diagnostic
                                  and 'AddressSanitizer' not in diagnostic
                                  and 'runtime error:' not in diagnostic)
                    results.append({'case': name, 'pass': passed, 'pid': started_pid,
                                    'returncode': proc.poll()})
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait(timeout=3)
            (out / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
    return 0 if all(r['pass'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())

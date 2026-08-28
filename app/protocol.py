"""Atlas Copco Open Protocol client.

Supports MIDs 0001, 0003, 0010, 0030, 0040, 0060, 0080, 0270, 9999.

Tolerant of:
  * multi-segment TCP responses (read full length-prefixed frame);
  * the leading `\\x00` separator that ScaniaProtocolAdapter (and others)
    prepend to every frame.

Usage::

    from app.protocol import open_protocol_session, MID40, parse_mid_0040
    raw = open_protocol_session("192.168.188.120", 4545, MID40)
    parsed = parse_mid_0040(raw.decode(errors="replace"))
"""
from __future__ import annotations

import socket
import time
from typing import Callable, Optional

# Open Protocol MIDs (20-byte payload + NUL terminator).
MID1    = '00200001001000000000'   # 0001 - Communication start
MID3    = '00200003001000000000'   # 0003 - Communication stop
MID10   = '00200010001000000000'   # 0010 - Parameter set ID list
MID30   = '00200030001000000000'   # 0030 - Job list
MID40   = '00200040002000000000'   # 0040 - Tool data
MID60   = '00200060001000000000'   # 0060 - Last tightening result data
MID80   = '00200080001000000000'   # 0080 - Open Protocol version
MID270  = '00200270001000000000'   # 0270 - Reboot controller
MID9999 = '00209999001000000000'   # 9999 - Keep alive

TIMEOUT_S: float = 3.0


# ---------------------------------------------------------------------------
# Socket plumbing
# ---------------------------------------------------------------------------
class ProtocolError(ConnectionError):
    """Raised when the Open Protocol frame is malformed."""


def _recv_exact(s: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from socket, looping until done or timeout."""
    buf = b''
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ProtocolError(
                f'Connection closed after {len(buf)} of {n} bytes')
        buf += chunk
    return buf


def _recv_oped(s: socket.socket) -> bytes:
    """Read a full Open Protocol frame using its 4-digit ASCII length header.

    Skips any leading `\\x00` separator (used by ScaniaProtocolAdapter),
    then reads exactly the number of bytes the controller declared.
    """
    # 1. Skip leading NUL separators.
    first = _recv_exact(s, 1)
    while first == b'\x00':
        first = _recv_exact(s, 1)
    # 2. Read remaining 3 bytes of the 4-digit length field.
    rest = _recv_exact(s, 3)
    header = first + rest
    try:
        total = int(header)
    except ValueError:
        raise ProtocolError(f'Invalid Open Protocol length header: {header!r}')
    if total < 4:
        raise ProtocolError(f'Unreasonable length header: {total}')
    # 3. Read body (length field itself is part of total).
    body = _recv_exact(s, total - 4)
    return header + body


def open_protocol_session(host: str, port: int,
                          mid_to_send: str,
                          timeout_s: float = TIMEOUT_S,
                          post_wait_s: float = 1.5) -> bytes:
    """Open a fresh socket, send MID 0001 + `mid_to_send`, return the response.

    Socket is closed at the end via `with`.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout_s)
        s.connect((host, port))
        # MID 0001 - required at the start of every session.
        s.sendall((MID1 + chr(0)).encode())
        _recv_oped(s)
        s.sendall((mid_to_send + chr(0)).encode())
        time.sleep(post_wait_s)        # controller needs time to assemble
        return _recv_oped(s)


def with_protocol_session(host: str, port: int,
                          mid_to_send: str,
                          timeout_s: float = TIMEOUT_S,
                          post_wait_s: float = 1.5) -> Callable:
    """Decorator helper for functions that want a one-shot MID fetch.

    Returns the raw response bytes.
    """
    return lambda: open_protocol_session(host, port, mid_to_send,
                                         timeout_s=timeout_s,
                                         post_wait_s=post_wait_s)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
# Field offsets below are best-effort and depend on controller revision.
# Each parser returns None when the response is too short to read safely.

def _s(raw: str, a: int, b: int) -> str:
    v = raw[a:b].strip() if b <= len(raw) else raw[a:].strip()
    return v or '\u2014'


def _n(raw: str, a: int, b: int) -> int:
    v = raw[a:b].strip().lstrip('0') if b <= len(raw) else ''
    return int(v) if v and v.isdigit() else 0


def parse_mid_0010(raw: str) -> dict:
    """Parameter set ID list."""
    if len(raw) < 24:
        return {'count': 0, 'ids': []}
    try:
        count = int(raw[20:24])
    except ValueError:
        return {'count': 0, 'ids': []}
    ids: list[str] = []
    for i in range(count):
        a, b = 24 + i * 4, 28 + i * 4
        if b > len(raw):
            break
        v = raw[a:b].strip()
        if v:
            ids.append(v)
    return {'count': count, 'ids': ids}


def parse_mid_0030(raw: str) -> dict:
    """Job list."""
    if len(raw) < 22:
        return {'count': 0, 'ids': []}
    try:
        count = int(raw[20:22])
    except ValueError:
        return {'count': 0, 'ids': []}
    ids: list[str] = []
    for i in range(count):
        a, b = 22 + i * 2, 24 + i * 2
        if b > len(raw):
            break
        v = raw[a:b].strip()
        if v:
            ids.append(v)
    return {'count': count, 'ids': ids}


def parse_mid_0040(raw: str) -> Optional[dict]:
    """Tool data (MID 0040)."""
    if len(raw) < 80:
        return None
    return {
        'tool_serial'           : _s(raw, 22, 36),
        'total_tightenings'     : _n(raw, 38, 48),
        'last_calibration_date' : _s(raw, 50, 60),
        'controller_serial'     : _s(raw, 71, 81),
        'calibration_value'     : _s(raw, 84, 89),
        'last_service_date'     : _s(raw, 91, 101),
        'tightenings_since_svc' : _n(raw, 113, 122),
        'firmware'              : _s(raw, 137, 156),
    }


def parse_mid_0060(raw: str) -> Optional[dict]:
    """Last tightening result data (MID 0060)."""
    if len(raw) < 80:
        return None
    status_map = {'0': 'Not used', '1': 'OK', '2': 'NOK', '3': 'Aborted'}
    tstatus_map = {'0': 'Low', '1': 'OK', '2': 'High', '3': 'NOK'}
    return {
        'cell_id'         : _s(raw, 20, 24),
        'channel_id'      : _s(raw, 24, 26),
        'job_number'      : _s(raw, 26, 30),
        'tightening'      : status_map.get(_s(raw, 30, 31), _s(raw, 30, 31)),
        'torque_status'   : tstatus_map.get(_s(raw, 31, 32), _s(raw, 31, 32)),
        'angle_status'    : tstatus_map.get(_s(raw, 32, 33), _s(raw, 32, 33)),
        'torque_min'      : _s(raw, 33, 43),
        'torque_target'   : _s(raw, 43, 53),
        'torque_max'      : _s(raw, 53, 63),
        'torque_value'    : _s(raw, 63, 73),
        'angle_min'       : _s(raw, 73, 80),
        'angle_target'    : _s(raw, 80, 87),
        'angle_max'       : _s(raw, 87, 94),
        'angle_value'     : _s(raw, 94, 101),
        'time_stamp'      : _s(raw, 101, 120),
        'batch_status'    : _s(raw, 120, 121),
        'batch_counter'   : _n(raw, 121, 125),
        'tightening_id'   : _s(raw, 125, 135),
    }


def parse_mid_0080(raw: str) -> Optional[dict]:
    """Open Protocol version (MID 0080)."""
    if len(raw) < 23:
        return None
    return {
        'major': raw[20:21],
        'minor': raw[21:22],
        'patch': raw[22:23],
    }


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------
def fetch_tool_data(host: str, port: int) -> dict:
    """Fetch MID 0040 and return parsed tool data. Raises ProtocolError."""
    raw = open_protocol_session(host, port, MID40).decode(errors='replace')
    parsed = parse_mid_0040(raw)
    if parsed is None:
        raise ProtocolError('MID 0040 response too short to parse')
    parsed['raw_response'] = raw
    return parsed


def fetch_last_tightening(host: str, port: int) -> dict:
    """Fetch MID 0060 and return parsed last tightening result."""
    raw = open_protocol_session(host, port, MID60).decode(errors='replace')
    parsed = parse_mid_0060(raw)
    if parsed is None:
        raise ProtocolError('MID 0060 response too short to parse')
    parsed['raw_response'] = raw
    return parsed


def fetch_controller_version(host: str, port: int) -> dict:
    """Fetch MID 0080 protocol version."""
    raw = open_protocol_session(host, port, MID80).decode(errors='replace')
    return parse_mid_0080(raw) or {}


def fetch_parameter_set_ids(host: str, port: int) -> dict:
    """Fetch MID 0010 parameter set ID list."""
    raw = open_protocol_session(host, port, MID10).decode(errors='replace')
    return parse_mid_0010(raw)


def fetch_job_list(host: str, port: int) -> dict:
    """Fetch MID 0030 job list."""
    raw = open_protocol_session(host, port, MID30).decode(errors='replace')
    return parse_mid_0030(raw)


def status_emoji(s: str) -> str:
    """Color emoji for tightening status text."""
    return {
        'OK': '\U0001f7e2', 'NOK': '\U0001f534',
        'Low': '\U0001f7e1', 'High': '\U0001f7e0',
        'Aborted': '\u26aa', 'Not used': '\u26aa',
    }.get(s, '\u2753')

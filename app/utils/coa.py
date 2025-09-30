import socket
import struct
import hashlib

RADIUS_CODE_DISCONNECT_REQUEST = 40
RADIUS_CODE_DISCONNECT_ACK = 41
RADIUS_CODE_DISCONNECT_NAK = 42
RADIUS_CODE_STATUS_SERVER = 12
RADIUS_CODE_ACCESS_ACCEPT = 2
RADIUS_CODE_ACCESS_REJECT = 3


def build_radius_packet(code: int, identifier: int, secret: str, attrs: list):
    """
    Build a valid RADIUS packet.
    attrs: list of (type, value) tuples.
    """
    header = struct.pack("!BBH", code, identifier, 0)
    authenticator = b"\x00" * 16
    packet = header + authenticator

    for attr_type, value in attrs:
        if isinstance(value, str):
            value = value.encode()
        packet += struct.pack("!BB", attr_type, len(value) + 2) + value

    length = len(packet)
    packet = packet[:2] + struct.pack("!H", length) + packet[4:]

    auth = hashlib.md5(packet + secret.encode()).digest()
    packet = packet[:4] + auth + packet[20:]
    return packet


def disconnect_user(username: str, nas_ip: str, secret: str, port: int = 3799, timeout: int = 3):
    """
    Send a Disconnect-Request to NAS (MikroTik).
    Returns True if ACK, False if NAK, raises on timeout.
    """
    attrs = [(1, username)]  # User-Name
    packet = build_radius_packet(RADIUS_CODE_DISCONNECT_REQUEST, 1, secret, attrs)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (nas_ip, port))
        resp, _ = sock.recvfrom(4096)
        code = resp[0]
        if code == RADIUS_CODE_DISCONNECT_ACK:
            return True
        elif code == RADIUS_CODE_DISCONNECT_NAK:
            return False
        else:
            return False
    except socket.timeout:
        raise RuntimeError("Disconnect-Request timeout")
    finally:
        sock.close()


def _send_status_server(nas_ip: str, secret: str, port: int, timeout: int = 3):
    """
    Kirim Status-Server ke port tertentu.
    Return: True jika ada balasan (Accept/Reject), False jika balasan lain, raise kalau timeout.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        pkt = build_radius_packet(RADIUS_CODE_STATUS_SERVER, 1, secret, [(4, nas_ip)])
        sock.sendto(pkt, (nas_ip, port))
        resp, _ = sock.recvfrom(4096)
        code = resp[0]
        if code in (RADIUS_CODE_ACCESS_ACCEPT, RADIUS_CODE_ACCESS_REJECT):
            return True
        return False
    except socket.timeout:
        raise RuntimeError(f"Timeout pada port {port}")
    finally:
        sock.close()


def test_connection_all(nas_ip: str, secret: str, timeout: int = 3):
    """
    Test semua port penting (1812, 1813, 3799).
    Return dict hasil per port.
    """
    results = {}
    for port in (1812, 1813, 3799):
        try:
            ok = _send_status_server(nas_ip, secret, port, timeout=timeout)
            results[port] = "ok" if ok else "unexpected-reply"
        except Exception as e:
            results[port] = f"fail: {e}"
    return results
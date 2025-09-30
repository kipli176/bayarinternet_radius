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


def test_connection(nas_ip: str, secret: str, port: int = 1812, timeout: int = 3):
    """
    Uji koneksi ke NAS:
      1) coba Status-Server (Code=12)
      2) fallback Access-Request dummy
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        # ---------- Status-Server ----------
        packet = build_radius_packet(RADIUS_CODE_STATUS_SERVER, 1, secret, [
            (4, nas_ip)  # NAS-IP-Address
        ])
        sock.sendto(packet, (nas_ip, port))
        resp, _ = sock.recvfrom(4096)
        code = resp[0]
        if code == RADIUS_CODE_ACCESS_ACCEPT:
            return True
        elif code == RADIUS_CODE_ACCESS_REJECT:
            # NAS menolak, tapi artinya koneksi OK
            return True
    except socket.timeout:
        # fallback ke Access-Request
        pass
    finally:
        sock.close()

    # ---------- Fallback Access-Request dummy ----------
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        packet = build_radius_packet(1, 1, secret, [  # 1 = Access-Request
            (1, "__ping__"),  # User-Name
        ])
        sock.sendto(packet, (nas_ip, port))
        resp, _ = sock.recvfrom(4096)
        code = resp[0]
        if code in (RADIUS_CODE_ACCESS_ACCEPT, RADIUS_CODE_ACCESS_REJECT):
            return True
        return False
    except socket.timeout:
        raise RuntimeError("RADIUS test_connection timeout")
    finally:
        sock.close()

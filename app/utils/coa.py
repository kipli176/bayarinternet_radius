import socket
import struct
import hashlib

RADIUS_CODE_DISCONNECT_REQUEST = 40
RADIUS_CODE_DISCONNECT_ACK = 41
RADIUS_CODE_DISCONNECT_NAK = 42

def build_radius_packet(code: int, identifier: int, secret: str, attrs: list):
    """
    Build a valid RADIUS Disconnect-Request packet.
    attrs: list of (type, value) tuples.
    """
    # header awal (panjang masih placeholder)
    header = struct.pack("!BBH", code, identifier, 0)
    authenticator = b"\x00" * 16
    packet = header + authenticator

    # tambahkan atribut
    for attr_type, value in attrs:
        if isinstance(value, str):
            value = value.encode()
        packet += struct.pack("!BB", attr_type, len(value) + 2) + value

    # perbaiki length
    length = len(packet)
    packet = packet[:2] + struct.pack("!H", length) + packet[4:]

    # hitung authenticator: MD5(Code+ID+Length+16x0+Attrs+Secret)
    auth = hashlib.md5(packet + secret.encode()).digest()

    # ganti authenticator dummy dengan MD5
    packet = packet[:4] + auth + packet[20:]
    return packet



def disconnect_user(username: str, nas_ip: str, secret: str, port: int = 3799, timeout: int = 3):
    """
    Send a Disconnect-Request to NAS (MikroTik).
    Returns True if ACK, False if NAK, raises on timeout.
    """
    # Attr 1 = User-Name
    attrs = [(1, username)]
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

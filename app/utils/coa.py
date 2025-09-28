import socket
import struct
import hashlib
import os
import binascii

RADIUS_CODE_DISCONNECT_REQUEST = 40
RADIUS_CODE_DISCONNECT_ACK = 41
RADIUS_CODE_DISCONNECT_NAK = 42

def build_radius_packet(code: int, identifier: int, secret: str, attrs: list):
    # random 16-byte authenticator
    ra = os.urandom(16)

    # header (length=0 placeholder)
    packet = struct.pack("!BBH", code, identifier, 0) + ra

    # append attributes
    for attr_type, value in attrs:
        if isinstance(value, str):
            value = value.encode()
        packet += struct.pack("!BB", attr_type, len(value) + 2) + value

    # set length
    length = len(packet)
    packet = packet[:2] + struct.pack("!H", length) + packet[4:]

    # calculate authenticator properly
    hash_input = packet[:4] + ra + packet[20:] + secret.encode()
    authenticator = hashlib.md5(hash_input).digest()

    # rebuild with real authenticator
    packet = packet[:4] + authenticator + packet[20:]
    return packet

def disconnect_user(username: str, nas_ip: str, secret: str, port: int = 3799, timeout: int = 3):
    identifier = os.urandom(1)[0]
    attrs = [(1, username)]
    packet = build_radius_packet(RADIUS_CODE_DISCONNECT_REQUEST, identifier, secret, attrs)

    print(f"[DEBUG] Sending Disconnect-Request to {nas_ip}:{port}")
    print(f"[DEBUG] Packet HEX: {binascii.hexlify(packet).decode()}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (nas_ip, port))
        resp, _ = sock.recvfrom(4096)
        print(f"[DEBUG] Sending Disconnect-Request for {username} -> {nas_ip}:{port}")
        print(f"[DEBUG] Using secret: {secret}")
        print(f"[DEBUG] Packet HEX: {packet.hex()}")
        print(f"[DEBUG] Response HEX: {binascii.hexlify(resp).decode()}")
        code = resp[0]
        if code == RADIUS_CODE_DISCONNECT_ACK:
            print("[DEBUG] Got Disconnect-ACK ✅")
            return True
        elif code == RADIUS_CODE_DISCONNECT_NAK:
            print("[DEBUG] Got Disconnect-NAK ❌")
            return False
        else:
            print(f"[DEBUG] Unknown RADIUS code {code}")
            return False
        

    except socket.timeout:
        raise RuntimeError("Disconnect-Request timeout")
    finally:
        sock.close()

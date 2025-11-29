# protocol.py
import struct


# ======================================================
# HELPERS
# ======================================================

def encode_string(s: str) -> bytes:
    data = s.encode("utf-8")
    return struct.pack("!H", len(data)) + data


def encode_varint(x: int) -> bytes:
    out = b""
    while True:
        encoded = x % 128
        x //= 128
        if x > 0:
            encoded |= 0x80
        out += struct.pack("!B", encoded)
        if x == 0:
            break
    return out


def recv_all(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Conexiune închisă prematur")
        data += chunk
    return data


# ======================================================
# ENCODER
# ======================================================

class ProtocolEncoder:

    @staticmethod
    def encode_connect(client_id="client", keep_alive=60, username=None, password=None):
        # 1. Variable Header
        # Protocol Name (MQTT) + Version (5)
        vh_base = encode_string("MQTT") + b"\x05"

        # Calculăm Connect Flags
        # Bit 1 = Clean Start (0x02)
        connect_flags = 0x02

        if username is not None:
            connect_flags |= 0x80  # Bit 7 = User Name Flag

        if password is not None:
            connect_flags |= 0x40  # Bit 6 = Password Flag

        # Adăugăm flags și keep alive
        vh_base += struct.pack("!B", connect_flags)
        vh_base += struct.pack("!H", keep_alive)

        # Properties Length (0)
        vh_base += b"\x00"

        # 2. Payload
        # Ordinea OBLIGATORIE: ClientID -> Will -> Username -> Password
        payload = encode_string(client_id)

        if username is not None:
            payload += encode_string(username)

        if password is not None:
            payload += encode_string(password)

        # 3. Asamblare finală
        remaining = len(vh_base) + len(payload)
        return b"\x10" + encode_varint(remaining) + vh_base + payload

    # ------------------ PUBLISH QoS0 ------------------
    @staticmethod
    def encode_publish(topic, message):
        topic_b = encode_string(topic)
        props = b"\x00"
        payload = message.encode()

        vh = topic_b + props
        remaining = len(vh) + len(payload)

        return b"\x30" + encode_varint(remaining) + vh + payload

    # ------------------ PUBLISH QoS1 ------------------
    @staticmethod
    def encode_publish_qos1(topic, message, pid):
        topic_b = encode_string(topic)
        props = b"\x00"
        payload = message.encode()

        vh = topic_b + struct.pack("!H", pid) + props
        remaining = len(vh) + len(payload)

        return b"\x32" + encode_varint(remaining) + vh + payload

    # ------------------ PUBLISH QoS2 ------------------
    @staticmethod
    def encode_publish_qos2(topic, message, pid):
        topic_b = encode_string(topic)
        props = b"\x00"
        payload = message.encode()

        vh = topic_b + struct.pack("!H", pid) + props
        remaining = len(vh) + len(payload)

        return b"\x34" + encode_varint(remaining) + vh + payload

    # ------------------ RESTUL PACHETELOR ------------------
    @staticmethod
    def encode_subscribe(packet_id, topic):
        payload = encode_string(topic) + b"\x00"  # QoS 0
        vh = struct.pack("!H", packet_id) + b"\x00"
        remaining = len(vh) + len(payload)
        return b"\x82" + encode_varint(remaining) + vh + payload

    @staticmethod
    def encode_puback(pid):
        vh = struct.pack("!H", pid) + b"\x00" + b"\x00"  # PacketID + Reason(Success) + PropsLen
        return b"\x40" + encode_varint(len(vh)) + vh

    @staticmethod
    def encode_pubrec(pid):
        vh = struct.pack("!H", pid) + b"\x00" + b"\x00"
        return b"\x50" + encode_varint(len(vh)) + vh

    @staticmethod
    def encode_pubrel(pid):
        vh = struct.pack("!H", pid) + b"\x00" + b"\x00"
        return b"\x62" + encode_varint(len(vh)) + vh

    @staticmethod
    def encode_pubcomp(pid):
        vh = struct.pack("!H", pid) + b"\x00" + b"\x00"
        return b"\x70" + encode_varint(len(vh)) + vh


# ======================================================
# DECODER
# ======================================================

class ProtocolDecoder:

    @staticmethod
    def decode_connack(sock):
        # Citim primul octet (Type + Flags)
        header = recv_all(sock, 1)
        if header[0] != 0x20:
            raise Exception(f"Nu este CONNACK, am primit: {hex(header[0])}")

        # Citim Remaining Length
        rem = recv_all(sock, 1)[0]  # Presupunem < 128 pentru CONNACK simplu
        body = recv_all(sock, rem)

        # Connack Flags (byte 0) si Reason Code (byte 1)
        return body[0], body[1]

    @staticmethod
    def decode_puback_from_bytes(body):
        return int.from_bytes(body[:2], 'big')

    @staticmethod
    def decode_pubrec_from_bytes(body):
        return int.from_bytes(body[:2], 'big')

    @staticmethod
    def decode_pubrel_from_bytes(body):
        return int.from_bytes(body[:2], 'big')

    @staticmethod
    def decode_pubcomp_from_bytes(body):
        return int.from_bytes(body[:2], 'big')
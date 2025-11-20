import struct

# ----------------------------- HELPERS -----------------------------

def encode_string(s: str) -> bytes:
    data = s.encode('utf-8')
    return struct.pack("!H", len(data)) + data #returneaza \length\codificareHexa

#returneaza numarul intreg intr-un format in baza 128
#in fiecare octet primii 7 biti sunt numarul codificat, iar bitul 8 indica daca mai exista octeti dupa el
#codificarea se realizeaza in little endian (numarul real este octet1 + octet2*128 + octet3*128^2+...)
#octetii plecand de la stanga la dreapta
def encode_varint(x: int) -> bytes:
    out = b""
    while True:
        encoded_byte = x % 128
        x //= 128
        if x > 0:
            encoded_byte |= 0x80
        out += struct.pack("!B", encoded_byte)
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

# ----------------------------- CONNECT -----------------------------

def encode_connect(client_id="python_client", keep_alive=60):
    variable_header = encode_string("MQTT") + struct.pack("!B", 5)
    variable_header += struct.pack("!B", 0x02)
    variable_header += struct.pack("!H", keep_alive)
    variable_header += b'\x00'
    payload = encode_string(client_id)
    packet_type = 0x10
    remaining_length = len(variable_header) + len(payload)
    fixed_header = bytes([packet_type]) + encode_varint(remaining_length)
    return fixed_header + variable_header + payload

def decode_connack(sock):
    first_byte = recv_all(sock, 1)
    if first_byte[0] != 0x20:
        raise Exception("Nu am primit CONNACK")
    remaining_length = recv_all(sock, 1)[0] #[0] ca sa fie valorea intreaga, nu codificarea hexa
    body = recv_all(sock, remaining_length)
    return body[0], body[1] #returneaza flags si reason code

# ---------------------------- PUBLISH -----------------------------

def encode_publish(topic, message):
    topic_bytes = encode_string(topic)
    properties = b'\x00'
    payload = message.encode('utf-8')
    variable_header = topic_bytes + properties
    remaining_length = len(variable_header) + len(payload)
    fixed_header = bytes([0x30]) + encode_varint(remaining_length)
    return fixed_header + variable_header + payload

# ---------------------------- SUBSCRIBE -----------------------------

def encode_subscribe(packet_id, topic):
    payload = encode_string(topic) + b'\x00'
    variable_header = struct.pack("!H", packet_id) + b'\x00'
    remaining_length = len(variable_header) + len(payload)
    fixed_header = bytes([0x82]) + encode_varint(remaining_length)
    return fixed_header + variable_header + payload

def decode_suback(sock):
    first = recv_all(sock, 1) #verifica primul octet
    if first[0] != 0x90:
        raise Exception("Nu am primit SUBACK")

    # Decode Remaining Length
    multiplier = 1
    value = 0
    while True:
        encoded_byte = recv_all(sock, 1)[0] #preia un octet
        value += (encoded_byte & 127) * multiplier #primii 7 biti, fara bit-ul care indica daca mai exista octeti
        multiplier *= 128
        if (encoded_byte & 128) == 0: #bit 8 indica terminarea octetilor
            break
    remaining_length = value

    body = recv_all(sock, remaining_length)

    return body

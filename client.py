import socket
import threading
import time
from protocol import encode_connect, decode_connack, encode_publish, encode_subscribe, decode_suback, recv_all

class MQTTClient:
    def __init__(self, host, port, client_id, keep_alive=60):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.keep_alive = keep_alive
        self.sock = None
        self.connected = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.sendall(encode_connect(self.client_id, self.keep_alive))
        _, rc = decode_connack(self.sock)
        if rc != 0:
            raise Exception(f"Conectare eșuată, reason code = {rc}")
        self.connected = True
        threading.Thread(target=self.ping_loop, daemon=True).start()

    def ping_loop(self):
        while self.connected:
            time.sleep(self.keep_alive // 2)
            try:
                self.sock.sendall(b'\xC0\x00')
            except:
                self.connected = False
                break

    def publish(self, topic, message):
        packet = encode_publish(topic, message)
        self.sock.sendall(packet)

    def subscribe(self, topic, packet_id=1):
        packet = encode_subscribe(packet_id, topic)
        self.sock.sendall(packet)
        suback = decode_suback(self.sock)
        return list(suback)

    def loop_receive(self):
        while self.connected:
            first = recv_all(self.sock, 1)
            ptype = first[0] >> 4
            if ptype == 3:
                self._handle_publish()

    def _handle_publish(self):
        multiplier = 1
        remaining = 0
        while True:
            b = recv_all(self.sock, 1)[0]
            remaining += (b & 127) * multiplier
            multiplier *= 128
            if (b & 128) == 0:
                break
        tlen = int.from_bytes(recv_all(self.sock, 2), 'big')
        topic = recv_all(self.sock, tlen).decode()
        prop_len = recv_all(self.sock, 1)[0]
        if prop_len:
            recv_all(self.sock, prop_len)
        payload_len = remaining - 2 - tlen - 1 - prop_len
        payload = recv_all(self.sock, payload_len).decode()
        print(f"[MSG] {topic} -> {payload}")

# Publisher helper
    def run_publisher(self, topic):
        print(f"[✔] Publisher pe topic '{topic}'")
        while True:
            msg = input("Message to send (exit pentru quit): ")
            if msg.lower() in ['exit','quit']:
                break
            self.publish(topic, msg)
            print(f"[→] Trimis: {msg}")

# Subscriber helper
    def run_subscriber(self, topic, packet_id=1):
        _ = self.subscribe(topic, packet_id)
        print(f"[✔] Abonat pe topic '{topic}'")
        threading.Thread(target=self.loop_receive, daemon=True).start()
        print("[✔] Aștept mesaje... (Ctrl+C pentru ieșire)")
import socket
import threading
import time
import json
from protocol import encode_connect, decode_connack, encode_publish, encode_subscribe, decode_suback, recv_all
from monitor import SystemMonitor


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
            raise Exception(f"Conectare esuata, reason code = {rc}")
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
        try:
            packet = encode_publish(topic, message)
            self.sock.sendall(packet)
        except Exception as e:
            print(f"Eroare Publish: {e}")
            self.connected = False

    def subscribe(self, topic, packet_id=1):
        packet = encode_subscribe(packet_id, topic)
        self.sock.sendall(packet)
        suback = decode_suback(self.sock)
        return list(suback)

    def loop_receive(self):
        while self.connected:
            try:
                first = recv_all(self.sock, 1)
                ptype = first[0] >> 4
                if ptype == 3:
                    self._handle_publish()
            except:
                break

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
        print(f"[RX] {topic} : {payload}")

    def _monitor_loop(self, interval=5):
        monitor = SystemMonitor()
        # Structura topicelor conform documentatiei: sistem/<client_id>/<param>
        prefix = f"sistem/{self.client_id}"
        print(f"Monitorizare pornita. Publicare JSON pe {prefix}/cpu, /mem, /temp")

        while self.connected:
            data = monitor.collect_metrics()

            # 1. CPU
            topic_cpu = f"{prefix}/cpu"
            payload_cpu = json.dumps({"cpu": data['cpu']})
            self.publish(topic_cpu, payload_cpu)

            # 2. RAM (Memorie)
            topic_mem = f"{prefix}/mem"
            payload_mem = json.dumps({"ram": data['ram']})
            self.publish(topic_mem, payload_mem)

            # 3. Temperatura
            topic_temp = f"{prefix}/temp"
            payload_temp = json.dumps({"temperatura": data['temperatura']})
            self.publish(topic_temp, payload_temp)

            print(f"Sent JSON data for {self.client_id}")
            time.sleep(interval)

    def run_publisher(self):
        t_monitor = threading.Thread(target=self._monitor_loop, args=(5,), daemon=True)
        t_monitor.start()

        print("Publisher activ. Scrie 'exit' pentru a iesi.")
        while True:
            try:
                msg = input()
                if msg.lower() in ['exit', 'quit']:
                    self.connected = False
                    break
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Eroare: {e}")
                break

    def run_subscriber(self, topic, packet_id=1):
        self.subscribe(topic, packet_id)
        print(f"Abonat la '{topic}'")
        threading.Thread(target=self.loop_receive, daemon=True).start()
        print("Astept pachete... (Ctrl+C pentru stop)")
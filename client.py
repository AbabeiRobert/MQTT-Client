# client.py
import socket
import threading
import time
import queue
import json
from protocol import ProtocolDecoder, ProtocolEncoder, recv_all
from monitor import SystemMonitor


class MQTTClient:
    def __init__(self, host, port, client_id, username=None, password=None, keep_alive=60):
        self.host = host
        self.port = port
        self.client_id = client_id

        self.username = username
        self.password = password

        self.packet_id_counter = 1
        self.keep_alive = keep_alive

        # QoS per metrică
        self.qos_cpu = 0
        self.qos_ram = 0
        self.qos_temp = 0

        self.sock = None
        self.connected = False

        # Cozi pentru ACK-uri
        self.puback_queue = queue.Queue()
        self.suback_queue = queue.Queue()

        # QoS2
        self.qos2_pubrec_queue = queue.Queue()
        self.qos2_pubcomp_queue = queue.Queue()

    # ======================================================
    # CONNECT
    # ======================================================
    def connect(self):
        self.sock = socket.socket()
        self.sock.connect((self.host, self.port))

        print(f"Trimit pachet CONNECT pentru {self.client_id} (User: {self.username})...")

        pkt = ProtocolEncoder.encode_connect(
            client_id=self.client_id,
            keep_alive=self.keep_alive,
            username=self.username,
            password=self.password
        )

        self.sock.sendall(pkt)

        # Asteptam CONNACK
        flags, rc = ProtocolDecoder.decode_connack(self.sock)

        if rc == 0:
            print("CONNACK primit: Succes (0x00)")
        elif rc == 0x86:
            raise Exception("Eroare: User sau parolă greșită (Bad User/Pass)")
        elif rc == 0x87:
            raise Exception("Eroare: Neautorizat (Not Authorized)")
        else:
            raise Exception(f"CONNACK error code: {hex(rc)}")

        self.connected = True

        # Pornim thread-urile de ascultare si ping
        threading.Thread(target=self.loop_receive, daemon=True).start()
        threading.Thread(target=self.ping_loop, daemon=True).start()

    def ping_loop(self):
        while self.connected:
            time.sleep(self.keep_alive // 2)
            try:
                self.sock.sendall(b"\xC0\x00")  # PINGREQ
            except:
                self.connected = False

    # ======================================================
    # PUBLISH
    # ======================================================
    def publish(self, topic, message, qos=0):
        if qos == 0:
            pkt = ProtocolEncoder.encode_publish(topic, message)
            self.sock.sendall(pkt)

        elif qos == 1:
            pid = self.next_pid()
            pkt = ProtocolEncoder.encode_publish_qos1(topic, message, pid)
            self.sock.sendall(pkt)
            ack_pid = self.puback_queue.get()
            # print(f"[PUBACK] {ack_pid}")

        elif qos == 2:
            pid = self.next_pid()
            pkt = ProtocolEncoder.encode_publish_qos2(topic, message, pid)
            self.sock.sendall(pkt)

            rec_pid = self.qos2_pubrec_queue.get()
            # print(f"[PUBREC] {rec_pid}")

            self.sock.sendall(ProtocolEncoder.encode_pubrel(pid))

            comp_pid = self.qos2_pubcomp_queue.get()
            # print(f"[PUBCOMP] {comp_pid}")

    def next_pid(self):
        pid = self.packet_id_counter
        self.packet_id_counter += 1
        if self.packet_id_counter > 65535:
            self.packet_id_counter = 1
        return pid

    # ======================================================
    # SUBSCRIBE
    # ======================================================
    def subscribe(self, topic, packet_id=1):
        pkt = ProtocolEncoder.encode_subscribe(packet_id, topic)
        self.sock.sendall(pkt)
        ack = self.suback_queue.get()
        print(f"[SUBACK primit] Abonat la {topic}")

    # ======================================================
    # RECEIVE LOOP
    # ======================================================
    def loop_receive(self):
        while self.connected:
            try:
                # Citim primul octet
                first = recv_all(self.sock, 1)
                packet_type = first[0] >> 4

                # Remaining length
                remaining = 0
                mul = 1
                while True:
                    b = recv_all(self.sock, 1)[0]
                    remaining += (b & 127) * mul
                    if (b & 128) == 0:
                        break
                    mul *= 128

                # Citim corpul pachetului
                body = recv_all(self.sock, remaining)

                if packet_type == 3:  # PUBLISH primit de la broker
                    self._handle_publish(first[0], body)

                elif packet_type == 4:  # PUBACK
                    pid = ProtocolDecoder.decode_puback_from_bytes(body)
                    self.puback_queue.put(pid)

                elif packet_type == 5:  # PUBREC
                    pid = ProtocolDecoder.decode_pubrec_from_bytes(body)
                    self.qos2_pubrec_queue.put(pid)

                elif packet_type == 6:  # PUBREL
                    pid = ProtocolDecoder.decode_pubrel_from_bytes(body)
                    # Raspundem automat cu PUBCOMP
                    self.sock.sendall(ProtocolEncoder.encode_pubcomp(pid))

                elif packet_type == 7:  # PUBCOMP
                    pid = ProtocolDecoder.decode_pubcomp_from_bytes(body)
                    self.qos2_pubcomp_queue.put(pid)

                elif packet_type == 9:  # SUBACK
                    self.suback_queue.put(body)

                elif packet_type == 13:  # PINGRESP
                    pass  # Doar ignoram, inseamna ca e vie conexiunea

            except Exception as e:
                if self.connected:  # Doar daca nu noi am inchis intentionat
                    print(f"Eroare in bucla de receptie: {e}")
                    self.connected = False
                break

    # ======================================================
    # PUBLISH HANDLER
    # ======================================================
    def _handle_publish(self, first_byte, body):
        qos = (first_byte & 0b0110) >> 1

        tlen = int.from_bytes(body[:2], 'big')
        topic = body[2:2 + tlen].decode()

        idx = 2 + tlen
        packet_id = None

        if qos in (1, 2):
            packet_id = int.from_bytes(body[idx:idx + 2], 'big')
            idx += 2

        if idx < len(body):
            prop_len = body[idx]
            idx += 1 + prop_len

        payload = body[idx:].decode(errors='ignore')

        # Trimitem ACK-urile necesare
        if qos == 1:
            self.sock.sendall(ProtocolEncoder.encode_puback(packet_id))
        elif qos == 2:
            self.sock.sendall(ProtocolEncoder.encode_pubrec(packet_id))

        print(f"\n[MESAJ NOU] Topic: {topic} | Data: {payload}")

    # ======================================================
    # CONSTANT PUBLISHER LOOP
    # ======================================================
    def _monitor_loop(self, qos_cpu, qos_ram, qos_temp, interval=5):
        mon = SystemMonitor()
        prefix = f"sistem/{self.client_id}"

        while self.connected:
            d = mon.collect_metrics()

            # Trimitem separat pe topicuri
            self.publish(f"{prefix}/cpu", json.dumps({"cpu": d["cpu"]}), qos=qos_cpu)
            self.publish(f"{prefix}/mem", json.dumps({"ram": d["ram"]}), qos=qos_ram)
            self.publish(f"{prefix}/temp", json.dumps({"temperatura": d["temperatura"]}), qos=qos_temp)

            print(f"[→] {prefix}: CPU={d['cpu']}% RAM={d['ram']}% Temp={d['temperatura']}C")
            time.sleep(interval)

    # ======================================================
    # RUN MODES
    # ======================================================
    def run_publisher(self):
        print(f"[Publisher] Start monitorizare (Interval: 5s)...")
        threading.Thread(
            target=self._monitor_loop,
            args=(self.qos_cpu, self.qos_ram, self.qos_temp),
            daemon=True
        ).start()

        while self.connected:
            cmd = input()
            if cmd.lower() in ("exit", "quit"):
                self.connected = False
                break

    def run_subscriber(self, topic):
        self.subscribe(topic)
        # Main thread ramane activ doar ca sa nu se inchida programul
        while self.connected:
            time.sleep(1)
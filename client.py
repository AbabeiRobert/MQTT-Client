# client.py
import socket
import threading
import time
import queue

from protocol import ProtocolDecoder, ProtocolEncoder, recv_all
from monitor import SystemMonitor


class MQTTClient:
    def __init__(self, host, port, client_id, username=None, password=None, keep_alive=60,
                 will_topic=None, will_message=None, will_qos=0, will_retain=False):
        self.host = host
        self.port = port
        self.client_id = client_id

        self.username = username
        self.password = password
        
        self.will_topic = will_topic
        self.will_message = will_message
        self.will_qos = will_qos
        self.will_retain = will_retain

        self.packet_id_counter = 1
        self.keep_alive = keep_alive

        # QoS per metrică
        self.qos_cpu = 0
        self.qos_ram = 0
        self.qos_temp = 0

        self.sock = None
        self.connected = False

#lock-uri pentru thread-safety
        self.sock_lock = threading.Lock()
        self.pid_lock = threading.Lock()

#cozi pentru comunicare intre thread-uri (ACK-uri)
        self.puback_queue = queue.Queue()
        self.suback_queue = queue.Queue()
        self.qos2_pubrec_queue = queue.Queue()
        self.qos2_pubcomp_queue = queue.Queue()

    def connect(self):
        self.sock = socket.socket()
#initiere conexiune TCP (Three-way handshake) catre broker
        self.sock.connect((self.host, self.port))

        print(f"Trimit pachet CONNECT pentru {self.client_id} (User: {self.username})...")
#codificam datele conform protocolului
        pkt = ProtocolEncoder.encode_connect(
            client_id=self.client_id,
            keep_alive=self.keep_alive,
            username=self.username,
            password=self.password,
            will_topic=self.will_topic,
            will_message=self.will_message,
            will_qos=self.will_qos,
            will_retain=self.will_retain
        )
#trimite fluxul de octeti (stream-ul) complet al pachetului CONNECT
        with self.sock_lock:
            self.sock.sendall(pkt)

# asteptam CONNACK de la broker
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
# pornim thread-urile de ascultare si ping
# thread principal de receptie MQTT: citeste, decodeaza si proceseaza toate pachetele primite
        threading.Thread(target=self.loop_receive, daemon=True).start()
# mentine conexiunea MQTT activa prin trimiterea periodica de pingreq
        threading.Thread(target=self.ping_loop, daemon=True).start()

    def disconnect(self):
        if self.connected:
            try:
                # Trimitem pachet DISCONNECT
                print(f"Deconectare graceful pentru {self.client_id}...")
                with self.sock_lock:
                    self.sock.sendall(ProtocolEncoder.encode_disconnect())
                self.connected = False
                self.sock.close()
            except Exception as e:
                print(f"Eroare la disconnect: {e}")

    def ping_loop(self):
        while self.connected:
            time.sleep(self.keep_alive // 2)
            try:
#PINGREQ folosind encoder-ul dedicat
                with self.sock_lock:
                    self.sock.sendall(ProtocolEncoder.encode_pingreq())
            except:
                self.connected = False

    # ======================================================
    # PUBLISH (Asincron)
    # ======================================================
    def publish(self, topic, message, qos=0):
#lansam publicarea pe un thread separat pentru a nu bloca GUI-ul sau monitorizarea
        threading.Thread(target=self._publish_sync_logic, args=(topic, message, qos), daemon=True).start()

    def _publish_sync_logic(self, topic, message, qos):
        try:
            if qos == 0:
                pkt = ProtocolEncoder.encode_publish(topic, message)
                with self.sock_lock:
                    self.sock.sendall(pkt)

            elif qos == 1:
                pid = self.next_pid()
                pkt = ProtocolEncoder.encode_publish_qos1(topic, message, pid)
                
                #retransmisie simpla la timeout
                while self.connected:
                    with self.sock_lock:
                        self.sock.sendall(pkt)
                    try:
                        #asteptam 2 secunde CONFIRMAREA
                        ack_pid = self.puback_queue.get(timeout=2.0)
                        if ack_pid == pid:
                            break
                        else:
                            #daca am primit alt PID il ignoram aici
                            pass
                    except queue.Empty:
                        print(f"[RETRANSMISIE QoS1] Packet ID {pid} nu a primit ACK. Retrimit...")
                        continue

            elif qos == 2:
                pid = self.next_pid()
                pkt = ProtocolEncoder.encode_publish_qos2(topic, message, pid)
                
                # Faza 1: PUBLISH -> Asteptare PUBREC
                while self.connected:
                    with self.sock_lock:
                        self.sock.sendall(pkt)
                    try:
                        # Asteptam sincron pachetul PUBREC. 
                        # Blocant DOAR in acest thread secundar.
                        rec_pid = self.qos2_pubrec_queue.get(timeout=2.0)
                        if rec_pid == pid:
                            break
                    except queue.Empty:
                        print(f"[RETRANSMISIE QoS2] Packet ID {pid} (PUBLISH) nu a primit PUBREC. Retrimit...")
                        continue

                # Faza 2: Trimite PUBREL -> Asteptare PUBCOMP
                pubrel_pkt = ProtocolEncoder.encode_pubrel(pid)
                while self.connected:
                    with self.sock_lock:
                        self.sock.sendall(pubrel_pkt)
                    try:
                        comp_pid = self.qos2_pubcomp_queue.get(timeout=2.0)
                        if comp_pid == pid:
                            break
                    except queue.Empty:
                        print(f"[RETRANSMISIE QoS2] Packet ID {pid} (PUBREL) nu a primit PUBCOMP. Retrimit...")
                        continue

        except Exception as e:
            print(f"Eroare in thread-ul de publish: {e}")

    def next_pid(self):
        with self.pid_lock:
            pid = self.packet_id_counter
            self.packet_id_counter += 1
            if self.packet_id_counter > 65535:
                self.packet_id_counter = 1
            return pid

    def subscribe(self, topic, packet_id=1):
        # Lansam abonarea pe un thread separat pentru a nu bloca GUI-ul
        threading.Thread(target=self._subscribe_sync_logic, args=(topic, packet_id), daemon=True).start()

    def _subscribe_sync_logic(self, topic, packet_id):
        try:
            pkt = ProtocolEncoder.encode_subscribe(packet_id, topic)
            with self.sock_lock:
                self.sock.sendall(pkt)
            # Asteptam SUBACK cu timeout
            try:
                ack = self.suback_queue.get(timeout=5.0)
                print(f"[SUBACK primit] Abonat la {topic}")
            except queue.Empty:
                print(f"[TIMEOUT] Nu s-a primit SUBACK pentru {topic}")
        except Exception as e:
            print(f"Eroare in thread-ul de subscribe: {e}")

#thread principal de receptie MQTT
#citeste pachetele brute de pe socket, le decodeaza conform MQTT v5 si directioneaza fiecare pachet catre logica corespunzatoare
    def loop_receive(self):
        while self.connected:
            try:
                # Decodarea lungimii variabile (Remaining Length) conform specificatiei MQTT v5
                # Algoritm standard pentru decodare VarInt (Base 128)
                # Referinta: https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html#_Toc3901011
                first = recv_all(self.sock, 1)
                packet_type = first[0] >> 4
                remaining = 0
                mul = 1
                while True:
                    b = recv_all(self.sock, 1)[0]
                    remaining += (b & 127) * mul
                    if (b & 128) == 0:
                        break
                    mul *= 128

#citim corpul pachetului
                body = recv_all(self.sock, remaining)
#in functie de tipul pachetului folosim metoda corespunzatoare de decodare
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

#logica de procesare a pachetelor PUBLISH conform standardului MQTT v5
#a fost preluata si adaptata din implementari uzuale de pe internet
    def _handle_publish(self, first_byte, body):
#extragem qos din primul octet
        qos = (first_byte & 0b0110) >> 1

        tlen = int.from_bytes(body[:2], 'big')
        topic = body[2:2 + tlen].decode()

        idx = 2 + tlen
        packet_id = None

        if qos in (1, 2):
            packet_id = int.from_bytes(body[idx:idx + 2], 'big')
            idx += 2

#decodam VarInt pentru Property Length
        prop_len = 0
        mul = 1
        while idx < len(body):
            b = body[idx]
            idx += 1
            prop_len += (b & 127) * mul
            if (b & 128) == 0:
                break
            mul *= 128
        
#sarim peste proprietati
        idx += prop_len
#extragem payload-ul
        payload = body[idx:].decode(errors='ignore')

#trimitem ACK-urile necesare
        if qos == 1:
            self.sock.sendall(ProtocolEncoder.encode_puback(packet_id))
        elif qos == 2:
            self.sock.sendall(ProtocolEncoder.encode_pubrec(packet_id))

        print(f"\n[MESAJ NOU] Topic: {topic} | Data: {payload}")


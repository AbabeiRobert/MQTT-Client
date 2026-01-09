import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import json
import queue
from client import MQTTClient
from monitor import SystemMonitor

class MQTTGui:
#constructorul clasei MQTTGUi: initializeaza starea aplicatiei si contruieste interfata grafica
    def __init__(self, root):
        self.root = root
        self.root.title("MQTT v5 Client - Monitorizare Sistem")
        self.root.geometry("900x700")
#clientul MQTT va fi instantiat la momentul apasarii butonului Connect
        self.client = None
#flag pentru monitoriza; devine True cand se apasa "Start Monitor"
        self.monitor_running = False
#referinta catre thread ul de monitorizare; creat la pornirea thread ului
        self.monitor_thread = None
        # Coada thread-safe pentru transferul log-urilor din thread-urile de fundal catre GUI
        self.log_queue = queue.Queue()
#construieste si fixeaza toate widget urile in fereastra principala
        self.setup_ui()
        self.check_log_queue()

        style = ttk.Style()
        style.configure("Treeview", rowheight=40)

    def setup_ui(self):
#container cu titlu pentru setarile de conexiune, plasat in fereastra si extins pe latime(LabelFrame poate contine si widgeturi)
        conn_frame = ttk.LabelFrame(self.root, text="Setări Conexiune")
        conn_frame.pack(fill="x", padx=10, pady=5)
#cream textul Broker Host si langa el casuta in care se poate scrie pe care o completam automat
        ttk.Label(conn_frame, text="Broker Host:").grid(row=0, column=0, padx=5, pady=5)
        self.ent_host = ttk.Entry(conn_frame)
        self.ent_host.insert(0, "broker.hivemq.com")
        self.ent_host.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=2, padx=5, pady=5)
        self.ent_port = ttk.Entry(conn_frame, width=10)
        self.ent_port.insert(0, "1883")
        self.ent_port.grid(row=0, column=3, padx=5, pady=5)


        ttk.Label(conn_frame, text="Client ID:").grid(row=1, column=0, padx=5, pady=5)
        self.ent_id = ttk.Entry(conn_frame)
        self.ent_id.insert(0, f"py-mqtt-user-{int(time.time())}")
        self.ent_id.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(conn_frame, text="User:").grid(row=1, column=2, padx=5, pady=5)
        self.ent_user = ttk.Entry(conn_frame)
        self.ent_user.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(conn_frame, text="Pass:").grid(row=1, column=4, padx=5, pady=5)
        self.ent_pass = ttk.Entry(conn_frame, show="*")
        self.ent_pass.grid(row=1, column=5, padx=5, pady=5)
        

        ttk.Label(conn_frame, text="Will Topic:").grid(row=2, column=0, padx=5, pady=5)
        self.ent_will_topic = ttk.Entry(conn_frame)
        self.ent_will_topic.insert(0, "sistem/status/disconnected")
        self.ent_will_topic.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Will Msg:").grid(row=2, column=2, padx=5, pady=5)
        self.ent_will_msg = ttk.Entry(conn_frame)
        self.ent_will_msg.insert(0, "Client offline")
        self.ent_will_msg.grid(row=2, column=3, padx=5, pady=5)

        ttk.Label(conn_frame, text="Rol:").grid(row=3, column=0, padx=5, pady=5)
#variabila care retine rolul ales (publisher / subscriber)
        self.role_var = tk.StringVar(value="subscriber")
#frame pentru a grupa butoanele de selectie a rolului
        role_frame = ttk.Frame(conn_frame)
        role_frame.grid(row=3, column=1, columnspan=2, sticky="w", padx=5, pady=5)

#butoane radio pentru selectarea rolului; la schimbare actualizeaza dinamic interfata
        ttk.Radiobutton(role_frame, text="Subscriber", variable=self.role_var, value="subscriber", command=self.update_topic_ui).pack(side="left", padx=5)
        ttk.Radiobutton(role_frame, text="Publisher", variable=self.role_var, value="publisher", command=self.update_topic_ui).pack(side="left", padx=5)

#container pentru optiunile specifice rolului
        self.dynamic_frame = ttk.Frame(conn_frame)
        self.dynamic_frame.grid(row=3, column=3, columnspan=3, padx=5, pady=5, sticky="w")
        
        self.pub_ui_frame = ttk.Frame(self.dynamic_frame)
        ttk.Label(self.pub_ui_frame, text="Pub Prefix:").pack(side="left", padx=2)
        self.ent_pub_prefix = ttk.Entry(self.pub_ui_frame, width=15)
        self.ent_pub_prefix.insert(0, "sistem")
        self.ent_pub_prefix.pack(side="left", padx=2)


        self.sub_ui_frame = ttk.Frame(self.dynamic_frame)
        
        self.var_sub_cpu = tk.BooleanVar(value=True)
        self.var_sub_ram = tk.BooleanVar(value=True)
        self.var_sub_temp = tk.BooleanVar(value=True)
        
        ttk.Label(self.sub_ui_frame, text="Mon:").pack(side="left", padx=2)
        ttk.Checkbutton(self.sub_ui_frame, text="CPU", variable=self.var_sub_cpu).pack(side="left", padx=2)
        ttk.Checkbutton(self.sub_ui_frame, text="RAM", variable=self.var_sub_ram).pack(side="left", padx=2)
        ttk.Checkbutton(self.sub_ui_frame, text="Temp", variable=self.var_sub_temp).pack(side="left", padx=2)

#butoane Connect/Disconnect
        btn_frame = ttk.Frame(conn_frame)
        btn_frame.grid(row=4, column=0, columnspan=6, pady=10)
#butonul Connect declanseaza secventa de conectare/autentificare
        self.btn_connect = ttk.Button(btn_frame, text="Connect", command=self.on_connect)
        self.btn_connect.pack(side="left", padx=5)
        
        self.btn_disconnect = ttk.Button(btn_frame, text="Disconnect", command=self.on_disconnect, state="disabled")
        self.btn_disconnect.pack(side="left", padx=5)
        
        # Initial call to set correct UI state
        self.update_topic_ui()

        mon_frame = ttk.LabelFrame(self.root, text="Monitorizare Sistem")
        mon_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(mon_frame, text="QoS Publicare:").pack(side="left", padx=5)
        self.qos_var = tk.IntVar(value=0)
        tk.Radiobutton(mon_frame, text="QoS 0", variable=self.qos_var, value=0).pack(side="left")
        tk.Radiobutton(mon_frame, text="QoS 1", variable=self.qos_var, value=1).pack(side="left")
        tk.Radiobutton(mon_frame, text="QoS 2", variable=self.qos_var, value=2).pack(side="left")
#vom apela functia on_start_monitor cand apasam pe "Start Monitor"
        self.btn_start_mon = ttk.Button(mon_frame, text="Start Monitor", command=self.on_start_monitor, state="disabled")
        self.btn_start_mon.pack(side="left", padx=20)

        self.btn_stop_mon = ttk.Button(mon_frame, text="Stop Monitor", command=self.on_stop_monitor, state="disabled")
        self.btn_stop_mon.pack(side="left", padx=5)

        table_frame = ttk.LabelFrame(self.root, text="Date Primite")
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("client", "metric", "valoare", "timestamp")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        self.tree.heading("client", text="Client ID")
        self.tree.heading("metric", text="Metrică")
        self.tree.heading("valoare", text="Valoare")
        self.tree.heading("timestamp", text="Timp")
        self.tree.column("client", width=150)
        self.tree.column("metric", width=100)
        self.tree.column("valoare", width=100)
        self.tree.column("timestamp", width=150)
        self.tree.pack(fill="both", expand=True)

        log_frame = ttk.LabelFrame(self.root, text="Jurnal Evenimente (Log)")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.txt_log = scrolledtext.ScrolledText(log_frame, state='disabled', height=10)
        self.txt_log.pack(fill="both", expand=True)


        self.current_pub_prefix = "sistem"

    def update_topic_ui(self):
        role = self.role_var.get()

        self.pub_ui_frame.pack_forget()
        self.sub_ui_frame.pack_forget()
        
        if role == "subscriber":
            self.sub_ui_frame.pack(fill="both", expand=True)
        else:
            self.pub_ui_frame.pack(fill="both", expand=True)

    def log(self, msg):
#trimitem log-ul in coada UI-ului
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {msg}")

    def check_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.txt_log.config(state='normal')
            self.txt_log.insert(tk.END, msg + "\n\n")
            self.txt_log.see(tk.END)
            self.txt_log.config(state='disabled')
        self.root.after(100, self.check_log_queue)

    def on_connect(self):
        host = self.ent_host.get()
        port = int(self.ent_port.get())
        cid = self.ent_id.get()
        user = self.ent_user.get() or None
        pw = self.ent_pass.get() or None
        
        w_topic = self.ent_will_topic.get()
        w_msg = self.ent_will_msg.get()
        will_topic = w_topic if w_topic else None
        will_msg = w_msg if w_msg else None
#apelam constructorul din client.py
        try:
            self.client = MQTTClient(
                host, port, cid, 
                username=user, password=pw,
                will_topic=will_topic,
                will_message=will_msg,
                will_qos=1 if will_topic else 0
            )
#se apeleaza functia connect din client.py
            self.client.connect()
#adaugam mesajul in coada
            self.log("Conectat la broker!")

#identificam rolul selectat de utilizator
            role = self.role_var.get()
            
            if role == "subscriber":
#subscriber: se aboneaza la metricile selectate + sistem/status/#
                subs = []
                if self.var_sub_cpu.get(): subs.append("sistem/+/cpu")
                if self.var_sub_ram.get(): subs.append("sistem/+/mem")
                if self.var_sub_temp.get(): subs.append("sistem/+/temp")
                
#abonare la metrici
                for t in subs:
                    self.client.subscribe(t)
#adaugam mesajul in coada
                    self.log(f"Abonat la {t}")
                    
#abonare OBLIGATORIE la Last Will scoped
#status/# era prea generic si prindea gunoaie de pe broker public
                self.client.subscribe("sistem/status/#")
                self.log("Abonat la sistem/status/# (Last Will)")

                if not subs:
                    self.log("ATENTIE: Nicio metrica selectata!")
                
#asteptam putin ca subscribe-urile asincrone sa se finalizeze
                time.sleep(0.5)

                self.btn_start_mon.config(state="disabled")
            else:
#publisher: Seteaza prefixul de publicare
                topic_val = self.ent_pub_prefix.get().strip()
                if not topic_val: topic_val = "sistem" # fallback
                self.current_pub_prefix = topic_val
                self.log(f"Rol: Publisher. Prefix setat: {topic_val}")
                self.btn_start_mon.config(state="normal")
            
#pornire thread receptie
            threading.Thread(target=self.receive_loop_gui, daemon=True).start()

            self.btn_connect.config(state="disabled")
            self.btn_disconnect.config(state="normal")
            
            if role == "publisher":
                self.btn_start_mon.config(state="normal")
            else:
                self.btn_start_mon.config(state="disabled")
            
        except Exception as e:
            messagebox.showerror("Eroare", str(e))
            self.log(f"Eroare conectare: {e}")

    def on_disconnect(self):
        if self.client:
            self.on_stop_monitor()
            self.client.disconnect()
            self.log("Deconectat.")
            self.btn_connect.config(state="normal")
            self.btn_disconnect.config(state="disabled")
            self.btn_start_mon.config(state="disabled")
            self.btn_stop_mon.config(state="disabled")

    def on_start_monitor(self):
        self.monitor_running = True
        self.btn_start_mon.config(state="disabled")
        self.btn_stop_mon.config(state="normal")
        
        qos = self.qos_var.get()
#thread care ruleaza monitor_worker pentru a afisa datele in GUI
        self.monitor_thread = threading.Thread(target=self.monitor_worker, args=(qos,), daemon=True)
        self.monitor_thread.start()
        self.log(f"Monitorizare pornită (QoS {qos})...")

    def on_stop_monitor(self):
        self.monitor_running = False
        self.btn_start_mon.config(state="normal")
        self.btn_stop_mon.config(state="disabled")
        self.log("Monitorizare oprită.")
#functie executata in thread separat pentru a nu bloca GUI-ul in timpul sleep(5)
    def monitor_worker(self, qos):
        mon = SystemMonitor()
        while self.monitor_running and self.client.connected:
            metrics = mon.collect_metrics()

            base_topic = f"{self.current_pub_prefix}/{self.client.client_id}"
            
#publicam fiecare metrica
            try:
                self.client.publish(f"{base_topic}/cpu", json.dumps({"cpu": metrics['cpu']}), qos=qos)
                self.client.publish(f"{base_topic}/mem", json.dumps({"ram": metrics['ram']}), qos=qos)
                self.client.publish(f"{base_topic}/temp", json.dumps({"temperatura": metrics['temperatura']}), qos=qos)
                
                self.log(f"Trimis date sistem: CPU={metrics['cpu']}%")
            except Exception as e:
                self.log(f"Eroare publish: {e}")
                
            time.sleep(5)

    def receive_loop_gui(self):
        original_handler = self.client._handle_publish
        
        def gui_handler(first_byte, body):
#apelam logica originala pt QoS/ACKs
            original_handler(first_byte, body)
            
#acum extragem datele pt GUI
            try:
                tlen = int.from_bytes(body[:2], 'big')
                topic = body[2:2 + tlen].decode()
                
#payload start
                idx = 2 + tlen
                if (first_byte & 0b0110) >> 1 > 0: # QoS > 0
                    idx += 2
                
#decodam VarInt pentru Property Length si aici
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
                
                payload = body[idx:].decode(errors='ignore')

                self.log(f"[RCVD] Topic: {topic} | Msg: {payload}")
                
#adaugam in tabel DOAR daca e formatul nostru
                try:
                    self.update_table(topic, payload)
                except Exception:
                    pass #nu e mesaj de metrica, ignoram pt tabel
                    
            except Exception as e:
                print(f"Eroare parse GUI: {e}")

#injectam handler-ul
        self.client._handle_publish = gui_handler

#thread-ul de receive din client ruleaza deja.
        while self.client.connected:
            time.sleep(1)

    def update_table(self, topic, payload):
# topic format: sistem/CLIENT_ID/METRICA
        parts = topic.split('/')
        if len(parts) >= 3:
            cid = parts[1]
            metric = parts[2]
            val = payload
            ts = time.strftime("%H:%M:%S")

            self.root.after(0, lambda: self.tree.insert("", 0, values=(cid, metric, val, ts)))

if __name__ == "__main__":
    root = tk.Tk()
    app = MQTTGui(root)
    root.mainloop()

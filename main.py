# main.py
from client import MQTTClient
import getpass  # Pentru a ascunde parola când o scrii

mode = ""
while mode not in ("subscriber", "publisher"):
    mode = input("Mode (publisher/subscriber): ").strip().lower()

host = input("Broker host (default localhost): ") or "localhost"
port_input = input("Broker port (default 1883): ")
port = int(port_input) if port_input else 1883
client_id = input("Client ID: ") or "client_test"

use_auth = input("Folosești user/parolă? (y/n): ").lower()
user = None
pwd = None

if use_auth == 'y':
    user = input("Username: ")
    # getpass ascunde caracterele tastate in terminal
    pwd = getpass.getpass("Password: ")

mqtt = MQTTClient(host, port, client_id, username=user, password=pwd)

try:
    mqtt.connect()
except Exception as e:
    print(f"\nCRITIC: Nu s-a putut realiza conexiunea!")
    print(f"Cauza: {e}")
    exit()

if mode == 'subscriber':
    print("\nStructura topic: sistem/<client_id>/<param>")
    print("La ce vrei sa te abonezi?")
    print("1. Tot sistemul (toti clientii, toti parametrii)")
    print("2. Doar CPU (de la toti clientii)")
    print("3. Doar RAM (de la toti clientii)")
    print("4. Doar Temperatura (de la toti clientii)")

    opt = input("Alege (1-4): ").strip()

    if opt == "2":
        topic = "sistem/+/cpu"
    elif opt == "3":
        topic = "sistem/+/mem"
    elif opt == "4":
        topic = "sistem/+/temp"
    else:
        topic = "sistem/#"

    mqtt.run_subscriber(topic)

else:
    print("\nAlege QoS pentru fiecare metrică.")

    def ask_qos(name):
        q = ""
        while q not in ("0", "1", "2"):
            q = input(f"QoS pentru {name} (0/1/2): ").strip()
        return int(q)

    mqtt.qos_cpu = ask_qos("CPU")
    mqtt.qos_ram = ask_qos("RAM")
    mqtt.qos_temp = ask_qos("Temperatură")

    mqtt.run_publisher()

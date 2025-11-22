from client import MQTTClient
import time

mode=""
while mode != "subscriber" and mode!= "publisher":
    mode = input("Mode (publisher/subscriber): ").strip().lower()
host = input("Broker host (default localhost): ") or "localhost"
port = int(input("Broker port (default 1883): ") or 1883)
client_id = input("Client ID: ") or "client_test"

mqtt = MQTTClient(host, port, client_id)

try:
    mqtt.connect()
    print(f"Conectat la {host}:{port}")
except Exception as e:
    print(f"Eroare conectare: {e}")
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
        # + este wildcard care va fi inlocuit de client_id
        topic = "sistem/+/cpu"
    elif opt == "3":
        topic = "sistem/+/mem"
    elif opt == "4":
        topic = "sistem/+/temp"
    else:
        # # este wildcard pentru tot restul caii
        topic = "sistem/#"

    mqtt.run_subscriber(topic)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

else:
    #publisher trimite automat la toate topicurile
    mqtt.run_publisher()
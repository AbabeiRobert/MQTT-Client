from client import MQTTClient
import time

mode = input("Mode (publisher/subscriber): ").strip().lower()
host = input("Broker host (default localhost): ") or "localhost"
port = int(input("Broker port (default 1883): ") or 1883)
client_id = input("Client ID: ") or "mqtt_demo"
topic = input("Topic: ") or "test/topic"

mqtt = MQTTClient(host, port, client_id)
mqtt.connect()

if mode == 'subscriber':
    mqtt.run_subscriber(topic)
    try:
        while True:
            time.sleep(1)  # menține procesul principal activ
    except KeyboardInterrupt:
        print("Subscriber oprit.")
else:
    mqtt.run_publisher(topic)

import paho.mqtt.client as mqtt
import json
import time

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("localhost", 1883)

# 1. Establish normal baseline readings first
print("Sending normal readings...")
for _ in range(3):
    payload = {"temperature": 22.0, "humidity": 50.0, "gas": 775.0}
    client.publish("sentinel/sensors/telemetry", json.dumps(payload))
    time.sleep(1.0)

# 2. Send a sudden spike (triggers the derivative d_gas / d_temp calculation)
print("Sending anomalous spike!")
anomaly_payload = {"temperature": 45.0, "humidity": 20.0, "gas": 1500.0}
client.publish("sentinel/sensors/telemetry", json.dumps(anomaly_payload))

client.disconnect()

"""Simula el ESP32 sin Wokwi: publica telemetría falsa e imprime los comandos recibidos.
Uso: python simular_esp32.py   (con el mismo MQTT_BASE que la app)"""
import json, os, random, time
import paho.mqtt.client as mqtt

BASE = os.getenv("MQTT_BASE", "gutiq123/coffeetracker")
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-esp32-{random.randint(0, 9999)}")
c.on_connect = lambda cl, u, f, rc, p=None: cl.subscribe(f"{BASE}/comando")
c.on_message = lambda cl, u, m: print("LED <-", m.payload.decode())
c.connect(os.getenv("MQTT_HOST", "broker.hivemq.com"), 1883)
c.loop_start()
while True:
    d = {"temp": round(random.uniform(20, 30), 1), "hum": round(random.uniform(50, 80), 1),
         "secado": random.randint(0, 100)}
    c.publish(f"{BASE}/telemetria", json.dumps(d))
    time.sleep(2)

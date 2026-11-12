"""Puente MQTT compartido por todas las páginas (una sola conexión)."""
import json
import os
import threading
import time
import uuid
from collections import deque

import paho.mqtt.client as mqtt
import streamlit as st

BROKER = os.getenv("MQTT_HOST", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
BASE = os.getenv("MQTT_BASE", "gutiq123/coffeetracker")  # debe coincidir con el sketch
T_TELE = f"{BASE}/telemetria"
T_CMD = f"{BASE}/comando"


class Bridge:
    def __init__(self):
        self._lock = threading.Lock()
        self._last = None
        self._last_ts = 0.0
        self._hist = deque(maxlen=300)
        self.connected = False
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=f"streamlit-coffee-{uuid.uuid4().hex[:6]}"
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.connect_async(BROKER, PORT, keepalive=30)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = True
        client.subscribe(T_TELE)

    def _on_disconnect(self, client, userdata, *args):
        self.connected = False

    def _on_message(self, client, userdata, msg):
        try:
            d = json.loads(msg.payload.decode())
            d["t"] = time.strftime("%H:%M:%S")
        except Exception:
            return
        with self._lock:
            self._last, self._last_ts = d, time.time()
            self._hist.append(d)

    def snapshot(self):
        with self._lock:
            return {
                "last": dict(self._last) if self._last else None,
                "age": time.time() - self._last_ts if self._last else None,
                "hist": list(self._hist),
            }

    def publicar_comando(self, cmd: str) -> bool:
        if not self.connected:
            return False
        return self.client.publish(T_CMD, cmd, qos=1).rc == mqtt.MQTT_ERR_SUCCESS


@st.cache_resource
def get_bridge() -> Bridge:
    return Bridge()

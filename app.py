import streamlit as st
from utils.mqtt_bridge import BROKER, T_CMD, T_TELE, get_bridge

st.set_page_config(page_title="Coffee-Tracker IoT", page_icon="☕", layout="wide")
bridge = get_bridge()

st.title("☕ Coffee-Tracker IoT")
st.caption("Trazabilidad y control de calidad de café de especialidad · Wokwi (ESP32) + Streamlit + MQTT")

st.markdown(
    """
**Ambientes**
- 🌱 **Control de Cosecha y Lotes**: voz y sliders, con telemetría en vivo desde Wokwi.
- 🔍 **Análisis Visual de Grano**: cámara web, diagnóstico Apto / Con Defectos y comando al circuito.

Usa el menú lateral para cambiar de página.
"""
)

c1, c2, c3 = st.columns(3)
c1.metric("Broker MQTT", BROKER)
c2.metric("Conexión", "🟢 conectado" if bridge.connected else "🔴 sin conexión")
snap = bridge.snapshot()
c3.metric("Última telemetría", f"hace {snap['age']:.0f} s" if snap["age"] is not None else "sin datos")
st.code(f"Wokwi → Streamlit : {T_TELE}\nStreamlit → Wokwi : {T_CMD}  (APTO | DEFECTOS)")

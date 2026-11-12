import hashlib

import cv2
import numpy as np
import streamlit as st

from utils.mqtt_bridge import T_CMD, get_bridge
from utils.vision import analizar_grano

st.set_page_config(page_title="Análisis Visual de Grano", page_icon="🔍", layout="wide")
bridge = get_bridge()
COMANDOS = {"Apto": "APTO", "Con Defectos": "DEFECTOS"}

st.title("🔍 Análisis Visual de Grano")
st.caption("Toma una foto de la muestra sobre un fondo liso. El diagnóstico se envía al circuito de Wokwi.")

with st.sidebar:
    st.header("Ajustes")
    fondo = st.radio("Fondo de la foto", ["Claro", "Oscuro"], horizontal=True)
    umbral = st.slider("Máx. % de granos defectuosos para «Apto»", 1, 40, 10)
    auto = st.toggle("Publicar a Wokwi automáticamente", value=True)
    st.write("MQTT:", "🟢 conectado" if bridge.connected else "🔴 sin conexión")

tab_cam, tab_file = st.tabs(["📷 Cámara", "🖼️ Subir imagen"])
with tab_cam:
    foto = st.camera_input("Fotografía de la muestra")
with tab_file:
    archivo = st.file_uploader("Imagen del grano", type=["jpg", "jpeg", "png"])

origen = foto or archivo
if origen is None:
    st.info("Toma o sube una foto para analizar.")
    st.stop()

datos = origen.getvalue()
img = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
res, anotada = analizar_grano(img, fondo_claro=(fondo == "Claro"), umbral_defectos=umbral)

col1, col2 = st.columns([3, 2])
col1.image(anotada, caption="Verde = grano normal · Rojo = posible defecto", use_container_width=True)
with col2:
    if res["estado"] is None:
        st.warning(res["resumen"])
        st.stop()
    (st.success if res["estado"] == "Apto" else st.error)(f"### {res['estado']}")
    st.metric("Granos detectados", res["granos"])
    st.metric("Granos con defectos", f"{res['pct_defectos']:.1f} %")
    st.metric("Uniformidad de color", f"{res['uniformidad']:.0f} / 100")
    st.markdown(res["resumen"])

# ---------- Comando MQTT hacia Wokwi ----------
cmd = COMANDOS[res["estado"]]
huella = hashlib.md5(datos).hexdigest() + fondo + str(umbral)
if auto and st.session_state.get("ultima_pub") != huella:
    if bridge.publicar_comando(cmd):
        st.session_state.ultima_pub = huella
        st.toast(f"Enviado a Wokwi: {cmd}", icon="📡")
    else:
        st.warning("No se pudo publicar: sin conexión MQTT.")
if st.button(f"📡 Reenviar «{cmd}» a Wokwi"):
    st.success("Comando enviado." if bridge.publicar_comando(cmd) else "Sin conexión MQTT.")
st.caption(f"Tópico: {T_CMD}")

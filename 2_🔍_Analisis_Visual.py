import hashlib

import cv2
import numpy as np
import streamlit as st

from utils.mqtt_bridge import T_CMD, get_bridge
from utils.vision import analizar_grano

st.set_page_config(page_title="Análisis Visual de Grano", page_icon="🔍", layout="wide")
bridge = get_bridge()
COMANDOS = {"Apto": "APTO", "Con Defectos": "DEFECTOS"}
MODOS = {"Automático": "auto", "Granos individuales": "granos", "Pila de granos": "pila"}

st.title("🔍 Análisis Visual de Grano")
st.caption("Toma o sube una foto de la muestra. El diagnóstico se envía al circuito de Wokwi.")

with st.sidebar:
    st.header("Ajustes")
    modo_txt = st.radio(
        "Tipo de foto", list(MODOS), index=0,
        help="Automático: intenta separar granos y, si no puede, evalúa la pila por zonas de color.",
    )
    umbral = st.slider("Máx. % de defectos para «Apto»", 1, 40, 10)
    tolerancia = st.slider(
        "Tolerancia de color (%)", 10, 60, 30,
        help="Qué tanto puede variar el brillo de un grano respecto a la mediana antes de marcarlo como defecto.",
    )
    auto = st.toggle("Publicar a Wokwi automáticamente", value=True)
    st.write("MQTT:", "🟢 conectado" if bridge.connected else "🔴 sin conexión")
    with st.expander("💡 Consejos para una buena foto"):
        st.markdown(
            "- Fondo **liso** (papel blanco o tela oscura), sin texto ni objetos.\n"
            "- Granos **separados** y bien enfocados; evita que toquen el borde de la foto.\n"
            "- Luz pareja, sin sombras fuertes ni reflejos.\n"
            "- Fotos de internet: recorta la zona de granos antes de subirla.\n"
            "- Los bloques grandes o raros se **descartan** (salen en amarillo)."
        )

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
if img is None:
    st.error("No pude leer la imagen. Prueba con otro archivo JPG o PNG.")
    st.stop()

res, anotada = analizar_grano(
    img, modo=MODOS[modo_txt], tolerancia=tolerancia / 100, umbral_defectos=umbral
)

if res.get("aviso"):
    st.info(res["aviso"])

col1, col2 = st.columns([3, 2])
with col1:
    t1, t2 = st.tabs(["Resultado", "Segmentación"])
    leyenda = (
        "Verde = grano normal · Rojo = posible defecto · Amarillo = descartado"
        if res["modo"] == "granos"
        else "Rojo = zonas con color fuera de rango"
    )
    t1.image(anotada, caption=leyenda, use_container_width=True)
    t2.image(res["mascara"], caption="Lo que la app considera grano (blanco) y cortes entre granos (rojo)",
             use_container_width=True)

with col2:
    if res["estado"] is None:
        st.warning(res["resumen"])
        st.stop()
    (st.success if res["estado"] == "Apto" else st.error)(f"### {res['estado']}")
    if res["modo"] == "granos":
        st.metric("Granos analizados", res["granos"])
        st.metric("Granos con defectos", f"{res['pct_defectos']:.1f} %")
    else:
        st.metric("Superficie fuera de rango", f"{res['pct_defectos']:.1f} %")
    st.metric("Uniformidad de color", f"{res['uniformidad']:.0f} / 100")
    st.markdown(res["resumen"])

# ---------- Comando MQTT hacia Wokwi ----------
cmd = COMANDOS[res["estado"]]
huella = hashlib.md5(datos).hexdigest() + modo_txt + str(umbral) + str(tolerancia)
if auto and st.session_state.get("ultima_pub") != huella:
    if bridge.publicar_comando(cmd):
        st.session_state.ultima_pub = huella
        st.toast(f"Enviado a Wokwi: {cmd}", icon="📡")
    else:
        st.warning("No se pudo publicar: sin conexión MQTT.")
if st.button(f"📡 Reenviar «{cmd}» a Wokwi"):
    st.success("Comando enviado." if bridge.publicar_comando(cmd) else "Sin conexión MQTT.")
st.caption(f"Tópico: {T_CMD}")

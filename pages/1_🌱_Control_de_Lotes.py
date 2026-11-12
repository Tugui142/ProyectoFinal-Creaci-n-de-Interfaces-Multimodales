import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.mqtt_bridge import get_bridge
from utils.voz import ETAPAS, extraer_datos, transcribir

st.set_page_config(page_title="Control de Lotes", page_icon="🌱", layout="wide")
bridge = get_bridge()
CSV = Path(__file__).resolve().parent.parent / "data" / "lotes.csv"
TOSTIONES = ["Sin tostar", "Clara", "Media", "Media-oscura", "Oscura"]

st.title("🌱 Control de Cosecha y Lotes")

# ---------- Telemetría en vivo (se refresca sola cada 2 s) ----------
@st.fragment(run_every=2)
def telemetria():
    snap = bridge.snapshot()
    last = snap["last"]
    a, b, c = st.columns(3)
    a.metric("🌡️ Temperatura", f"{last['temp']:.1f} °C" if last else "—")
    b.metric("💧 Humedad", f"{last['hum']:.1f} %" if last else "—")
    c.metric("☀️ Secado / radiación", f"{last['secado']} %" if last else "—")
    if snap["hist"]:
        df = pd.DataFrame(snap["hist"]).set_index("t")[["temp", "hum", "secado"]]
        st.line_chart(df, height=200)
    elif not bridge.connected:
        st.warning("Sin conexión al broker MQTT.")
    else:
        st.info("Esperando datos de Wokwi… inicia la simulación.")

st.subheader("Telemetría en vivo")
telemetria()

# ---------- Estado de los controles ----------
defaults = {"lote": "", "finca": "", "variedad": "Castillo", "etapa": ETAPAS[0],
            "peso": 25.0, "altitud": 1800, "horas_ferm": 0, "tostion": TOSTIONES[0], "notas": ""}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ---------- Entrada por voz ----------
st.subheader("Registro del lote")
audio = st.audio_input("🎙️ Dicta el registro. Ejemplo: «fermentación, 30 kilos, 1850 metros, 36 horas»")
if audio is not None:
    datos = audio.getvalue()
    huella = hashlib.md5(datos).hexdigest()
    if st.session_state.get("ultimo_audio") != huella:   # procesar cada grabación una sola vez
        st.session_state.ultimo_audio = huella
        try:
            texto = transcribir(datos)
            ext = extraer_datos(texto)
            if "peso" in ext:
                st.session_state.peso = min(max(ext["peso"], 1.0), 500.0)
            if "altitud" in ext:
                st.session_state.altitud = int(min(max(ext["altitud"], 800), 2300))
            if "horas_ferm" in ext:
                st.session_state.horas_ferm = int(min(max(ext["horas_ferm"], 0), 96))
            if "etapa" in ext:
                st.session_state.etapa = ext["etapa"]
            st.session_state.notas = (st.session_state.notas + " " + texto).strip()
            st.success(f"Entendí: «{texto}»")
        except Exception as e:
            st.error(f"No pude transcribir el audio ({type(e).__name__}). Ingresa los datos manualmente.")

# ---------- Sliders y campos manuales ----------
c1, c2, c3 = st.columns(3)
c1.text_input("Código de lote", key="lote", placeholder="L-2026-001")
c2.text_input("Finca / vereda", key="finca")
c3.text_input("Variedad", key="variedad")

st.select_slider("Etapa del proceso", options=ETAPAS, key="etapa")
s1, s2, s3 = st.columns(3)
s1.slider("Peso (kg)", 1.0, 500.0, step=0.5, key="peso")
s2.slider("Altitud (msnm)", 800, 2300, step=10, key="altitud")
s3.slider("Fermentación (horas)", 0, 96, key="horas_ferm")
st.select_slider("Nivel de tostión", options=TOSTIONES, key="tostion")
st.text_area("Notas", key="notas", height=80)

if st.button("💾 Registrar lote", type="primary", disabled=not st.session_state.lote.strip()):
    last = bridge.snapshot()["last"] or {}
    reg = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **{k: st.session_state[k] for k in defaults},
        "temp": last.get("temp"), "hum": last.get("hum"), "secado": last.get("secado"),
    }
    CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([reg]).to_csv(CSV, mode="a", header=not CSV.exists(), index=False)
    st.success("Lote registrado con la telemetría del momento.")

st.subheader("Historial")
if CSV.exists():
    hist = pd.read_csv(CSV)
    st.dataframe(hist.iloc[::-1], use_container_width=True)
    st.download_button("⬇️ Descargar CSV", hist.to_csv(index=False), "lotes.csv", "text/csv")
else:
    st.caption("Aún no hay lotes registrados.")

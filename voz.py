"""Transcripción de voz (es-CO) y extracción de datos del dictado."""
import io
import re

import speech_recognition as sr

ETAPAS = ["Recolección", "Despulpado", "Fermentación", "Lavado", "Secado", "Trillado", "Tostado"]
_CLAVES = {
    "recolec": "Recolección", "cosech": "Recolección", "despulp": "Despulpado",
    "fermenta": "Fermentación", "lavad": "Lavado", "secad": "Secado",
    "trill": "Trillado", "tost": "Tostado",
}


def transcribir(wav_bytes: bytes) -> str:
    r = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(wav_bytes)) as src:
        audio = r.record(src)
    return r.recognize_google(audio, language="es-CO")


def extraer_datos(texto: str) -> dict:
    """Busca etapa, kilos, altitud y horas de fermentación en el texto dictado."""
    t = texto.lower()
    out = {}
    for clave, etapa in _CLAVES.items():
        if clave in t:
            out["etapa"] = etapa
            break
    num = r"(\d+(?:[.,]\d+)?)"
    for campo, patron in {
        "peso": rf"{num}\s*(?:kilos?|kg|kilogramos?)",
        "altitud": rf"{num}\s*(?:metros|msnm)",
        "horas_ferm": rf"{num}\s*horas?",
    }.items():
        m = re.search(patron, t)
        if m:
            out[campo] = float(m.group(1).replace(",", "."))
    return out

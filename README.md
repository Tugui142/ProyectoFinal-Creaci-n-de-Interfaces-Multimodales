# Coffee-Tracker IoT · Streamlit

App web multipágina (Streamlit + MQTT) para el curso Interfaces Multimodales.
Se comunica con el ESP32 simulado en Wokwi mediante el broker público HiveMQ.

- Tópico de telemetría (Wokwi → web): `gutiq123/coffeetracker/telemetria`
- Tópico de comandos (web → Wokwi): `gutiq123/coffeetracker/comando` (`APTO` | `DEFECTOS`)

## Correr en local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Desplegar en Streamlit Community Cloud
1. Sube este repositorio a GitHub.
2. En share.streamlit.io: *New app* → elige el repo, rama `main`, archivo principal `app.py`.
3. El prefijo MQTT ya viene configurado (`gutiq123/coffeetracker`). Si lo cambias, hazlo igual en `utils/mqtt_bridge.py` y en el sketch de Wokwi.

Nota: en la nube el archivo `data/lotes.csv` es temporal (se borra al reiniciar); descárgalo desde la página de lotes.

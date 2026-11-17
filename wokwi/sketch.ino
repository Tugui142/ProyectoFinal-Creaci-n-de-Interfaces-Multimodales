// Coffee-Tracker IoT - ESP32 (Wokwi)
// Publica telemetría por MQTT y recibe el diagnóstico de calidad desde Streamlit.
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define DHT_PIN   15
#define POT_PIN   34
#define LED_VERDE 26
#define LED_ROJO  27

// Prefijo MQTT: debe coincidir con utils/mqtt_bridge.py (MQTT_BASE) en la app
const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;
const char* T_TELE = "gutiq123/coffeetracker/telemetria";
const char* T_CMD  = "gutiq123/coffeetracker/comando";

DHT dht(DHT_PIN, DHT22);
LiquidCrystal_I2C lcd(0x27, 16, 2);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

String diagnostico = "---";
float temp = 0, hum = 0;
int secado = 0;
unsigned long ultimoEnvio = 0;

void mostrarLCD() {
  char l1[17], l2[17];
  snprintf(l1, sizeof(l1), "T%4.1f H%2.0f S%3d%%", temp, hum, secado);
  snprintf(l2, sizeof(l2), "Cafe: %-9s", diagnostico.c_str());
  lcd.setCursor(0, 0); lcd.print(l1);
  lcd.setCursor(0, 1); lcd.print(l2);
}

void alRecibir(char* topic, byte* payload, unsigned int len) {
  String msg;
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  msg.trim(); msg.toUpperCase();
  if (msg == "APTO") {
    digitalWrite(LED_VERDE, HIGH); digitalWrite(LED_ROJO, LOW);
    diagnostico = "APTO";
  } else if (msg == "DEFECTOS") {
    digitalWrite(LED_VERDE, LOW); digitalWrite(LED_ROJO, HIGH);
    diagnostico = "DEFECTOS";
  }
  Serial.println("Comando: " + msg);
  mostrarLCD();
}

void conectarWiFi() {
  WiFi.begin("Wokwi-GUEST", "", 6);
  while (WiFi.status() != WL_CONNECTED) { delay(250); Serial.print("."); }
  Serial.println("\nWiFi OK");
}

void conectarMQTT() {
  while (!mqtt.connected()) {
    String id = "esp32-coffee-" + String(random(0xffff), HEX);
    if (mqtt.connect(id.c_str())) {
      mqtt.subscribe(T_CMD);
      Serial.println("MQTT OK");
    } else {
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);
  dht.begin();
  lcd.init(); lcd.backlight();
  lcd.print("Coffee-Tracker");
  conectarWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(alRecibir);
  conectarMQTT();
  lcd.clear();
}

void loop() {
  if (!mqtt.connected()) conectarMQTT();
  mqtt.loop();

  if (millis() - ultimoEnvio >= 2000) {
    ultimoEnvio = millis();
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) { temp = t; hum = h; }
    secado = map(analogRead(POT_PIN), 0, 4095, 0, 100);

    char buf[80];
    snprintf(buf, sizeof(buf), "{\"temp\":%.1f,\"hum\":%.1f,\"secado\":%d}", temp, hum, secado);
    mqtt.publish(T_TELE, buf);
    mostrarLCD();
  }
}

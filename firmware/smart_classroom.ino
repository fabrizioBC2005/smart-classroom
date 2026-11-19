/*
 * Smart Classroom — firmware del nodo de aula
 * ESP32 DevKit V1
 *
 * PRINCIPIO DE DISENO: la logica critica vive AQUI, no en el servidor.
 * Si se cae el WiFi, el broker o el backend, el ventilador igual se
 * enciende y el OLED sigue mostrando el semaforo. La demo no muere por
 * un problema de red, que es la causa mas comun de fracaso en este tipo
 * de proyectos.
 *
 * Sensores:
 *   SCD41    (I2C 0x62) — CO2 real por NDIR fotoacustico
 *   BME280   (I2C 0x76) — temperatura, humedad, presion
 *   BH1750   (I2C 0x23) — iluminacion en lux
 *   2x VL53L0X          — conteo direccional en la puerta (XSHUT en GPIO 16/17)
 *   SSD1306  (I2C 0x3C) — OLED de estado local
 *
 * NOTA IMPORTANTE SOBRE EL MQ-135:
 *   El MQ-135 NO mide CO2. Es un sensor de oxidos metalicos sensible a
 *   compuestos volatiles, amoniaco y humo. Su "curva de CO2" no entrega
 *   ppm confiables, deriva con la humedad y tiene reactividad cruzada.
 *   Como todo el proyecto descansa sobre el CO2, usar MQ-135 invalidaria
 *   la medicion. Por eso aqui va un SCD41 (o un MH-Z19C por UART).
 *
 * Librerias (Gestor de librerias de Arduino IDE):
 *   - Sensirion I2C SCD4x
 *   - Adafruit BME280 Library + Adafruit Unified Sensor
 *   - BH1750 (Christopher Laws)
 *   - Adafruit SSD1306 + Adafruit GFX
 *   - VL53L0X (Pololu)
 *   - PubSubClient (Nick O'Leary)
 *   - ArduinoJson (Benoit Blanchon)
 */

#include <WiFi.h>
#include <Wire.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <SensirionI2CScd4x.h>
#include <Adafruit_BME280.h>
#include <BH1750.h>
#include <Adafruit_SSD1306.h>
#include <VL53L0X.h>

#include "config.h"   // copia config.h.example -> config.h y edita

// ----------------------------------------------------------- pines
#define PIN_RELE_VENT   26
#define PIN_RELE_LUZ    27
#define PIN_LED_VERDE   32
#define PIN_LED_AMBAR   33
#define PIN_LED_ROJO    25
#define PIN_BUZZER      14
#define PIN_XSHUT_A     16
#define PIN_XSHUT_B     17
#define I2C_SDA         21
#define I2C_SCL         22

// --------------------------------------------- umbrales locales (fallback)
// Se usan SIEMPRE. Si ademas llega un comando del backend, ese manda,
// pero estos garantizan que el aula nunca queda sin proteccion.
const float CO2_ALERTA_LOCAL  = 1000.0;
const float CO2_CRITICO_LOCAL = 1400.0;
const float CO2_APAGAR_LOCAL  = 880.0;   // histeresis

const unsigned long INTERVALO_PUBLICACION_MS = 10000;
const unsigned long INTERVALO_SENSORES_MS    = 5000;
const unsigned long TIMEOUT_COMANDO_MS       = 600000;  // 10 min

// ------------------------------------------------------------- objetos
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
SensirionI2CScd4x scd4x;
Adafruit_BME280 bme;
BH1750 luxmetro;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
VL53L0X tofA, tofB;

// ------------------------------------------------------------- estado
float co2 = 0, temp = 0, hum = 0, lux = 0;
bool  hayBME = false, hayLux = false, hayTof = false;
int   ocupantes = 0;

bool  ventilacionOn = false;
bool  ventilacionForzadaRemota = false;
unsigned long tsComandoRemoto = 0;

unsigned long ultimaPublicacion = 0, ultimaLectura = 0, ultimoReintentoMqtt = 0;

// conteo direccional en la puerta
bool aActivo = false, bActivo = false;
unsigned long tsA = 0, tsB = 0;
const int  UMBRAL_TOF_MM   = 1200;
const unsigned long VENTANA_CRUCE_MS = 900;

char topicTelemetria[128];
char topicComando[128];
char topicEstado[128];

// ===================================================================
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println(F("\n[Smart Classroom] iniciando..."));

  pinMode(PIN_RELE_VENT, OUTPUT);
  pinMode(PIN_RELE_LUZ, OUTPUT);
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_AMBAR, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  // Modulos de rele comunes son activos en BAJO. Invierte si el tuyo no lo es.
  digitalWrite(PIN_RELE_VENT, HIGH);
  digitalWrite(PIN_RELE_LUZ, HIGH);

  Wire.begin(I2C_SDA, I2C_SCL);

  snprintf(topicTelemetria, sizeof(topicTelemetria), "%s/%s/%s/telemetria", MQTT_BASE_TOPIC, SEDE_SLUG, AULA_CODIGO);
  snprintf(topicComando,    sizeof(topicComando),    "%s/%s/%s/comando",    MQTT_BASE_TOPIC, SEDE_SLUG, AULA_CODIGO);
  snprintf(topicEstado,     sizeof(topicEstado),     "%s/%s/%s/estado",     MQTT_BASE_TOPIC, SEDE_SLUG, AULA_CODIGO);

  iniciarOLED();
  iniciarSensores();
  conectarWiFi();

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMensajeMqtt);
  mqtt.setBufferSize(768);

  Serial.println(F("[Smart Classroom] listo"));
}

// ===================================================================
void loop() {
  // El orden importa: primero se lee y se decide localmente, y recien
  // despues se atiende la red. Asi la proteccion nunca depende del WiFi.
  unsigned long ahora = millis();

  if (ahora - ultimaLectura >= INTERVALO_SENSORES_MS) {
    ultimaLectura = ahora;
    leerSensores();
    decidirLocalmente();
    actualizarOLED();
  }

  if (hayTof) contarPuerta();

  if (WiFi.status() != WL_CONNECTED) {
    conectarWiFi();
  } else {
    if (!mqtt.connected() && ahora - ultimoReintentoMqtt > 5000) {
      ultimoReintentoMqtt = ahora;
      conectarMqtt();
    }
    mqtt.loop();

    if (mqtt.connected() && ahora - ultimaPublicacion >= INTERVALO_PUBLICACION_MS) {
      ultimaPublicacion = ahora;
      publicarTelemetria();
    }
  }

  // El comando remoto caduca: si el backend se cae con la ventilacion
  // forzada, el nodo vuelve solo a su logica local.
  if (ventilacionForzadaRemota && millis() - tsComandoRemoto > TIMEOUT_COMANDO_MS) {
    ventilacionForzadaRemota = false;
    Serial.println(F("[ctrl] comando remoto caducado, vuelvo a logica local"));
  }
}

// =============================================================== sensores
void iniciarSensores() {
  scd4x.begin(Wire);
  scd4x.stopPeriodicMeasurement();
  delay(500);
  uint16_t err = scd4x.startPeriodicMeasurement();
  if (err) Serial.println(F("[scd41] ERROR al iniciar"));
  else     Serial.println(F("[scd41] ok"));

  hayBME = bme.begin(0x76) || bme.begin(0x77);
  Serial.println(hayBME ? F("[bme280] ok") : F("[bme280] ausente"));

  hayLux = luxmetro.begin();
  Serial.println(hayLux ? F("[bh1750] ok") : F("[bh1750] ausente"));

  hayTof = iniciarToF();
  Serial.println(hayTof ? F("[vl53l0x] ok") : F("[vl53l0x] ausente (aforo solo por CO2)"));
}

bool iniciarToF() {
  pinMode(PIN_XSHUT_A, OUTPUT);
  pinMode(PIN_XSHUT_B, OUTPUT);
  digitalWrite(PIN_XSHUT_A, LOW);
  digitalWrite(PIN_XSHUT_B, LOW);
  delay(50);

  // Los dos sensores nacen con la misma direccion I2C: se levantan de a
  // uno y al primero se le reasigna.
  digitalWrite(PIN_XSHUT_A, HIGH);
  delay(50);
  if (!tofA.init()) return false;
  tofA.setAddress(0x30);
  tofA.setTimeout(150);
  tofA.startContinuous(60);

  digitalWrite(PIN_XSHUT_B, HIGH);
  delay(50);
  if (!tofB.init()) return false;
  tofB.setTimeout(150);
  tofB.startContinuous(60);
  return true;
}

void leerSensores() {
  uint16_t c; float t, h;
  bool listo = false;
  scd4x.getDataReadyFlag(listo);
  if (listo && scd4x.readMeasurement(c, t, h) == 0 && c != 0) {
    co2 = (float)c;
    if (!hayBME) { temp = t; hum = h; }
  }
  if (hayBME) {
    temp = bme.readTemperature();
    hum  = bme.readHumidity();
  }
  if (hayLux) lux = luxmetro.readLightLevel();
}

// ==================================================== conteo en la puerta
void contarPuerta() {
  int dA = tofA.readRangeContinuousMillimeters();
  int dB = tofB.readRangeContinuousMillimeters();
  unsigned long ahora = millis();

  bool a = (!tofA.timeoutOccurred() && dA > 0 && dA < UMBRAL_TOF_MM);
  bool b = (!tofB.timeoutOccurred() && dB > 0 && dB < UMBRAL_TOF_MM);

  if (a && !aActivo) { aActivo = true; tsA = ahora; }
  if (b && !bActivo) { bActivo = true; tsB = ahora; }
  if (!a) aActivo = false;
  if (!b) bActivo = false;

  // El orden de activacion da la direccion: A antes que B = entra.
  if (tsA && tsB && abs((long)(tsA - tsB)) < (long)VENTANA_CRUCE_MS) {
    if (tsA < tsB) ocupantes++;
    else if (ocupantes > 0) ocupantes--;
    tsA = tsB = 0;
  }
  if (tsA && ahora - tsA > VENTANA_CRUCE_MS) tsA = 0;
  if (tsB && ahora - tsB > VENTANA_CRUCE_MS) tsB = 0;
}

// =============================================== decision local (fallback)
void decidirLocalmente() {
  if (ventilacionForzadaRemota) return;   // el backend tiene prioridad

  if (co2 >= CO2_ALERTA_LOCAL && !ventilacionOn) {
    aplicarVentilacion(true);
    Serial.printf("[local] ventilacion ON por umbral (%.0f ppm)\n", co2);
  } else if (co2 <= CO2_APAGAR_LOCAL && ventilacionOn) {
    aplicarVentilacion(false);
    Serial.printf("[local] ventilacion OFF (%.0f ppm)\n", co2);
  }

  digitalWrite(PIN_LED_VERDE, co2 < CO2_ALERTA_LOCAL);
  digitalWrite(PIN_LED_AMBAR, co2 >= CO2_ALERTA_LOCAL && co2 < CO2_CRITICO_LOCAL);
  digitalWrite(PIN_LED_ROJO,  co2 >= CO2_CRITICO_LOCAL);

  static unsigned long ultimoBeep = 0;
  if (co2 >= CO2_CRITICO_LOCAL && millis() - ultimoBeep > 60000) {
    ultimoBeep = millis();
    tone(PIN_BUZZER, 2000, 180);
  }
}

void aplicarVentilacion(bool on) {
  ventilacionOn = on;
  digitalWrite(PIN_RELE_VENT, on ? LOW : HIGH);   // rele activo en BAJO
}

// =================================================================== MQTT
void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("[wifi] conectando a %s ", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) {
    delay(400);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : " sin red (sigo en local)");
}

void conectarMqtt() {
  char id[48];
  snprintf(id, sizeof(id), "esp32-%s-%s", SEDE_SLUG, AULA_CODIGO);

  bool ok;
  if (strlen(MQTT_USER) > 0)
    ok = mqtt.connect(id, MQTT_USER, MQTT_PASSWORD, topicEstado, 1, true, "{\"online\":false}");
  else
    ok = mqtt.connect(id, topicEstado, 1, true, "{\"online\":false}");

  if (ok) {
    Serial.println(F("[mqtt] conectado"));
    mqtt.publish(topicEstado, "{\"online\":true,\"fw\":\"" FIRMWARE_VERSION "\"}", true);
    mqtt.subscribe(topicComando, 1);
  } else {
    Serial.printf("[mqtt] fallo rc=%d\n", mqtt.state());
  }
}

void onMensajeMqtt(char* topic, byte* payload, unsigned int len) {
  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, payload, len)) return;

  const char* actuador = doc["actuador"] | "";
  const char* accion   = doc["accion"]   | "";
  const char* motivo   = doc["motivo"]   | "";

  if (strcmp(actuador, "ventilacion") == 0) {
    bool on = (strcmp(accion, "on") == 0);
    aplicarVentilacion(on);
    ventilacionForzadaRemota = on;
    tsComandoRemoto = millis();
    Serial.printf("[remoto] ventilacion %s (%s)\n", accion, motivo);
  } else if (strcmp(actuador, "iluminacion") == 0) {
    digitalWrite(PIN_RELE_LUZ, strcmp(accion, "on") == 0 ? LOW : HIGH);
  }
}

void publicarTelemetria() {
  StaticJsonDocument<384> doc;
  doc["device_id"] = DEVICE_ID;
  doc["ts"]        = (double)(millis() / 1000.0);   // el backend usa su reloj si falta NTP
  doc["co2_ppm"]   = co2;
  doc["temp_c"]    = temp;
  doc["hum_pct"]   = hum;
  if (hayLux) doc["lux"] = lux;
  if (hayTof) doc["ocupantes"] = ocupantes;
  doc["vent"]      = ventilacionOn;
  doc["fw"]        = FIRMWARE_VERSION;
  doc["rssi"]      = WiFi.RSSI();

  char buf[384];
  size_t n = serializeJson(doc, buf);
  mqtt.publish(topicTelemetria, buf, n);
}

// ==================================================================== OLED
void iniciarOLED() {
  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("[oled] ausente"));
    return;
  }
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.println(F("Smart Classroom"));
  oled.print(F("Aula "));
  oled.println(AULA_CODIGO);
  oled.display();
}

void actualizarOLED() {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print(F("Aula "));
  oled.print(AULA_CODIGO);
  oled.setCursor(92, 0);
  oled.print(mqtt.connected() ? F("NET") : F("---"));

  oled.setTextSize(2);
  oled.setCursor(0, 16);
  oled.print((int)co2);
  oled.setTextSize(1);
  oled.print(F(" ppm"));

  oled.setCursor(0, 38);
  oled.printf("%.1fC  %.0f%%  n=%d", temp, hum, ocupantes);

  oled.setCursor(0, 52);
  if (co2 >= CO2_CRITICO_LOCAL)      oled.print(F("CRITICO"));
  else if (co2 >= CO2_ALERTA_LOCAL)  oled.print(F("ALERTA"));
  else                               oled.print(F("OK"));
  if (ventilacionOn) oled.print(F("  [VENT ON]"));

  oled.display();
}

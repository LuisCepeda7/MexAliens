#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// Si la pantalla sigue en blanco o con bloques, cambia 0x27 por 0x3F
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Sensor de temperatura DS18B20 en el pin 9
OneWire oneWire(9);
DallasTemperature sensors(&oneWire);

// ---------------------------------------------------------------
// LEDs: cada uno representa UNA tarjeta del sitio web
// Orden de la trama:  HR, SpO2, RAD, GLU, SUEÑO, HUESO, BOCINA
// ---------------------------------------------------------------
const int NUM_LEDS = 6;
const int ledPins[NUM_LEDS] = {
  7,  // 0 Frecuencia cardiaca  -> ROJO
  4,  // 1 Oxigeno (SpO2)       -> BLANCO
  5,  // 2 Radiacion            -> AMARILLO
  6,  // 3 Glucosa              -> NARANJA
  3,  // 4 Sueno                -> AZUL
  2   // 5 Densidad osea        -> VERDE
};
const char* nombres[NUM_LEDS] = {"HR", "O2", "RAD", "GLU", "SLP", "BON"};

const int pinBocina = 8;           // salida a la base del transistor de la bocina
const int FREQ_ALARMA = 1500;      // Hz

// Si el puente deja de mandar datos por este tiempo, se apaga todo
const unsigned long TIMEOUT_MS = 5000;

bool alertas[NUM_LEDS];
bool bocinaActiva = false;
bool enlaceActivo = false;
unsigned long ultimoMensaje = 0;

// Buffer para leer una linea del puerto serie (ej. "1001001")
char bufferSerie[16];
byte idxBuffer = 0;

float temperatura = -127.0;
unsigned long ultimaTemp = 0;
unsigned long ultimoLCD = 0;

void setup() {
  Serial.begin(9600);

  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcd.clear();

  sensors.begin();
  sensors.setWaitForConversion(false);  // no bloquea el loop (para no perder datos del serial)
  sensors.requestTemperatures();

  for (int i = 0; i < NUM_LEDS; i++) {
    pinMode(ledPins[i], OUTPUT);
    digitalWrite(ledPins[i], LOW);
    alertas[i] = false;
  }
  pinMode(pinBocina, OUTPUT);
  noTone(pinBocina);

  // Prueba rapida de LEDs al encender
  lcd.setCursor(0, 0);
  lcd.print("Astro-Monitor");
  for (int i = 0; i < NUM_LEDS; i++) {
    digitalWrite(ledPins[i], HIGH);
    delay(150);
    digitalWrite(ledPins[i], LOW);
  }
  lcd.clear();
}

void loop() {
  leerSerie();
  revisarTimeout();
  actualizarSalidas();
  leerTemperatura();
  actualizarLCD();
}

// Lee caracteres sin bloquear. La trama es 7 caracteres '0'/'1' terminados en '\n'
void leerSerie() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      procesarTrama();
      idxBuffer = 0;
    } else if (c != '\r') {
      if (idxBuffer < sizeof(bufferSerie) - 1) {
        bufferSerie[idxBuffer++] = c;
      } else {
        idxBuffer = 0;  // trama demasiado larga: descartar
      }
    }
  }
}

void procesarTrama() {
  if (idxBuffer < NUM_LEDS + 1) return;  // incompleta

  for (int i = 0; i < NUM_LEDS + 1; i++) {
    if (bufferSerie[i] != '0' && bufferSerie[i] != '1') return;  // trama invalida
  }

  for (int i = 0; i < NUM_LEDS; i++) {
    alertas[i] = (bufferSerie[i] == '1');
  }
  bocinaActiva = (bufferSerie[NUM_LEDS] == '1');
  enlaceActivo = true;
  ultimoMensaje = millis();
}

void revisarTimeout() {
  if (enlaceActivo && (millis() - ultimoMensaje > TIMEOUT_MS)) {
    enlaceActivo = false;
    for (int i = 0; i < NUM_LEDS; i++) alertas[i] = false;
    bocinaActiva = false;
  }
}

void actualizarSalidas() {
  for (int i = 0; i < NUM_LEDS; i++) {
    digitalWrite(ledPins[i], alertas[i] ? HIGH : LOW);
  }
  if (bocinaActiva) {
    tone(pinBocina, FREQ_ALARMA);
  } else {
    noTone(pinBocina);
  }
}

void leerTemperatura() {
  if (millis() - ultimaTemp >= 1000) {
    ultimaTemp = millis();
    temperatura = sensors.getTempCByIndex(0);
    sensors.requestTemperatures();
  }
}

void actualizarLCD() {
  if (millis() - ultimoLCD < 500) return;
  ultimoLCD = millis();

  // Linea 1: alertas activas
  char linea[17];
  if (!enlaceActivo) {
    snprintf(linea, sizeof(linea), "Sin enlace sitio");
  } else {
    linea[0] = '\0';
    bool hayAlerta = false;
    for (int i = 0; i < NUM_LEDS; i++) {
      if (alertas[i]) {
        if (strlen(linea) + strlen(nombres[i]) + 1 < sizeof(linea)) {
          strcat(linea, nombres[i]);
          strcat(linea, " ");
        }
        hayAlerta = true;
      }
    }
    if (!hayAlerta) snprintf(linea, sizeof(linea), "Sitio: todo OK");
  }
  lcd.setCursor(0, 0);
  lcd.print(linea);
  for (size_t i = strlen(linea); i < 16; i++) lcd.print(' ');

  // Linea 2: temperatura local del brazalete
  lcd.setCursor(0, 1);
  lcd.print("T:");
  if (temperatura == -127.0) {
    lcd.print("ERR");
  } else {
    lcd.print(temperatura, 1);
    lcd.print((char)223);
    lcd.print("C");
  }
  lcd.print("          ");
}

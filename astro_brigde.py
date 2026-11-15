"""
astro_bridge.py - Puente híbrido sitio web -> Arduino (con Simulador Virtual automático)
Funciona CON Arduino físico conectado por USB o SIN Arduino (modo virtual en consola).
"""
import argparse
import os
import sqlite3
import sys
import time

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

BAUD = 9600
INTERVALO = 1.0   # segundos entre lecturas de la base de datos
MAX_EDAD = 8.0    # si no llegan filas nuevas en 8 s, apagar todo

# Orden de la trama = orden de los pines en astro_monitor.ino
ORDEN = ["HR", "SpO2", "RAD", "GLU", "SUENO", "HUESO", "BOCINA"]
ICONOS_LED = ["🔴 HR", "⚪ SpO2", "🟡 RAD", "🟠 GLU", "🔵 SUEÑO", "🟢 HUESO", "🔊 BOCINA"]


class DummySerial:
    """Simula el puerto Serial cuando no tienes el Arduino físico conectado a tu laptop."""
    def __init__(self, port_name="VIRTUAL-SIM"):
        self.port = port_name

    def write(self, data):
        pass

    def reset_input_buffer(self):
        pass

    def close(self):
        pass


def detectar_puerto_automatico():
    """Busca automáticamente si hay un Arduino conectado en algún puerto COM."""
    if not HAS_SERIAL:
        return "VIRTUAL"
    puertos = list(serial.tools.list_ports.comports())
    for p in puertos:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["arduino", "ch340", "usb", "serial", "cp210"]):
            return p.device
    return puertos[0].device if puertos else "COM3"


def calcular_alertas(fila):
    """Mismos umbrales que index.html: las tarjetas solo titilan en emergencia (status RED)."""
    hr, spo2, rad, glu, sleep, bone, status = fila
    emerg = (status == "RED")
    return [
        emerg and (hr > 105 or hr < 55),        # HR      -> LED rojo
        emerg and spo2 < 94,                    # SpO2    -> LED blanco
        emerg and rad > 1.3,                    # Rad     -> LED amarillo
        emerg and (glu < 70 or glu > 140),      # Glucosa -> LED naranja
        emerg and sleep < 4.5,                  # Sueno   -> LED azul
        emerg and bone < 94.0,                  # Hueso   -> LED verde
        emerg,                                  # Bocina
    ]


def trama(alertas):
    return "".join("1" if a else "0" for a in alertas) + "\n"


def dibujar_brazalete_consola(alertas):
    """Muestra en consola qué LEDs del brazalete están encendidos o apagados."""
    chips = []
    for icono, activo in zip(ICONOS_LED, alertas):
        if activo:
            chips.append(f"[{icono}: ON ⚡]")
        else:
            chips.append(f"[{icono}: off]")
    return " ".join(chips)


def leer_ultima_fila(ruta_db):
    """Devuelve (id, fila) de la lectura más reciente, o None si no se pudo leer."""
    try:
        uri = "file:" + ruta_db.replace("\\", "/") + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1.0) as conn:
            cur = conn.execute(
                "SELECT id, heart_rate, spo2, radiation_msv, glucose_mgdl, "
                "sleep_hours, bone_density_index, status_color "
                "FROM vitals ORDER BY id DESC LIMIT 1"
            )
            r = cur.fetchone()
            if r is None:
                return None
            return r[0], tuple(r[1:])
    except sqlite3.Error as e:
        print(f"[!] Esperando lecturas en base de datos ({e})...")
        return None


def abrir_puerto(puerto):
    if not HAS_SERIAL or puerto.upper() == "VIRTUAL":
        print("💡 [MODO SIMULACIÓN VIRTUAL ACTIVO] No se requiere Arduino físico conectado.")
        return DummySerial("VIRTUAL")
    try:
        arduino = serial.Serial(puerto, BAUD, timeout=1)
        time.sleep(2)  # el Arduino se reinicia al abrir el puerto
        print(f"✅ Arduino físico conectado en {puerto}.")
        return arduino
    except Exception as e:
        print(f"⚠️ No se detectó Arduino físico en {puerto} ({e}).")
        print("💡 Cambiando automáticamente a MODO BRAZALETE VIRTUAL en consola...")
        return DummySerial(puerto)


def enviar(arduino, texto, puerto):
    """Escribe en el puerto; si es virtual no falla; si es físico y se pierde, reconecta."""
    if isinstance(arduino, DummySerial):
        return arduino
    try:
        arduino.write(texto.encode("ascii"))
        arduino.reset_input_buffer()
        return arduino
    except Exception:
        print("[!] Se perdió el puerto físico, pasando a respaldo...")
        try:
            arduino.close()
            time.sleep(1)
            return abrir_puerto(puerto)
        except Exception:
            return DummySerial(puerto)


def modo_prueba(arduino, puerto):
    print("🔄 Prueba secuencial de LEDs del brazalete (Ctrl+C para salir)")
    try:
        while True:
            for i, nombre in enumerate(ORDEN):
                alertas = [False] * 7
                alertas[i] = True
                t = trama(alertas)
                arduino = enviar(arduino, t, puerto)
                print(f"Trama {t.strip()} -> Probando: {ICONOS_LED[i]}  |  {dibujar_brazalete_consola(alertas)}")
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    return arduino


def main():
    ap = argparse.ArgumentParser(description="Puente sitio web -> Arduino (Físico o Virtual)")
    # Ahora 'puerto' es opcional (nargs='?'): si no lo pones, lo detecta solo o entra en modo virtual
    ap.add_argument("puerto", nargs="?", default=None, help="Puerto serie, ej. COM3 (opcional)")
    ap.add_argument("--db", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "astronaut_health.db"),
                    help="Ruta de astronaut_health.db (por defecto, junto a este script)")
    ap.add_argument("--test", action="store_true", help="Probar cada LED sin leer el sitio")
    args = ap.parse_args()

    puerto_elegido = args.puerto or detectar_puerto_automatico()

    if not args.test and not os.path.exists(args.db):
        print(f"⚠️ Aún no existe {args.db}. Corre primero 'python app.py' en otra terminal.")
        sys.exit(1)

    arduino = abrir_puerto(puerto_elegido)
    print(f"🚀 Monitoreando telemetría de BIO-SHIELD 3D en tiempo real (Ctrl+C para salir)...")

    try:
        if args.test:
            arduino = modo_prueba(arduino, puerto_elegido)
            return

        ultimo_id = None
        ultimo_cambio = 0.0
        ultima_trama = None

        while True:
            res = leer_ultima_fila(args.db)
            ahora = time.monotonic()

            if res is not None:
                fila_id, fila = res
                if fila_id != ultimo_id:
                    ultimo_id = fila_id
                    ultimo_cambio = ahora

            sin_datos = res is None or (ahora - ultimo_cambio) > MAX_EDAD
            alertas = [False] * 7 if sin_datos else calcular_alertas(fila)
            t = trama(alertas)

            arduino = enviar(arduino, t, puerto_elegido)
            if t != ultima_trama:
                if sin_datos:
                    print(f"Trama {t.strip()}  ->  ⏸️ Sin datos nuevos (abre la página web en el navegador)")
                else:
                    activos = ", ".join(n for n, a in zip(ORDEN, alertas) if a) or "✅ Todo Nominal (LEDs apagados)"
                    print(f"\nTrama Serial: {t.strip()}  ->  {activos}")
                    print(dibujar_brazalete_consola(alertas))
                ultima_trama = t
            time.sleep(INTERVALO)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if not isinstance(arduino, DummySerial):
                arduino.write(b"0000000\n")
            arduino.close()
        except Exception:
            pass
        print("\nCerrado.")


if __name__ == "__main__":
    main()
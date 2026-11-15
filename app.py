from flask import Flask, render_template, jsonify, request, send_file
from werkzeug.utils import secure_filename
import sqlite3
import random
from datetime import datetime
import asyncio
import io
import os

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

app = Flask(__name__)
DB_NAME = "astronaut_health.db"

# Carpeta persistente para guardar los dibujos IA, videos y modelos 3D (.fbx, .obj, .glb)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

BACKEND_TRANSLATIONS = {
    "Comandante & Ing. Sistemas": "Commander & Systems Eng.",
    "Oficial Médico & Bióloga": "Medical Officer & Biologist",
    "Especialista de Misión": "Mission Specialist",
    "Ingeniero de Vuelo / EVA": "Flight Engineer / EVA",
    "Navegación & Rover": "Navigation & Rover",
    "Rutina ARED Fuerza/Hipertrofia (2h)": "ARED Strength/Hypertrophy Routine (2h)",
    "Gravedad (G)": "Gravity (G)",
    "Lectura de Dosímetro Personal CSA": "CSA Personal Dosimeter Reading",
    "Radiación (R)": "Radiation (R)",
    "Bitácora Neuro-Vestibular y Sueño": "Neuro-Vestibular & Sleep Log",
    "Aislamiento (I)": "Isolation (I)",
    "Control Metabólico y Vitamina D": "Metabolic & Vitamin D Control",
    "Entorno Hostil (E)": "Hostile Environment (E)",
    "Nave (Tránsito a Marte)": "Spacecraft (Mars Transit)"
}

habitat_state = {
    "temp_c": 22.4,
    "air_quality_ppm": 410,
    "smoke_detected": False,
    "light_lux": 650,
    "buzzer_active": False
}

manual_overrides = {}
crew_emergency_states = {}

def translate_text(text, lang):
    if lang == 'en':
        return BACKEND_TRANSLATIONS.get(text, text)
    return text

def get_astro_health_summary(astro_id):
    em_state = crew_emergency_states.get(astro_id, {"active": False, "disease": "cardio"})
    ovr = manual_overrides.get(astro_id)
    if em_state.get("active"):
        return "RED", em_state.get("disease", "cardio"), "EMERGENCY"
    if ovr:
        g = ovr.get("glucose", 95)
        s = ovr.get("sleep", 7.5)
        m = ovr.get("mood", 8)
        if g < 70 or g > 140 or s < 4.0 or m <= 3:
            return "RED", em_state.get("disease", "hypoxia"), "CLINICAL_ALERT"
        elif g > 115 or s < 6.0 or m <= 5:
            return "YELLOW", em_state.get("disease", "cardio"), "WARNING"
    return "GREEN", em_state.get("disease", "cardio"), "OPTIMAL"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS astronauts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                role TEXT,
                gender TEXT DEFAULT 'M',
                age INTEGER,
                height_cm REAL,
                weight_kg REAL,
                blood_type TEXT,
                base_hr INTEGER,
                bone_base REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id INTEGER,
                timestamp TEXT,
                environment TEXT,
                heart_rate INTEGER,
                spo2 INTEGER,
                radiation_msv REAL,
                glucose_mgdl INTEGER,
                sleep_hours REAL,
                mood_score INTEGER,
                bone_density_index REAL,
                status_color TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                astronaut_id INTEGER,
                title TEXT,
                hazard_type TEXT,
                xp_reward INTEGER,
                completed INTEGER DEFAULT 0
            )
        ''')

        # NUEVA TABLA PARA GUARDAR PERMANENTEMENTE DIBUJOS IA, VIDEOS Y MODELOS 3D
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_media (
                media_key TEXT PRIMARY KEY,
                file_url TEXT,
                media_type TEXT,
                updated_at TEXT
            )
        ''')

        cursor.execute("SELECT COUNT(*) FROM astronauts")
        if cursor.fetchone()[0] == 0:
            crew = [
                ("Cmdr. Shadow Cepeda", "Comandante & Ing. Sistemas", "M", 20, 178.0, 82.0, "O+", 64, 98.2),
                ("Dra. Elena Vance", "Oficial Médico & Bióloga", "F", 34, 164.0, 58.0, "A-", 72, 95.8),
                ("Esp. Kamila", "Especialista de Misión", "F", 21, 163.0, 60.0, "O+", 68, 97.4),
                ("Esp. Marcus Vance", "Ingeniero de Vuelo / EVA", "M", 29, 188.0, 96.0, "B+", 62, 97.1),
                ("Piloto Kenji Sato", "Navegación & Rover", "M", 31, 172.0, 68.0, "AB+", 70, 96.0)
            ]
            cursor.executemany('''
                INSERT INTO astronauts (name, role, gender, age, height_cm, weight_kg, blood_type, base_hr, bone_base)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', crew)

            for astro_id in range(1, 6):
                default_missions = [
                    (astro_id, "Rutina ARED Fuerza/Hipertrofia (2h)", "Gravedad (G)", 150, 0),
                    (astro_id, "Lectura de Dosímetro Personal CSA", "Radiación (R)", 100, 0),
                    (astro_id, "Bitácora Neuro-Vestibular y Sueño", "Aislamiento (I)", 100, 0),
                    (astro_id, "Control Metabólico y Vitamina D", "Entorno Hostil (E)", 80, 0)
                ]
                cursor.executemany('''
                    INSERT INTO missions (astronaut_id, title, hazard_type, xp_reward, completed)
                    VALUES (?, ?, ?, ?, ?)
                ''', default_missions)
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

# ENDPOINT PARA SUBIR Y GUARDAR EN BASE DE DATOS LOS DIBUJOS IA, VIDEOS O MODELOS 3D (.FBX, .OBJ, .GLB)
@app.route('/api/upload_media', methods=['GET', 'POST'])
def handle_upload_media():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            if 'file' not in request.files:
                return jsonify({"error": "No file"}), 400
            f = request.files['file']
            media_key = request.form.get('media_key', 'default_key')
            media_type = request.form.get('media_type', 'image')
            if f.filename == '':
                return jsonify({"error": "Empty filename"}), 400

            ext = os.path.splitext(f.filename)[1].lower()
            safe_name = secure_filename(f"{media_key}_{int(datetime.now().timestamp())}{ext}")
            save_path = os.path.join(UPLOAD_FOLDER, safe_name)
            f.save(save_path)
            file_url = f"/static/uploads/{safe_name}"

            cursor.execute('''
                INSERT INTO custom_media (media_key, file_url, media_type, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(media_key) DO UPDATE SET
                    file_url = excluded.file_url,
                    media_type = excluded.media_type,
                    updated_at = excluded.updated_at
            ''', (media_key, file_url, media_type, datetime.now().strftime("%H:%M:%S")))
            conn.commit()
            return jsonify({"status": "ok", "media_key": media_key, "file_url": file_url, "media_type": media_type})

        cursor.execute("SELECT media_key, file_url, media_type FROM custom_media")
        media_dict = {r[0]: {"url": r[1], "type": r[2]} for r in cursor.fetchall()}
        return jsonify(media_dict)

@app.route('/api/astronauts', methods=['GET', 'POST'])
def handle_astronauts():
    lang = request.args.get('lang', 'en')
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            data = request.json
            action = data.get('action', 'create')

            if action == 'update_body':
                cursor.execute('''
                    UPDATE astronauts SET height_cm = ?, weight_kg = ?, gender = ? WHERE id = ?
                ''', (float(data['height_cm']), float(data['weight_kg']), data.get('gender', 'M'), int(data['id'])))

            elif action == 'edit_full':
                cursor.execute('''
                    UPDATE astronauts 
                    SET name = ?, role = ?, gender = ?, height_cm = ?, weight_kg = ?, blood_type = ?
                    WHERE id = ?
                ''', (
                    data['name'], data['role'], data.get('gender', 'M'),
                    float(data['height_cm']), float(data['weight_kg']),
                    data.get('blood_type', 'O+'), int(data['id'])
                ))

            elif action == 'set_emergency':
                a_id = int(data['id'])
                is_active = bool(data.get('active', False))
                dis = data.get('disease', 'cardio')
                crew_emergency_states[a_id] = {"active": is_active, "disease": dis}
                if not is_active:
                    manual_overrides.pop(a_id, None)

            elif action == 'delete':
                astro_id = int(data['id'])
                cursor.execute("DELETE FROM astronauts WHERE id = ?", (astro_id,))
                cursor.execute("DELETE FROM missions WHERE astronaut_id = ?", (astro_id,))
                cursor.execute("DELETE FROM vitals WHERE astronaut_id = ?", (astro_id,))
                manual_overrides.pop(astro_id, None)
                crew_emergency_states.pop(astro_id, None)

            else:
                cursor.execute('''
                    INSERT INTO astronauts (name, role, gender, age, height_cm, weight_kg, blood_type, base_hr, bone_base)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 70, 97.0)
                ''', (data['name'], data['role'], data.get('gender', 'M'), int(data.get('age', 22)), float(data['height_cm']), float(data['weight_kg']), data.get('blood_type', 'O+')))
                new_id = cursor.lastrowid
                for title, haz, xp in [
                    ("Rutina ARED Fuerza/Hipertrofia (2h)", "Gravedad (G)", 150),
                    ("Lectura de Dosímetro Personal CSA", "Radiación (R)", 100),
                    ("Bitácora Neuro-Vestibular y Sueño", "Aislamiento (I)", 100)
                ]:
                    cursor.execute('INSERT INTO missions (astronaut_id, title, hazard_type, xp_reward, completed) VALUES (?, ?, ?, ?, 0)', (new_id, title, haz, xp))
            conn.commit()

        cursor.execute("SELECT id, name, role, gender, age, height_cm, weight_kg, blood_type, base_hr, bone_base FROM astronauts")
        rows = cursor.fetchall()
        crew_list = []
        for r in rows:
            a_id = r[0]
            h_m = r[5] / 100.0
            bmi = round(r[6] / (h_m * h_m), 1)
            health_status, active_dis, alert_reason = get_astro_health_summary(a_id)
            ovr = manual_overrides.get(a_id)
            crew_list.append({
                "id": a_id, "name": r[1], "role": translate_text(r[2], lang), "raw_role": r[2],
                "gender": r[3], "age": r[4], "height_cm": r[5], "weight_kg": r[6],
                "blood_type": r[7], "base_hr": r[8], "bone_base": r[9], "bmi": bmi,
                "health_status": health_status,
                "active_disease": active_dis,
                "alert_reason": alert_reason,
                "manual_override": ovr
            })
    return jsonify(crew_list)

@app.route('/api/vitals', methods=['GET'])
def get_vitals():
    astro_id = int(request.args.get('astronaut_id', 1))
    req_mode = request.args.get('mode', 'normal')
    env = request.args.get('env', 'Nave (Tránsito a Marte)')
    req_disease = request.args.get('disease', 'cardio')

    em_state = crew_emergency_states.get(astro_id, {"active": False, "disease": req_disease})
    is_emerg = em_state.get("active", False) or (req_mode == 'emergency')
    disease = em_state.get("disease", req_disease) if em_state.get("active") else req_disease

    rad_base = 0.85 if "Marte" in env else (0.45 if "Gateway" in env else 0.35)

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT base_hr, bone_base FROM astronauts WHERE id = ?", (astro_id,))
        row = cursor.fetchone()
        base_hr = row[0] if row else 70
        bone_base = row[1] if row else 96.0

        override = manual_overrides.get(astro_id)

        if is_emerg:
            if disease == 'hypoxia':
                hr = random.randint(122, 142)
                spo2 = random.randint(76, 84)
            elif disease == 'dcs':
                hr = random.randint(112, 132)
                spo2 = random.randint(87, 91)
            elif disease == 'eva':
                hr = random.randint(135, 155)
                spo2 = random.randint(89, 93)
            elif disease == 'sans':
                hr = random.randint(92, 108)
                spo2 = random.randint(94, 97)
            else:
                hr = random.randint(148, 174)
                spo2 = random.randint(82, 88)
            rad = round(rad_base + random.uniform(1.6, 2.8), 2)
            glucose = override["glucose"] if override else random.randint(145, 180)
            sleep = override["sleep"] if override else 4.0
            mood = override["mood"] if override else 3
            bone = round(bone_base - 4.5, 1)
            status = "RED"
        else:
            hr = random.randint(base_hr - 3, base_hr + 8)
            spo2 = random.randint(96, 99)
            rad = round(rad_base + random.uniform(0.05, 0.22), 2)
            glucose = override["glucose"] if override else random.randint(88, 104)
            sleep = override["sleep"] if override else 7.5
            mood = override["mood"] if override else 8
            bone = bone_base

            if glucose < 70 or glucose > 140 or sleep < 4.0 or mood <= 3:
                status = "RED"
                hr = random.randint(118, 136)
            elif glucose > 115 or sleep < 6.0 or mood <= 5 or hr >= 95 or rad >= 1.2:
                status = "YELLOW"
            else:
                status = "GREEN"

        now = datetime.now().strftime("%H:%M:%S")
        cursor.execute('''
            INSERT INTO vitals (astronaut_id, timestamp, environment, heart_rate, spo2, radiation_msv, glucose_mgdl, sleep_hours, mood_score, bone_density_index, status_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (astro_id, now, env, hr, spo2, rad, glucose, sleep, mood, bone, status))
        conn.commit()

        cursor.execute('''
            SELECT timestamp, heart_rate, spo2, glucose_mgdl 
            FROM vitals WHERE astronaut_id = ? ORDER BY id DESC LIMIT 12
        ''', (astro_id,))
        history = cursor.fetchall()[::-1]

    return jsonify({
        "current": {
            "timestamp": now, "environment": env, "heart_rate": hr, "spo2": spo2,
            "radiation_msv": rad, "glucose_mgdl": glucose, "sleep_hours": sleep,
            "mood_score": mood, "bone_density_index": bone, "status_color": status,
            "has_manual_override": bool(override),
            "server_emergency": em_state.get("active", False),
            "active_disease": disease
        },
        "history": {
            "labels": [r[0] for r in history],
            "hr": [r[1] for r in history],
            "spo2": [r[2] for r in history],
            "glucose": [r[3] for r in history]
        }
    })

@app.route('/api/manual_entry', methods=['POST'])
def manual_entry():
    data = request.json
    astro_id = int(data.get('astronaut_id', 1))
    if data.get('action') == 'clear':
        manual_overrides.pop(astro_id, None)
        crew_emergency_states.pop(astro_id, None)
        return jsonify({"status": "cleared"})

    glucose = int(data.get('glucose', 95))
    sleep = float(data.get('sleep', 7.5))
    mood = int(data.get('mood', 8))
    env = data.get('environment', 'Nave (Tránsito a Marte)')

    manual_overrides[astro_id] = {
        "glucose": glucose,
        "sleep": sleep,
        "mood": mood
    }

    hr = random.randint(118, 135) if (glucose < 70 or glucose > 140 or sleep < 4.0) else 75
    status = "RED" if (glucose > 140 or glucose < 70 or sleep < 4.0 or mood <= 3) else ("YELLOW" if (glucose > 110 or sleep < 6.0) else "GREEN")

    now = datetime.now().strftime("%H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vitals (astronaut_id, timestamp, environment, heart_rate, spo2, radiation_msv, glucose_mgdl, sleep_hours, mood_score, bone_density_index, status_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (astro_id, now, env, hr, 98, 0.45, glucose, sleep, mood, 96.5, status))
        conn.commit()

    return jsonify({"status": "ok", "evaluated_color": status})

@app.route('/api/missions', methods=['GET', 'POST'])
def handle_missions():
    astro_id = int(request.args.get('astronaut_id', 1))
    lang = request.args.get('lang', 'en')
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            mission_id = request.json.get('id')
            cursor.execute("UPDATE missions SET completed = CASE WHEN completed = 0 THEN 1 ELSE 0 END WHERE id = ?", (mission_id,))
            conn.commit()
            astro_id = int(request.json.get('astronaut_id', astro_id))

        cursor.execute("SELECT id, title, hazard_type, xp_reward, completed FROM missions WHERE astronaut_id = ?", (astro_id,))
        missions = [
            {
                "id": r[0],
                "title": translate_text(r[1], lang),
                "hazard": translate_text(r[2], lang),
                "xp": r[3],
                "completed": bool(r[4])
            }
            for r in cursor.fetchall()
        ]
        total_xp = sum(m["xp"] for m in missions if m["completed"])
    return jsonify({"missions": missions, "total_xp": total_xp})

@app.route('/api/habitat_sensors', methods=['GET', 'POST'])
def handle_habitat_sensors():
    global habitat_state
    if request.method == 'POST':
        data = request.json
        habitat_state["temp_c"] = float(data.get("temp_c", habitat_state["temp_c"]))
        habitat_state["air_quality_ppm"] = int(data.get("air_quality_ppm", habitat_state["air_quality_ppm"]))
        habitat_state["smoke_detected"] = bool(data.get("smoke_detected", False))
        habitat_state["light_lux"] = int(data.get("light_lux", habitat_state["light_lux"]))
        habitat_state["buzzer_active"] = (
            habitat_state["smoke_detected"] or 
            habitat_state["temp_c"] > 35.0 or 
            habitat_state["air_quality_ppm"] > 1200
        )
    return jsonify(habitat_state)

@app.route('/api/osdr_datasets', methods=['GET'])
def get_osdr_datasets():
    lang = request.args.get('lang', 'en')
    if lang == 'en':
        datasets = [
            {
                "id": "OSD-570",
                "title": "NASA OSDR: Cardiovascular Response to Cosmic Radiation",
                "metric": "Arrhythmia Risk / CSA Dosimetry",
                "baseline": "0.42 mSv/d",
                "anomaly_threshold": "> 1.50 mSv/d (Solar Storm Alert)",
                "finding": "Increased arterial stiffness after 60 days outside the magnetosphere."
            },
            {
                "id": "OSD-51",
                "title": "NASA OSDR: Muscle Atrophy & Bone Loss in Microgravity",
                "metric": "Bone Mineral Density (Femur/Spine)",
                "baseline": "98.0%",
                "anomaly_threshold": "< 90.0% (Fracture risk upon Mars landing)",
                "finding": "1.2% to 1.5% monthly loss without ARED exercise countermeasures."
            },
            {
                "id": "OSD-242",
                "title": "NASA HRP: Spaceflight-Associated Neuro-ocular Syndrome (SANS)",
                "metric": "Optic Nerve Sheath Diameter (Ultrasound)",
                "baseline": "4.8 mm",
                "anomaly_threshold": "> 5.8 mm (Papilledema due to fluid shift)",
                "finding": "Fluid shifts toward the head in zero gravity, putting pressure on the retina."
            }
        ]
    else:
        datasets = [
            {
                "id": "OSD-570",
                "title": "NASA OSDR: Respuesta Cardiovascular a Radiación Cósmica",
                "metric": "Riesgo Arritmia / Dosimetría CSA",
                "baseline": "0.42 mSv/d",
                "anomaly_threshold": "> 1.50 mSv/d (Alerta Tormenta Solar)",
                "finding": "Incremento de rigidez arterial tras 60 días fuera de la magnetósfera."
            },
            {
                "id": "OSD-51",
                "title": "NASA OSDR: Atrofia Muscular y Pérdida Ósea en Microgravedad",
                "metric": "Densidad Mineral Ósea (Fémur/Columna)",
                "baseline": "98.0%",
                "anomaly_threshold": "< 90.0% (Riesgo de fractura al aterrizar en Marte)",
                "finding": "Pérdida de 1.2% a 1.5% mensual sin contramedida de ejercicio ARED."
            },
            {
                "id": "OSD-242",
                "title": "NASA HRP: Síndrome Neuro-Ocular Asociado a Vuelos Espaciales (SANS)",
                "metric": "Diámetro de Vaina del Nervio Óptico (Ultrasonido)",
                "baseline": "4.8 mm",
                "anomaly_threshold": "> 5.8 mm (Edema de papila por desplazamiento de fluidos)",
                "finding": "El fluido sube a la cabeza en gravedad cero presionando la retina."
            }
        ]
    return jsonify(datasets)

@app.route('/api/tts', methods=['GET'])
def neural_tts():
    text = request.args.get('text', 'Protocol activated.')
    lang = request.args.get('lang', 'en')
    voice = 'en-US-AriaNeural' if lang == 'en' else request.args.get('voice', 'es-MX-DaliaNeural')

    if not HAS_EDGE_TTS:
        return jsonify({"error": "edge-tts not installed"}), 501

    async def generate_audio():
        communicate = edge_tts.Communicate(text, voice, rate="+5%")
        audio_stream = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])
        audio_stream.seek(0)
        return audio_stream

    audio_data = asyncio.run(generate_audio())
    return send_file(audio_data, mimetype="audio/mpeg")

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True, port=5000) 


```markdown
# MEXALIENS // BIO-SHIELD 3D (A.R.E.S.)

**Astronaut Remote Evaluation System (A.R.E.S.)** is an autonomous biometric monitoring, cabin telemetry, and 3D-assisted medical triage platform developed by team **MexAliens** for the **NASA International Space Apps Challenge 2026** in Puebla, Mexico.

## Description

During deep-space missions to the Moon or Mars, communication latency with Earth reaches up to 20 minutes each way (40 minutes round-trip). When acute medical emergencies occur without a physician onboard, waiting for Mission Control is not viable.

BIO-SHIELD 3D enables zero-latency self-evaluation and immediate triage by integrating:
- **3D Anatomical Digital Twin (8 Maya `.FBX` Morphs):** Sculpted in ZBrush and rigged in Autodesk Maya (`NASA_male`, `NASA_female`, `NASA_skiny_`, `NASA_fat_`, `NASA_tall_`). Reflects biological sex, height, weight, and BMI, using custom WebGL shaders (`onBeforeCompile`) to isolate injured zones (**Head**, **Torso**, **Limbs**) in red.
- **Instant Visual Safety Placards & 9 CPR Methods:** Zero-second-read emergency action cards for 5 critical conditions (Cardiovascular Collapse with 9 Microgravity CPR Methods, Decompression Sickness, Acute Hypoxia, EVA Injuries, and SANS), a 110 BPM CPR metronome, POCUS ultrasound simulator, and hands-free bilingual AI voice triage.
- **Wearable Hardware & Cross-Crew Alert Network:** Real-time SQLite synchronization across screens and an Arduino circuit (`astro_brigde.py` + `astro_monitor.ino`) driving a 16x2 I2C LCD, DS18B20 temperature sensor, 6 color-coded vital LEDs, and an active buzzer.

## Technologies Used

- **Frontend & 3D:** HTML5, Tailwind CSS, JavaScript (ES6+), Three.js (`FBXLoader`, custom GLSL zone shaders), Chart.js, MediaDevices Vision API (webcam fatigue scan), Web Speech API (live voice transcription), ZBrush, and Autodesk Maya.
- **Backend & AI:** Python (Flask `app.py`), SQLite (`astronaut_health.db`), Microsoft Azure Neural TTS (`edge-tts`), Google Gemini, and Anthropic Claude.
- **Hardware:** Arduino (Uno / Nano) in C/C++ (`Wire.h`, `LiquidCrystal_I2C.h`, `OneWire.h`, `DallasTemperature.h`) connected via Python `PySerial` (`astro_brigde.py` with automatic virtual console fallback).

## Installation & Quick Start

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/LuisCepeda7/MexAliens.git](https://github.com/LuisCepeda7/MexAliens.git)
   cd MexAliens

```

2. **Install Python dependencies:**
```bash
pip install flask werkzeug pyserial edge-tts requests

```


3. **Start the web server:**
```bash
python app.py

```


Open **`http://localhost:5000`** in your browser.
4. **Run the Arduino / Virtual Wristband Bridge (Optional):**
```bash
python astro_brigde.py

```


*(Automatically connects to physical Arduino via USB or runs the virtual LED simulator in console).*

## Usage

1. **Crew & 3D Morphing:** Select a crew member from the **Crew Roster** or click **3D Body Config** to adjust sex, height, and weight across the 8 `.fbx` models.
2. **Live Telemetry & Voice AI:** Monitor the 6 floating vital cards and cabin sensors, or click **AI Voice Command** to ask for specific vitals (*"How is my oxygen?"*) or daily protocol tasks.
3. **Emergency Triage:** Click **Simulate Emergency** or any 3D body zone to trigger red anatomical zoning, cross-crew alerts, the 110 BPM CPR metronome, and instant visual action placards.
4. **Daily Protocol & POCUS:** Complete countermeasures for XP, log capillary glucose/sleep, or open the **POCUS Ultrasound** and **NASA OSDR** modals.

## Project Structure

* `app.py`: Flask backend, REST APIs, clinical triage rules, and neural TTS.
* `astro_brigde.py`: PySerial SQLite-to-Arduino bridge (7-bit frame: `HR, SpO2, RAD, GLU, SLEEP, BONE, BUZZER`).
* `astro_monitor.ino`: Arduino firmware for I2C LCD, DS18B20, 6 LEDs, and buzzer.
* `templates/index.html`: 3D WebGL HUD, GLSL shaders, Chart.js telemetry, and emergency modals.
* `static/models/`: 8 ZBrush/Maya `.fbx` anatomical meshes.
* `astronaut_health.db`: SQLite database for crew profiles, vitals, and uploaded media.

## Official Scientific References

1. **Casas, A. (2026).** *Risks of human spaceflight.* NASA HRP: `https://www.nasa.gov/hrp/risks/`
2. **Robles RMA, Carrillo ER (2024).** *Reanimación cardiopulmonar en microgravedad y en los vuelos espaciales tripulados.* Med Crit. 2024;38(1):40-50.
3. **NASA OSDR & CSA:** Reference datasets `OSD-570`, `OSD-51`, and `OSD-242`.

## AI Tools Disclosure

Generative AI tools (**Google Gemini**, **Anthropic Claude**, **Microsoft Azure Neural TTS**, and **Web Speech API**) were used as methodological support for code structuring, WebGL shader zoning, NASA medical literature synthesis, and real-time voice guidance.

## Authors - Team MexAliens

* **Claudia Angélica Cansino Pérez** — clau10angelica@gmail.com
* **Gael Barranco Macip** — gaelmacip23ball@gmail.com
* **Isabel Miroslava González Juárez** — imiroslavagj@gmail.com
* **Jessica Cuahutle Romano** — jessica.cuahutle.r@gmail.com
* **Kamilah Astrid Guerrero Uribe** — kamilahguerrero1506@gmail.com
* **Luis Gilberto Cepeda Pérez** — luiscepeda136@gmail.com

```

```

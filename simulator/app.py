"""
MSFS Simulator Mock - A web UI to simulate aircraft state for testing.

Run this, then run the checklist app with:
    PYTHONPATH=simulator python run.py
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import requests

app = FastAPI(title="MSFS Simulator Mock")


class AircraftState(BaseModel):
    """Current aircraft state."""
    # Position & Movement
    sim_on_ground: bool = True
    altitude_agl: float = 0.0
    altitude_msl: float = 0.0
    vertical_speed: float = 0.0
    indicated_airspeed: float = 0.0
    ground_velocity: float = 0.0

    # Controls
    gear_handle_position: bool = True  # True = down
    flaps_percent: float = 0.0
    spoilers_armed: bool = False
    parking_brake: bool = True

    # Engines
    eng1_running: bool = False
    eng2_running: bool = False
    eng1_n1: float = 0.0
    eng2_n1: float = 0.0

    # Lights
    light_beacon: bool = False
    light_nav: bool = False
    light_landing: bool = False
    light_taxi: bool = False
    light_strobe: bool = False

    # Systems
    transponder_state: int = 0  # 0=off, 1=standby, 2=test, 3=on, 4=alt
    autopilot_master: bool = False
    seatbelt_sign: bool = False
    rudder_trim_pct: float = 0.0  # -100 to 100, 0 = neutral
    fuel_total_lbs: float = 0.0  # in pounds (checklist converts to kg)
    altimeter_hpa: float = 1013.0


# Global state
state = AircraftState()

# Preset phases for quick testing
PHASE_PRESETS = {
    "cold_dark": AircraftState(
        sim_on_ground=True, parking_brake=True, eng1_running=False, eng2_running=False,
        gear_handle_position=True, flaps_percent=0, spoilers_armed=False,
        seatbelt_sign=False, fuel_total_lbs=15000, altimeter_hpa=1013
    ),
    "before_start": AircraftState(
        sim_on_ground=True, parking_brake=True, eng1_running=False, eng2_running=False,
        gear_handle_position=True, flaps_percent=0, spoilers_armed=False,
        light_beacon=True, seatbelt_sign=True, fuel_total_lbs=15000, altimeter_hpa=1013
    ),
    "after_start": AircraftState(
        sim_on_ground=True, parking_brake=True, eng1_running=True, eng2_running=True,
        eng1_n1=20, eng2_n1=20, gear_handle_position=True, flaps_percent=0,
        spoilers_armed=False, light_beacon=True, seatbelt_sign=True,
        fuel_total_lbs=15000, altimeter_hpa=1013
    ),
    "taxi": AircraftState(
        sim_on_ground=True, parking_brake=False, eng1_running=True, eng2_running=True,
        eng1_n1=25, eng2_n1=25, ground_velocity=15, gear_handle_position=True,
        flaps_percent=15, spoilers_armed=False, light_beacon=True, light_taxi=True,
        light_nav=True, seatbelt_sign=True, fuel_total_lbs=14800, altimeter_hpa=1013
    ),
    "lineup": AircraftState(
        sim_on_ground=True, parking_brake=False, eng1_running=True, eng2_running=True,
        eng1_n1=25, eng2_n1=25, ground_velocity=0, gear_handle_position=True,
        flaps_percent=15, spoilers_armed=False, light_beacon=True, light_strobe=True,
        light_landing=True, light_nav=True, transponder_state=4, seatbelt_sign=True,
        fuel_total_lbs=14700, altimeter_hpa=1013
    ),
    "climb": AircraftState(
        sim_on_ground=False, altitude_agl=5000, altitude_msl=6000, vertical_speed=2000,
        indicated_airspeed=250, ground_velocity=280, eng1_running=True, eng2_running=True,
        eng1_n1=85, eng2_n1=85, gear_handle_position=False, flaps_percent=0,
        spoilers_armed=False, light_beacon=True, light_strobe=True, light_landing=True,
        light_nav=True, transponder_state=4, seatbelt_sign=True,
        fuel_total_lbs=14000, altimeter_hpa=1013
    ),
    "cruise": AircraftState(
        sim_on_ground=False, altitude_agl=35000, altitude_msl=36000, vertical_speed=0,
        indicated_airspeed=280, ground_velocity=450, eng1_running=True, eng2_running=True,
        eng1_n1=80, eng2_n1=80, gear_handle_position=False, flaps_percent=0,
        spoilers_armed=False, light_beacon=True, light_strobe=True, light_nav=True,
        transponder_state=4, autopilot_master=True, seatbelt_sign=False,
        fuel_total_lbs=10000, altimeter_hpa=1013
    ),
    "descent": AircraftState(
        sim_on_ground=False, altitude_agl=15000, altitude_msl=16000, vertical_speed=-1500,
        indicated_airspeed=300, ground_velocity=380, eng1_running=True, eng2_running=True,
        eng1_n1=50, eng2_n1=50, gear_handle_position=False, flaps_percent=0,
        spoilers_armed=False, light_beacon=True, light_strobe=True, light_nav=True,
        transponder_state=4, autopilot_master=True, seatbelt_sign=True,
        fuel_total_lbs=6000, altimeter_hpa=1013
    ),
    "approach": AircraftState(
        sim_on_ground=False, altitude_agl=2500, altitude_msl=3500, vertical_speed=-700,
        indicated_airspeed=180, ground_velocity=200, eng1_running=True, eng2_running=True,
        eng1_n1=55, eng2_n1=55, gear_handle_position=True, flaps_percent=25,
        spoilers_armed=True, light_beacon=True, light_strobe=True, light_landing=True,
        light_nav=True, transponder_state=4, seatbelt_sign=True,
        fuel_total_lbs=5000, altimeter_hpa=1013
    ),
    "landing": AircraftState(
        sim_on_ground=False, altitude_agl=500, altitude_msl=1500, vertical_speed=-700,
        indicated_airspeed=145, ground_velocity=150, eng1_running=True, eng2_running=True,
        eng1_n1=60, eng2_n1=60, gear_handle_position=True, flaps_percent=40,
        spoilers_armed=True, light_beacon=True, light_strobe=True, light_landing=True,
        light_nav=True, transponder_state=4, seatbelt_sign=True,
        fuel_total_lbs=4800, altimeter_hpa=1013
    ),
    "after_landing": AircraftState(
        sim_on_ground=True, ground_velocity=25, eng1_running=True, eng2_running=True,
        eng1_n1=30, eng2_n1=30, gear_handle_position=True, flaps_percent=0,
        spoilers_armed=False, parking_brake=False, light_beacon=True, light_taxi=True,
        light_nav=True, transponder_state=3, seatbelt_sign=True,
        fuel_total_lbs=4500, altimeter_hpa=1013
    ),
    "parking": AircraftState(
        sim_on_ground=True, ground_velocity=0, eng1_running=False, eng2_running=False,
        gear_handle_position=True, flaps_percent=0, spoilers_armed=False,
        parking_brake=True, light_beacon=False, light_nav=True, seatbelt_sign=False,
        fuel_total_lbs=4500, altimeter_hpa=1013
    ),
}


@app.get("/api/state")
async def get_state():
    """Get current aircraft state."""
    return state.model_dump()


@app.post("/api/state")
async def set_state(new_state: AircraftState):
    """Update aircraft state."""
    global state
    state = new_state
    return {"success": True}


# Presets that represent post-flight states (need _was_airborne = True)
POST_FLIGHT_PRESETS = {"climb", "cruise", "descent", "approach", "landing", "after_landing", "parking"}

@app.post("/api/preset/{preset_name}")
async def apply_preset(preset_name: str):
    """Apply a preset phase configuration."""
    global state
    if preset_name in PHASE_PRESETS:
        state = PHASE_PRESETS[preset_name].model_copy()

        # For post-flight presets, tell checklist app we've been airborne
        if preset_name in POST_FLIGHT_PRESETS:
            try:
                requests.post("http://localhost:2549/api/set-airborne", timeout=1)
            except Exception:
                pass  # Checklist app might not be running

        return {"success": True, "preset": preset_name}
    return {"success": False, "error": "Unknown preset"}


@app.get("/", response_class=HTMLResponse)
async def ui():
    """Serve the simulator UI."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>MSFS Simulator Mock</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }
        h1 {
            text-align: center;
            margin-bottom: 20px;
            color: #0f0;
            text-shadow: 0 0 10px #0f0;
        }
        .container { max-width: 900px; margin: 0 auto; }

        /* Presets */
        .presets {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 24px;
            padding: 16px;
            background: #252540;
            border-radius: 8px;
        }
        .presets button {
            padding: 8px 16px;
            background: #3a3a5c;
            border: 1px solid #4a4a6c;
            color: #fff;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
        }
        .presets button:hover { background: #4a4a7c; }
        .presets button.active { background: #0a0; border-color: #0f0; }

        /* Sections */
        .section {
            background: #252540;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .section h2 {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #888;
            margin-bottom: 12px;
            border-bottom: 1px solid #3a3a5c;
            padding-bottom: 8px;
        }

        /* Controls grid */
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }
        .control {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .control label {
            font-size: 12px;
            color: #aaa;
        }
        .control input[type="number"],
        .control input[type="range"] {
            padding: 8px;
            background: #1a1a2e;
            border: 1px solid #3a3a5c;
            border-radius: 4px;
            color: #fff;
            font-family: monospace;
        }
        .control input[type="number"] { width: 100%; }

        /* Toggle switches */
        .toggle {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            background: #1a1a2e;
            border-radius: 4px;
            cursor: pointer;
        }
        .toggle.on { background: #0a3a0a; border: 1px solid #0f0; }
        .toggle .indicator {
            width: 40px;
            height: 22px;
            background: #333;
            border-radius: 11px;
            position: relative;
        }
        .toggle .indicator::after {
            content: '';
            position: absolute;
            width: 18px;
            height: 18px;
            background: #666;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: all 0.2s;
        }
        .toggle.on .indicator { background: #0a0; }
        .toggle.on .indicator::after { left: 20px; background: #0f0; }

        /* Status bar */
        .status {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 12px;
            background: #0a0a15;
            border-top: 1px solid #3a3a5c;
            display: flex;
            justify-content: center;
            gap: 24px;
            font-family: monospace;
        }
        .status span { color: #0f0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MSFS SIMULATOR</h1>

        <div class="presets">
            <button onclick="loadPreset('cold_dark')">Cold & Dark</button>
            <button onclick="loadPreset('before_start')">Before Start</button>
            <button onclick="loadPreset('after_start')">After Start</button>
            <button onclick="loadPreset('taxi')">Taxi</button>
            <button onclick="loadPreset('lineup')">Line-Up</button>
            <button onclick="loadPreset('climb')">Climb</button>
            <button onclick="loadPreset('cruise')">Cruise</button>
            <button onclick="loadPreset('descent')">Descent</button>
            <button onclick="loadPreset('approach')">Approach</button>
            <button onclick="loadPreset('landing')">Landing</button>
            <button onclick="loadPreset('after_landing')">After Landing</button>
            <button onclick="loadPreset('parking')">Parking</button>
        </div>

        <div class="section">
            <h2>Position & Movement</h2>
            <div class="controls">
                <div class="control">
                    <label>Altitude MSL (ft)</label>
                    <input type="number" id="altitude_msl" onchange="updateState()">
                </div>
                <div class="control">
                    <label>Altitude AGL (ft)</label>
                    <input type="number" id="altitude_agl" onchange="updateState()">
                </div>
                <div class="control">
                    <label>Vertical Speed (fpm)</label>
                    <input type="number" id="vertical_speed" onchange="updateState()">
                </div>
                <div class="control">
                    <label>IAS (kts)</label>
                    <input type="number" id="indicated_airspeed" onchange="updateState()">
                </div>
                <div class="control">
                    <label>Ground Speed (kts)</label>
                    <input type="number" id="ground_velocity" onchange="updateState()">
                </div>
                <div class="toggle" id="sim_on_ground" onclick="toggleBool('sim_on_ground')">
                    <span>On Ground</span>
                    <div class="indicator"></div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Flight Controls</h2>
            <div class="controls">
                <div class="toggle" id="gear_handle_position" onclick="toggleBool('gear_handle_position')">
                    <span>Gear Down</span>
                    <div class="indicator"></div>
                </div>
                <div class="control">
                    <label>Flaps %</label>
                    <input type="number" id="flaps_percent" min="0" max="100" onchange="updateState()">
                </div>
                <div class="toggle" id="spoilers_armed" onclick="toggleBool('spoilers_armed')">
                    <span>Spoilers Armed</span>
                    <div class="indicator"></div>
                </div>
                <div class="toggle" id="parking_brake" onclick="toggleBool('parking_brake')">
                    <span>Parking Brake</span>
                    <div class="indicator"></div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Engines</h2>
            <div class="controls">
                <div class="toggle" id="eng1_running" onclick="toggleBool('eng1_running')">
                    <span>Engine 1</span>
                    <div class="indicator"></div>
                </div>
                <div class="control">
                    <label>ENG1 N1 %</label>
                    <input type="number" id="eng1_n1" min="0" max="100" onchange="updateState()">
                </div>
                <div class="toggle" id="eng2_running" onclick="toggleBool('eng2_running')">
                    <span>Engine 2</span>
                    <div class="indicator"></div>
                </div>
                <div class="control">
                    <label>ENG2 N1 %</label>
                    <input type="number" id="eng2_n1" min="0" max="100" onchange="updateState()">
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Lights</h2>
            <div class="controls">
                <div class="toggle" id="light_beacon" onclick="toggleBool('light_beacon')">
                    <span>Beacon</span>
                    <div class="indicator"></div>
                </div>
                <div class="toggle" id="light_nav" onclick="toggleBool('light_nav')">
                    <span>NAV</span>
                    <div class="indicator"></div>
                </div>
                <div class="toggle" id="light_strobe" onclick="toggleBool('light_strobe')">
                    <span>Strobe</span>
                    <div class="indicator"></div>
                </div>
                <div class="toggle" id="light_landing" onclick="toggleBool('light_landing')">
                    <span>Landing</span>
                    <div class="indicator"></div>
                </div>
                <div class="toggle" id="light_taxi" onclick="toggleBool('light_taxi')">
                    <span>Taxi</span>
                    <div class="indicator"></div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Systems</h2>
            <div class="controls">
                <div class="toggle" id="seatbelt_sign" onclick="toggleBool('seatbelt_sign')">
                    <span>Seatbelt Sign</span>
                    <div class="indicator"></div>
                </div>
                <div class="control">
                    <label>Transponder (0=off, 1=sby, 3=on, 4=alt)</label>
                    <input type="number" id="transponder_state" min="0" max="4" onchange="updateState()">
                </div>
                <div class="toggle" id="autopilot_master" onclick="toggleBool('autopilot_master')">
                    <span>Autopilot</span>
                    <div class="indicator"></div>
                </div>
                <div class="control">
                    <label>Rudder Trim % (-100 to 100)</label>
                    <input type="number" id="rudder_trim_pct" min="-100" max="100" onchange="updateState()">
                </div>
                <div class="control">
                    <label>Fuel (lbs)</label>
                    <input type="number" id="fuel_total_lbs" onchange="updateState()">
                </div>
                <div class="control">
                    <label>Altimeter (hPa)</label>
                    <input type="number" id="altimeter_hpa" onchange="updateState()">
                </div>
            </div>
        </div>
    </div>

    <div class="status">
        <div>ALT: <span id="s_alt">0</span> ft</div>
        <div>VS: <span id="s_vs">0</span> fpm</div>
        <div>GS: <span id="s_gs">0</span> kts</div>
        <div>FUEL: <span id="s_fuel">0</span> kg</div>
    </div>

    <script>
        let state = {};

        async function loadState() {
            const resp = await fetch('/api/state');
            state = await resp.json();
            updateUI();
        }

        function updateUI() {
            // Update number inputs
            ['altitude_msl', 'altitude_agl', 'vertical_speed', 'indicated_airspeed',
             'ground_velocity', 'flaps_percent', 'eng1_n1', 'eng2_n1',
             'transponder_state', 'rudder_trim_pct', 'fuel_total_lbs', 'altimeter_hpa'].forEach(key => {
                const el = document.getElementById(key);
                if (el) el.value = state[key] || 0;
            });

            // Update toggles
            ['sim_on_ground', 'gear_handle_position', 'spoilers_armed', 'parking_brake',
             'eng1_running', 'eng2_running', 'light_beacon', 'light_nav', 'light_strobe',
             'light_landing', 'light_taxi', 'autopilot_master', 'seatbelt_sign'].forEach(key => {
                const el = document.getElementById(key);
                if (el) el.classList.toggle('on', state[key]);
            });

            // Update status bar
            document.getElementById('s_alt').textContent = Math.round(state.altitude_msl || 0);
            document.getElementById('s_vs').textContent = Math.round(state.vertical_speed || 0);
            document.getElementById('s_gs').textContent = Math.round(state.ground_velocity || 0);
            document.getElementById('s_fuel').textContent = Math.round((state.fuel_total_lbs || 0) * 0.453592);
        }

        async function updateState() {
            // Collect all values
            ['altitude_msl', 'altitude_agl', 'vertical_speed', 'indicated_airspeed',
             'ground_velocity', 'flaps_percent', 'eng1_n1', 'eng2_n1',
             'transponder_state', 'rudder_trim_pct', 'fuel_total_lbs', 'altimeter_hpa'].forEach(key => {
                const el = document.getElementById(key);
                if (el) state[key] = parseFloat(el.value) || 0;
            });

            await fetch('/api/state', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(state)
            });
            updateUI();
        }

        async function toggleBool(key) {
            state[key] = !state[key];
            await fetch('/api/state', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(state)
            });
            updateUI();
        }

        async function loadPreset(name) {
            await fetch('/api/preset/' + name, {method: 'POST'});
            await loadState();
        }

        // Initial load
        loadState();
    </script>
</body>
</html>"""


def main():
    print("\n" + "="*50)
    print("  MSFS SIMULATOR MOCK")
    print("="*50)
    print(f"\n  UI:  http://localhost:2550")
    print(f"  API: http://localhost:2550/api/state")
    print("\n  To use with checklist app:")
    print("    PYTHONPATH=simulator python run.py")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=2550)


if __name__ == "__main__":
    main()

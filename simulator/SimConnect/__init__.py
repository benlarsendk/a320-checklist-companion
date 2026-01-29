"""
Mock SimConnect library for testing without MSFS.

This module mimics the real SimConnect library interface but fetches
state from the simulator app running on localhost:2550.
"""

import requests
from typing import Any, Optional

SIMULATOR_URL = "http://localhost:2550"


class SimConnect:
    """Mock SimConnect connection."""

    def __init__(self):
        self._connected = False
        try:
            # Test connection to simulator
            resp = requests.get(f"{SIMULATOR_URL}/api/state", timeout=1)
            if resp.status_code == 200:
                self._connected = True
                print("[MockSimConnect] Connected to simulator")
        except Exception as e:
            raise ConnectionError(f"Cannot connect to simulator at {SIMULATOR_URL}: {e}")

    def exit(self):
        """Disconnect from simulator."""
        self._connected = False
        print("[MockSimConnect] Disconnected")


class AircraftRequests:
    """Mock AircraftRequests that fetches state from simulator."""

    # Map SimConnect variable names to our state keys
    VAR_MAP = {
        "SIM_ON_GROUND": "sim_on_ground",
        "PLANE_ALT_ABOVE_GROUND": "altitude_agl",
        "INDICATED_ALTITUDE": "altitude_msl",
        "VERTICAL_SPEED": "vertical_speed",
        "AIRSPEED_INDICATED": "indicated_airspeed",
        "GROUND_VELOCITY": "ground_velocity",
        "GEAR_HANDLE_POSITION": "gear_handle_position",
        "TRAILING_EDGE_FLAPS_LEFT_PERCENT": "flaps_percent",
        "SPOILERS_ARMED": "spoilers_armed",
        "BRAKE_PARKING_POSITION": "parking_brake",
        "ENG COMBUSTION:1": "eng1_running",
        "ENG COMBUSTION:2": "eng2_running",
        "TURB ENG N1:1": "eng1_n1",
        "TURB ENG N1:2": "eng2_n1",
        "LIGHT_BEACON": "light_beacon",
        "LIGHT_NAV": "light_nav",
        "LIGHT_LANDING": "light_landing",
        "LIGHT_TAXI": "light_taxi",
        "LIGHT_STROBE": "light_strobe",
        "TRANSPONDER_STATE:1": "transponder_state",
        "AUTOPILOT_MASTER": "autopilot_master",
        "CABIN SEATBELTS ALERT SWITCH": "seatbelt_sign",
        "RUDDER_TRIM_PCT": "rudder_trim_pct",
        "ENG_COMBUSTION_1": "eng1_running",
        "ENG_COMBUSTION_2": "eng2_running",
        "AUTOPILOT_MASTER": "autopilot_master",
        "FUEL_TOTAL_QUANTITY_WEIGHT": "fuel_total_lbs",
        "KOHLSMAN_SETTING_MB": "altimeter_hpa",
    }

    def __init__(self, sc: SimConnect, _time: int = 0):
        self._sc = sc
        self._state: dict = {}
        self._fetch_state()

    def _fetch_state(self) -> None:
        """Fetch current state from simulator."""
        try:
            resp = requests.get(f"{SIMULATOR_URL}/api/state", timeout=1)
            if resp.status_code == 200:
                self._state = resp.json()
        except Exception:
            pass

    def get(self, var_name: str) -> Optional[Any]:
        """Get a SimConnect variable value."""
        self._fetch_state()

        state_key = self.VAR_MAP.get(var_name)
        if state_key and state_key in self._state:
            return self._state[state_key]
        return None

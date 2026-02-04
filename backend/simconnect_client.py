import asyncio
import logging
from typing import Optional, Callable, Any

from .flight_state import FlightState
from .config import config

logger = logging.getLogger(__name__)


# SimConnect variable definitions
# Variable names must match Python-SimConnect library (underscores, not spaces)
# See: https://github.com/odwdinc/Python-SimConnect/blob/master/SimConnect/RequestList.py
SIMCONNECT_VARS = {
    # Core flight state
    "SIM_ON_GROUND": "sim_on_ground",
    "PLANE_ALT_ABOVE_GROUND": "altitude_agl",
    "INDICATED_ALTITUDE": "altitude_msl",
    "VERTICAL_SPEED": "vertical_speed",
    "AIRSPEED_INDICATED": "indicated_airspeed",
    "GROUND_VELOCITY": "ground_velocity",
    # Flight controls
    "GEAR_HANDLE_POSITION": "gear_handle_position",
    "TRAILING_EDGE_FLAPS_LEFT_PERCENT": "flaps_percent",
    "SPOILERS_ARMED": "spoilers_armed",
    "BRAKE_PARKING_POSITION": "parking_brake",
    # Engines - use GENERAL_ENG_COMBUSTION (indexed) and N1 values
    "GENERAL_ENG_COMBUSTION:1": "eng1_combustion",
    "GENERAL_ENG_COMBUSTION:2": "eng2_combustion",
    "TURB_ENG_N1:1": "eng1_n1",
    "TURB_ENG_N1:2": "eng2_n1",
    "ENG_N1_RPM:1": "eng1_n1_rpm",
    "ENG_N1_RPM:2": "eng2_n1_rpm",
    # Lights
    "LIGHT_BEACON": "light_beacon",
    "LIGHT_NAV": "light_nav",
    "LIGHT_LANDING": "light_landing",
    "LIGHT_TAXI": "light_taxi",
    "LIGHT_STROBE": "light_strobe",
    # Systems
    "AUTOPILOT_MASTER": "autopilot_master",
    # Fuel & Instruments
    "FUEL_TOTAL_QUANTITY": "fuel_total_gal",  # Fuel in gallons (converted to kg)
    "KOHLSMAN_SETTING_MB": "altimeter_hpa",  # Altimeter in millibars/hPa
    # Cabin signs
    "CABIN_SEATBELTS_ALERT_SWITCH": "seatbelt_sign",
    "CABIN_NO_SMOKING_ALERT_SWITCH": "no_smoking_sign",
    # APU - use PCT_RPM to detect if running (no APU_SWITCH in library)
    "APU_PCT_RPM": "apu_pct_rpm",
    "APU_GENERATOR_SWITCH": "apu_gen_switch",
    # Trim
    "RUDDER_TRIM_PCT": "rudder_trim_pct",
    "ELEVATOR_TRIM_POSITION": "elevator_trim",
    # Electrical
    "ELECTRICAL_MASTER_BATTERY": "master_battery",
}

# Conversion factors
GAL_TO_KG = 3.03  # Jet fuel (Jet-A) gallons to kg (approx 6.7 lbs/gal * 0.453)


class SimConnectClient:
    """Manages connection to MSFS via SimConnect."""

    def __init__(self):
        self._sc = None
        self._aq = None
        self._connected = False
        self._running = False
        self._state = FlightState()
        self._state_callback: Optional[Callable[[FlightState], Any]] = None
        self._poll_task: Optional[asyncio.Task] = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> FlightState:
        return self._state

    def set_state_callback(self, callback: Callable[[FlightState], Any]):
        """Set callback to be called when state updates."""
        self._state_callback = callback

    async def connect(self) -> bool:
        """Attempt to connect to SimConnect."""
        if not config.SIMCONNECT_ENABLED:
            logger.info("SimConnect disabled in config")
            return False

        try:
            from SimConnect import SimConnect, AircraftRequests

            self._sc = SimConnect()
            self._aq = AircraftRequests(self._sc, _time=0)
            self._connected = True
            logger.info("Connected to SimConnect")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to SimConnect: {e}")
            self._connected = False
            self._sc = None
            self._aq = None
            return False

    def disconnect(self):
        """Disconnect from SimConnect."""
        if self._sc:
            try:
                self._sc.exit()
            except Exception:
                pass
        self._sc = None
        self._aq = None
        self._connected = False
        logger.info("Disconnected from SimConnect")

    def _poll_state(self) -> FlightState:
        """Poll current state from SimConnect."""
        if not self._connected or not self._aq:
            return self._state

        try:
            state_dict = {}

            for sc_var, attr_name in SIMCONNECT_VARS.items():
                try:
                    value = self._aq.get(sc_var)
                    if value is not None:
                        # Convert boolean values
                        if attr_name in ("sim_on_ground", "gear_handle_position",
                                        "spoilers_armed", "parking_brake",
                                        "eng1_combustion", "eng2_combustion",
                                        "light_beacon", "light_nav", "light_landing",
                                        "light_taxi", "light_strobe", "autopilot_master",
                                        "seatbelt_sign", "no_smoking_sign",
                                        "apu_gen_switch", "master_battery"):
                            value = bool(value)
                        # Convert fuel from gallons to kg
                        elif attr_name == "fuel_total_gal":
                            state_dict["fuel_total_kg"] = value * GAL_TO_KG
                            continue
                        # Round altimeter to integer hPa
                        elif attr_name == "altimeter_hpa":
                            value = int(round(value))
                        state_dict[attr_name] = value
                except Exception as e:
                    logger.debug(f"Error reading {sc_var}: {e}")

            self._state = FlightState(**state_dict)
            return self._state

        except Exception as e:
            logger.error(f"Error polling SimConnect: {e}")
            self._connected = False
            return self._state

    async def start_polling(self):
        """Start the polling loop."""
        self._running = True
        poll_interval = 1.0 / config.SIMCONNECT_POLL_RATE

        while self._running:
            if not self._connected:
                # Try to reconnect
                await self.connect()
                if not self._connected:
                    await asyncio.sleep(config.SIMCONNECT_RETRY_INTERVAL)
                    continue

            # Poll in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                state = await loop.run_in_executor(None, self._poll_state)

                if self._state_callback:
                    await self._state_callback(state)

            except Exception as e:
                logger.error(f"Polling error: {e}")

            await asyncio.sleep(poll_interval)

    async def stop_polling(self):
        """Stop the polling loop."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self.disconnect()

    def _engine_running(self, engine: int) -> bool:
        """Check if an engine is running using multiple detection methods."""
        if engine == 1:
            n1_pct = self._state.eng1_n1
            n1_rpm = self._state.eng1_n1_rpm / 163.84 if self._state.eng1_n1_rpm else 0
            combustion = self._state.eng1_combustion
        else:
            n1_pct = self._state.eng2_n1
            n1_rpm = self._state.eng2_n1_rpm / 163.84 if self._state.eng2_n1_rpm else 0
            combustion = self._state.eng2_combustion
        return max(n1_pct, n1_rpm) > 15 or combustion

    def _engines_running(self, both: bool = False) -> bool:
        """Check if engines are running (both or any)."""
        if both:
            return self._engine_running(1) and self._engine_running(2)
        return self._engine_running(1) or self._engine_running(2)

    def get_variable(self, var_name: str) -> Any:
        """Get a specific SimConnect variable value from current state."""
        var_map = {
            # Parking brake
            "BRAKE_PARKING_POSITION": self._state.parking_brake,
            # Beacon
            "LIGHT_BEACON": self._state.light_beacon,
            # Flight controls
            "TRAILING_EDGE_FLAPS_LEFT_PERCENT": self._state.flaps_percent,
            "SPOILERS_ARMED": self._state.spoilers_armed,
            "GEAR_HANDLE_POSITION": self._state.gear_handle_position,
            # Lights
            "LIGHT_NAV": self._state.light_nav,
            "LIGHT_LANDING": self._state.light_landing,
            "LIGHT_TAXI": self._state.light_taxi,
            "LIGHT_STROBE": self._state.light_strobe,
            # Cabin signs
            "CABIN_SEATBELTS_ALERT_SWITCH": self._state.seatbelt_sign,
            "CABIN_NO_SMOKING_ALERT_SWITCH": self._state.no_smoking_sign,
            # APU - running if RPM > 0
            "APU_SWITCH": self._state.apu_pct_rpm > 0,
            "APU_GENERATOR_SWITCH": self._state.apu_gen_switch,
            # Trim
            "RUDDER_TRIM_PCT": self._state.rudder_trim_pct,
            # Engines - use multiple detection methods
            "ENG_COMBUSTION": self._engines_running(both=True),
            "ENG_COMBUSTION_ANY": self._engines_running(both=False),
            # Electrical
            "ELECTRICAL_MASTER_BATTERY": self._state.master_battery,
        }
        return var_map.get(var_name)

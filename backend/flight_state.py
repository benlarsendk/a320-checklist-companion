from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Phase(str, Enum):
    # Departure phases
    COCKPIT_PREPARATION = "cockpit_preparation"
    BEFORE_START = "before_start"
    AFTER_START = "after_start"
    TAXI = "taxi"
    LINE_UP = "line_up"

    # Flight phases (not checklist phases, but useful for detection)
    TAKEOFF_ROLL = "takeoff_roll"
    CLIMB = "climb"
    CRUISE = "cruise"
    DESCENT = "descent"

    # Arrival phases
    APPROACH = "approach"
    LANDING = "landing"
    AFTER_LANDING = "after_landing"
    PARKING = "parking"
    SECURING = "securing"


# Phases that have associated checklists
CHECKLIST_PHASES = [
    Phase.COCKPIT_PREPARATION,
    Phase.BEFORE_START,
    Phase.AFTER_START,
    Phase.TAXI,
    Phase.LINE_UP,
    Phase.APPROACH,
    Phase.LANDING,
    Phase.AFTER_LANDING,
    Phase.PARKING,
    Phase.SECURING,
]

# Phase display names
PHASE_DISPLAY = {
    Phase.COCKPIT_PREPARATION: "COCKPIT PREP",
    Phase.BEFORE_START: "BEFORE START",
    Phase.AFTER_START: "AFTER START",
    Phase.TAXI: "TAXI",
    Phase.LINE_UP: "LINE-UP",
    Phase.TAKEOFF_ROLL: "TAKEOFF",
    Phase.CLIMB: "CLIMB",
    Phase.CRUISE: "CRUISE",
    Phase.DESCENT: "DESCENT",
    Phase.APPROACH: "APPROACH",
    Phase.LANDING: "LANDING",
    Phase.AFTER_LANDING: "AFTER LANDING",
    Phase.PARKING: "PARKING",
    Phase.SECURING: "SECURING",
}


class FlightState(BaseModel):
    """Current state of the aircraft from SimConnect."""

    # Core state
    sim_on_ground: bool = True
    altitude_agl: float = 0.0  # feet above ground
    altitude_msl: float = 0.0  # feet MSL
    vertical_speed: float = 0.0  # feet/min
    indicated_airspeed: float = 0.0  # knots
    ground_velocity: float = 0.0  # knots

    # Controls & Configuration
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

    # Fuel & Instruments (for checklist integration)
    fuel_total_kg: float = 0.0  # Total fuel in kg
    altimeter_hpa: int = 1013  # Altimeter setting in hPa


class PhaseDetector:
    """Detects the current flight phase based on aircraft state."""

    def __init__(self):
        self._was_airborne = False
        self._last_phase = Phase.COCKPIT_PREPARATION

    def detect(self, state: FlightState) -> Phase:
        on_ground = state.sim_on_ground
        engines_running = state.eng1_running or state.eng2_running
        both_engines = state.eng1_running and state.eng2_running
        parking_brake = state.parking_brake
        ground_speed = state.ground_velocity
        vertical_speed = state.vertical_speed
        altitude_agl = state.altitude_agl
        gear_down = state.gear_handle_position

        if on_ground:
            if self._was_airborne:
                # We just landed
                if ground_speed < 5:
                    if not engines_running:
                        self._was_airborne = False
                        if parking_brake:
                            return Phase.PARKING
                        return Phase.SECURING
                    return Phase.AFTER_LANDING
                return Phase.AFTER_LANDING

            # On ground, haven't been airborne yet (or reset)
            if not engines_running:
                if parking_brake:
                    return Phase.COCKPIT_PREPARATION
                return Phase.PARKING

            if engines_running and parking_brake:
                return Phase.AFTER_START

            if engines_running and not parking_brake:
                if ground_speed < 5:
                    return Phase.BEFORE_START
                if ground_speed < 30:
                    return Phase.TAXI
                # High ground speed = takeoff roll
                self._was_airborne = True
                return Phase.TAKEOFF_ROLL

            return Phase.TAXI

        else:
            # Airborne
            self._was_airborne = True

            if vertical_speed > 500:
                return Phase.CLIMB

            if vertical_speed < -500:
                if altitude_agl < 3000 or gear_down:
                    return Phase.APPROACH
                return Phase.DESCENT

            # Level flight
            if altitude_agl < 3000:
                return Phase.APPROACH

            return Phase.CRUISE

    def reset(self):
        """Reset the detector state."""
        self._was_airborne = False
        self._last_phase = Phase.COCKPIT_PREPARATION


def get_next_checklist_phase(current: Phase) -> Optional[Phase]:
    """Get the next checklist phase after the current one."""
    try:
        idx = CHECKLIST_PHASES.index(current)
        if idx < len(CHECKLIST_PHASES) - 1:
            return CHECKLIST_PHASES[idx + 1]
    except ValueError:
        pass
    return None


def get_prev_checklist_phase(current: Phase) -> Optional[Phase]:
    """Get the previous checklist phase before the current one."""
    try:
        idx = CHECKLIST_PHASES.index(current)
        if idx > 0:
            return CHECKLIST_PHASES[idx - 1]
    except ValueError:
        pass
    return None

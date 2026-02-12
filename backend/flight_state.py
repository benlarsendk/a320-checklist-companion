from enum import Enum
from typing import Optional
from pydantic import BaseModel

# Named constants for magic numbers
N1_RPM_SCALE = 163.84
N1_RUNNING_THRESHOLD = 15
CRUISE_ALT_THRESHOLD = 10000
APPROACH_AGL_THRESHOLD = 1000
TAXI_SPEED_KTS = 10
LANDING_SPEED_KTS = 30
PARKING_SPEED_KTS = 5
LEVEL_VS_THRESHOLD = 500
DESCENT_VS_THRESHOLD = -500


class Phase(str, Enum):
    # Departure phases
    COCKPIT_PREPARATION = "cockpit_preparation"
    BEFORE_START = "before_start"
    AFTER_START = "after_start"
    TAXI = "taxi"
    LINE_UP = "line_up"
    AFTER_TAKEOFF = "after_takeoff"

    # Flight phases
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
    Phase.AFTER_TAKEOFF,
    Phase.CRUISE,
    Phase.DESCENT,
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
    Phase.AFTER_TAKEOFF: "AFTER TAKEOFF",
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
    eng1_combustion: bool = False
    eng2_combustion: bool = False
    eng1_n1: float = 0.0
    eng2_n1: float = 0.0
    eng1_n1_rpm: float = 0.0  # 0-16384 scale
    eng2_n1_rpm: float = 0.0  # 0-16384 scale

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

    # Cabin signs
    seatbelt_sign: bool = False  # Seat belt sign on/off
    no_smoking_sign: bool = False  # No smoking sign on/off

    # APU
    apu_pct_rpm: float = 0.0  # APU RPM percentage (>0 = running)
    apu_gen_switch: bool = False  # APU generator switch

    # Trim
    rudder_trim_pct: float = 0.0  # Rudder trim percentage
    elevator_trim: float = 0.0  # Elevator trim position

    # Electrical
    master_battery: bool = False  # Master battery switch


class PhaseDetector:
    """State machine for flight phase detection. Only progresses forward automatically."""

    def __init__(self):
        self._current_phase = Phase.COCKPIT_PREPARATION

    @property
    def current_phase(self) -> Phase:
        return self._current_phase

    def _engines_running(self, state: FlightState) -> bool:
        """Check if any engine is running."""
        eng1_n1 = max(state.eng1_n1, state.eng1_n1_rpm / N1_RPM_SCALE if state.eng1_n1_rpm else 0)
        eng2_n1 = max(state.eng2_n1, state.eng2_n1_rpm / N1_RPM_SCALE if state.eng2_n1_rpm else 0)
        return eng1_n1 > N1_RUNNING_THRESHOLD or eng2_n1 > N1_RUNNING_THRESHOLD or state.eng1_combustion or state.eng2_combustion

    def detect(self, state: FlightState) -> Phase:
        """Check if we should advance to the next phase. Never goes backward."""
        engines_running = self._engines_running(state)
        ground_speed = state.ground_velocity
        on_ground = state.sim_on_ground

        # State machine - only forward transitions
        if self._current_phase == Phase.COCKPIT_PREPARATION:
            # Advance when beacon on (ready for pushback)
            if state.light_beacon:
                self._current_phase = Phase.BEFORE_START

        elif self._current_phase == Phase.BEFORE_START:
            # Advance when engines start
            if engines_running:
                self._current_phase = Phase.AFTER_START

        elif self._current_phase == Phase.AFTER_START:
            # Advance when taxi speed reached
            if ground_speed >= TAXI_SPEED_KTS:
                self._current_phase = Phase.TAXI

        elif self._current_phase == Phase.TAXI:
            # Advance when landing lights on (entering runway)
            if state.light_landing:
                self._current_phase = Phase.LINE_UP

        elif self._current_phase == Phase.LINE_UP:
            # Advance when airborne
            if not on_ground:
                self._current_phase = Phase.AFTER_TAKEOFF

        elif self._current_phase == Phase.AFTER_TAKEOFF:
            # Advance when reaching cruise altitude (above 10,000 ft MSL and level)
            if state.altitude_msl > CRUISE_ALT_THRESHOLD and abs(state.vertical_speed) < LEVEL_VS_THRESHOLD:
                self._current_phase = Phase.CRUISE

        elif self._current_phase == Phase.CRUISE:
            # Advance to descent when descending and still above 10,000 ft
            if state.vertical_speed < DESCENT_VS_THRESHOLD and state.altitude_msl > CRUISE_ALT_THRESHOLD:
                self._current_phase = Phase.DESCENT

        elif self._current_phase == Phase.DESCENT:
            # Advance to approach when descending below 10,000 ft MSL
            if state.altitude_msl > 0 and state.altitude_msl < CRUISE_ALT_THRESHOLD:
                self._current_phase = Phase.APPROACH

        elif self._current_phase == Phase.APPROACH:
            # Advance when below 1000 ft AGL (use AGL for final approach)
            if state.altitude_agl < APPROACH_AGL_THRESHOLD:
                self._current_phase = Phase.LANDING

        elif self._current_phase == Phase.LANDING:
            # Advance when on ground and slowed down
            if on_ground and ground_speed < LANDING_SPEED_KTS:
                self._current_phase = Phase.AFTER_LANDING

        elif self._current_phase == Phase.AFTER_LANDING:
            # Advance when stopped and engines off
            if ground_speed < PARKING_SPEED_KTS and not engines_running:
                self._current_phase = Phase.PARKING

        elif self._current_phase == Phase.PARKING:
            # Advance when securing (manual or auto)
            pass  # Stay here until manual advance

        elif self._current_phase == Phase.SECURING:
            # Final state
            pass

        return self._current_phase

    def reset(self):
        """Reset to initial state."""
        self._current_phase = Phase.COCKPIT_PREPARATION

    def set_phase(self, phase: Phase):
        """Manually set the phase (for manual override)."""
        self._current_phase = phase

    def sync_to_phase(self, phase: Phase):
        """Alias for set_phase - sync detector to a manually selected phase."""
        self._current_phase = phase


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

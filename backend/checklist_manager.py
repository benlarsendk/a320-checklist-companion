import json
import logging
import re
from typing import Optional, Any, TYPE_CHECKING
from pathlib import Path

from .config import config
from .flight_state import Phase, CHECKLIST_PHASES, PHASE_DISPLAY, get_next_checklist_phase, get_prev_checklist_phase

if TYPE_CHECKING:
    from .simbrief_client import FlightPlan

logger = logging.getLogger(__name__)


class ChecklistItem:
    """Represents a single checklist item."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.challenge = data["challenge"]
        self.response = data["response"]
        self.response_template = data["response"]  # Original template with placeholders
        self.verify = data.get("verify")  # Auto-verify config
        self.checked = False  # Pilot acknowledged
        self.verified: Optional[bool] = None  # Sim verified (None if not verifiable)
        # SimBrief expected values (for comparison with MSFS actual)
        self.simbrief_value: Optional[str] = None  # Raw expected value
        self.simbrief_type: Optional[str] = None  # Type: "fuel", "baro", "trim"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "challenge": self.challenge,
            "response": self.response,
            "checked": self.checked,
            "verified": self.verified,
            "simbrief_value": self.simbrief_value,
            "simbrief_type": self.simbrief_type,
        }

    def reset(self):
        self.checked = False
        self.verified = None
        self.response = self.response_template
        self.simbrief_value = None
        self.simbrief_type = None


class Checklist:
    """Represents a checklist for a specific phase."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.title = data["title"]
        self.trigger = data.get("trigger", "")
        self.items = [ChecklistItem(item) for item in data["items"]]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "trigger": self.trigger,
            "items": [item.to_dict() for item in self.items],
        }

    def reset(self):
        for item in self.items:
            item.reset()

    def is_complete(self) -> bool:
        return all(item.checked for item in self.items)

    def get_item(self, item_id: str) -> Optional[ChecklistItem]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None


class ChecklistManager:
    """Manages all checklists and their state."""

    def __init__(self, training_mode: bool = False):
        self.checklists: dict[str, Checklist] = {}
        self.current_phase: Phase = Phase.COCKPIT_PREPARATION
        self.phase_mode: str = "auto"  # "auto" or "manual"
        self.phase_history: list[str] = []
        self.training_mode: bool = training_mode
        self._load_checklists()

    def _load_checklists(self):
        """Load checklists from JSON file based on training mode."""
        checklist_file = config.TRAINING_CHECKLIST_FILE if self.training_mode else config.CHECKLIST_FILE
        try:
            with open(checklist_file, "r") as f:
                data = json.load(f)

            # Load departure checklists
            for checklist_data in data["phases"].get("departure", []):
                checklist = Checklist(checklist_data)
                self.checklists[checklist.id] = checklist

            # Load climb checklists (after takeoff, above 10k)
            for checklist_data in data["phases"].get("climb", []):
                checklist = Checklist(checklist_data)
                self.checklists[checklist.id] = checklist

            # Load cruise checklists (cruise, descent, below 10k)
            for checklist_data in data["phases"].get("cruise", []):
                checklist = Checklist(checklist_data)
                self.checklists[checklist.id] = checklist

            # Load arrival checklists
            for checklist_data in data["phases"].get("arrival", []):
                checklist = Checklist(checklist_data)
                self.checklists[checklist.id] = checklist

            mode_str = "training" if self.training_mode else "normal"
            logger.info(f"Loaded {len(self.checklists)} checklists ({mode_str} mode)")

        except Exception as e:
            logger.error(f"Failed to load checklists: {e}")
            raise

    def set_training_mode(self, enabled: bool):
        """Switch between training and normal checklists."""
        if self.training_mode != enabled:
            self.training_mode = enabled
            self.checklists.clear()
            self._load_checklists()
            # Reset to first phase
            self.current_phase = Phase.COCKPIT_PREPARATION
            self.phase_mode = "auto"
            self.phase_history = []
            logger.info(f"Switched to {'training' if enabled else 'normal'} checklists")

    def get_current_checklist(self) -> Optional[Checklist]:
        """Get the checklist for the current phase."""
        return self.checklists.get(self.current_phase.value)

    def get_checklist(self, phase_id: str) -> Optional[Checklist]:
        """Get a specific checklist by phase ID."""
        return self.checklists.get(phase_id)

    def set_phase(self, phase: Phase, record_history: bool = True):
        """Set the current phase."""
        if self.current_phase != phase:
            if record_history and self.current_phase.value not in self.phase_history:
                self.phase_history.append(self.current_phase.value)
            self.current_phase = phase
            logger.info(f"Phase changed to: {phase.value}")

    def next_phase(self) -> bool:
        """Move to the next checklist phase. Returns True if successful."""
        next_p = get_next_checklist_phase(self.current_phase)
        if next_p:
            self.set_phase(next_p)
            self.phase_mode = "manual"
            return True
        return False

    def prev_phase(self) -> bool:
        """Move to the previous checklist phase. Returns True if successful."""
        prev_p = get_prev_checklist_phase(self.current_phase)
        if prev_p:
            self.set_phase(prev_p, record_history=False)
            self.phase_mode = "manual"
            return True
        return False

    def check_item(self, phase_id: str, item_id: str) -> bool:
        """Mark an item as checked. Returns True if successful."""
        checklist = self.get_checklist(phase_id)
        if checklist:
            item = checklist.get_item(item_id)
            if item:
                item.checked = True
                return True
        return False

    def uncheck_item(self, phase_id: str, item_id: str) -> bool:
        """Mark an item as unchecked. Returns True if successful."""
        checklist = self.get_checklist(phase_id)
        if checklist:
            item = checklist.get_item(item_id)
            if item:
                item.checked = False
                return True
        return False

    def toggle_item(self, phase_id: str, item_id: str) -> bool:
        """Toggle an item's checked state. Returns True if successful."""
        checklist = self.get_checklist(phase_id)
        if checklist:
            item = checklist.get_item(item_id)
            if item:
                item.checked = not item.checked
                return True
        return False

    def reset_all(self):
        """Reset all checklists to unchecked."""
        for checklist in self.checklists.values():
            checklist.reset()
        self.current_phase = Phase.COCKPIT_PREPARATION
        self.phase_mode = "auto"
        self.phase_history = []
        logger.info("All checklists reset")

    def update_verification(self, var_name: str, value: Any):
        """Update auto-verification status based on SimConnect variable."""
        for checklist in self.checklists.values():
            for item in checklist.items:
                if item.verify and item.verify.get("var") == var_name:
                    condition = item.verify.get("condition")
                    expected = item.verify.get("value")

                    if condition == "eq":
                        item.verified = (value == expected)
                    elif condition == "gte":
                        item.verified = (value >= expected)
                    elif condition == "lte":
                        item.verified = (value <= expected)
                    elif condition == "gt":
                        item.verified = (value > expected)
                    elif condition == "lt":
                        item.verified = (value < expected)

    def get_all_checklists(self) -> dict:
        """Get all checklists as a dict."""
        return {
            phase_id: checklist.to_dict()
            for phase_id, checklist in self.checklists.items()
        }

    def get_state_dict(self) -> dict:
        """Get the current state as a dict for API/WebSocket."""
        current_checklist = self.get_current_checklist()
        return {
            "phase": self.current_phase.value,
            "phase_display": PHASE_DISPLAY.get(self.current_phase, self.current_phase.value),
            "phase_mode": self.phase_mode,
            "checklist": current_checklist.to_dict() if current_checklist else None,
            "phase_history": self.phase_history,
        }

    def inject_flight_plan(self, flight_plan: "FlightPlan"):
        """
        Inject flight plan data into checklist item responses.
        Replaces ___ placeholders with actual values from the flight plan.
        Also stores raw values for comparison with MSFS actual data.
        """
        if not flight_plan:
            return

        # Store raw values and types for MSFS comparison
        simbrief_data = {
            "fuel": {
                "value": flight_plan.fuel_block,
                "type": "fuel",
                "units": flight_plan.fuel_units,
            },
            "baro_ref": {
                "value": flight_plan.origin_qnh,
                "type": "baro",
                "units": "hPa",
            },
            "baro_ref_ldg": {
                "value": flight_plan.dest_qnh,
                "type": "baro",
                "units": "hPa",
            },
            "pitch_trim": {
                "value": flight_plan.trim_percent,
                "type": "trim",
                "units": "%",
            },
        }

        for checklist in self.checklists.values():
            for item in checklist.items:
                # Check if response has a placeholder
                if "___" not in item.response_template:
                    continue

                # Get SimBrief data for this item
                sb_data = simbrief_data.get(item.id)
                if not sb_data or not sb_data["value"]:
                    continue

                # Store SimBrief value and type for frontend use
                item.simbrief_value = str(sb_data["value"])
                item.simbrief_type = sb_data["type"]

                # Format display value based on type
                if sb_data["type"] == "fuel":
                    display_val = f"{sb_data['value']:,} "
                elif sb_data["type"] == "baro":
                    display_val = f"{sb_data['value']} "
                elif sb_data["type"] == "trim":
                    display_val = f"{sb_data['value']:.1f}"
                else:
                    display_val = str(sb_data["value"])

                # Wrap in span for styling (simbrief-value class)
                styled_val = f'<span class="simbrief-value">{display_val}</span>'
                item.response = item.response_template.replace("___", styled_val)

        logger.info("Flight plan data injected into checklists")

    def clear_flight_plan_data(self):
        """Reset all checklist responses to their templates."""
        for checklist in self.checklists.values():
            for item in checklist.items:
                item.response = item.response_template
                item.simbrief_value = None
                item.simbrief_type = None
        logger.info("Flight plan data cleared from checklists")

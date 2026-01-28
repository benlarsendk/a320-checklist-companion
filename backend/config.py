import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Get the base directory, handling both normal and frozen (PyInstaller) execution."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - PyInstaller extracts to _MEIPASS temp folder
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent.parent


class Config:
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 2549  # RFC 2549 - IP over Avian Carriers

    # SimConnect settings
    SIMCONNECT_ENABLED: bool = True
    SIMCONNECT_POLL_RATE: int = 10  # Hz
    SIMCONNECT_RETRY_INTERVAL: float = 5.0  # Seconds between reconnect attempts

    # Phase transition settings
    AUTO_PHASE_TRANSITION: bool = True
    PHASE_TRANSITION_DELAY: float = 2.0  # Seconds before auto-transition

    # Paths - computed at import time
    BASE_DIR: Path = get_base_dir()
    DATA_DIR: Path = BASE_DIR / "data"
    FRONTEND_DIR: Path = BASE_DIR / "frontend"
    CHECKLIST_FILE: Path = DATA_DIR / "A320_Normal_Checklist_2026.json"
    TRAINING_CHECKLIST_FILE: Path = DATA_DIR / "A320_Training_Checklist.json"
    SETTINGS_FILE: Path = DATA_DIR / "settings.json"


config = Config()

from pathlib import Path


class Config:
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # SimConnect settings
    SIMCONNECT_ENABLED: bool = True
    SIMCONNECT_POLL_RATE: int = 10  # Hz
    SIMCONNECT_RETRY_INTERVAL: float = 5.0  # Seconds between reconnect attempts

    # Phase transition settings
    AUTO_PHASE_TRANSITION: bool = True
    PHASE_TRANSITION_DELAY: float = 2.0  # Seconds before auto-transition

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    FRONTEND_DIR: Path = BASE_DIR / "frontend"
    CHECKLIST_FILE: Path = DATA_DIR / "A320_Normal_Checklist_2026.json"
    SETTINGS_FILE: Path = DATA_DIR / "settings.json"


config = Config()

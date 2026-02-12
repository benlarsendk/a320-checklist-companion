"""Persistent settings storage for the checklist companion."""

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from .config import config

logger = logging.getLogger(__name__)


class Settings(BaseModel):
    """Application settings model."""

    simbrief_username: str = ""
    dark_mode: bool = False
    training_mode: bool = False


class SettingsManager:
    """Thread-safe settings manager with JSON file persistence."""

    def __init__(self, settings_file: Optional[Path] = None):
        self._settings_file = settings_file or config.SETTINGS_FILE
        self._settings = Settings()
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        """Load settings from file."""
        with self._lock:
            try:
                if self._settings_file.exists():
                    with open(self._settings_file, "r") as f:
                        data = json.load(f)
                    self._settings = Settings(**data)
                    logger.info(f"Settings loaded from {self._settings_file}")
                else:
                    logger.info("No settings file found, using defaults")
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
                self._settings = Settings()

    def _save(self):
        """Save settings to file."""
        with self._lock:
            try:
                self._settings_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self._settings_file, "w") as f:
                    json.dump(self._settings.model_dump(), f, indent=2)
                logger.info(f"Settings saved to {self._settings_file}")
            except Exception as e:
                logger.error(f"Failed to save settings: {e}")
                raise

    @property
    def settings(self) -> Settings:
        """Get current settings."""
        with self._lock:
            return self._settings.model_copy()

    def update(self, **kwargs) -> Settings:
        """Update settings and persist to file."""
        with self._lock:
            data = self._settings.model_dump()
            data.update(kwargs)
            self._settings = Settings(**data)
        self._save()
        return self.settings

    def get_simbrief_username(self) -> str:
        """Get SimBrief username."""
        with self._lock:
            return self._settings.simbrief_username

    def set_simbrief_username(self, username: str):
        """Set SimBrief username."""
        self.update(simbrief_username=username)


# Global settings manager instance
settings_manager = SettingsManager()

"""Text-to-Speech module - handles audio file playback and Web Speech API fallback."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Text-to-Speech engine that prioritizes custom audio files
    and falls back to Web Speech API (handled client-side).
    """

    def __init__(self, audio_dir: Path):
        self.audio_dir = audio_dir
        self.announcements_dir = audio_dir / "announcements"
        self.checklists_dir = audio_dir / "checklists"
        self.items_dir = audio_dir / "items"

        # Cache of available audio files
        self._audio_cache: Dict[str, Path] = {}
        self._scan_audio_files()

    def _scan_audio_files(self):
        """Scan for available audio files."""
        self._audio_cache.clear()

        for directory in [self.announcements_dir, self.checklists_dir, self.items_dir]:
            if directory.exists():
                for audio_file in directory.glob("*.mp3"):
                    key = audio_file.stem  # filename without extension
                    self._audio_cache[key] = audio_file
                for audio_file in directory.glob("*.wav"):
                    key = audio_file.stem
                    self._audio_cache[key] = audio_file

        logger.info(f"Found {len(self._audio_cache)} audio files")

    def has_audio(self, key: str) -> bool:
        """Check if custom audio exists for a key."""
        return key in self._audio_cache

    def get_audio_path(self, key: str) -> Optional[Path]:
        """Get path to audio file if it exists."""
        return self._audio_cache.get(key)

    def get_audio_url(self, key: str) -> Optional[str]:
        """Get URL path for audio file (for client playback)."""
        if key in self._audio_cache:
            path = self._audio_cache[key]
            # Return relative URL for the audio endpoint
            return f"/audio/{path.parent.name}/{path.name}"
        return None

    def get_speech_command(self, key: str, text: str) -> Dict[str, Any]:
        """
        Get command for playing speech.

        Returns a dict that tells the client what to do:
        - If audio file exists: {"type": "audio", "url": "..."}
        - If no audio: {"type": "tts", "text": "..."}
        """
        audio_url = self.get_audio_url(key)
        if audio_url:
            return {
                "type": "audio",
                "url": audio_url,
                "key": key,
            }
        else:
            return {
                "type": "tts",
                "text": text,
                "key": key,
            }

    def get_checklist_announcement(self, checklist_id: str, checklist_title: str) -> Dict[str, Any]:
        """Get command to announce checklist is available."""
        key = f"{checklist_id}_title"
        text = f"{checklist_title} checklist"
        return self.get_speech_command(key, text)

    def get_item_challenge(self, item_id: str, challenge_text: str) -> Dict[str, Any]:
        """Get command to read a checklist item challenge."""
        key = f"{item_id}_challenge"
        return self.get_speech_command(key, challenge_text)

    def get_announcement(self, announcement_type: str) -> Dict[str, Any]:
        """Get standard announcement (checklist_available, checklist_complete, etc.)."""
        announcements = {
            "checklist_available": "Checklist available",
            "checklist_complete": "Checklist complete",
            "item_verified": "Verified",
            "item_not_verified": "Not verified",
        }
        text = announcements.get(announcement_type, announcement_type)
        return self.get_speech_command(announcement_type, text)

    def refresh_cache(self):
        """Rescan audio files."""
        self._scan_audio_files()

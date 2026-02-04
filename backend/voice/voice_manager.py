"""Voice Manager - orchestrates TTS and STT for checklist voice interaction."""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum

from .tts import TTSEngine
from .stt import STTEngine
from .response_matcher import ResponseMatcher

logger = logging.getLogger(__name__)


class VoiceEvent(str, Enum):
    """Voice system events."""
    CHECKLIST_AVAILABLE = "checklist_available"
    CHECKLIST_COMPLETE = "checklist_complete"
    ITEM_CHALLENGE = "item_challenge"
    ITEM_RESPONSE_ACCEPTED = "item_response_accepted"
    ITEM_RESPONSE_REJECTED = "item_response_rejected"
    LISTENING_STARTED = "listening_started"
    LISTENING_STOPPED = "listening_stopped"
    TRANSCRIPTION_RESULT = "transcription_result"
    ERROR = "error"


@dataclass
class VoiceSettings:
    """Voice system settings."""
    enabled: bool = True
    auto_read_challenges: bool = True
    auto_advance_on_response: bool = True
    volume: float = 1.0
    speech_rate: float = 1.0
    ptt_keyboard_key: str = "Space"
    ptt_gamepad_button: Optional[int] = None
    use_whisper: bool = True


class VoiceManager:
    """
    Manages voice interaction for checklists.

    Coordinates between:
    - TTS: Reading challenges and announcements
    - STT: Recognizing pilot responses
    - ResponseMatcher: Validating responses
    """

    def __init__(self, audio_dir: Path, models_dir: Path):
        self.tts = TTSEngine(audio_dir)
        self.stt = STTEngine(models_dir)
        self.matcher = ResponseMatcher()

        self.settings = VoiceSettings()

        # Callbacks for events
        self._event_callbacks: list[Callable[[VoiceEvent, Dict[str, Any]], Any]] = []

        # Current state
        self._current_checklist_id: Optional[str] = None
        self._current_item_id: Optional[str] = None
        self._expected_response: Optional[str] = None
        self._is_listening = False

    def add_event_callback(self, callback: Callable[[VoiceEvent, Dict[str, Any]], Any]):
        """Add callback for voice events."""
        self._event_callbacks.append(callback)

    def remove_event_callback(self, callback: Callable[[VoiceEvent, Dict[str, Any]], Any]):
        """Remove event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    async def _emit_event(self, event: VoiceEvent, data: Dict[str, Any]):
        """Emit event to all callbacks."""
        for callback in self._event_callbacks:
            try:
                result = callback(event, data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current voice system status."""
        return {
            "enabled": self.settings.enabled,
            "stt": self.stt.get_status(),
            "tts": {
                "audio_files_available": len(self.tts._audio_cache),
            },
            "is_listening": self._is_listening,
            "current_item": self._current_item_id,
            "settings": {
                "auto_read_challenges": self.settings.auto_read_challenges,
                "auto_advance_on_response": self.settings.auto_advance_on_response,
                "volume": self.settings.volume,
                "speech_rate": self.settings.speech_rate,
                "ptt_keyboard_key": self.settings.ptt_keyboard_key,
                "ptt_gamepad_button": self.settings.ptt_gamepad_button,
                "use_whisper": self.settings.use_whisper,
            }
        }

    async def announce_checklist_available(
        self,
        checklist_id: str,
        checklist_title: str
    ) -> Dict[str, Any]:
        """
        Announce that a checklist is available.

        Returns command for client to execute (play audio or use TTS).
        """
        self._current_checklist_id = checklist_id

        # First announce "Checklist available"
        announcement = self.tts.get_announcement("checklist_available")

        # Then the checklist title
        title_speech = self.tts.get_checklist_announcement(checklist_id, checklist_title)

        await self._emit_event(VoiceEvent.CHECKLIST_AVAILABLE, {
            "checklist_id": checklist_id,
            "checklist_title": checklist_title,
        })

        return {
            "sequence": [announcement, title_speech],
            "settings": {
                "volume": self.settings.volume,
                "rate": self.settings.speech_rate,
            }
        }

    async def announce_checklist_complete(self, checklist_id: str) -> Dict[str, Any]:
        """Announce checklist completion."""
        announcement = self.tts.get_announcement("checklist_complete")

        await self._emit_event(VoiceEvent.CHECKLIST_COMPLETE, {
            "checklist_id": checklist_id,
        })

        return {
            "sequence": [announcement],
            "settings": {
                "volume": self.settings.volume,
                "rate": self.settings.speech_rate,
            }
        }

    async def read_item_challenge(
        self,
        item_id: str,
        challenge: str,
        expected_response: str
    ) -> Dict[str, Any]:
        """
        Read a checklist item challenge.

        Returns command for client to execute.
        """
        self._current_item_id = item_id
        self._expected_response = expected_response

        speech = self.tts.get_item_challenge(item_id, challenge)

        await self._emit_event(VoiceEvent.ITEM_CHALLENGE, {
            "item_id": item_id,
            "challenge": challenge,
            "expected_response": expected_response,
            "accepted_phrases": self.matcher.get_accepted_phrases(expected_response),
        })

        return {
            "sequence": [speech],
            "settings": {
                "volume": self.settings.volume,
                "rate": self.settings.speech_rate,
            },
            "expect_response": True,
            "accepted_phrases": self.matcher.get_accepted_phrases(expected_response),
        }

    async def start_listening(self) -> Dict[str, Any]:
        """Start listening for voice input (PTT pressed)."""
        self._is_listening = True

        await self._emit_event(VoiceEvent.LISTENING_STARTED, {
            "item_id": self._current_item_id,
            "expected_response": self._expected_response,
        })

        return {
            "action": "start_recording",
            "use_whisper": self.settings.use_whisper and self.stt.is_available,
        }

    async def stop_listening(self, audio_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Stop listening and process audio (PTT released).

        Args:
            audio_data: WebM audio data from browser (if using Whisper)

        Returns response with transcription result.
        """
        self._is_listening = False

        await self._emit_event(VoiceEvent.LISTENING_STOPPED, {})

        # If we have audio data and Whisper is available, transcribe
        if audio_data and self.stt.is_available:
            transcribed = await self.stt.transcribe_webm(audio_data)

            if transcribed:
                return await self.process_response(transcribed)
            else:
                return {
                    "action": "transcription_failed",
                    "error": "Could not transcribe audio",
                }

        # Otherwise, client should use Web Speech API
        return {
            "action": "use_web_speech",
        }

    async def process_response(self, spoken_text: str) -> Dict[str, Any]:
        """
        Process a spoken response (from Whisper or Web Speech API).

        Returns whether the response was accepted.
        """
        if not self._expected_response:
            return {
                "action": "no_expected_response",
                "spoken": spoken_text,
            }

        is_match, confidence = self.matcher.match(spoken_text, self._expected_response)

        await self._emit_event(VoiceEvent.TRANSCRIPTION_RESULT, {
            "spoken": spoken_text,
            "expected": self._expected_response,
            "is_match": is_match,
            "confidence": confidence,
        })

        if is_match:
            await self._emit_event(VoiceEvent.ITEM_RESPONSE_ACCEPTED, {
                "item_id": self._current_item_id,
                "spoken": spoken_text,
                "expected": self._expected_response,
                "confidence": confidence,
            })

            return {
                "action": "response_accepted",
                "item_id": self._current_item_id,
                "spoken": spoken_text,
                "expected": self._expected_response,
                "confidence": confidence,
                "auto_advance": self.settings.auto_advance_on_response,
            }
        else:
            await self._emit_event(VoiceEvent.ITEM_RESPONSE_REJECTED, {
                "item_id": self._current_item_id,
                "spoken": spoken_text,
                "expected": self._expected_response,
            })

            return {
                "action": "response_rejected",
                "item_id": self._current_item_id,
                "spoken": spoken_text,
                "expected": self._expected_response,
                "accepted_phrases": self.matcher.get_accepted_phrases(self._expected_response),
            }

    async def download_whisper_model(
        self,
        model_name: str = "base",
        progress_callback: Optional[Callable[[float], Any]] = None
    ) -> bool:
        """Download and load Whisper model."""
        return await self.stt.download_model(model_name, progress_callback)

    def update_settings(self, **kwargs):
        """Update voice settings."""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
                logger.info(f"Voice setting updated: {key}={value}")

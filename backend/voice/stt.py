"""Speech-to-Text module - Whisper integration with Web Speech API fallback."""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Optional, Callable, Any
import io

logger = logging.getLogger(__name__)

# Set up FFmpeg path from imageio-ffmpeg if available
# This MUST happen before whisper is imported
FFMPEG_PATH = None
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(FFMPEG_PATH)

    # Add to PATH for this process and all subprocesses
    current_path = os.environ.get("PATH", "")
    if ffmpeg_dir not in current_path:
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path

    # Also try to patch whisper's audio module to use our ffmpeg
    print(f"[STT] FFmpeg path: {FFMPEG_PATH}")
    logger.info(f"Using FFmpeg from imageio-ffmpeg: {FFMPEG_PATH}")
except ImportError as e:
    print(f"[STT] imageio-ffmpeg not installed: {e}")
    logger.warning("imageio-ffmpeg not installed, Whisper may fail to decode audio")
except Exception as e:
    print(f"[STT] Error setting up FFmpeg: {e}")
    logger.error(f"Error setting up FFmpeg: {e}")

# Whisper model options
WHISPER_MODELS = {
    "tiny": {"size_mb": 75, "description": "Fastest, least accurate"},
    "base": {"size_mb": 142, "description": "Good balance"},
    "small": {"size_mb": 466, "description": "More accurate, slower"},
}

DEFAULT_MODEL = "base"


class STTEngine:
    """
    Speech-to-Text engine using OpenAI Whisper.
    Falls back to Web Speech API (client-side) if Whisper unavailable.
    """

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._whisper = None
        self._model = None
        self._model_name: Optional[str] = None
        self._is_loading = False

    @property
    def is_available(self) -> bool:
        """Check if Whisper is loaded and ready."""
        return self._model is not None

    @property
    def is_loading(self) -> bool:
        """Check if model is currently loading."""
        return self._is_loading

    def get_status(self) -> dict:
        """Get current STT engine status."""
        return {
            "whisper_available": self.is_available,
            "whisper_loading": self.is_loading,
            "model_name": self._model_name,
            "models_downloaded": self._get_downloaded_models(),
            "available_models": WHISPER_MODELS,
        }

    def _get_downloaded_models(self) -> list:
        """Get list of downloaded model names."""
        downloaded = []
        for model_name in WHISPER_MODELS:
            # Check if whisper has cached the model
            cache_dir = Path.home() / ".cache" / "whisper"
            model_file = cache_dir / f"{model_name}.pt"
            if model_file.exists():
                downloaded.append(model_name)
        return downloaded

    async def download_model(
        self,
        model_name: str = DEFAULT_MODEL,
        progress_callback: Optional[Callable[[float], Any]] = None
    ) -> bool:
        """
        Download Whisper model.

        Args:
            model_name: Name of model to download (tiny, base, small)
            progress_callback: Optional callback for download progress (0.0 - 1.0)

        Returns:
            True if successful
        """
        if model_name not in WHISPER_MODELS:
            logger.error(f"Unknown model: {model_name}")
            return False

        try:
            self._is_loading = True

            # Import whisper (this will trigger download if needed)
            import whisper

            logger.info(f"Downloading Whisper model: {model_name}")

            # Load model (downloads if not cached)
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(
                None,
                lambda: whisper.load_model(model_name)
            )
            self._model_name = model_name
            self._whisper = whisper

            logger.info(f"Whisper model '{model_name}' loaded successfully")
            return True

        except ImportError:
            logger.error("Whisper not installed. Install with: pip install openai-whisper")
            return False
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False
        finally:
            self._is_loading = False

    async def load_model(self, model_name: str = DEFAULT_MODEL) -> bool:
        """Load a Whisper model (must already be downloaded)."""
        return await self.download_model(model_name)

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw PCM audio bytes (16-bit signed, mono)
            sample_rate: Audio sample rate (default 16000 Hz)

        Returns:
            Transcribed text or None if failed
        """
        if not self.is_available:
            logger.warning("Whisper not available for transcription")
            return None

        try:
            # Write audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                with wave.open(f, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)  # 16-bit
                    wav.setframerate(sample_rate)
                    wav.writeframes(audio_data)

            # Transcribe in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._model.transcribe(
                    temp_path,
                    language="en",
                    fp16=False,  # Use FP32 for CPU compatibility
                )
            )

            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

            text = result.get("text", "").strip()
            logger.debug(f"Transcribed: '{text}'")
            return text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    async def transcribe_webm(self, webm_data: bytes) -> Optional[str]:
        """
        Transcribe WebM audio data (from browser MediaRecorder).

        Args:
            webm_data: WebM audio file bytes

        Returns:
            Transcribed text or None if failed
        """
        if not self.is_available:
            logger.warning("Whisper not available for transcription")
            return None

        try:
            # Write WebM to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                webm_path = f.name
                f.write(webm_data)

            # Debug: check file size
            file_size = Path(webm_path).stat().st_size
            logger.info(f"WebM file written: {webm_path}, size: {file_size} bytes")

            if file_size < 100:
                logger.error(f"WebM file too small ({file_size} bytes), likely corrupted")
                Path(webm_path).unlink(missing_ok=True)
                return None

            # Convert WebM to raw PCM audio using FFmpeg
            # Output: 16kHz mono 16-bit signed little-endian PCM
            ffmpeg_exe = FFMPEG_PATH or "ffmpeg"
            try:
                logger.info(f"Converting with FFmpeg: {ffmpeg_exe}")
                result = subprocess.run(
                    [ffmpeg_exe, "-y", "-i", webm_path,
                     "-ar", "16000",  # 16kHz sample rate (what Whisper expects)
                     "-ac", "1",       # mono
                     "-f", "s16le",    # raw 16-bit signed little-endian PCM
                     "-"],             # output to stdout
                    capture_output=True,
                    timeout=30
                )
                if result.returncode != 0:
                    logger.error(f"FFmpeg conversion failed: {result.stderr.decode()}")
                    Path(webm_path).unlink(missing_ok=True)
                    return None

                # Convert raw PCM bytes to numpy float32 array (what Whisper expects)
                import numpy as np
                audio_data = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                logger.info(f"Audio converted: {len(audio_data)} samples, {len(audio_data)/16000:.2f} seconds")

            except FileNotFoundError:
                logger.error(f"FFmpeg not found at: {ffmpeg_exe}")
                Path(webm_path).unlink(missing_ok=True)
                return None

            # Clean up webm file
            Path(webm_path).unlink(missing_ok=True)

            # Transcribe the audio array directly (bypasses Whisper's ffmpeg call)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._model.transcribe(
                    audio_data,  # Pass numpy array directly
                    language="en",
                    fp16=False,
                )
            )

            text = result.get("text", "").strip()
            logger.info(f"Transcribed: '{text}'")
            return text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            import traceback
            traceback.print_exc()
            return None

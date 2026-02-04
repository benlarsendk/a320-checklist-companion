import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import config
from .flight_state import FlightState, Phase, PhaseDetector, CHECKLIST_PHASES
from .simconnect_client import SimConnectClient
from .checklist_manager import ChecklistManager
from .websocket_manager import WebSocketManager
from .settings import settings_manager
from .simbrief_client import (
    simbrief_client,
    SimBriefError,
    SimBriefUserNotFound,
    SimBriefNetworkError,
)
from .voice import VoiceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
simconnect = SimConnectClient()
checklist_manager = ChecklistManager(training_mode=settings_manager.settings.training_mode)
websocket_manager = WebSocketManager()
phase_detector = PhaseDetector()
voice_manager = VoiceManager(
    audio_dir=config.BASE_DIR / "audio",
    models_dir=config.BASE_DIR / "models",
)

# Verification variables to monitor
VERIFY_VARS = [
    "BRAKE_PARKING_POSITION",
    "LIGHT_BEACON",
    "TRAILING_EDGE_FLAPS_LEFT_PERCENT",
    "SPOILERS_ARMED",
    "TRANSPONDER_STATE",
    "GEAR_HANDLE_POSITION",
    "CABIN_SEATBELTS_ALERT_SWITCH",
    "CABIN_NO_SMOKING_ALERT_SWITCH",
    "APU_SWITCH",
    "APU_GENERATOR_SWITCH",
    "RUDDER_TRIM_PCT",
    "ENG_COMBUSTION",
    "LIGHT_NAV",
    "LIGHT_STROBE",
    "ELECTRICAL_MASTER_BATTERY",
]


async def on_state_update(state: FlightState):
    """Called when SimConnect state updates."""
    # Update verification status for checklist items
    for var in VERIFY_VARS:
        value = simconnect.get_variable(var)
        if value is not None:
            checklist_manager.update_verification(var, value)

    # Auto-detect phase if in auto mode
    if checklist_manager.phase_mode == "auto" and config.AUTO_PHASE_TRANSITION:
        detected = phase_detector.detect(state)
        # Only change to phases that have checklists
        if detected in CHECKLIST_PHASES:
            checklist_manager.set_phase(detected)

    # Broadcast state to all WebSocket clients
    await websocket_manager.send_state_update(
        connected=simconnect.connected,
        flight_state=state.model_dump() if simconnect.connected else None,
        checklist_state=checklist_manager.get_state_dict(),
        auto_transition=config.AUTO_PHASE_TRANSITION,
        flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
    )


async def periodic_broadcast():
    """Periodically broadcast state even when SimConnect is not connected."""
    while True:
        if not simconnect.connected:
            await websocket_manager.send_state_update(
                connected=False,
                flight_state=None,
                checklist_state=checklist_manager.get_state_dict(),
                auto_transition=config.AUTO_PHASE_TRANSITION,
                flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
            )
        await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting MSFS Checklist Companion...")

    # Set up state callback
    simconnect.set_state_callback(on_state_update)

    # Start SimConnect polling in background
    polling_task = asyncio.create_task(simconnect.start_polling())
    broadcast_task = asyncio.create_task(periodic_broadcast())

    logger.info(f"Server running on http://{config.HOST}:{config.PORT}")

    yield

    # Cleanup
    logger.info("Shutting down...")
    await simconnect.stop_polling()
    polling_task.cancel()
    broadcast_task.cancel()
    try:
        await polling_task
        await broadcast_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="MSFS A320 Checklist Companion", lifespan=lifespan)


# Pydantic models for API
class CheckItemRequest(BaseModel):
    phase: str
    item_id: str


class SetPhaseRequest(BaseModel):
    phase: str


class SettingsRequest(BaseModel):
    simbrief_username: str = ""
    dark_mode: bool = False
    training_mode: bool = False


# REST API endpoints
@app.get("/api/state")
async def get_state():
    """Get current flight state and checklist state."""
    return {
        "connected": simconnect.connected,
        "flight_state": simconnect.state.model_dump() if simconnect.connected else None,
        **checklist_manager.get_state_dict(),
    }


@app.get("/api/checklist")
async def get_all_checklists():
    """Get full checklist structure."""
    return checklist_manager.get_all_checklists()


@app.get("/api/checklist/current")
async def get_current_checklist():
    """Get current active checklist."""
    checklist = checklist_manager.get_current_checklist()
    if checklist:
        return checklist.to_dict()
    raise HTTPException(status_code=404, detail="No current checklist")


@app.post("/api/checklist/check")
async def check_item(request: CheckItemRequest):
    """Mark item as checked."""
    success = checklist_manager.check_item(request.phase, request.item_id)
    if success:
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
        )
        return {"success": True}
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/checklist/uncheck")
async def uncheck_item(request: CheckItemRequest):
    """Mark item as unchecked."""
    success = checklist_manager.uncheck_item(request.phase, request.item_id)
    if success:
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
        )
        return {"success": True}
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/checklist/toggle")
async def toggle_item(request: CheckItemRequest):
    """Toggle item checked state."""
    success = checklist_manager.toggle_item(request.phase, request.item_id)
    if success:
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
        )
        return {"success": True}
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/checklist/next")
async def next_phase():
    """Force move to next phase."""
    success = checklist_manager.next_phase()
    if success:
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
        )
        return {"success": True, "phase": checklist_manager.current_phase.value}
    raise HTTPException(status_code=400, detail="No next phase available")


@app.post("/api/checklist/prev")
async def prev_phase():
    """Force move to previous phase."""
    success = checklist_manager.prev_phase()
    if success:
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
        )
        return {"success": True, "phase": checklist_manager.current_phase.value}
    raise HTTPException(status_code=400, detail="No previous phase available")


@app.post("/api/checklist/phase")
async def set_phase(request: SetPhaseRequest):
    """Set specific phase."""
    try:
        phase = Phase(request.phase)
        checklist_manager.set_phase(phase)
        checklist_manager.phase_mode = "manual"
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
        )
        return {"success": True, "phase": phase.value}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid phase")


@app.post("/api/checklist/reset")
async def reset_checklists():
    """Reset all checklists."""
    checklist_manager.reset_all()
    phase_detector.reset()
    await websocket_manager.send_state_update(
        connected=simconnect.connected,
        flight_state=simconnect.state.model_dump() if simconnect.connected else None,
        checklist_state=checklist_manager.get_state_dict(),
    )
    return {"success": True}


@app.post("/api/mode/auto")
async def set_auto_mode():
    """Set phase detection to auto mode."""
    checklist_manager.phase_mode = "auto"
    await websocket_manager.send_state_update(
        connected=simconnect.connected,
        flight_state=simconnect.state.model_dump() if simconnect.connected else None,
        checklist_state=checklist_manager.get_state_dict(),
    )
    return {"success": True, "mode": "auto"}


@app.post("/api/mode/manual")
async def set_manual_mode():
    """Set phase detection to manual mode."""
    checklist_manager.phase_mode = "manual"
    await websocket_manager.send_state_update(
        connected=simconnect.connected,
        flight_state=simconnect.state.model_dump() if simconnect.connected else None,
        checklist_state=checklist_manager.get_state_dict(),
    )
    return {"success": True, "mode": "manual"}


# Settings endpoints
@app.get("/api/settings")
async def get_settings():
    """Get current settings."""
    return settings_manager.settings.model_dump()


@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    """Save settings."""
    # Check if training mode changed
    old_training_mode = settings_manager.settings.training_mode

    settings_manager.update(
        simbrief_username=request.simbrief_username,
        dark_mode=request.dark_mode,
        training_mode=request.training_mode
    )

    # If training mode changed, reload checklists
    if request.training_mode != old_training_mode:
        checklist_manager.set_training_mode(request.training_mode)
        # Broadcast updated state
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
            auto_transition=config.AUTO_PHASE_TRANSITION,
            flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
        )

    return {"success": True, "settings": settings_manager.settings.model_dump()}


# SimBrief endpoints
@app.get("/api/flightplan")
async def get_flight_plan():
    """Get cached flight plan."""
    if simbrief_client.flight_plan:
        return {
            "success": True,
            "flight_plan": simbrief_client.flight_plan.model_dump(),
        }
    return {"success": False, "flight_plan": None, "message": "No flight plan loaded"}


@app.post("/api/flightplan/fetch")
async def fetch_flight_plan():
    """Fetch latest flight plan from SimBrief."""
    username = settings_manager.get_simbrief_username()
    if not username:
        raise HTTPException(status_code=400, detail="SimBrief username not configured")

    try:
        flight_plan = await simbrief_client.fetch_flight_plan(username)

        # Inject flight plan data into checklists
        checklist_manager.inject_flight_plan(flight_plan)

        # Broadcast updated state
        await websocket_manager.send_state_update(
            connected=simconnect.connected,
            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
            checklist_state=checklist_manager.get_state_dict(),
            auto_transition=config.AUTO_PHASE_TRANSITION,
            flight_plan=flight_plan.model_dump(),
        )

        return {"success": True, "flight_plan": flight_plan.model_dump()}

    except SimBriefUserNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SimBriefNetworkError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SimBriefError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/flightplan/clear")
async def clear_flight_plan():
    """Clear the cached flight plan."""
    simbrief_client.clear_flight_plan()
    checklist_manager.clear_flight_plan_data()

    await websocket_manager.send_state_update(
        connected=simconnect.connected,
        flight_state=simconnect.state.model_dump() if simconnect.connected else None,
        checklist_state=checklist_manager.get_state_dict(),
        auto_transition=config.AUTO_PHASE_TRANSITION,
        flight_plan=None,
    )

    return {"success": True}


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket_manager.connect(websocket)

    # Send initial state
    await websocket.send_json({
        "type": "state_update",
        "data": {
            "connected": simconnect.connected,
            "flight_state": simconnect.state.model_dump() if simconnect.connected else None,
            **checklist_manager.get_state_dict(),
            "auto_transition": config.AUTO_PHASE_TRANSITION,
            "flight_plan": simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
        }
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            msg_data = data.get("data", {})

            if msg_type == "check_item":
                checklist_manager.toggle_item(msg_data.get("phase"), msg_data.get("item_id"))
                await websocket_manager.send_state_update(
                    connected=simconnect.connected,
                    flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                    checklist_state=checklist_manager.get_state_dict(),
                    flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                )

            elif msg_type == "set_phase":
                try:
                    phase = Phase(msg_data.get("phase"))
                    checklist_manager.set_phase(phase)
                    # Sync the phase detector to this phase
                    phase_detector.sync_to_phase(phase)
                    # Check if this matches what detector would now detect
                    detected = phase_detector.detect(simconnect.state)
                    if phase == detected:
                        checklist_manager.phase_mode = "auto"
                    else:
                        checklist_manager.phase_mode = "manual"
                    await websocket_manager.send_state_update(
                        connected=simconnect.connected,
                        flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                        checklist_state=checklist_manager.get_state_dict(),
                        flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                    )
                except ValueError:
                    pass

            elif msg_type == "next_phase":
                checklist_manager.next_phase()
                # Sync detector to new phase
                phase_detector.sync_to_phase(checklist_manager.current_phase)
                # Check if we landed on the auto-detected phase
                detected = phase_detector.detect(simconnect.state)
                if checklist_manager.current_phase == detected:
                    checklist_manager.phase_mode = "auto"
                await websocket_manager.send_state_update(
                    connected=simconnect.connected,
                    flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                    checklist_state=checklist_manager.get_state_dict(),
                    flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                )

            elif msg_type == "prev_phase":
                checklist_manager.prev_phase()
                # Sync detector to new phase
                phase_detector.sync_to_phase(checklist_manager.current_phase)
                # Check if we landed on the auto-detected phase
                detected = phase_detector.detect(simconnect.state)
                if checklist_manager.current_phase == detected:
                    checklist_manager.phase_mode = "auto"
                await websocket_manager.send_state_update(
                    connected=simconnect.connected,
                    flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                    checklist_state=checklist_manager.get_state_dict(),
                    flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                )

            elif msg_type == "reset":
                checklist_manager.reset_all()
                phase_detector.reset()
                await websocket_manager.send_state_update(
                    connected=simconnect.connected,
                    flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                    checklist_state=checklist_manager.get_state_dict(),
                    flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                )

            elif msg_type == "set_mode":
                mode = msg_data.get("mode")
                if mode in ("auto", "manual"):
                    checklist_manager.phase_mode = mode
                    await websocket_manager.send_state_update(
                        connected=simconnect.connected,
                        flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                        checklist_state=checklist_manager.get_state_dict(),
                        flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                    )

            # Voice commands
            elif msg_type == "voice_start_listening":
                result = await voice_manager.start_listening()
                await websocket.send_json({"type": "voice_listening", "data": result})

            elif msg_type == "voice_stop_listening":
                # Audio data comes as base64-encoded in msg_data
                import base64
                audio_b64 = msg_data.get("audio_data")
                audio_data = base64.b64decode(audio_b64) if audio_b64 else None
                result = await voice_manager.stop_listening(audio_data)

                # If response accepted and auto-advance enabled, check the item
                if result.get("action") == "response_accepted" and result.get("auto_advance"):
                    item_id = result.get("item_id")
                    if item_id:
                        phase = checklist_manager.current_phase.value
                        checklist_manager.toggle_item(phase, item_id)
                        await websocket_manager.send_state_update(
                            connected=simconnect.connected,
                            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                            checklist_state=checklist_manager.get_state_dict(),
                            flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                        )

                await websocket.send_json({"type": "voice_result", "data": result})

            elif msg_type == "voice_web_speech_result":
                # Process result from Web Speech API (fallback)
                spoken_text = msg_data.get("text", "")
                result = await voice_manager.process_response(spoken_text)

                # If response accepted and auto-advance enabled, check the item
                if result.get("action") == "response_accepted" and result.get("auto_advance"):
                    item_id = result.get("item_id")
                    if item_id:
                        phase = checklist_manager.current_phase.value
                        checklist_manager.toggle_item(phase, item_id)
                        await websocket_manager.send_state_update(
                            connected=simconnect.connected,
                            flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                            checklist_state=checklist_manager.get_state_dict(),
                            flight_plan=simbrief_client.flight_plan.model_dump() if simbrief_client.flight_plan else None,
                        )

                await websocket.send_json({"type": "voice_result", "data": result})

            elif msg_type == "voice_announce_checklist":
                checklist = checklist_manager.get_current_checklist()
                if checklist:
                    result = await voice_manager.announce_checklist_available(
                        checklist.id,
                        checklist.title
                    )
                    await websocket.send_json({"type": "voice_speak", "data": result})

            elif msg_type == "voice_read_item":
                item_id = msg_data.get("item_id")
                checklist = checklist_manager.get_current_checklist()
                if checklist:
                    item = next((i for i in checklist.items if i["id"] == item_id), None)
                    if item:
                        result = await voice_manager.read_item_challenge(
                            item_id,
                            item["challenge"],
                            item["response"]
                        )
                        await websocket.send_json({"type": "voice_speak", "data": result})

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket_manager.disconnect(websocket)


# =============================================================================
# Voice API Endpoints
# =============================================================================

class VoiceSettingsRequest(BaseModel):
    enabled: bool = True
    auto_read_challenges: bool = True
    auto_advance_on_response: bool = True
    volume: float = 1.0
    speech_rate: float = 1.0
    ptt_keyboard_key: str = "Space"
    ptt_gamepad_button: int | None = None
    use_whisper: bool = True


class VoiceResponseRequest(BaseModel):
    spoken_text: str


class WhisperDownloadRequest(BaseModel):
    model_name: str = "base"


@app.get("/api/voice/status")
async def get_voice_status():
    """Get voice system status."""
    return voice_manager.get_status()


@app.post("/api/voice/settings")
async def update_voice_settings(request: VoiceSettingsRequest):
    """Update voice settings."""
    voice_manager.update_settings(**request.model_dump())
    return {"success": True, "settings": voice_manager.get_status()["settings"]}


@app.post("/api/voice/download-whisper")
async def download_whisper_model(request: WhisperDownloadRequest):
    """Download Whisper model for local STT."""
    try:
        success = await voice_manager.download_whisper_model(request.model_name)
        if success:
            return {"success": True, "status": voice_manager.stt.get_status()}
        else:
            return {"success": False, "error": "Failed to load model. Make sure openai-whisper is installed."}
    except Exception as e:
        logger.error(f"Whisper download error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/voice/announce-checklist")
async def announce_checklist():
    """Announce current checklist is available."""
    checklist = checklist_manager.get_current_checklist()
    if not checklist:
        raise HTTPException(status_code=400, detail="No current checklist")

    result = await voice_manager.announce_checklist_available(
        checklist.id,
        checklist.title
    )
    return result


@app.post("/api/voice/read-item/{item_id}")
async def read_checklist_item(item_id: str):
    """Read a specific checklist item challenge."""
    checklist = checklist_manager.get_current_checklist()
    if not checklist:
        raise HTTPException(status_code=400, detail="No current checklist")

    item = next((i for i in checklist.items if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    result = await voice_manager.read_item_challenge(
        item_id,
        item["challenge"],
        item["response"]
    )
    return result


@app.post("/api/voice/process-response")
async def process_voice_response(request: VoiceResponseRequest):
    """Process a spoken response (from Web Speech API)."""
    result = await voice_manager.process_response(request.spoken_text)

    # If response accepted and auto-advance enabled, check the item
    if result.get("action") == "response_accepted" and result.get("auto_advance"):
        item_id = result.get("item_id")
        if item_id:
            phase = checklist_manager.current_phase.value
            checklist_manager.toggle_item(phase, item_id)
            await websocket_manager.send_state_update(
                connected=simconnect.connected,
                flight_state=simconnect.state.model_dump() if simconnect.connected else None,
                checklist_state=checklist_manager.get_state_dict(),
            )

    return result


class TranscribeRequest(BaseModel):
    audio_data: str  # base64 encoded


@app.post("/api/voice/test-transcribe")
async def test_transcribe(request: TranscribeRequest):
    """Test transcription with audio data."""
    import base64

    if not voice_manager.stt.is_available:
        return {"text": None, "error": "Whisper not loaded. Download the model first."}

    try:
        audio_bytes = base64.b64decode(request.audio_data)
        text = await voice_manager.stt.transcribe_webm(audio_bytes)

        if text:
            return {"text": text, "error": None}
        else:
            return {"text": None, "error": "Could not transcribe audio"}
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return {"text": None, "error": str(e)}


# Serve audio files
audio_dir = config.BASE_DIR / "audio"
if audio_dir.exists():
    app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")


# Serve frontend static files
app.mount("/static", StaticFiles(directory=str(config.FRONTEND_DIR)), name="static")


@app.get("/api/network-info")
async def get_network_info():
    """Get network information for QR code generation."""
    import socket
    try:
        # Get local IP by connecting to an external address (doesn't actually connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    return {
        "ip": local_ip,
        "port": config.PORT,
        "url": f"http://{local_ip}:{config.PORT}"
    }


@app.get("/")
async def serve_frontend():
    """Serve the frontend."""
    return FileResponse(config.FRONTEND_DIR / "index.html")


@app.get("/welcome")
async def serve_welcome():
    """Serve the welcome/startup page."""
    return FileResponse(config.FRONTEND_DIR / "welcome.html")


@app.get("/settings")
async def serve_settings():
    """Serve the settings page."""
    return FileResponse(config.FRONTEND_DIR / "settings.html")

# A320 Checklist Companion

## Project Overview
A checklist companion app for the Airbus A320 in Microsoft Flight Simulator. Runs as a native Windows desktop app with a web UI accessible via QR code on mobile devices.

## Tech Stack
- **Backend:** Python 3.13, FastAPI, Uvicorn, WebSockets
- **Frontend:** Vanilla HTML/CSS/JS (in `frontend/`)
- **Desktop:** PyWebView for native window
- **MSFS Integration:** SimConnect library
- **Build:** PyInstaller (single-file executable)

## Project Structure
```
├── backend/           # FastAPI server
│   ├── main.py        # API endpoints and WebSocket handler
│   ├── config.py      # Configuration and path resolution
│   ├── checklist_manager.py
│   ├── simconnect_client.py
│   └── simbrief_client.py
├── frontend/          # Web UI (HTML/CSS/JS)
├── data/              # Checklist JSON files
├── assets/            # App icon
├── build/             # Build configuration
│   ├── build.bat      # Local build script (requires Python 3.13)
│   ├── checklist.spec # PyInstaller spec file
│   └── build_requirements.txt
└── desktop_app.py     # Desktop app entry point
```

## Building

### Local Build
```cmd
cd build
build.bat
```
Requires Python 3.13 (pythonnet doesn't support 3.14+).
Output: `build/dist/A320 Checklist Companion.exe`

### CI Build
GitHub Actions builds on tag push (`v*`). See `.github/workflows/build-release.yml`.

## Key Implementation Details

### Frozen App Paths
When running as a PyInstaller executable, `sys._MEIPASS` contains the temp extraction path. See `backend/config.py:get_base_dir()`.

### Uvicorn Import
The FastAPI app must be imported directly (not as a string) for PyInstaller compatibility. See `desktop_app.py`.

### SimConnect DLL
The SimConnect.dll is bundled via dynamic path detection in `checklist.spec` using `importlib.util.find_spec()`.

## Running from Source
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```
Then open http://localhost:2549

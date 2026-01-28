# A320 Checklist Companion

A desktop checklist companion for the Airbus A320 in Microsoft Flight Simulator. Features automatic phase detection via SimConnect and flight plan integration with SimBrief.

## Features

- **Native Desktop App** - Runs as a Windows application with optional mobile access via QR code
- **Interactive Checklists** - Tap to check off items, with visual feedback
- **SimConnect Integration** - Automatic phase detection based on aircraft state
- **SimBrief Integration** - Fetch your flight plan to populate fuel, baro settings, and route info
- **Real-time Updates** - WebSocket-based live sync across devices
- **Mobile-Friendly** - Use on your phone/tablet by scanning the QR code
- **Training Mode** - Extended checklists with more detailed items for learning
- **Dark Mode** - Optimized for low-light cockpit environments
- **Auto-Verification** - Some items automatically verify against simulator state

## Quick Start (Windows)

### Option 1: Download Release (Easiest)

1. Download the latest release from [Releases](https://github.com/benlarsendk/a320-checklist-companion/releases)
2. Extract and run `A320 Checklist Companion.exe`
3. Scan the QR code with your phone, or click "Open Checklist"

### Option 2: Run from Source

1. Install [Python 3.10+](https://python.org)
2. Clone or download this repository
3. Double-click `run.bat` or run:
   ```bash
   pip install -r requirements.txt
   python desktop_app.py
   ```

### Option 3: Build Your Own Executable

1. Install [Python 3.10+](https://python.org)
2. Run `build.bat`
3. Find the output in `dist\A320 Checklist Companion\`

## Screenshots

The UI shows:
- Current checklist phase with trigger condition
- Challenge/response format with dotted leader lines
- SimBrief values highlighted (expected)
- MSFS values shown alongside (actual) when connected
- Flight plan banner with route and fuel

## Usage

### Basic Operation

1. Launch the app - you'll see the welcome screen with QR code
2. **On PC**: Click "Open Checklist on This Computer"
3. **On Phone/Tablet**: Scan the QR code to access the checklist
4. Navigate through checklists using **PREV** / **NEXT** buttons
5. Tap items to mark them as checked
6. Use **RESET** to clear all checklists and start over

### Settings (Gear Icon)

- **Dark Mode** - Toggle dark theme for night flying
- **Training Checklists** - Extended checklists with more detailed items
- **SimBrief Username** - Enter your username to fetch flight plans
- **QR Code** - Scan to access on your phone

### SimBrief Integration

1. Open Settings (gear icon)
2. Enter your SimBrief username or Pilot ID
3. Click **Save Settings**
4. Click **Fetch Flight Plan** to load your latest OFP
5. Return to the checklist - fuel and baro values are now populated

### SimConnect (MSFS)

When MSFS is running:
- Connection status shows "LIVE" (green) when connected
- Phase automatically advances based on aircraft state
- Checklist items show actual vs expected values (e.g., `6,500 / 6,591 KG`)
- Some items auto-verify (parking brake, gear, spoilers, etc.)

## Configuration

The server runs on port **2549** (RFC 2549 - IP over Avian Carriers 🐦).

Edit `backend/config.py` to change:
- `HOST` / `PORT` - Server binding (default: `0.0.0.0:2549`)
- `SIMCONNECT_ENABLED` - Enable/disable SimConnect (default: `True`)
- `AUTO_PHASE_TRANSITION` - Auto-advance phases (default: `True`)

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI server & endpoints
│   ├── checklist_manager.py # Checklist state management
│   ├── simconnect_client.py # MSFS SimConnect integration
│   ├── simbrief_client.py   # SimBrief API client
│   ├── settings.py          # Persistent settings storage
│   ├── flight_state.py      # Flight state & phase detection
│   └── config.py            # Configuration
├── frontend/
│   ├── index.html           # Main checklist UI
│   ├── welcome.html         # Welcome/QR code screen (exe only)
│   ├── settings.html        # Settings page
│   ├── app.js               # Frontend JavaScript
│   └── styles.css           # Styling
├── data/
│   ├── A320_Normal_Checklist_2026.json   # Standard checklist
│   └── A320_Training_Checklist.json      # Extended training checklist
├── build/
│   ├── build.bat            # Windows build script
│   ├── build_requirements.txt  # Build environment dependencies
│   ├── checklist.spec       # PyInstaller configuration
│   └── installer.iss        # Inno Setup installer script
├── desktop_app.py           # Desktop GUI launcher (with splash screen)
├── run.py                   # CLI server launcher (no splash)
└── run.bat                  # Quick-start for Windows
```

## Building

### Prerequisites

- Python 3.10+
- Windows (for building Windows exe)

### Build Steps

1. Open the `build` folder
2. Run `build.bat` - this will:
   - Create a separate virtual environment in `build/venv`
   - Install all build dependencies
   - Build the executable with PyInstaller

3. Output will be in `build/dist/A320 Checklist Companion/`

### Creating an Installer

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Open `build/installer.iss` in Inno Setup
3. Compile to create the installer exe in `build/installer_output/`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Current flight & checklist state |
| `/api/settings` | GET/POST | Get/save settings |
| `/api/flightplan` | GET | Get cached flight plan |
| `/api/flightplan/fetch` | POST | Fetch from SimBrief |
| `/api/network-info` | GET | Get server IP for QR code |
| `/ws` | WebSocket | Real-time state updates |

## License

MIT

## Acknowledgments

- Checklist based on Airbus A320 FCOM Normal Procedures
- Training checklist based on FlyUK A320 checklist
- Built with FastAPI, PyWebView, SimConnect, and vanilla JavaScript

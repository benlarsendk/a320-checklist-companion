# A320 Checklist Companion

A web-based interactive checklist companion for the Airbus A320 in Microsoft Flight Simulator. Features automatic phase detection via SimConnect and flight plan integration with SimBrief.

## Features

- **Interactive Checklists** - Tap to check off items, with visual feedback
- **SimConnect Integration** - Automatic phase detection based on aircraft state (Windows/MSFS only)
- **SimBrief Integration** - Fetch your flight plan to populate fuel, baro settings, and route info
- **Real-time Updates** - WebSocket-based live sync across devices
- **Mobile-Friendly** - Dark theme optimized for tablet/phone use in the cockpit
- **Auto-Verification** - Some items automatically verify against simulator state (parking brake, gear, etc.)

## Screenshots

The UI shows:
- Current checklist phase with trigger condition
- Challenge/response format items
- SimBrief values highlighted in yellow (expected)
- MSFS values highlighted in blue (actual) when connected
- Flight plan banner with route and fuel

## Installation

### Prerequisites

- Python 3.10+
- Microsoft Flight Simulator (for SimConnect features, Windows only)
- SimBrief account (for flight plan integration)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/benlarsendk/a320-checklist-companion.git
   cd a320-checklist-companion
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the server:
   ```bash
   python run.py
   ```

5. Open in browser: `http://localhost:8080`

## Usage

### Basic Operation

1. Navigate through checklists using **PREV** / **NEXT** buttons
2. Tap items to mark them as checked
3. Use **RESET** to clear all checklists and start over

### SimBrief Integration

1. Click the gear icon (settings) in the top right
2. Enter your SimBrief username or Pilot ID
3. Click **Save Settings**
4. Click **Fetch Flight Plan** to load your latest OFP
5. Return to the checklist - fuel and baro values are now populated

### SimConnect (Windows/MSFS)

When running on Windows with MSFS active:
- Connection status shows "LIVE" (green) when connected
- Phase automatically advances based on aircraft state
- Checklist items show actual vs expected values (e.g., `6,500 / 6,591 KG`)
- Some items auto-verify (parking brake, gear, spoilers, etc.)

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI server & endpoints
│   ├── checklist_manager.py # Checklist state management
│   ├── simconnect_client.py # MSFS SimConnect integration
│   ├── simbrief_client.py   # SimBrief API client
│   ├── settings.py          # Persistent settings storage
│   ├── flight_state.py      # Flight state & phase detection
│   ├── websocket_manager.py # WebSocket connection handling
│   └── config.py            # Configuration
├── frontend/
│   ├── index.html           # Main checklist UI
│   ├── settings.html        # Settings page
│   ├── app.js               # Frontend JavaScript
│   └── styles.css           # Styling
├── data/
│   └── A320_Normal_Checklist_2026.json  # Checklist definitions
├── requirements.txt
└── run.py                   # Entry point
```

## Configuration

Edit `backend/config.py` to change:
- `HOST` / `PORT` - Server binding (default: `0.0.0.0:8080`)
- `SIMCONNECT_ENABLED` - Enable/disable SimConnect (default: `True`)
- `AUTO_PHASE_TRANSITION` - Auto-advance phases (default: `True`)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Current flight & checklist state |
| `/api/settings` | GET/POST | Get/save settings |
| `/api/flightplan` | GET | Get cached flight plan |
| `/api/flightplan/fetch` | POST | Fetch from SimBrief |
| `/api/checklist/toggle` | POST | Toggle item checked state |
| `/ws` | WebSocket | Real-time state updates |

## License

MIT

## Acknowledgments

- Checklist based on Airbus A320 FCOM Normal Procedures
- Built with FastAPI, SimConnect, and vanilla JavaScript

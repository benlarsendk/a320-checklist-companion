# A320 Checklist Companion

A checklist companion for the Airbus A320 in Microsoft Flight Simulator. Use it on your PC or scan the QR code to use on your phone/tablet.

![Windows](https://img.shields.io/badge/Windows-10%2B-blue)
![MSFS](https://img.shields.io/badge/MSFS-2020%20%7C%202024-green)

## Getting Started

### Download and Run (Recommended)

1. **[Download the latest release](https://github.com/benlarsendk/a320-checklist-companion/releases/latest)**
2. Extract the ZIP file
3. Run `A320 Checklist Companion.exe`
4. That's it! Use the checklist on your PC, or scan the QR code to use on your phone

No installation required. No Python needed. Just extract and run.

---

## Features

- **Works on any device** - Use on PC, or scan QR code for phone/tablet
- **SimConnect Integration** - Auto-detects flight phase when MSFS is running
- **SimBrief Integration** - Import your flight plan for accurate fuel/weight values
- **Two Checklist Modes** - Normal (quick) or Training (detailed)
- **Dark Mode** - Easy on the eyes for night flights
- **Offline** - No internet required (except for SimBrief fetch)

## How to Use

1. **Start the app** - You'll see a welcome screen with a QR code
2. **Choose how to use it:**
   - Click **"Open Checklist"** to use on your PC
   - Or **scan the QR code** with your phone to use there
3. **Go through your checklists** - Tap items to check them off
4. **Use PREV/NEXT** to move between checklist phases

### Optional: Connect SimBrief

1. Click the **gear icon** (settings)
2. Enter your **SimBrief username**
3. Click **Fetch Flight Plan**
4. Your fuel and weight values will now appear in the checklist!

### Optional: MSFS Integration

Just have MSFS running - the app will automatically:
- Connect and show "LIVE" status
- Advance checklists based on your flight phase
- Show actual vs expected values (e.g., fuel loaded vs planned)

---

## For Developers

### Run from Source

```bash
# Clone the repo
git clone https://github.com/benlarsendk/a320-checklist-companion.git
cd a320-checklist-companion

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run the server
python run.py
```

Then open `http://localhost:2549` in your browser.

### Build the Executable

```bash
cd build
build.bat
```

Output will be in `build/dist/A320 Checklist Companion/`

---

## Project Structure

```
├── backend/           # Python server (FastAPI)
├── frontend/          # Web UI (HTML/CSS/JS)
├── data/              # Checklist JSON files
├── build/             # Build scripts for Windows exe
├── run.py             # Start server (for developers)
└── desktop_app.py     # Desktop app with welcome screen
```

## Configuration

The app runs on port **2549**. Edit `backend/config.py` to change settings.

## License

MIT

## Credits

- Checklist based on Airbus A320 FCOM
- Training checklist based on FlyUK A320 procedures

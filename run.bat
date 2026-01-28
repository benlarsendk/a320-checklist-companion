@echo off
echo Starting A320 Checklist Companion...
echo.

REM Check if venv exists
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe desktop_app.py
) else (
    REM Try system Python
    python desktop_app.py
)

if errorlevel 1 (
    echo.
    echo Failed to start. Make sure Python is installed and dependencies are installed:
    echo   pip install -r requirements.txt
    echo.
    pause
)

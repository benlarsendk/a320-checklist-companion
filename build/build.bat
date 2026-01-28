@echo off
setlocal enabledelayedexpansion

echo.
echo  ============================================
echo   A320 CHECKLIST COMPANION - Build Script
echo  ============================================
echo.

REM Get the directory where this script is located
set "BUILD_DIR=%~dp0"
set "PROJECT_DIR=%BUILD_DIR%.."

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH
    echo  Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)

echo  [1/5] Checking Python version...
python --version

REM Create build virtual environment
if not exist "%BUILD_DIR%venv" (
    echo.
    echo  [2/5] Creating build virtual environment...
    python -m venv "%BUILD_DIR%venv"
) else (
    echo.
    echo  [2/5] Using existing build virtual environment...
)

echo.
echo  [3/5] Activating build environment...
call "%BUILD_DIR%venv\Scripts\activate.bat"

REM Install dependencies
echo.
echo  [4/5] Installing build dependencies...
pip install -r "%BUILD_DIR%build_requirements.txt"

REM Build the executable
echo.
echo  [5/5] Building executable...
echo.

REM Change to project directory for PyInstaller
pushd "%PROJECT_DIR%"
pyinstaller "%BUILD_DIR%checklist.spec" --noconfirm --distpath "%BUILD_DIR%dist" --workpath "%BUILD_DIR%work"
popd

if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   BUILD COMPLETE!
echo  ============================================
echo.
echo   Output folder:
echo   %BUILD_DIR%dist\A320 Checklist Companion\
echo.
echo   To run the app:
echo   %BUILD_DIR%dist\A320 Checklist Companion\A320 Checklist Companion.exe
echo.
echo   To create an installer, install Inno Setup and compile:
echo   %BUILD_DIR%installer.iss
echo.
pause

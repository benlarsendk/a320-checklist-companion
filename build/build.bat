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

REM Check if Python 3.13 is available (required for pythonnet/pywebview compatibility)
py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python 3.13 is not installed
    echo  Please install Python 3.13 from https://python.org
    echo  Note: Python 3.14+ is not supported due to pythonnet compatibility
    echo.
    pause
    exit /b 1
)

echo  [1/5] Checking Python version...
py -3.13 --version

REM Create build virtual environment (delete old one if Python version changed)
if exist "%BUILD_DIR%venv\pyvenv.cfg" (
    findstr /C:"3.13" "%BUILD_DIR%venv\pyvenv.cfg" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [INFO] Removing old venv (wrong Python version)...
        rmdir /s /q "%BUILD_DIR%venv"
    )
)

if not exist "%BUILD_DIR%venv" (
    echo.
    echo  [2/5] Creating build virtual environment with Python 3.13...
    py -3.13 -m venv "%BUILD_DIR%venv"
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

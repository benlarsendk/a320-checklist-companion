# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for MSFS A320 Checklist Companion

Build with: pyinstaller build/checklist.spec (from project root)
Or run build/build.bat
"""

import os
import sys
from pathlib import Path
import importlib.util

block_cipher = None

# SPECPATH is the build folder, project root is one level up
PROJECT_ROOT = Path(SPECPATH).parent

# Find SimConnect DLL dynamically (works in venv or global install)
simconnect_spec = importlib.util.find_spec('SimConnect')
simconnect_dll = Path(simconnect_spec.origin).parent / 'SimConnect.dll'

a = Analysis(
    [str(PROJECT_ROOT / 'desktop_app.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Include frontend files
        (str(PROJECT_ROOT / 'frontend'), 'frontend'),
        # Include data files (checklists)
        (str(PROJECT_ROOT / 'data' / 'A320_Normal_Checklist_2026.json'), 'data'),
        (str(PROJECT_ROOT / 'data' / 'A320_Training_Checklist.json'), 'data'),
        # Include SimConnect DLL
        (str(simconnect_dll), 'SimConnect'),
    ],
    hiddenimports=[
        # Uvicorn
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # Webview
        'webview',
        'clr',  # For Windows webview
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='A320 Checklist Companion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,  # No console window - pure GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: 'assets/icon.ico'
)

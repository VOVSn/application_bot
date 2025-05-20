# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Source paths are relative to the .spec file location (project root).
# Destination paths are relative to the top-level directory created in dist/
# For one-folder mode (onedir), this is dist/ApplicationBotGUI/

datas_to_bundle = [
    # Config files (user-editable, copied to the root of the output directory)
    # These will be located at dist/ApplicationBotGUI/settings.json etc.
    ('application_bot/settings.json', '.'),
    ('application_bot/questions.json', '.'),

    # Application resources (bundled with app, not typically user-edited by default)
    # These will be placed in the output directory, or subdirectories thereof.
    # e.g., dist/ApplicationBotGUI/languages.json
    ('application_bot/languages.json', '.'),
    # e.g., dist/ApplicationBotGUI/web_ui/ and its contents
    ('application_bot/web_ui', 'web_ui'),
    # e.g., dist/ApplicationBotGUI/fonts/DejaVuSans.ttf
    ('application_bot/fonts/DejaVuSans.ttf', os.path.join('fonts', 'DejaVuSans.ttf'))
]

# Hidden imports that PyInstaller might miss.
# pyinstaller-hooks-contrib (in your requirements.txt) should handle many of these,
# especially for popular libraries like pywebview.
# Explicitly adding them can be a fallback if hooks don't cover everything.
hidden_imports_list = [
    'webview.platforms.winforms', # For Windows (MSHTML/EdgeChromium via C#/.NET WinForms)
    'webview.platforms.cocoa',    # For macOS (WebKit via Objective-C/Cocoa)
    'webview.platforms.gtk',      # For Linux (WebKitGTK via PyGObject)
    'webview.platforms.qt',       # For Linux/macOS/Windows (QtWebEngine/QtWebKit via PyQt/PySide)
    # Add 'anyio._backends._asyncio' if you encounter 'RuntimeError: No async_backend specified' with anyio/httpx
    # 'PIL._tkinter_finder', # Unlikely needed as Pillow is used for PDF, not Tkinter UI
]


a = Analysis(
    ['application_bot/gui.py'], # Main script of the application
    pathex=['.'],  # Root directory of the project (where this .spec file is)
    binaries=[],   # List of tuples for non-python .dlls or .so files if any
    datas=datas_to_bundle,
    hiddenimports=hidden_imports_list,
    hookspath=[],  # Custom hooks directory
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False, # For one-folder builds, this is usually False.
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [], # Additional scripts (usually not needed for the main executable)
    exclude_binaries=True,
    name='ApplicationBotGUI', # Name of the executable file
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, # Set to True to strip symbols from executable/binaries (can make debugging harder)
    upx=True,    # Set to True to use UPX compression (if UPX is installed and in PATH)
    console=False, # False for a GUI application (no console window). Set to True for debugging.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None, # None means auto-detect architecture
    codesign_identity=None, # For macOS code signing
    entitlements_file=None, # For macOS entitlements
    icon='application_bot/icon.ico', # Path to the icon file (.ico on Windows, .icns on macOS)
)

# COLLECT creates the output folder for one-folder mode
coll = COLLECT(
    exe,
    a.binaries, # Binary files collected by Analysis
    a.zipfiles, # ZIP files (usually just the PYZ archive)
    a.datas,    # Data files specified in Analysis
    strip=False, # As above for EXE
    upx=True,    # As above for EXE, applies to bundled binaries
    upx_exclude=[],
    name='ApplicationBotGUI', # Name of the folder created in the 'dist' directory
)
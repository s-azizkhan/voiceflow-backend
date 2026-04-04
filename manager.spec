# ─────────────────────────────────────────────────────────────────────────────
# PyInstaller spec for VoiceFlow Manager (system tray + hotkey)
# Build:  .venv\Scripts\python.exe -m PyInstaller manager.spec
# ─────────────────────────────────────────────────────────────────────────────

import os
from pathlib import Path

block_cipher = None
SRC_DIR = Path(os.getcwd())

a = Analysis(
    [str(SRC_DIR / "manager.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Tray
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        # Notifications
        "win10toast",
        # Clipboard
        "pyperclip",
        "tkinter",
        "tkinter.tix",
        # Hotkey
        "pynput",
        "pynput.keyboard",
        "pynput.keyboard._win32",
        "pynput.mouse",
        "pynput.mouse._win32",
        # WebSocket
        "websocket",
        "websocket._abnf",
        "websocket._core",
        "websocket._exceptions",
        "websocket._handshake",
        "websocket._socket",
        "websocket._url",
        # Standard lib that might be needed
        "urllib.request",
        "json",
        "threading",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voiceflow-manager",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="voiceflow-manager",
)

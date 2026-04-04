# ─────────────────────────────────────────────────────────────────────────────
# PyInstaller spec for voiceflow-backend portable server
# Build:  .venv\Scripts\python.exe -m PyInstaller server.spec
# ─────────────────────────────────────────────────────────────────────────────

import os
from pathlib import Path

block_cipher = None
SRC_DIR = Path(os.getcwd())

a = Analysis(
    [str(SRC_DIR / "server.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[
        (str(SRC_DIR / ".env"), "."),
    ],
    hiddenimports=[
        "moonshine_voice",
        "moonshine_voice.transcriber",
        "torchaudio",
        "sounddevice",
        "soundfile",
        "dotenv",
        "fastapi",
        "starlette",
        "uvicorn",
        "python_multipart",
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
    name="voiceflow-server",
    debug=False,
    strip=False,
    upx=False,
    console=False,           # windowed — no console window
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="voiceflow-server",
)

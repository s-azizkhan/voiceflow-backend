"""
VoiceFlow Manager — System tray app that controls the server and provides
a global hotkey (Ctrl+Alt+V) for push-to-talk transcription.

Usage:
    python manager.py              (development)
    dist\voiceflow-manager\voiceflow-manager.exe  (portable)
"""

import asyncio
import json
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

# ── Detect frozen / dev ──────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    MANAGER_DIR = Path(sys.executable).parent
    # In installer layout: VoiceFlow/manager/voiceflow-manager.exe
    # and   VoiceFlow/server/voiceflow-server.exe
    # So server exe is in the sibling "server/" directory
    SERVER_EXE = MANAGER_DIR.parent / "voiceflow-server.exe"
else:
    BASE_DIR = Path(__file__).parent
    MANAGER_DIR = BASE_DIR
    SERVER_EXE = MANAGER_DIR / "dist" / "voiceflow-server" / "voiceflow-server.exe"
SERVER_PORT = 8765
SERVER_URL = f"http://localhost:{SERVER_PORT}"
WS_URL = f"ws://localhost:{SERVER_PORT}/vocal"

# ── Logging ─────────────────────────────────────────────────────────────────────

LOG_FILE = MANAGER_DIR / "voiceflow-manager.log"


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── Server subprocess ───────────────────────────────────────────────────────────

server_proc: Optional[subprocess.Popen] = None


def check_server_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{SERVER_URL}/health", timeout=1)
        return True
    except Exception:
        return False


def start_server() -> bool:
    global server_proc
    if server_proc and server_proc.poll() is None:
        if check_server_running():
            log("Server already running")
            return True
    if not SERVER_EXE.exists():
        log(f"ERROR: server not found at {SERVER_EXE}")
        return False
    log(f"Starting server: {SERVER_EXE}")
    try:
        server_proc = subprocess.Popen(
            [str(SERVER_EXE)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SERVER_EXE.parent),
        )
        threading.Thread(target=_read_server_output, daemon=True).start()
        log(f"Server started (PID {server_proc.pid})")
        return True
    except Exception as e:
        log(f"ERROR starting server: {e}")
        return False


def _read_server_output():
    global server_proc
    while server_proc:
        if server_proc.stdout is None:
            break
        line = server_proc.stdout.readline()
        if not line:
            break
        log(line.rstrip())


def stop_server():
    global server_proc
    if server_proc and server_proc.poll() is None:
        log("Stopping server...")
        try:
            import urllib.request
            req = urllib.request.Request(f"{SERVER_URL}/__ctrl__/stop", method="POST")
            urllib.request.urlopen(req, timeout=3)
            time.sleep(1)
        except Exception:
            pass
        if server_proc.poll() is None:
            try:
                os.kill(server_proc.pid, 9)
            except (ProcessLookupError, AttributeError, PermissionError):
                subprocess.run(["taskkill", "/F", "/PID", str(server_proc.pid)], capture_output=True)
            server_proc.wait(timeout=5)
        server_proc = None
        log("Server stopped.")


# ── Vocal WebSocket client ──────────────────────────────────────────────────────

class VocalClient:
    """Connects to /vocal WebSocket and collects transcription text."""

    def __init__(self):
        self.text = ""
        self.connected = False
        self._ws = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self.text = ""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            import websocket
            ws = websocket.WebSocketApp(
                WS_URL,
                on_message=self._on_message,
                on_open=self._on_open,
                on_error=self._on_error,
            )
            self._ws = ws
            ws.run_forever(ping_timeout=5)
        except Exception as e:
            log(f"VocalClient error: {e}")

    def _on_open(self, ws):
        self.connected = True
        log("VocalClient connected to /vocal")

    def _on_error(self, ws, error):
        self.connected = False
        log(f"VocalClient error: {error}")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            t = data.get("type", "")
            txt = data.get("text", "")
            if t == "partial" or t == "final":
                self.text = txt
        except Exception:
            pass

    def close(self):
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self.connected = False


# ── Global hotkey ───────────────────────────────────────────────────────────────

_listening = False
_vocal_client: Optional[VocalClient] = None


def _wait_for_server():
    """Wait up to 15s for server to be ready."""
    for _ in range(30):
        if check_server_running():
            return True
        time.sleep(0.5)
    return False


def _call_vocal_api(action: str) -> dict:
    """Call /vocal/start or /vocal/stop."""
    import urllib.request
    req = urllib.request.Request(
        f"{SERVER_URL}/vocal/{action}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _show_toast(title: str, msg: str, duration: int = 5):
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, msg, duration=duration, threaded=True)
    except Exception:
        log(f"Toast failed: {msg}")


def _copy_to_clipboard(text: str):
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    # Fallback: tkinter
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        return False


def toggle_listening():
    global _listening, _vocal_client

    if not check_server_running():
        log("Server not running — starting...")
        if not start_server():
            _show_toast("VoiceFlow", "Failed to start server", duration=3)
            return
        if not _wait_for_server():
            _show_toast("VoiceFlow", "Server failed to respond", duration=3)
            return

    if not _listening:
        # ── Start listening ──────────────────────────────────────────────────
        log("Hotkey: START listening")
        try:
            _call_vocal_api("start")
        except Exception as e:
            log(f"Failed to start vocal: {e}")
            _show_toast("VoiceFlow", f"Error: {e}", duration=3)
            return

        _vocal_client = VocalClient()
        _vocal_client.start()
        _listening = True
        _update_tray_icon("listening")
        _show_toast("VoiceFlow", "Listening... Press Ctrl+Alt+V to stop", duration=2)
        log("Listening started")

    else:
        # ── Stop listening ───────────────────────────────────────────────────
        log("Hotkey: STOP listening")
        _listening = False
        _update_tray_icon("stopping")

        # Capture text before closing client
        captured_text = ""
        if _vocal_client:
            captured_text = _vocal_client.text
            _vocal_client.close()
            _vocal_client = None

        # Tell server to stop and get final text
        try:
            result = _call_vocal_api("stop")
            text = result.get("text", "") or captured_text
            log(f"Vocal stop: {text or '(no speech)'}")
        except Exception as e:
            log(f"Failed to stop vocal: {e}")
            text = captured_text

        _update_tray_icon("idle")

        if text and text.strip():
            _show_toast("VoiceFlow", f"\"{text.strip()}\"", duration=5)
        else:
            log("No speech detected")
            _show_toast("VoiceFlow", "No speech detected", duration=3)


# ── System tray ────────────────────────────────────────────────────────────────

_tray = None
_tray_lock = threading.Lock()


def _create_icon(mode: str = "idle") -> "PIL.Image.Image":
    """Create a colored icon using Pillow."""
    try:
        from PIL import Image, ImageDraw

        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if mode == "idle":
            color = "#555555"
            draw.ellipse([4, 4, size - 4, size - 4], fill=color)
        elif mode == "listening":
            color = "#e74c3c"
            draw.ellipse([4, 4, size - 4, size - 4], fill=color)
            # Pulse ring
            draw.ellipse([8, 8, size - 8, size - 8], outline="#ff7b6b", width=3)
        elif mode == "starting":
            color = "#f39c12"
            draw.ellipse([4, 4, size - 4, size - 4], fill=color)
        else:  # stopping
            color = "#27ae60"
            draw.ellipse([4, 4, size - 4, size - 4], fill=color)

        return img
    except Exception as e:
        log(f"Icon creation failed: {e}")
        # Return a minimal fallback
        from PIL import Image
        return Image.new("RGBA", (32, 32), (80, 80, 80, 255))


def _update_tray_icon(mode: str):
    with _tray_lock:
        global _tray
        if _tray is None:
            return
        try:
            _tray.icon = _create_icon(mode)
            _tray.update_menu()
        except Exception as e:
            log(f" Tray update failed: {e}")


def _build_menu():
    server_status = "Running" if check_server_running() else "Stopped"

    def menu_item(label: str, action, enabled: bool = True):
        try:
            import pystray
            return pystray.MenuItem(label, action, enabled=enabled)
        except Exception:
            return None

    try:
        import pystray
        return pystray.Menu(
            menu_item(f"Server: {server_status}", lambda _: None, enabled=False),
            menu_item("Start Server", lambda _: _start_server_action(), enabled=(not check_server_running())),
            menu_item("Stop Server", lambda _: _stop_server_action(), enabled=check_server_running()),
            menu_item("Restart Server", lambda _: _restart_server_action()),
            pystray.Menu.SEPARATOR,
            menu_item("Open Dashboard", lambda _: webbrowser.open(f"{SERVER_URL}/__dashboard__")),
            menu_item("Open API Root", lambda _: webbrowser.open(SERVER_URL)),
            pystray.Menu.SEPARATOR,
            menu_item(f"Hotkey: Ctrl+Alt+V  ({'Active' if _listening else 'Idle'})", lambda _: None, enabled=False),
            pystray.Menu.SEPARATOR,
            menu_item("Exit", lambda _: _exit_app()),
        )
    except Exception as e:
        log(f"Menu build error: {e}")
        return pystray.Menu(lambda _: None)


def _start_server_action():
    if start_server():
        time.sleep(2)
        _refresh_tray()


def _stop_server_action():
    stop_server()
    _refresh_tray()


def _restart_server_action():
    stop_server()
    time.sleep(1)
    start_server()
    time.sleep(2)
    _refresh_tray()


def _refresh_tray():
    with _tray_lock:
        global _tray
        if _tray:
            try:
                _tray.menu = _build_menu()
                _tray.update_menu()
            except Exception as e:
                log(f" Tray refresh failed: {e}")


def _exit_app():
    log("Exiting VoiceFlow Manager...")
    global _listening
    _listening = False
    stop_server()
    global _tray
    if _tray:
        _tray.stop()
    sys.exit(0)


def _tray_poll():
    """Periodically refresh tray menu to reflect server state."""
    while True:
        time.sleep(5)
        _refresh_tray()


def _register_hotkey():
    """Register Ctrl+Alt+V global hotkey using pynput GlobalHotKeys."""
    try:
        from pynput.keyboard import GlobalHotKeys

        def on_activate():
            log("Hotkey Ctrl+Alt+V pressed")
            try:
                toggle_listening()
            except Exception as e:
                log(f"Hotkey action error: {e}")

        log("Registering global hotkey: Ctrl+Alt+V")
        hk = GlobalHotKeys({'<ctrl>+<alt>+<v>': on_activate})
        hk.start()
        log("Global hotkey registered")
        hk.join()

    except Exception as e:
        log(f"Hotkey registration failed: {e}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    log("=" * 40)
    log("VoiceFlow Manager starting...")
    log(f"Server exe: {SERVER_EXE}")
    log(f"Manager dir: {MANAGER_DIR}")

    # Auto-start server
    if not check_server_running():
        log("Server not running — auto-starting...")
        start_server()
        _wait_for_server()
    else:
        log("Server already running")

    # Start tray polling thread
    threading.Thread(target=_tray_poll, daemon=True).start()

    # Start hotkey listener
    threading.Thread(target=_register_hotkey, daemon=True).start()

    # Build and run system tray
    try:
        import pystray
        from PIL import Image
        icon_img = _create_icon("idle")
        global _tray
        _tray = pystray.Icon(
            "voiceflow",
            icon_img,
            "VoiceFlow Server",
            menu=_build_menu(),
        )
        log("Tray icon running")
        _tray.run()
    except Exception as e:
        log(f"Tray error: {e}")
        # Fallback: keep alive without tray
        log("Running without tray — press Enter to exit")
        input()


if __name__ == "__main__":
    main()

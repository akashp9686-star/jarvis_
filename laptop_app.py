"""
Laptop app entry point. Same jarvis_core brain as phone_app.py - only the
platform object and the UI differ.

The HUD (JarvisGUI and friends, ported from your original jarvis.py) lives
in gui.py, next to this file. gui.py's run_gui(platform) creates the
window and wires platform.gui_window to it automatically.
"""
import threading
import time

import keyboard

from jarvis_core.commands import route_command, _shutdown_requested
from jarvis_platform.windows_platform import WindowsPlatform
from gui import run_gui

platform = WindowsPlatform(gui_window=None)  # gui.py sets this once the HUD window exists

WAKE_WORDS = ["jarvis"]

# ---------------------------------------------------------------------
# Laptop-only commands: restart, log off, and window control. These are
# NEVER added to the phone app's command table.
# ---------------------------------------------------------------------
LAPTOP_ONLY_COMMANDS = [
    (["restart"], lambda cmd, p: p.restart()),
    (["log off", "log out", "sign out"], lambda cmd, p: p.log_off()),
    (["minimize"], lambda cmd, p: p.minimize_window()),
    (["close window"], lambda cmd, p: p.close_active_window()),
    (["restore"], lambda cmd, p: p.restore_window()),
    (["maximize"], lambda cmd, p: p.maximize_window()),
]


def _strip_wake_word(command):
    for w in WAKE_WORDS:
        command = command.replace(w, " ")
    return " ".join(command.split()).strip()


def main():
    platform.speak("Jarvis is ready. Say 'hey Jarvis' followed by your command, sir.")
    while not _shutdown_requested.is_set():
        try:
            heard = platform.listen(timeout=3, phrase_time_limit=4)
        except Exception:
            time.sleep(1)
            continue

        if not heard or not any(w in heard for w in WAKE_WORDS):
            continue

        platform.beep_heard()
        command = _strip_wake_word(heard)
        if not command:
            command = platform.listen(timeout=5, phrase_time_limit=6, speak_network_errors=True)
        if not command:
            continue

        try:
            route_command(command, platform, extra_commands=LAPTOP_ONLY_COMMANDS)
        except Exception as e:
            platform.speak("Something went wrong handling that command.")


def monitor_quit_hotkey():
    while not _shutdown_requested.is_set():
        if keyboard.is_pressed("ctrl+shift+q"):
            _shutdown_requested.set()
            break
        time.sleep(0.1)


if __name__ == "__main__":
    threading.Thread(target=main, daemon=True).start()
    threading.Thread(target=monitor_quit_hotkey, daemon=True).start()
    # Qt must run on the main thread - this blocks here until the window
    # closes or shutdown is requested (voice "exit", Ctrl+Shift+Q, or the
    # EXIT APP button).
    run_gui(platform)
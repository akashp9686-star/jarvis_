"""
Windows implementation of JarvisPlatform. This is basically your original
jarvis.py's OS-touching code, moved here unchanged, just reorganized
behind the shared interface. Your PyQt5 GUI (laptop_app.py) creates ONE
of these and passes it into jarvis_core.commands.route_command().
"""
import ctypes
import json
import logging
import os
import shutil
import subprocess
import threading
import time
import webbrowser

import psutil
import pygetwindow as gw
import pyttsx3
import speech_recognition as sr

from .base import JarvisPlatform

try:
    import winsound
    HAVE_WINSOUND = True
except ImportError:
    HAVE_WINSOUND = False

try:
    import pythoncom
    HAVE_PYTHONCOM = True
except ImportError:
    HAVE_PYTHONCOM = False

log = logging.getLogger("jarvis")

APP_NAME_FILLERS = [
    "can you", "could you", "would you", "will you",
    "please", "for me", "now", "jarvis", "hey",
]


class WindowsPlatform(JarvisPlatform):
    def __init__(self, gui_window=None):
        self.gui_window = gui_window  # optional, for the HUD chat log
        self._speak_lock = threading.Lock()
        self._engine = None

        # Mic is opened ONCE and kept open for the app's lifetime instead
        # of being re-opened + recalibrated on every listen() call - that
        # repeated open/calibrate was the source of the ~sub-second gap
        # between listens. dynamic_energy_threshold handles small drift
        # in background noise afterward, so a one-time calibration is
        # enough for normal use.
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = 300
        self._recognizer.dynamic_energy_threshold = True
        self._mic = None
        self._mic_source = None
        self._mic_lock = threading.Lock()

    def _ensure_mic_open(self):
        """Opens the microphone stream and calibrates ambient noise the
        first time listen() is called, then reuses that same open stream
        forever after. Safe to call repeatedly - it's a no-op once open."""
        if self._mic_source is not None:
            return self._mic_source
        with self._mic_lock:
            if self._mic_source is not None:  # re-check after acquiring lock
                return self._mic_source
            self._mic = sr.Microphone()
            self._mic_source = self._mic.__enter__()  # opens the stream, stays open
            self._recognizer.adjust_for_ambient_noise(self._mic_source, duration=0.5)
            log.info("Microphone opened and calibrated once; reusing for all future listens.")
            return self._mic_source

    def _get_engine(self):
        """Create the TTS engine once and reuse it - re-creating it on
        every speak() call (the old behavior) is what made replies slow.
        We manage the speech loop manually (startLoop/iterate) instead of
        calling runAndWait() repeatedly, because reusing one engine across
        multiple runAndWait() calls is a known pyttsx3-on-Windows bug that
        makes it go silent after the first sentence."""
        if self._engine is None:
            if HAVE_PYTHONCOM:
                try:
                    pythoncom.CoInitialize()
                except Exception as e:
                    log.debug(f"CoInitialize skipped: {e}")
            self._engine = pyttsx3.init()
            voices = self._engine.getProperty("voices")
            if voices:
                self._engine.setProperty("voice", voices[0].id)
            self._engine.setProperty("rate", 175)
            self._engine.setProperty("volume", 1.0)
            self._engine.startLoop(False)
        return self._engine

    # ---- Voice I/O ----------------------------------------------------
    def speak(self, text):
        if not text:
            return
        print(f"Jarvis says: {text}")
        if self.gui_window:
            self.gui_window.add_message("Jarvis", text)

        with self._speak_lock:
            try:
                engine = self._get_engine()
                engine.say(text)
                while engine.isBusy():
                    engine.iterate()
                    time.sleep(0.05)
            except Exception as e:
                log.error(f"[TTS error] {e}, retrying with a fresh engine")
                # pyttsx3 engines occasionally get stuck (a known Windows
                # SAPI5 quirk) - if that happens, rebuild just this once
                # instead of silently failing.
                try:
                    if self._engine is not None:
                        try:
                            self._engine.endLoop()
                        except Exception:
                            pass
                    self._engine = None
                    engine = self._get_engine()
                    engine.say(text)
                    while engine.isBusy():
                        engine.iterate()
                        time.sleep(0.05)
                except Exception as e2:
                    log.error(f"[TTS error on retry] {e2}")

    def listen(self, timeout=3, phrase_time_limit=4, speak_network_errors=False):
        source = self._ensure_mic_open()
        try:
            audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return ""
        except Exception as e:
            log.error(f"Unexpected error capturing audio in listen(): {e}")
            return ""

        # Recognition (network call) happens OUTSIDE the mic capture, so
        # the mic itself is free again immediately after the phrase ends -
        # no dead air waiting on Google's response before we can listen again.
        try:
            command = self._recognizer.recognize_google(audio).lower()
            print(f"Heard: {command}")
            return command
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            log.error(f"Speech recognition request error: {e}")
            if speak_network_errors:
                self.speak("Network error. Please check your internet connection.")
            return ""
        except Exception as e:
            log.error(f"Unexpected error in listen(): {e}")
            return ""

    def close_mic(self):
        """Optional cleanup - call on app exit if you want to release the
        mic stream explicitly. Not required for normal operation."""
        if self._mic is not None:
            try:
                self._mic.__exit__(None, None, None)
            except Exception as e:
                log.debug(f"close_mic failed: {e}")
            finally:
                self._mic = None
                self._mic_source = None

    def beep_heard(self):
        if HAVE_WINSOUND:
            try:
                winsound.Beep(1000, 120)
            except Exception as e:
                log.debug(f"beep_heard failed: {e}")

    # ---- Generic actions ------------------------------------------------
    def open_url(self, url):
        webbrowser.open(url)

    def _find_vscode(self):
        code_path = shutil.which("code")
        if code_path:
            return code_path
        for path in [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ]:
            if os.path.exists(path):
                return path
        return None

    def _find_start_app(self, name):
        safe_name = name.replace("'", "").replace('"', "").strip()
        if not safe_name:
            return None
        ps_command = (
            f"Get-StartApps | Where-Object {{ $_.Name -like '*{safe_name}*' }} "
            "| Select-Object -First 1 Name, AppID | ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_command],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip()
            if not output:
                return None
            data = json.loads(output)
            if isinstance(data, list):
                data = data[0] if data else None
            if not data:
                return None
            return data.get("Name"), data.get("AppID")
        except Exception as e:
            log.error(f"find_start_app failed for '{name}': {e}")
            return None

    def _extract_app_name(self, command):
        idx = command.find("open")
        name = command[idx + len("open"):] if idx != -1 else command
        for filler in APP_NAME_FILLERS:
            name = name.replace(filler, " ")
        return " ".join(name.split()).strip()

    def open_app(self, command):
        app_name = self._extract_app_name(command)
        if not app_name:
            self.speak("Which app would you like me to open?")
            return

        if "youtube" in app_name:
            self.open_url("https://www.youtube.com")
            self.speak("YouTube opened successfully.")
            return
        if "google" in app_name and "chrome" not in app_name:
            self.open_url("https://www.google.com")
            self.speak("Google opened successfully.")
            return
        if app_name == "browser":
            self.open_url("https://www.google.com")
            self.speak("Browser opened successfully.")
            return
        if "vs code" in app_name or "visual studio code" in app_name:
            vscode_path = self._find_vscode()
            if vscode_path:
                subprocess.Popen([vscode_path])
                self.speak("VS Code opened successfully.")
                return

        found = self._find_start_app(app_name)
        if found:
            name, app_id = found
            try:
                os.system(f'start explorer.exe shell:appsFolder\\{app_id}')
                self.speak(f"Opening {name}.")
            except Exception as e:
                log.error(f"Failed to launch {name} ({app_id}): {e}")
                self.speak(f"I found {name} but couldn't open it.")
            return

        exe_path = shutil.which(app_name.replace(" ", ""))
        if exe_path:
            try:
                subprocess.Popen([exe_path])
                self.speak(f"Opening {app_name}.")
                return
            except Exception as e:
                log.error(f"Failed to launch {exe_path}: {e}")

        self.speak(f"Sorry, I couldn't find an app called {app_name} on this laptop.")

    # ---- Power actions ---------------------------------------------------
    def power_action(self):
        """'shutdown'/'lock' both route here on Windows -> real shutdown."""
        self.speak("Shutting down your laptop.")
        os.system("shutdown /s /t 1")

    def restart(self):
        self.speak("Restarting your laptop.")
        os.system("shutdown /r /t 1")

    def log_off(self):
        self.speak("Logging off.")
        try:
            result = ctypes.windll.user32.ExitWindowsEx(0, 0)  # EWX_LOGOFF
            if not result:
                raise OSError(f"ExitWindowsEx failed, error code: {ctypes.GetLastError()}")
        except Exception as e:
            log.error(f"ExitWindowsEx failed, falling back to 'shutdown /l': {e}")
            os.system("shutdown /l")

    def check_battery(self):
        battery = psutil.sensors_battery()
        if battery:
            plugged = "charging" if battery.power_plugged else "not charging"
            self.speak(f"Your battery is at {battery.percent} percent and is {plugged}.")
        else:
            self.speak("Sorry, I couldn't read the battery status.")

    # ---- Window control (Windows-only) -----------------------------------
    def minimize_window(self):
        try:
            win = gw.getActiveWindow()
            if win:
                win.minimize()
                self.speak("Window minimized successfully.")
        except Exception as e:
            log.error(f"minimize_window failed: {e}")
            self.speak("Couldn't minimize the window.")

    def close_active_window(self):
        try:
            win = gw.getActiveWindow()
            if win:
                win.close()
                self.speak("Window closed successfully.")
        except Exception as e:
            log.error(f"close_active_window failed: {e}")
            self.speak("Couldn't close the window.")

    def restore_window(self):
        try:
            win = gw.getActiveWindow()
            if win:
                win.restore()
                self.speak("Window restored successfully.")
        except Exception as e:
            log.error(f"restore_window failed: {e}")
            self.speak("Couldn't restore the window.")

    def maximize_window(self):
        try:
            win = gw.getActiveWindow()
            if win:
                win.maximize()
                self.speak("Window maximized successfully.")
        except Exception as e:
            log.error(f"maximize_window failed: {e}")
            self.speak("Couldn't maximize the window.")
"""
The one interface both windows_platform.py and android_platform.py
implement. jarvis_core/commands.py only ever calls methods on this
interface - it never touches os.system, ctypes, pygetwindow, Android
intents, etc. directly. That's what makes the command logic shared.
"""
from abc import ABC, abstractmethod


class JarvisPlatform(ABC):
    # ---- Voice I/O -------------------------------------------------
    @abstractmethod
    def speak(self, text: str):
        ...

    @abstractmethod
    def listen(self, timeout=3, phrase_time_limit=4) -> str:
        ...

    # ---- Generic actions available on both platforms ---------------
    @abstractmethod
    def open_url(self, url: str):
        ...

    @abstractmethod
    def open_app(self, command: str):
        """command is the full spoken sentence, e.g. 'open whatsapp'."""
        ...

    @abstractmethod
    def power_action(self):
        """The word 'shutdown' maps here. Laptop -> real shutdown.
        Phone -> lock the screen."""
        ...

    @abstractmethod
    def check_battery(self):
        ...

    # ---- Laptop-only actions (default: not supported) ---------------
    def restart(self):
        raise NotImplementedError("Restart is only available on the laptop app.")

    def log_off(self):
        raise NotImplementedError("Log off is only available on the laptop app.")

    def minimize_window(self):
        raise NotImplementedError("Window control is only available on the laptop app.")

    def close_active_window(self):
        raise NotImplementedError("Window control is only available on the laptop app.")

    def restore_window(self):
        raise NotImplementedError("Window control is only available on the laptop app.")

    def maximize_window(self):
        raise NotImplementedError("Window control is only available on the laptop app.")

    # ---- Phone-only actions (default: not supported) -----------------
    def make_call(self, number: str):
        raise NotImplementedError("Calling is only available on the phone app.")

    def send_sms(self, number: str, message: str):
        raise NotImplementedError("SMS is only available on the phone app.")

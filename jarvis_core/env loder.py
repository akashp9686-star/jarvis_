"""
env_loader.py - Loads key=value pairs from a .env file into os.environ,
without requiring the third-party python-dotenv package.

Why this exists: python-dotenv was listed in buildozer.spec's
requirements, but wasn't reliably ending up importable in the built APK -
the app crashed on launch with `ModuleNotFoundError: No module named
'dotenv'` (visible in Logcat), which killed the Python side while
Android's native rendering threads were still running, producing a
downstream FORTIFY/SIGABRT crash. Removing the dependency removes the
failure point entirely, on both desktop and Android - this file works
identically on both platforms.

Call load_env() once, as early as possible - jarvis_core/__init__.py
does this automatically, before any other jarvis_core module reads
os.environ for API keys.
"""
import os


def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

"""
Command registry + router. This is the module that used to be scattered
across jarvis.py's route_command()/COMMAND_TABLE. Every handler now takes
(command, platform) and only ever talks to `platform`, never to os.system /
ctypes / pygetwindow / Android intents directly. That's what makes this
file identical on laptop and phone.

Each app (laptop_app.py / phone_app.py) builds its own COMMAND_TABLE by
combining CORE_COMMANDS with a small platform-specific extension list
(e.g. the phone app adds "call" and "text").
"""
import random
import threading

from .ai import ask_jarvis
from .memory import clear_memory
from .weather import get_weather
from .web_search import search_web
from .spotify_client import play_song

_shutdown_requested = threading.Event()


def tell_time(_command, platform):
    from datetime import datetime
    now = datetime.now()
    platform.speak(f"It's currently {now.strftime('%I:%M %p').lstrip('0')}.")


def tell_date(_command, platform):
    from datetime import datetime
    now = datetime.now()
    platform.speak(f"Today is {now.strftime('%A, %B %d, %Y')}.")


def tell_identity(_command, platform):
    platform.speak("I am Jarvis, your personal assistant. I was created by Aakash p.")


FOLLOWUPS = [
    "By the way, how was your day?",
    "How are you feeling right now?",
    "Did anything interesting happen today?",
    "Are you enjoying your evening?",
]


def handle_greeting(command, platform):
    reply = ask_jarvis(command)
    platform.speak(reply)
    if random.choice([True, False]):
        platform.speak(random.choice(FOLLOWUPS))


def request_exit(_command, platform):
    platform.speak("Goodbye. Shutting down Jarvis.")
    _shutdown_requested.set()


def _play_or_open(command, platform):
    if "spotify" in command or "song" in command or "music" in command:
        song = command.replace("play", "").replace("on spotify", "").strip()
        play_song(song, platform)
    else:
        platform.open_app(command)


# ---------------------------------------------------------------------
# Commands available on EVERY platform. The Windows-only ones (restart,
# log off, minimize/maximize/close window) live in laptop_app.py instead,
# and phone-only ones (call, text) live in phone_app.py - see below.
# ---------------------------------------------------------------------
CORE_COMMANDS = [
    (["exit", "quit", "goodbye"], request_exit),
    (["forget everything", "clear memory", "clear conversation", "forget our conversation"], clear_memory),
    (["shutdown", "lock"], lambda cmd, platform: platform.power_action()),
    (["battery"], lambda cmd, platform: platform.check_battery()),
    (["play"], _play_or_open),
    (["open"], lambda cmd, platform: platform.open_app(cmd)),
    (["who are you", "who made you", "who created you", "your creator", "your name"], tell_identity),
    (["weather"], get_weather),
    (["what time", "what's the time", "current time", "tell me the time", "time now", "time is it"], tell_time),
    (["what date", "what's the date", "today's date", "what day is it", "what's the day",
      "what day", "which day", "day today", "today's day", "date today"], tell_date),
    (["search the web for", "search google for", "google search for", "look up"], search_web),
    (["hi", "hello", "hey", "how are you", "whats up", "what's up"], handle_greeting),
]

# Words that signal "this needs a real, current web result" - not
# something the AI's frozen training knowledge can answer reliably.
# Anything else just talks to the AI directly, which is faster and more
# natural for general conversation and knowledge questions.
LIVE_INFO_KEYWORDS = [
    "latest", "current", "currently", "today's", "right now", "this week",
    "this month", "this year", "recent", "news", "score", "stock price",
    "exchange rate", "who is the current", "who is the president",
    "who is the prime minister", "election result", "release date",
]


def _needs_live_search(command):
    return any(keyword in command for keyword in LIVE_INFO_KEYWORDS)


# Phrases the AI tends to use when it's guessing or doesn't actually know -
# if its answer contains one of these, search the web for a real answer
# instead of speaking the uncertain one.
UNCERTAINTY_PHRASES = [
    "i don't have real-time", "i don't have access to real-time",
    "i don't have access to current", "as of my last update",
    "as of my knowledge cutoff", "i don't have up-to-date",
    "i'm not able to browse", "i cannot browse the internet",
    "i don't have information on", "i'm not sure",
    "i don't have specific information", "i don't have the ability to check",
]


def _seems_uncertain(reply):
    reply_lower = reply.lower()
    return any(phrase in reply_lower for phrase in UNCERTAINTY_PHRASES)


MASTER_ACKS = [
    "Yes, sir.",
    "Right away, sir.",
    "Of course, sir.",
    "Certainly, sir.",
]


def route_command(command, platform, extra_commands=None):
    """extra_commands lets each app prepend platform-specific entries
    (checked first, so e.g. phone_app.py's 'call' beats nothing in core)."""
    platform.speak(random.choice(MASTER_ACKS))

    table = (extra_commands or []) + CORE_COMMANDS
    for keywords, handler in table:
        if any(keyword in command for keyword in keywords):
            handler(command, platform)
            return

    if _needs_live_search(command):
        search_web(command, platform)
        return

    reply = ask_jarvis(command)
    if _seems_uncertain(reply):
        platform.speak("Let me check that for you.")
        search_web(command, platform)
    else:
        platform.speak(reply)
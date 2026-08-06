"""
Phone app entry point. Run this on Android (packaged via Buildozer).
Same jarvis_core brain as laptop_app.py - only the platform object and
the UI differ. The HUD (JarvisPhoneUI - visually matches the desktop's
Iron-Man look, laid out for a phone screen) lives in phone_gui.py.
"""
import re

from jarvis_core.commands import route_command
from jarvis_platform.android_platform import AndroidPlatform
from phone_gui import run_gui

platform = AndroidPlatform()


# ---------------------------------------------------------------------
# Phone-only commands: calling and texting. These are NEVER added to the
# laptop app's command table, so "call mom" does nothing on the laptop.
# ---------------------------------------------------------------------
MESSAGE_TRIGGER = re.compile(r"(?:saying|that says|message)\s+(.+)")


def _split_number_and_message(command):
    """Only look for digits in the part of the sentence BEFORE the
    message trigger word - otherwise numbers mentioned inside the
    message itself (e.g. 'saying running 10 minutes late') get glued
    onto the phone number. See test_command_parsing.py for the case
    that caught this."""
    match = MESSAGE_TRIGGER.search(command)
    number_part = command[:match.start()] if match else command
    message = match.group(1).strip() if match else ""

    digits = re.sub(r"[^\d]", "", number_part)
    number = digits if len(digits) >= 7 else ""
    return number, message


def _handle_call(command, platform_):
    number, _ = _split_number_and_message(command)
    if not number:
        platform_.speak("What number would you like me to call? Please say the digits.")
        return
    platform_.make_call(number)


def _handle_text(command, platform_):
    number, message = _split_number_and_message(command)
    if not number:
        platform_.speak("What number would you like me to text?")
        return
    platform_.send_sms(number, message)


PHONE_ONLY_COMMANDS = [
    (["call"], _handle_call),
    (["text", "send a message", "send sms"], _handle_text),
]


if __name__ == "__main__":
    run_gui(platform, extra_commands=PHONE_ONLY_COMMANDS)
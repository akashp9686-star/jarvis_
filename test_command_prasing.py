"""
test_command_parsing.py - Run this on your laptop to sanity-check the
number/message extraction from phone_app.py BEFORE testing on a real
device. Catches the most common bugs (wrong digits, message not split
out correctly, wrong contact matched) in seconds instead of a
multi-minute build/deploy cycle.

    python test_command_parsing.py
"""
import re

# --- copied from phone_app.py so this can run standalone ---

# Contact book: name (lowercase) -> phone number
CONTACTS = {
    "aakash": "9686240473",
    "appa": "9449680473",
    "amma": "9481822809",
}

MESSAGE_TRIGGER = re.compile(r"(?:saying|that says|message)\s+(.+)")


def _find_contact(text):
    """Look for a known contact name in the text. Returns (name, number) or (None, None)."""
    lower = text.lower()
    for name, number in CONTACTS.items():
        if re.search(rf"\b{name}\b", lower):
            return name, number
    return None, None


def _split_number_and_message(command):
    match = MESSAGE_TRIGGER.search(command)
    number_part = command[:match.start()] if match else command
    message = match.group(1).strip() if match else ""

    # 1. Try matching a known contact name first (e.g. "call amma",
    #    "text Aakash saying I'm running late")
    contact_name, contact_number = _find_contact(number_part)
    if contact_number:
        return contact_number, message, contact_name

    # 2. Fall back to extracting raw digits from the command
    digits = re.sub(r"[^\d]", "", number_part)
    number = digits if len(digits) >= 7 else ""
    return number, message, None


TEST_CASES = [
    "call 9876543210",
    "call nine eight seven six five four three two one zero",  # spoken digits as words - see note below
    "call my mom at 9876543210",
    "text 9876543210 saying I'm on my way",
    "text 9876543210 that says running 10 minutes late",
    "send sms 9876543210 message call me back",
    "call 987 654 3210",
    "text 98765",  # too short - should fail extraction on purpose
    # --- named contacts ---
    "call Aakash",
    "call aakash",
    "text aakash saying I'm on my way",
    "call appa",
    "text appa that says I'll be home by 8",
    "call amma",
    "text amma message pick up milk on your way back",
]

if __name__ == "__main__":
    for cmd in TEST_CASES:
        number, message, contact_name = _split_number_and_message(cmd)
        status = "OK" if number else "NO NUMBER FOUND"
        who = f" ({contact_name})" if contact_name else ""
        print(f"[{status:16}] '{cmd}'")
        print(f"                  -> number: {number or '(none)'!r}{who}, message: {message or '(none)'!r}")
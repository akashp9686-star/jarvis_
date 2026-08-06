"""
Rolling short-term conversation memory. Identical on laptop and phone -
no OS-specific code here at all.
"""

CONVERSATION_HISTORY = []
MAX_HISTORY_MESSAGES = 16  # ~8 back-and-forth exchanges


def remember(role, content):
    if not content:
        return
    CONVERSATION_HISTORY.append({"role": role, "content": content})
    if len(CONVERSATION_HISTORY) > MAX_HISTORY_MESSAGES:
        del CONVERSATION_HISTORY[: len(CONVERSATION_HISTORY) - MAX_HISTORY_MESSAGES]


def clear_memory(_command, platform):
    CONVERSATION_HISTORY.clear()
    platform.speak("Okay, I've cleared our conversation history.")

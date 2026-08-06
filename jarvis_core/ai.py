"""
LLM chat (OpenRouter). Identical on laptop and phone - it's just an HTTPS
call, no OS dependency.
"""
import logging
import os

import requests

from .memory import CONVERSATION_HISTORY, remember

log = logging.getLogger("jarvis")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

JARVIS_PERSONA = (
    "You are Jarvis, a personal voice assistant. Your creator is Aakash p. "
    "If asked who you are, say you are Jarvis. If asked who made, built, or "
    "created you, say Aakash p is your creator. Keep replies conversational "
    "and fairly brief, since they will be spoken aloud. The conversation "
    "history below may include earlier turns - use it to resolve follow-up "
    "questions that depend on earlier context."
)


def ask_jarvis(prompt):
    if not OPENROUTER_API_KEY:
        return "My language model key isn't set up yet. Please add OPENROUTER_API_KEY to your .env file."

    remember("user", prompt)

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "system", "content": JARVIS_PERSONA}] + CONVERSATION_HISTORY,
    }
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=data, timeout=15,
        )
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            reply = result["choices"][0]["message"]["content"]
            remember("assistant", reply)
            return reply
        log.error(f"Unexpected OpenRouter response: {result}")
        return "Sorry, I couldn't get a proper response."
    except Exception as e:
        log.error(f"OpenRouter request failed: {e}")
        return "Sorry, I ran into an error reaching the language model."

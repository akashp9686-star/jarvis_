"""
Weather via wttr.in - identical on laptop and phone.
"""
import logging
import re

import requests

log = logging.getLogger("jarvis")


def get_weather(command, platform):
    match = re.search(r"weather (?:in|for|of|at)\s+(.+)", command)
    city = match.group(1).strip() if match else ""

    try:
        url = f"https://wttr.in/{city}?format=%C+%t" if city else "https://wttr.in/?format=%C+%t"
        response = requests.get(url, timeout=10, headers={"User-Agent": "curl"})
        weather_text = response.text.strip()

        if response.status_code != 200 or not weather_text or "Unknown location" in weather_text:
            platform.speak(f"Sorry, I couldn't find the weather{' for ' + city if city else ''}.")
            return

        location_phrase = f"in {city}" if city else "here"
        platform.speak(f"The weather {location_phrase} is {weather_text}.")
    except Exception as e:
        log.error(f"Weather fetch failed: {e}")
        platform.speak("Sorry, I couldn't fetch the weather right now.")

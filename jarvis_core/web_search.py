"""
Web search / quick-answer scraping - identical logic on laptop and phone.
The only platform-specific bit (actually opening a URL) is delegated to
platform.open_url(), since `webbrowser.open()` doesn't work on Android.
"""
import logging

import requests
from bs4 import BeautifulSoup

from .ai import ask_jarvis
from .memory import remember

log = logging.getLogger("jarvis")


def search_web(query, platform):
    try:
        query = query.replace("search", "").replace("what is", "").replace("who is", "").strip()
        if not query:
            platform.speak("What would you like me to search for?")
            return ""

        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        platform.open_url(url)

        selectors = [
            "div.BNeawe.s3v9rd.AP7Wnd",
            "div.BNeawe.tAd8D.AP7Wnd",
            "span.hgKElc",
            "div[data-attrid='description']",
            "div[data-attrid='wa:/description']",
        ]

        for selector in selectors:
            tag = soup.select_one(selector)
            if tag and tag.get_text(strip=True):
                answer = tag.get_text(strip=True)
                remember("user", query)
                remember("assistant", answer)
                platform.speak(answer)
                return answer

        log.info("No scrape match found, falling back to LLM answer.")
        reply = ask_jarvis(query)
        platform.speak(reply)
        return reply
    except Exception as e:
        log.error(f"search_web failed: {e}")
        platform.speak("An error occurred while searching.")
        return "An error occurred while searching."

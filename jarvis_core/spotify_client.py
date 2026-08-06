"""
Spotify track lookup - identical on laptop and phone. Opening the result
(platform.open_url) is the only delegated part.
"""
import logging
import os

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

log = logging.getLogger("jarvis")

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

_sp = None


def get_spotify_client():
    global _sp
    if _sp is not None:
        return _sp
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        log.warning("Spotify credentials not set.")
        return None
    try:
        _sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        ))
        return _sp
    except Exception as e:
        log.error(f"Spotify auth failed: {e}")
        return None


def play_song(song_name, platform):
    if not song_name:
        platform.speak("What song would you like me to play?")
        return

    client = get_spotify_client()
    if client is None:
        platform.speak(f"Searching for {song_name} on Spotify.")
        platform.open_url(f"https://open.spotify.com/search/{song_name.replace(' ', '%20')}")
        return

    try:
        results = client.search(q=song_name, limit=1, type="track")
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            platform.speak(f"I couldn't find {song_name} on Spotify.")
            return

        track = tracks[0]
        track_url = track["external_urls"]["spotify"]
        platform.speak(f"Here's {track['name']} by {track['artists'][0]['name']}.")
        platform.open_url(track_url)
    except Exception as e:
        log.error(f"Spotify search failed: {e}")
        platform.speak(f"Searching for {song_name} on Spotify.")
        platform.open_url(f"https://open.spotify.com/search/{song_name.replace(' ', '%20')}")

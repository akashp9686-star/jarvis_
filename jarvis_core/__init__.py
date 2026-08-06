"""
jarvis_core package init. This runs once, the very first time anything
imports jarvis_core (which both laptop_app.py and phone_app.py do before
touching ai.py/spotify_client.py) - so it's the right place to load the
.env file into os.environ before those modules read their keys.
"""
from dotenv import load_dotenv

load_dotenv()
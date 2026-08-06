[app]
title = Jarvis
package.name = jarvis
package.domain = org.aakashp
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
# .env has no extension, so include_exts above won't catch it - this
# pattern-based include is what actually gets your API keys bundled in.
source.include_patterns = .env
version = 0.1

# jarvis_core needs requests, beautifulsoup4, spotipy (which needs
# urllib3/oauthlib). Kivy is required for the UI. plyer gives TTS.
# python-dotenv is required if jarvis_core loads .env via load_dotenv().
# python3 is pinned to a known-stable version instead of left unpinned -
# unpinned requirements pull whatever the newest python-for-android
# recipe is, which recently resolved to Python 3.14 (very new), and
# bleeding-edge Python versions frequently aren't fully compatible with
# p4a's build recipes yet. This is the most likely cause of the native
# compile failure we hit.
requirements = python3==3.11.9,kivy,plyer,requests,beautifulsoup4,spotipy,pyjnius,python-dotenv

orientation = portrait
fullscreen = 0

# RECORD_AUDIO -> listen(); CALL_PHONE + READ_PHONE_STATE -> make_call();
# INTERNET -> ai.py/weather.py/web_search.py/spotify_client.py.
# SEND_SMS is deliberately NOT requested - send_sms() opens the SMS app
# for the user to tap send instead, since Play Store restricts silent
# SEND_SMS to the device's default messaging app.
android.permissions = INTERNET, RECORD_AUDIO, CALL_PHONE, READ_PHONE_STATE

android.api = 33
android.minapi = 24
# Building arm64-v8a ONLY, not armeabi-v7a - dropped the 32-bit target.
# Modern Android NDKs increasingly have rough edges building 32-bit
# targets from source, and it was the second-most-likely cause of the
# native compile failure. arm64-v8a alone covers essentially every real
# Android phone from the last ~7+ years, and this also roughly halves
# build time since it's no longer compiling everything twice.
android.archs = arm64-v8a

# Required so power_action() can call DevicePolicyManager.lockNow() once
# the user enables Jarvis as a Device Administrator in Settings.
android.add_activites =

[buildozer]
log_level = 2

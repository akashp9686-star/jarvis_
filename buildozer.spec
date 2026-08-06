[app]
title = Jarvis
package.name = jarvis
package.domain = org.aakashp
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.include_patterns = .env
version = 0.1

# jarvis_core needs requests, beautifulsoup4, spotipy (which needs
# urllib3/oauthlib). Kivy is required for the UI. plyer gives TTS.
requirements = python3==3.11.9,kivy,plyer,requests,beautifulsoup4,typing_extensions,spotipy,pyjnius

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
# arm64-v8a only - virtually every phone since ~2017 is 64-bit, and
# building armeabi-v7a (32-bit) too hits a known python-for-android
# linker issue ("unable to find library -luuid") on this toolchain.
android.archs = arm64-v8a

# Pin the exact python-for-android version buildozer clones. Without this,
# buildozer always git-clones p4a's bleeding-edge "master" branch, which
# currently defaults to a Python 3.14 hostpython recipe that conflicts
# with the 3.11 Python this build otherwise uses - causing:
#   "python3 should have same version as hostpython3, 3.11.9 != 3.14.2"
p4a.branch = v2024.01.21

# Required so power_action() can call DevicePolicyManager.lockNow() once
# the user enables Jarvis as a Device Administrator in Settings.
android.add_activites =

[buildozer]
log_level = 2

# Jarvis — Laptop + Android scaffold

A voice assistant with a shared "brain" that runs on both a laptop and an Android phone, with platform-specific action layers for each.

## Table of Contents

- [What this is](#what-this-is)
- [Prerequisites](#prerequisites)
- [Running the laptop app](#running-the-laptop-app)
- [Running/building the phone app](#runningbuilding-the-phone-app)
- [Laptop vs phone differences](#whats-genuinely-newdifferent-on-the-phone)
- [Known simplifications](#known-simplifications-youll-want-to-harden-before-shipping)
- [Why this split](#why-this-split-instead-of-one-literal-file)
- [Contributing](#contributing)
- [Owner](#owner)
- [License](#license)

## What this is

Your original single-file `jarvis.py` split into a shared brain
(`jarvis_core/`) and two swappable platform layers (`jarvis_platform/`),
so the same command logic runs on both the laptop and an Android phone.

```
jarvis_core/            <- shared, no OS-specific code
    ai.py                  (OpenRouter chat)
    memory.py               (conversation history)
    weather.py
    web_search.py
    spotify_client.py
    commands.py             (command table + route_command)

jarvis_platform/
    base.py                 (the interface both platforms implement)
    windows_platform.py     (your original OS code, moved here as-is)
    android_platform.py     (NEW: lock, call, sms, Android TTS/STT, app launch)

laptop_app.py            <- entry point for the laptop
phone_app.py              <- entry point for the phone (Kivy)
buildozer.spec             <- packages phone_app.py into an .apk
```

## Prerequisites

- Python 3.9+ for the laptop app
- [Buildozer](https://buildozer.readthedocs.io/) for building the Android app
- An OpenRouter API key (for `ai.py`) and any other service keys used in `jarvis_core/`
- An Android device (or emulator) with USB debugging enabled, for testing the phone app

## Running the laptop app

```
pip install -r requirements-laptop.txt
python laptop_app.py
```

This is functionally your old `jarvis.py`, reorganized. **Your PyQt5 HUD
GUI is not copied into `laptop_app.py` yet** — see the TODO comment at
the top of that file for the 3 small steps to wire your existing GUI
classes back in. Everything else (shutdown, restart, log off, window
control, weather, Spotify, search, chat) works exactly as before.

## Running/building the phone app

```
pip install buildozer
buildozer android debug     # builds bin/jarvis-0.1-debug.apk
adb install bin/jarvis-0.1-debug.apk
```

First run on the device: grant microphone + phone permissions when
prompted, then go to **Settings → Security → Device admin apps** and
enable Jarvis, so "lock" works.

## What's genuinely new/different on the phone

| Laptop                                 | Phone                                                               |
| --------------------------------------- | -------------------------------------------------------------------- |
| "shutdown" → real shutdown              | "shutdown" / "lock" → screen lock (`DevicePolicyManager.lockNow()`)  |
| always-on "hey Jarvis" listening        | tap-to-talk mic button (see note below)                              |
| "restart" / "log off" / window control  | not available (no phone equivalent)                                  |
| —                                        | "call [number]" → places a call (`ACTION_CALL`)                      |
| —                                        | "text [number] saying [message]" → opens SMS app pre-filled          |

## Known simplifications you'll want to harden before shipping

1. **No always-on wake word on Android.** Background mic listening needs
   a foreground service + battery-optimization exemption and is fragile
   across phone brands. Start with the mic button; add always-on later
   if you still want it, using Android's `SpeechRecognizer` in a
   foreground service.
2. **Device Admin for lock requires a custom `AndroidManifest.xml`** with
   a `DeviceAdminReceiver` — Buildozer's default template doesn't
   include one automatically. You'll need to add a small p4a
   bootstrap/recipe or a custom manifest snippet for `power_action()` to
   actually work; right now it will raise until that's wired up.
3. **Contact-name calling** ("call mom") isn't implemented —
   `phone_app.py` currently expects spoken digits. Add a `READ_CONTACTS`
   lookup via `ContactsContract` in `android_platform.py` if you want
   name lookups.
4. **`open_app` on Android** matches installed apps by label substring —
   test it against your actual installed app list; some OEM launchers
   rename apps in ways that won't match cleanly.

## Why this split instead of one literal file

PyQt5, `pywin32`, `keyboard`, `pygetwindow`, `winsound`, and `ctypes`
Windows API calls have no Android equivalent — a phone OS doesn't allow
apps to do most of what those libraries do. The shared/swappable split
above is the standard way real cross-platform assistants handle this:
one brain, one thin platform-specific action layer per OS.

## Contributing

This is currently a personal/solo project. Issues and pull requests are
welcome — see [CODEOWNERS](./CODEOWNERS) for review assignment.

## Owner

Maintained by [@akashp9686-star](https://github.com/akashp9686-star).

## License

No license specified yet — consider adding one (e.g. MIT) if you plan to
share or open source this project.

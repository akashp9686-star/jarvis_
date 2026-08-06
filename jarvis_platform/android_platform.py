"""
Android implementation of JarvisPlatform, for use inside a Kivy app built
with Buildozer. Uses pyjnius to call native Android APIs directly (there's
no PyQt5/pywin32/ctypes equivalent on Android - this is the real
replacement for those calls).

IMPORTANT - things you'll need to test/tune on a real device:
  * speak()/listen() here assume `plyer` for TTS and a push-to-talk style
    listen() using Android's SpeechRecognizer. True always-on "hey jarvis"
    wake-word listening in the background is NOT realistic for a first
    version on Android (needs a foreground service + battery-optimization
    exemption + is fragile across OEMs) - start with a mic button
    ("tap to talk") instead of continuous listening.
  * power_action() (lock) requires the user to manually enable this app
    as a Device Administrator once, in Settings, before it will work.
  * make_call() requires the user to grant the CALL_PHONE runtime
    permission (a Google Play "sensitive permission" - expect to justify
    it in Play Console if you publish this).
  * send_sms() intentionally does NOT auto-send silently. It opens the
    SMS app pre-filled and lets the user tap send - Google restricts
    silent SEND_SMS to a device's default messaging app, which Jarvis
    realistically won't be.

buildozer.spec permissions needed (see buildozer.spec in this project):
    android.permissions = INTERNET, RECORD_AUDIO, CALL_PHONE, READ_PHONE_STATE
"""
import logging

from .base import JarvisPlatform

log = logging.getLogger("jarvis")

try:
    from jnius import autoclass, cast
    from android.permissions import request_permissions, Permission  # noqa: F401
    ON_ANDROID = True
except ImportError:
    # Lets you import this module on a laptop (e.g. for linting/tests)
    # without pyjnius/python-for-android installed.
    ON_ANDROID = False


class AndroidPlatform(JarvisPlatform):
    def __init__(self, gui_window=None):
        # gui_window is set by phone_gui.py's run_gui() once the HUD
        # window exists, the same convention windows_platform.py uses -
        # speak() below writes into it so the on-screen status line and
        # log actually update instead of sitting frozen.
        self.gui_window = gui_window
        if ON_ANDROID:
            self.PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self.activity = self.PythonActivity.mActivity
            self._request_runtime_permissions()

    def _request_runtime_permissions(self):
        request_permissions([
            Permission.RECORD_AUDIO,
            Permission.CALL_PHONE,
            Permission.READ_PHONE_STATE,
        ])

    # ---- Voice I/O ------------------------------------------------------
    def speak(self, text):
        if not text:
            return
        print(f"Jarvis says: {text}")
        if self.gui_window:
            self.gui_window.add_message("Jarvis", text)
        try:
            from plyer import tts
            tts.speak(message=text)
        except Exception as e:
            log.error(f"[Android TTS error] {e}")

    def listen(self, timeout=5, phrase_time_limit=6, speak_network_errors=False):
        """Push-to-talk style: launches Android's built-in speech recognizer
        UI and blocks (via a small event) until it returns a result or times
        out. Wire this to a mic button in phone_app.py rather than a
        continuous background loop."""
        if not ON_ANDROID:
            return ""
        try:
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            Intent = autoclass("android.content.Intent")
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
            )
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)

            result_holder = {"text": ""}
            done = __import__("threading").Event()

            def on_activity_result(request_code, result_code, intent_data):
                try:
                    matches = intent_data.getStringArrayListExtra(
                        RecognizerIntent.EXTRA_RESULTS
                    )
                    if matches and matches.size() > 0:
                        result_holder["text"] = matches.get(0).lower()
                except Exception as e:
                    log.error(f"Speech result parsing failed: {e}")
                finally:
                    done.set()

            from android import activity as _android_activity
            _android_activity.bind(on_activity_result=on_activity_result)
            self.activity.startActivityForResult(intent, 1001)
            done.wait(timeout=timeout + phrase_time_limit)
            print(f"Heard: {result_holder['text']}")
            return result_holder["text"]
        except Exception as e:
            log.error(f"Unexpected error in Android listen(): {e}")
            return ""

    # ---- Generic actions --------------------------------------------------
    def open_url(self, url):
        if not ON_ANDROID:
            return
        try:
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            self.activity.startActivity(intent)
        except Exception as e:
            log.error(f"open_url failed: {e}")

    def open_app(self, command):
        """Fuzzy-matches an installed app's display name, same idea as the
        Start Menu lookup on Windows, but via Android's PackageManager."""
        app_name = command.replace("open", "").strip()
        for filler in ("can you", "could you", "please", "for me", "now", "jarvis", "hey"):
            app_name = app_name.replace(filler, " ")
        app_name = " ".join(app_name.split())

        if not app_name:
            self.speak("Which app would you like me to open?")
            return
        if not ON_ANDROID:
            return

        try:
            pm = self.activity.getPackageManager()
            packages = pm.getInstalledApplications(0)
            match = None
            for i in range(packages.size()):
                app_info = packages.get(i)
                label = str(pm.getApplicationLabel(app_info))
                if app_name.lower() in label.lower():
                    match = (label, app_info.packageName)
                    break

            if not match:
                self.speak(f"Sorry, I couldn't find an app called {app_name}.")
                return

            label, package_name = match
            launch_intent = pm.getLaunchIntentForPackage(package_name)
            if launch_intent:
                self.activity.startActivity(launch_intent)
                self.speak(f"Opening {label}.")
            else:
                self.speak(f"I found {label} but couldn't open it.")
        except Exception as e:
            log.error(f"open_app failed: {e}")
            self.speak(f"Sorry, I couldn't open {app_name}.")

    # ---- Power action: shutdown/lock both map here -> LOCK SCREEN ---------
    def power_action(self):
        if not ON_ANDROID:
            return
        try:
            DevicePolicyManager = autoclass("android.app.admin.DevicePolicyManager")
            Context = autoclass("android.content.Context")
            dpm = cast(
                DevicePolicyManager,
                self.activity.getSystemService(Context.DEVICE_POLICY_SERVICE),
            )
            self.speak("Locking your phone.")
            dpm.lockNow()
        except Exception as e:
            log.error(f"power_action (lock) failed - is this app a Device Admin yet? {e}")
            self.speak(
                "I can't lock the phone yet. Please enable Jarvis as a "
                "device administrator in Settings first."
            )

    def check_battery(self):
        if not ON_ANDROID:
            return
        try:
            Intent = autoclass("android.content.Intent")
            IntentFilter = autoclass("android.content.IntentFilter")
            BatteryManager = autoclass("android.os.BatteryManager")
            filt = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            battery_status = self.activity.registerReceiver(None, filt)
            level = battery_status.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            scale = battery_status.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            percent = int(level * 100 / scale) if scale > 0 else -1
            plugged = battery_status.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) != 0
            status = "charging" if plugged else "not charging"
            self.speak(f"Your battery is at {percent} percent and is {status}.")
        except Exception as e:
            log.error(f"check_battery failed: {e}")
            self.speak("Sorry, I couldn't read the battery status.")

    # ---- Phone-only: calling and texting -----------------------------------
    def make_call(self, number):
        if not ON_ANDROID:
            return
        if not number:
            self.speak("Who would you like me to call?")
            return
        try:
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            intent = Intent(Intent.ACTION_CALL)
            intent.setData(Uri.parse(f"tel:{number}"))
            self.speak(f"Calling {number}.")
            self.activity.startActivity(intent)
        except Exception as e:
            log.error(f"make_call failed (check CALL_PHONE permission): {e}")
            self.speak("I couldn't place that call. Please check call permission is granted.")

    def send_sms(self, number, message):
        if not ON_ANDROID:
            return
        if not number:
            self.speak("Who would you like me to text?")
            return
        try:
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            intent = Intent(Intent.ACTION_SENDTO, Uri.parse(f"smsto:{number}"))
            intent.putExtra("sms_body", message or "")
            self.speak(f"Opening a text to {number}. Tap send when you're ready.")
            self.activity.startActivity(intent)
        except Exception as e:
            log.error(f"send_sms failed: {e}")
            self.speak("I couldn't open the messaging app.")

"""
phone_gui.py - Android HUD-style GUI, visually matching the desktop's
Iron-Man look (dark background, cyan ring, orange accent arc, animated
"JARVIS" centerpiece) but laid out for a portrait phone screen instead of
a 1366x768 desktop window: one column, big tap-to-speak dial in the
middle, status line below it, a battery panel, and a log popup instead of
a separate dialog window.

Usage from phone_app.py:

    from phone_gui import run_gui
    run_gui(platform, extra_commands=PHONE_ONLY_COMMANDS)

IMPORTANT ASSUMPTION: this assumes AndroidPlatform
(jarvis_platform/android_platform.py) has a `gui_window` attribute that
speak() checks and calls `self.gui_window.add_message(sender, text)` on -
the same convention windows_platform.py uses. If android_platform.py
doesn't have that yet, add to it:

    # in __init__:
    self.gui_window = gui_window
    # in speak(), after doing the actual TTS:
    if self.gui_window:
        self.gui_window.add_message("Jarvis", text)

Send me android_platform.py if you'd like me to wire that in directly
instead of assuming it.
"""
import math
import threading
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Ellipse, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from jarvis_core.commands import route_command

# ---- palette, matching the desktop HUD's colors -----------------------
BG = (5 / 255, 9 / 255, 15 / 255, 1)
CYAN = (60 / 255, 200 / 255, 255 / 255, 1)
CYAN_DIM = (0.27, 0.5, 0.6, 0.55)
ORANGE = (255 / 255, 165 / 255, 60 / 255, 1)
PANEL_BG = (10 / 255, 25 / 255, 38 / 255, 0.75)
BORDER = (44 / 255, 143 / 255, 194 / 255, 1)
TEXT_MAIN = (0.75, 0.91, 1, 1)
TEXT_DIM = (0.5, 0.75, 0.86, 1)

Window.clearcolor = BG


class JarvisHud(Widget):
    """Animated circular dial - canvas-drawn phone equivalent of the
    desktop's JarvisHud QWidget. Same visual language (rotating cyan ring,
    orange accent arc, tick-mark bezel, glow, 'JARVIS' label), redrawn
    every frame via Clock instead of Qt's paintEvent."""
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.label = Label(text="JARVIS", bold=True, color=TEXT_MAIN, font_size=dp(18))
        self.add_widget(self.label)
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_interval(self._tick, 1 / 25)

    def _tick(self, dt):
        self.angle = (self.angle + 4) % 360
        self._redraw()

    def _redraw(self, *args):
        self.canvas.before.clear()
        cx, cy = self.center
        radius = min(self.width, self.height) / 2 - dp(6)
        if radius <= dp(10):
            return
        with self.canvas.before:
            # outer tick-mark bezel
            Color(*CYAN_DIM)
            for i in range(48):
                a = math.radians(i * 7.5)
                tick_len = dp(7) if i % 6 == 0 else dp(3)
                x1 = cx + radius * math.cos(a)
                y1 = cy + radius * math.sin(a)
                x2 = cx + (radius - tick_len) * math.cos(a)
                y2 = cy + (radius - tick_len) * math.sin(a)
                Line(points=[x1, y1, x2, y2], width=1)

            # rotating cyan ring
            ring_r = radius - dp(16)
            Color(*CYAN)
            Line(circle=(cx, cy, ring_r, self.angle, self.angle + 250), width=dp(3.5))

            # orange accent arc
            Color(*ORANGE)
            Line(circle=(cx, cy, ring_r, self.angle + 260, self.angle + 288), width=dp(3))

            # inner glow disc
            glow_r = radius * 0.55
            Color(0.14, 0.43, 0.59, 0.55)
            Ellipse(pos=(cx - glow_r, cy - glow_r), size=(glow_r * 2, glow_r * 2))

            # thin static inner ring
            Color(0.47, 0.86, 1, 0.6)
            Line(circle=(cx, cy, radius * 0.62), width=1)

        self.label.center = self.center


class StatBox(BoxLayout):
    """Small titled panel (e.g. BATTERY) - phone equivalent of the
    desktop's InfoBox."""
    def __init__(self, title, **kwargs):
        super().__init__(orientation="vertical", padding=dp(8), spacing=dp(2), **kwargs)
        with self.canvas.before:
            Color(*PANEL_BG)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])
            Color(*BORDER)
            self._border = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(6)), width=1)
        self.bind(pos=self._update_bg, size=self._update_bg)

        title_lbl = Label(text=title, color=TEXT_MAIN, bold=True, font_size=dp(11),
                           size_hint_y=None, height=dp(16), halign="left", valign="middle")
        title_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.add_widget(title_lbl)

        self.value_label = Label(text="--", color=TEXT_MAIN, font_size=dp(16), bold=True,
                                  halign="left", valign="middle")
        self.value_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.add_widget(self.value_label)

    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(6))

    def set_value(self, text):
        self.value_label.text = text


class LogPopup(Popup):
    """Phone equivalent of the desktop's LogDialog - full conversation
    history, opened from a button instead of a separate window."""
    def __init__(self, **kwargs):
        super().__init__(title="Conversation Log", size_hint=(0.92, 0.85),
                          separator_color=BORDER, title_color=TEXT_MAIN,
                          background_color=(0.02, 0.05, 0.08, 1), **kwargs)
        self.scroll = ScrollView()
        self.log_box = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(10), spacing=dp(6))
        self.log_box.bind(minimum_height=self.log_box.setter("height"))
        self.scroll.add_widget(self.log_box)
        self.content = self.scroll

    def add_message(self, sender, message):
        lbl = Label(text=f"[b]{sender}:[/b] {message}", markup=True, color=CYAN,
                    size_hint_y=None, halign="left", valign="top")
        lbl.bind(width=lambda w, *_: setattr(w, "text_size", (w.width, None)))
        lbl.bind(texture_size=lambda w, *_: setattr(w, "height", w.texture_size[1] + dp(6)))
        self.log_box.add_widget(lbl)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0))


class JarvisPhoneUI(FloatLayout):
    def __init__(self, platform, extra_commands=None, **kwargs):
        super().__init__(**kwargs)
        self.platform = platform
        self.extra_commands = extra_commands or []
        self.log_popup = LogPopup()

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        self.add_widget(root)

        # ---- top: clock + date (mirrors the desktop's top bar, stacked
        # instead of side-by-side since a phone is narrow) ----
        top = BoxLayout(size_hint_y=None, height=dp(56))
        self.clock_label = Label(text="00:00", font_size=dp(30), color=(1, 1, 1, 1), bold=True,
                                  halign="left", valign="middle")
        self.clock_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        self.date_label = Label(text="---, -- ---", font_size=dp(13), color=TEXT_DIM,
                                 halign="right", valign="middle")
        self.date_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        top.add_widget(self.clock_label)
        top.add_widget(self.date_label)
        root.add_widget(top)

        # ---- middle: HUD dial doubling as the tap-to-speak control ----
        hud_wrap = FloatLayout()
        self.hud = JarvisHud()
        hud_wrap.add_widget(self.hud)
        self.mic_button = Button(
            text="TAP TO\nSPEAK", size_hint=(None, None), size=(dp(120), dp(120)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            background_normal="", background_color=(0, 0, 0, 0),
            color=TEXT_MAIN, bold=True, font_size=dp(13),
        )
        self.mic_button.bind(on_press=self.on_mic_pressed)
        hud_wrap.add_widget(self.mic_button)
        root.add_widget(hud_wrap)

        # ---- status / last-exchange line (mirrors the desktop's status box) ----
        self.status_label = Label(
            text="Say 'hey Jarvis' or tap the dial to speak, sir.",
            color=TEXT_MAIN, font_size=dp(13), size_hint_y=None, height=dp(56),
            halign="center", valign="middle",
        )
        self.status_label.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        root.add_widget(self.status_label)

        # ---- bottom row: battery + log button ----
        bottom_row = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(10))
        self.battery_box = StatBox("BATTERY")
        bottom_row.add_widget(self.battery_box)
        log_btn = Button(
            text="VIEW\nLOG", size_hint_x=0.55,
            background_normal="", background_color=(0.06, 0.12, 0.18, 1),
            color=TEXT_MAIN, font_size=dp(12), bold=True,
        )
        log_btn.bind(on_press=lambda *_: self.log_popup.open())
        bottom_row.add_widget(log_btn)
        root.add_widget(bottom_row)

        Clock.schedule_interval(self._refresh_clock, 1)
        self._refresh_clock(0)
        Clock.schedule_interval(self._refresh_battery, 5)
        self._refresh_battery(0)

    def _refresh_clock(self, dt):
        now = datetime.now()
        self.clock_label.text = now.strftime("%I:%M %p").lstrip("0")
        self.date_label.text = now.strftime("%a, %d %b")

    def _refresh_battery(self, dt):
        # plyer gives a cross-platform battery reading on Android without
        # needing psutil (which isn't in buildozer.spec's requirements).
        try:
            from plyer import battery
            status = battery.status
            pct = status.get("percentage")
            charging = status.get("isCharging")
            self.battery_box.set_value(f"{pct:.0f}%" + (" (charging)" if charging else "") if pct is not None else "N/A")
        except Exception:
            self.battery_box.set_value("N/A")

    # ---- called by platform.speak() via platform.gui_window -------------
    def add_message(self, sender, message):
        Clock.schedule_once(lambda dt: self._add_message_ui(sender, message))

    def _add_message_ui(self, sender, message):
        self.status_label.text = f"{sender}: {message}"
        self.log_popup.add_message(sender, message)

    # ---- tap-to-speak ------------------------------------------------
    def on_mic_pressed(self, _instance):
        self.status_label.text = "Listening..."
        threading.Thread(target=self._handle_voice, daemon=True).start()

    def _handle_voice(self):
        command = self.platform.listen(timeout=5, phrase_time_limit=6, speak_network_errors=True)
        if not command:
            Clock.schedule_once(lambda dt: setattr(
                self.status_label, "text", "Didn't catch that - tap and try again."
            ))
            return
        Clock.schedule_once(lambda dt: self._add_message_ui("You", command))
        try:
            route_command(command, self.platform, extra_commands=self.extra_commands)
        except Exception:
            self.platform.speak("Something went wrong handling that command.")


class _JarvisPhoneApp(App):
    def __init__(self, platform, extra_commands=None, **kwargs):
        super().__init__(**kwargs)
        self._platform = platform
        self._extra_commands = extra_commands

    def build(self):
        ui = JarvisPhoneUI(self._platform, extra_commands=self._extra_commands)
        self._platform.gui_window = ui  # so platform.speak() writes into this UI
        return ui


def run_gui(platform, extra_commands=None):
    """Call this from phone_app.py's `if __name__ == '__main__':` block,
    same pattern as gui.run_gui(platform) on the laptop side."""
    _JarvisPhoneApp(platform, extra_commands=extra_commands).run()
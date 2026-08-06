"""
gui.py - The Iron-Man-style HUD from your original jarvis.py, ported over
unchanged in appearance. The only real change: buttons call
platform.power_action() / platform.restart() / platform.log_off() instead
of calling shutdown_pc()/restart_pc()/log_off_pc() directly, and
exit_program() sets the shared _shutdown_requested flag from
jarvis_core.commands instead of a local one.

Usage from laptop_app.py:

    from gui import run_gui
    run_gui(platform)   # platform = your WindowsPlatform instance

run_gui() creates the QApplication + JarvisGUI window, hooks
platform.gui_window up to it so platform.speak() writes into the HUD chat
log, and blocks (on the main thread) until the app closes.
"""
import os
import shutil
import socket
import sys
import threading
import time
from datetime import datetime, timedelta

import psutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTextEdit, QPushButton, QFrame, QDialog, QSizePolicy
)
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QRadialGradient
from PyQt5.QtCore import Qt, QTimer, QRectF

from jarvis_core.commands import _shutdown_requested


# ---------------------------------------------------------------------------
# System-stats helpers used by the GUI panels
# ---------------------------------------------------------------------------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_disk_info(letter):
    path = f"{letter}:\\"
    if os.path.exists(path):
        try:
            usage = shutil.disk_usage(path)
            used_gb = (usage.total - usage.free) / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            return f"{used_gb:.1f} GB/{total_gb:.1f} GB used"
        except Exception:
            return "N/A"
    return None  # drive doesn't exist


def format_uptime(seconds):
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{days}d {hours}h {minutes}m"


# ---------------------------------------------------------------------------
# Animated circular "JARVIS" HUD centerpiece
# ---------------------------------------------------------------------------
class JarvisHud(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.pulse = 0.0
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)  # ~25 fps

    def _tick(self):
        self.angle = (self.angle + 2) % 360
        self.pulse = (self.pulse + 0.05) % (2 * 3.14159)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 12
        if radius <= 20:
            return

        painter.save()
        painter.translate(cx, cy)
        painter.setPen(QPen(QColor(70, 170, 210, 150), 1.4))
        for i in range(72):
            painter.save()
            painter.rotate(i * 5)
            tick_len = 10 if i % 6 == 0 else 5
            painter.drawLine(0, int(-radius), 0, int(-radius + tick_len))
            painter.restore()
        painter.restore()

        ring_rect = QRectF(cx - radius + 22, cy - radius + 22, (radius - 22) * 2, (radius - 22) * 2)
        pen = QPen(QColor(60, 200, 255), 8)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        painter.drawArc(ring_rect, int(self.angle * 16), int(250 * 16))

        pen2 = QPen(QColor(255, 165, 60), 6)
        pen2.setCapStyle(Qt.FlatCap)
        painter.setPen(pen2)
        painter.drawArc(ring_rect, int((self.angle + 260) * 16), int(28 * 16))

        glow_radius = radius * 0.62
        gradient = QRadialGradient(cx, cy, glow_radius)
        gradient.setColorAt(0.0, QColor(35, 110, 150, 230))
        gradient.setColorAt(0.7, QColor(15, 60, 90, 160))
        gradient.setColorAt(1.0, QColor(10, 20, 30, 30))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(cx - glow_radius, cy - glow_radius, glow_radius * 2, glow_radius * 2))

        painter.setPen(QPen(QColor(120, 220, 255, 180), 1.5))
        painter.setBrush(Qt.NoBrush)
        inner_radius = radius * 0.68
        painter.drawEllipse(QRectF(cx - inner_radius, cy - inner_radius, inner_radius * 2, inner_radius * 2))

        painter.setPen(QColor(225, 250, 255))
        font_size = max(14, int(radius * 0.17))
        font = QFont("Consolas", font_size, QFont.Bold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, font_size * 0.15)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, "JARVIS")


# ---------------------------------------------------------------------------
# Small reusable "info box" panel (NETWORK / DISK / SYSTEM style boxes)
# ---------------------------------------------------------------------------
class InfoBox(QFrame):
    def __init__(self, title, rows, parent=None):
        """rows: list of (key, label_text, initial_value)"""
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 25, 38, 160);
                border: 1px solid #2c8fc2;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #ffffff; font-weight: bold; font-size: 13px; letter-spacing: 2px; border: none;"
        )
        layout.addWidget(title_lbl)

        self.value_labels = {}
        for key, label_text, value in rows:
            row = QHBoxLayout()
            l = QLabel(label_text)
            l.setStyleSheet("color: #7fbfdc; font-size: 11px; border: none;")
            v = QLabel(value)
            v.setStyleSheet("color: #eafcff; font-size: 11px; font-weight: bold; border: none;")
            v.setAlignment(Qt.AlignRight)
            row.addWidget(l)
            row.addStretch()
            row.addWidget(v)
            layout.addLayout(row)
            self.value_labels[key] = v

        self.setLayout(layout)

    def set_value(self, key, value):
        if key in self.value_labels:
            self.value_labels[key].setText(value)


# ---------------------------------------------------------------------------
# Small horizontal usage bar (used for RAM / battery)
# ---------------------------------------------------------------------------
class UsageBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.percent = 0
        self.setFixedHeight(10)
        self.setMinimumWidth(120)

    def set_percent(self, percent):
        self.percent = max(0, min(100, percent))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        painter.setPen(QPen(QColor(60, 150, 190), 1))
        painter.setBrush(QColor(10, 20, 30))
        painter.drawRoundedRect(rect, 3, 3)

        fill_width = int((rect.width() - 2) * (self.percent / 100))
        if fill_width > 0:
            color = QColor(60, 200, 255) if self.percent < 85 else QColor(255, 90, 90)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(1, 1, fill_width, rect.height() - 2, 2, 2)


# ---------------------------------------------------------------------------
# Full conversation log popup (kept out of the main HUD to preserve the look)
# ---------------------------------------------------------------------------
class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conversation Log")
        self.resize(500, 500)
        self.setStyleSheet("background-color: #0a141e;")

        layout = QVBoxLayout()
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet(
            "background-color: black; color: #7fdcff; font-family: Consolas; font-size: 13px; border: 1px solid #2c8fc2;"
        )
        layout.addWidget(self.chat)
        self.setLayout(layout)

    def add_message(self, sender, message):
        self.chat.append(f"{sender}: {message}")


# ---------------------------------------------------------------------------
# Main HUD-style GUI
# ---------------------------------------------------------------------------
class JarvisGUI(QWidget):
    def __init__(self, platform):
        super().__init__()
        self.platform = platform  # WindowsPlatform instance - buttons call into this

        self.setWindowTitle("J.A.R.V.I.S. Interface")
        self.resize(1366, 768)
        self.setMinimumSize(1100, 650)

        self.setStyleSheet("""
            QWidget { background-color: #05090f; }
            QLabel { color: #bfe9ff; }
            QPushButton {
                background-color: rgba(10, 30, 45, 200);
                color: #9fe0ff;
                border: 1px solid #2c8fc2;
                border-radius: 3px;
                padding: 4px 10px;
                font-family: Consolas;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QPushButton:hover { background-color: rgba(30, 90, 120, 220); }
        """)

        self._prev_net = psutil.net_io_counters()
        self._prev_net_time = time.time()

        self.log_dialog = LogDialog(self)

        outer = QVBoxLayout()
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        outer.addLayout(self._build_top_bar())
        outer.addLayout(self._build_middle_row(), stretch=1)
        outer.addLayout(self._build_bottom_row())

        self.setLayout(outer)

        # Live stats refresh
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.refresh_stats)
        self.stats_timer.start(1000)
        self.refresh_stats()

    # ---------------- Top bar: RAM, power buttons, calendar, clock -------
    def _build_top_bar(self):
        bar = QHBoxLayout()
        bar.setSpacing(24)

        # RAM usage block
        ram_box = QVBoxLayout()
        ram_title = QLabel("RAM USAGE")
        ram_title.setStyleSheet("color: #7fbfdc; font-size: 10px; letter-spacing: 1px;")
        self.ram_value = QLabel("0%")
        self.ram_value.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        ram_box.addWidget(ram_title)
        ram_box.addWidget(self.ram_value)
        bar.addLayout(ram_box)

        # Power buttons - now call into `platform` instead of bare functions
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        shutdown_btn = QPushButton("SHUTDOWN")
        shutdown_btn.clicked.connect(lambda: self.platform.power_action())
        restart_btn = QPushButton("RESTART")
        restart_btn.clicked.connect(lambda: self.platform.restart())
        logoff_btn = QPushButton("LOG OFF")
        logoff_btn.clicked.connect(lambda: self.platform.log_off())
        exit_btn = QPushButton("EXIT APP")
        exit_btn.setStyleSheet(
            "QPushButton { background-color: rgba(60,10,10,200); color: #ff9d9d; border: 1px solid #c23535; }"
            "QPushButton:hover { background-color: rgba(120,20,20,220); }"
        )
        exit_btn.clicked.connect(self.exit_program)
        for b in (shutdown_btn, restart_btn, logoff_btn, exit_btn):
            btn_row.addWidget(b)
        bar.addLayout(btn_row)

        bar.addStretch()

        # Mini calendar (current week, today highlighted)
        bar.addLayout(self._build_calendar())

        bar.addStretch()

        # Big clock
        clock_box = QVBoxLayout()
        clock_box.setAlignment(Qt.AlignCenter)
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: white; font-size: 34px; font-weight: 200;")
        self.ampm_label = QLabel("AM")
        self.ampm_label.setStyleSheet("color: #7fbfdc; font-size: 12px;")
        self.ampm_label.setAlignment(Qt.AlignCenter)
        clock_box.addWidget(self.time_label, alignment=Qt.AlignCenter)
        clock_box.addWidget(self.ampm_label)
        bar.addLayout(clock_box)

        bar.addStretch()

        # Big date block (day number + month + weekday)
        date_box = QVBoxLayout()
        date_box.setAlignment(Qt.AlignCenter)
        self.day_num_label = QLabel("01")
        self.day_num_label.setStyleSheet("color: white; font-size: 34px; font-weight: bold;")
        self.day_num_label.setAlignment(Qt.AlignCenter)
        self.month_label = QLabel("MONTH")
        self.month_label.setStyleSheet(
            "background-color: #d98a2b; color: black; font-size: 10px; font-weight: bold; padding: 1px 4px;"
        )
        self.month_label.setAlignment(Qt.AlignCenter)
        self.weekday_label = QLabel("WEEKDAY")
        self.weekday_label.setStyleSheet("color: #7fbfdc; font-size: 10px; letter-spacing: 1px;")
        self.weekday_label.setAlignment(Qt.AlignCenter)
        date_box.addWidget(self.day_num_label)
        date_box.addWidget(self.month_label)
        date_box.addWidget(self.weekday_label)
        bar.addLayout(date_box)

        return bar

    def _build_calendar(self):
        grid = QGridLayout()
        grid.setSpacing(4)
        today = datetime.now().date()
        start_of_week = today - timedelta(days=(today.weekday() + 1) % 7)  # Sunday-start week
        weekday_labels = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]

        for col, wd in enumerate(weekday_labels):
            lbl = QLabel(wd)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #7fbfdc; font-size: 10px;")
            grid.addWidget(lbl, 0, col)

        for col in range(7):
            date_val = start_of_week + timedelta(days=col)
            lbl = QLabel(str(date_val.day).zfill(2))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedWidth(24)
            if date_val == today:
                lbl.setStyleSheet(
                    "background-color: #2c8fc2; color: white; font-size: 11px; font-weight: bold; border-radius: 2px;"
                )
            else:
                lbl.setStyleSheet("color: #cfeeff; font-size: 11px;")
            grid.addWidget(lbl, 1, col)

        return grid

    # ---------------- Middle row: left dial, center HUD, right panels ----
    def _build_middle_row(self):
        row = QHBoxLayout()
        row.setSpacing(18)

        # Left: small CPU gauge dial (reuses the same painted-arc style)
        left_col = QVBoxLayout()
        left_col.addStretch()
        self.cpu_dial = JarvisHud()
        self.cpu_dial.setMinimumSize(140, 140)
        self.cpu_dial.setMaximumSize(180, 180)
        left_col.addWidget(self.cpu_dial, alignment=Qt.AlignCenter)
        left_col.addStretch()
        row.addLayout(left_col, stretch=2)

        # Center: main animated JARVIS HUD
        self.main_hud = JarvisHud()
        row.addWidget(self.main_hud, stretch=5)

        # Right: NETWORK / DISK / SYSTEM info boxes
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        self.network_box = InfoBox("NETWORK", [
            ("ip", "IP Address", get_local_ip()),
            ("up", "Upload", "0.0 B/s"),
            ("down", "Download", "0.0 B/s"),
        ])
        right_col.addWidget(self.network_box)

        self.disk_box = InfoBox("DISK", [
            ("c", "C:\\", get_disk_info("C") or "N/A"),
            ("d", "D:\\", get_disk_info("D") or "N/A"),
        ])
        right_col.addWidget(self.disk_box)

        self.system_box = InfoBox("SYSTEM", [
            ("cpu", "CPU Usage", "0%"),
            ("ram", "RAM Usage", "0%"),
            ("swap", "SWAP Usage", "0%"),
        ])
        right_col.addWidget(self.system_box)

        right_col.addStretch()
        row.addLayout(right_col, stretch=2)

        return row

    # ---------------- Bottom row: battery, status box, log button --------
    def _build_bottom_row(self):
        row = QHBoxLayout()
        row.setSpacing(18)

        # Battery
        batt_box = QVBoxLayout()
        batt_title = QLabel("BATTERY")
        batt_title.setStyleSheet("color: #7fbfdc; font-size: 10px; letter-spacing: 1px;")
        batt_row = QHBoxLayout()
        self.battery_bar = UsageBar()
        self.battery_pct_label = QLabel("0%")
        self.battery_pct_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        batt_row.addWidget(self.battery_bar)
        batt_row.addWidget(self.battery_pct_label)
        batt_box.addWidget(batt_title)
        batt_box.addLayout(batt_row)
        row.addLayout(batt_box, stretch=2)

        # Status / last-exchange box
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame { background-color: rgba(10, 25, 38, 160); border: 1px solid #2c8fc2; border-radius: 4px; }
        """)
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(12, 6, 12, 8)
        title_lbl = QLabel("J.A.R.V.I.S.")
        title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 12px; letter-spacing: 2px; border: none;")
        title_lbl.setAlignment(Qt.AlignCenter)
        self.status_line = QLabel("Say 'hey Jarvis' followed by your command, sir.")
        self.status_line.setStyleSheet("color: #9fe0ff; font-size: 12px; border: none;")
        self.status_line.setAlignment(Qt.AlignCenter)
        self.status_line.setWordWrap(True)
        status_layout.addWidget(title_lbl)
        status_layout.addWidget(self.status_line)
        status_frame.setLayout(status_layout)
        row.addWidget(status_frame, stretch=5)

        # Uptime + log button
        right_box = QVBoxLayout()
        self.uptime_label = QLabel("Uptime: --")
        self.uptime_label.setStyleSheet("color: #7fbfdc; font-size: 11px;")
        log_btn = QPushButton("VIEW FULL LOG")
        log_btn.clicked.connect(self.show_log)
        right_box.addWidget(self.uptime_label, alignment=Qt.AlignRight)
        right_box.addWidget(log_btn, alignment=Qt.AlignRight)
        row.addLayout(right_box, stretch=2)

        return row

    # ---------------- Live updates ---------------------------------------
    def refresh_stats(self):
        now = datetime.now()
        self.time_label.setText(now.strftime("%I:%M"))
        self.ampm_label.setText(now.strftime("%p"))
        self.day_num_label.setText(now.strftime("%d"))
        self.month_label.setText(now.strftime("%B").upper())
        self.weekday_label.setText(now.strftime("%A").upper())

        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        self.ram_value.setText(f"{mem.percent:.0f}%")
        self.system_box.set_value("cpu", f"{cpu:.0f}%")
        self.system_box.set_value("ram", f"{mem.percent:.0f}%")
        self.system_box.set_value("swap", f"{swap.percent:.0f}%")

        battery = psutil.sensors_battery()
        if battery:
            self.battery_bar.set_percent(battery.percent)
            plugged = " (charging)" if battery.power_plugged else ""
            self.battery_pct_label.setText(f"{battery.percent:.0f}%{plugged}")

        uptime_seconds = time.time() - psutil.boot_time()
        self.uptime_label.setText(f"Uptime: {format_uptime(uptime_seconds)}")

        current_net = psutil.net_io_counters()
        current_time = time.time()
        elapsed = max(current_time - self._prev_net_time, 0.001)
        up_speed = (current_net.bytes_sent - self._prev_net.bytes_sent) / elapsed
        down_speed = (current_net.bytes_recv - self._prev_net.bytes_recv) / elapsed
        self._prev_net = current_net
        self._prev_net_time = current_time
        self.network_box.set_value("up", self._format_speed(up_speed))
        self.network_box.set_value("down", self._format_speed(down_speed))

    @staticmethod
    def _format_speed(bytes_per_sec):
        if bytes_per_sec >= 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        if bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        return f"{bytes_per_sec:.1f} B/s"

    # ---------------- Chat plumbing (called by platform.speak()) ---------
    def add_message(self, sender, message):
        self.status_line.setText(f"{sender}: {message}")
        self.log_dialog.add_message(sender, message)

    def show_log(self):
        self.log_dialog.show()
        self.log_dialog.raise_()

    def exit_program(self):
        _shutdown_requested.set()
        self.close()


# ---------------------------------------------------------------------------
# Watches the shared shutdown flag (voice "exit"/"quit", Ctrl+Shift+Q, or
# the EXIT APP button all set it) and closes the Qt app cleanly.
# ---------------------------------------------------------------------------
def _watch_for_shutdown(app):
    while not _shutdown_requested.is_set():
        time.sleep(0.2)
    app.quit()


# ---------------------------------------------------------------------------
# Entry point called from laptop_app.py. Must run on the main thread - Qt
# requires that. Blocks until the window is closed / shutdown is requested.
# ---------------------------------------------------------------------------
def run_gui(platform):
    app = QApplication(sys.argv)
    gui_window = JarvisGUI(platform)
    platform.gui_window = gui_window  # so platform.speak() writes into the HUD
    gui_window.show()

    watcher = threading.Thread(target=_watch_for_shutdown, args=(app,), daemon=True)
    watcher.start()

    app.exec_()
    sys.exit(0)
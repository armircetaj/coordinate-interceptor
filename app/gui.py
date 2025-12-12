import sys
import os
import time
import ctypes
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QPlainTextEdit, QListWidget, QLabel
)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon, QPalette, QColor
from win10toast import ToastNotifier
from app.proxy_runner import ProxyRunner
import app.interceptor as interceptor

notifier = ToastNotifier()
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")

def show_notification(lat, lng, country, city):
    try:
        # Only show icon if file exists, otherwise omit it to avoid WPARAM error
        icon = ICON_PATH if os.path.exists(ICON_PATH) else None
        notifier.show_toast(
            "Phaenon Interceptor",
            f"{country}, {city}\nLat: {lat:.4f}, Lng: {lng:.4f}",
            icon_path=icon,
            duration=6,
            threaded=True
        )
    except Exception as e:
        # Silently fail if notification doesn't work
        pass

class ProxyMonitor(QThread):
    match_found = Signal(str, float, float, str, str)
    log_message = Signal(str)

    def __init__(self, runner):
        super().__init__()
        self.runner = runner
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            line = self.runner.get_stdout_line()
            if not line:
                # Add a small delay to prevent busy-waiting and 100% CPU usage
                time.sleep(0.1)
                continue
            if line.startswith("MATCH|"):
                parts = line.split("|")
                if len(parts) == 6:
                    _, url, lat, lng, country, city = parts
                    try:
                        self.match_found.emit(url, float(lat), float(lng), country, city)
                    except ValueError:
                        pass
            else:
                self.log_message.emit(line)

    def stop(self):
        self.running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.runner = ProxyRunner()
        self.monitor = None
        interceptor.notify_fn = show_notification
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Phaenon Interceptor")
        self.setGeometry(100, 100, 800, 600)
        self._enable_dark_title_bar()

        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)

        self.status_label = QLabel("Status: Stopped")
        layout.addWidget(self.status_label)

        self.start_btn = QPushButton("Start Proxy")
        self.start_btn.clicked.connect(self.start_proxy)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Proxy")
        self.stop_btn.clicked.connect(self.stop_proxy)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        layout.addWidget(QLabel("Matches:"))
        self.matches_list = QListWidget()
        layout.addWidget(self.matches_list)

        layout.addWidget(QLabel("Log:"))
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        self.log("Ready. Click Start Proxy.")

    def start_proxy(self):
        if self.runner.start():
            self.status_label.setText("Status: Running (port 8080)")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.log("Proxy started on port 8080")

            self.monitor = ProxyMonitor(self.runner)
            self.monitor.match_found.connect(self.on_match)
            self.monitor.log_message.connect(self.log)
            self.monitor.start()
        else:
            self.log("ERROR: Failed to start proxy")

    def stop_proxy(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor.wait()
            self.monitor = None

        if self.runner.stop():
            self.status_label.setText("Status: Stopped")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.log("Proxy stopped")

    def on_match(self, url, lat, lng, country, city):
        item = f"{url} | {city}, {country} | {lat:.5f}, {lng:.5f}"
        self.matches_list.addItem(item)
        self.log(f"MATCH: {item}")
        show_notification(lat, lng, country, city)

    def log(self, msg):
        self.log_box.appendPlainText(msg)

    def closeEvent(self, event):
        self.stop_proxy()
        event.accept()

    def _enable_dark_title_bar(self):
        """Try to set a dark title bar on Windows 10+."""
        try:
            if sys.platform != "win32":
                return
            hwnd = int(self.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Windows 10 1809+
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            value = ctypes.c_int(1)
            set_window_attribute(ctypes.c_void_p(hwnd),
                                 ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE),
                                 ctypes.byref(value),
                                 ctypes.sizeof(value))
        except Exception:
            # Ignore if the API is unavailable
            pass

def main():
    app = QApplication(sys.argv)

    # Dark theme palette (simple)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(20, 20, 20))
    palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Highlight, QColor(64, 128, 255))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    # Basic dark stylesheet for inputs
    app.setStyleSheet("""
        QWidget { background-color: #1e1e1e; color: #e0e0e0; }
        QPushButton { background-color: #2e2e2e; border: 1px solid #3a3a3a; padding: 6px; }
        QPushButton:hover { background-color: #3a3a3a; }
        QPlainTextEdit, QListWidget { background-color: #121212; color: #e0e0e0; border: 1px solid #3a3a3a; }
        QLabel { color: #e0e0e0; }
    """)

    # Application/window icon
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    w = MainWindow()
    if os.path.exists(ICON_PATH):
        w.setWindowIcon(QIcon(ICON_PATH))
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

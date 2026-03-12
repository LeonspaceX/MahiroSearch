#!/usr/bin/env python3
"""MahiroSearch - AI Semantic Search for Local Files."""

import os
import signal
import sys

# Improve rendering quality on high-DPI monitors (125%/150%).
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")


class _StderrFilter:
    _SUPPRESS = (
        b"libpng warning: iCCP",
        b"libpng warning: bKGD",
    )

    def __init__(self, real):
        if real is None:
            real = getattr(sys, "__stderr__", None)
        if real is None:
            real = _NullStderr()
        self._real = real
        self._buf = b""

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        self._buf += data
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if not any(s in line for s in self._SUPPRESS):
                self._real.write(line.decode(errors="replace") + "\n")
                self._real.flush()

    def flush(self):
        if self._buf:
            line = self._buf.decode(errors="replace")
            if not any(s.decode() in line for s in self._SUPPRESS):
                self._real.write(line)
                self._real.flush()
            self._buf = b""

    def __getattr__(self, name):
        return getattr(self._real, name)


class _NullStderr:
    def write(self, _data):
        return 0

    def flush(self):
        return None


sys.stderr = _StderrFilter(sys.stderr)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from config import AppConfig
from services import Services
from utils import autostart


def _ensure_valid_app_font(app: QApplication) -> None:
    """Guard against invalid point size (-1) fonts on some platforms/themes."""
    font = app.font()
    if font.pointSize() > 0:
        return

    if font.pixelSize() > 0:
        point_size = max(9, int(round(font.pixelSize() * 72 / 96)))
    else:
        point_size = 10

    font.setPointSize(point_size)
    app.setFont(font)


def cleanup_resources():
    try:
        Services.stop_file_watcher()
        search_engine = Services._search_engine
        if search_engine and hasattr(search_engine, "_embedder"):
            import asyncio

            asyncio.run(search_engine._embedder.aclose())
    except Exception:
        pass


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    _ensure_valid_app_font(app)

    from qfluentwidgets import Theme, setTheme
    from ui.main_window import MainWindow

    setTheme(Theme.AUTO)
    app.setApplicationName("MahiroSearch")
    app.setOrganizationName("MahiroSearch")

    def handle_sigint(signum, frame):
        print("\n收到退出信号，正在关闭应用...")
        app.quit()

    signal.signal(signal.SIGINT, handle_sigint)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, handle_sigint)

    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    cfg = AppConfig.load()
    Services.initialize(cfg)
    autostart.ensure(cfg.auto_start)
    if cfg.auto_index_new_files:
        Services.start_file_watcher()

    window = MainWindow(cfg)
    window.show()

    app.aboutToQuit.connect(cleanup_resources)

    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        print("\n收到退出信号，正在关闭应用...")
        exit_code = 0
    finally:
        cleanup_resources()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

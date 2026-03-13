#!/usr/bin/env python3
"""MahiroSearch - AI Semantic Search for Local Files."""

import getpass
import hashlib
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

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
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


def _single_instance_server_name() -> str:
    user = getpass.getuser() or "default"
    digest = hashlib.sha256(user.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"MahiroSearch.{digest}"


class SingleInstanceManager:
    ACTIVATE_MESSAGE = b"ACTIVATE"

    def __init__(self, server_name: str) -> None:
        self._server_name = server_name
        self._server: QLocalServer | None = None
        self._activate_handler = None
        self._activation_pending = False

    def notify_existing_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(250):
            return False

        socket.write(self.ACTIVATE_MESSAGE)
        socket.flush()
        socket.waitForBytesWritten(250)
        socket.disconnectFromServer()
        return True

    def start(self) -> bool:
        self._server = QLocalServer()
        self._server.newConnection.connect(self._on_new_connection)
        if self._server.listen(self._server_name):
            return True

        probe = QLocalSocket()
        probe.connectToServer(self._server_name)
        if probe.waitForConnected(250):
            probe.disconnectFromServer()
            return False

        QLocalServer.removeServer(self._server_name)
        return self._server.listen(self._server_name)

    def set_activate_handler(self, handler) -> None:
        self._activate_handler = handler
        if self._activation_pending and self._activate_handler is not None:
            self._activation_pending = False
            QTimer.singleShot(0, self._activate_handler)

    def cleanup(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None
        QLocalServer.removeServer(self._server_name)

    def _on_new_connection(self) -> None:
        if self._server is None:
            return

        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda s=socket: self._handle_message(s))
            socket.disconnected.connect(socket.deleteLater)

    def _handle_message(self, socket: QLocalSocket) -> None:
        message = bytes(socket.readAll()).decode(errors="ignore").strip()
        if message == self.ACTIVATE_MESSAGE.decode():
            if self._activate_handler is not None:
                QTimer.singleShot(0, self._activate_handler)
            else:
                self._activation_pending = True
        socket.disconnectFromServer()


class _MacActivationHandler(QObject):
    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self._window = window

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ApplicationActivate:
            QTimer.singleShot(0, self._window.bring_to_front)
        return False


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    _ensure_valid_app_font(app)
    if sys.platform == "darwin":
        app.setQuitOnLastWindowClosed(False)

    from qfluentwidgets import Theme, setTheme
    from ui.main_window import MainWindow

    setTheme(Theme.AUTO)
    app.setApplicationName("MahiroSearch")
    app.setOrganizationName("MahiroSearch")

    instance_manager = SingleInstanceManager(_single_instance_server_name())
    if instance_manager.notify_existing_instance():
        return
    if not instance_manager.start():
        if instance_manager.notify_existing_instance():
            return
        print("MahiroSearch is already running.")
        return

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
    instance_manager.set_activate_handler(window.bring_to_front)
    if sys.platform == "darwin":
        activation_handler = _MacActivationHandler(window, app)
        app._mac_activation_handler = activation_handler
        app.installEventFilter(activation_handler)

    app.aboutToQuit.connect(cleanup_resources)
    app.aboutToQuit.connect(instance_manager.cleanup)

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

"""Main application window."""

import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from config import AppConfig
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import FluentWindow, NavigationItemPosition
from ui.pages.index_page import IndexPage
from ui.pages.search_page import SearchPage
from ui.pages.settings_page import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self._quitting = False
        self._use_tray = sys.platform != "darwin" and QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_icon: QSystemTrayIcon | None = None
        self._app_icon = self._load_app_icon()
        self.setup_ui()
        self.setup_tray()

    def setup_ui(self):
        self.setWindowTitle("MahiroSearch")
        self.resize(1120, 780)
        self.setWindowIcon(self._app_icon)

        self.search_page = SearchPage(self.cfg)
        self.search_page.setObjectName("searchPage")

        self.index_page = IndexPage(self.cfg)
        self.index_page.setObjectName("indexPage")

        self.settings_page = SettingsPage(self.cfg)
        self.settings_page.setObjectName("settingsPage")

        self.addSubInterface(self.search_page, FIF.SEARCH, "搜索")
        self.addSubInterface(self.index_page, FIF.FOLDER, "索引")
        self.addSubInterface(
            self.settings_page,
            FIF.SETTING,
            "设置",
            NavigationItemPosition.BOTTOM,
        )

        self.switchTo(self.search_page)

    def setup_tray(self):
        if not self._use_tray:
            return

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._app_icon)
        self.tray_icon.setToolTip("MahiroSearch")

        menu = QMenu()
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        menu.setWindowOpacity(1.0)

        show_action = QAction("显示", self)
        show_action.triggered.connect(self.show_window)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_from_tray)

        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _load_app_icon(self) -> QIcon:
        root = Path(__file__).resolve().parents[1]
        for path in (root / "icon.ico", root / "icon.png"):
            if path.exists():
                icon = QIcon(str(path))
                if not icon.isNull():
                    return icon
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def show_window(self):
        self.bring_to_front()

    def bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        elif not self.isVisible():
            self.show()

        self.setWindowState(
            (self.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowActive
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def systemTitleBarRect(self, size):
        if sys.platform == "darwin":
            return QRect(0, 0, 75, size.height())
        return super().systemTitleBarRect(size)

    def quit_from_tray(self):
        self._quitting = True
        if self.tray_icon is not None:
            self.tray_icon.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            self.close()

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        if self._use_tray and self.tray_icon is not None and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            return
        event.accept()

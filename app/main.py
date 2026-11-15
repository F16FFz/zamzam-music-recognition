"""Точка входа приложения Zamzam."""
from __future__ import annotations

import ctypes
import logging
import sys
import time
from ctypes import wintypes

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .config import APP_ID, APP_NAME, APP_TITLE, ensure_dirs, resource_path
from .ui.hotkeys import GlobalHotkey
from .ui.main_window import MainWindow
from .ui.theme import stylesheet
from .ui.tray import TrayIcon

_MUTEX_NAME = "Local\\Zamzam.SingleInstance"
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9


def _focus_existing_window(timeout: float = 2.5) -> bool:
    """Находит уже запущенное окно Zamzam и выводит его на передний план."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        handle = user32.FindWindowW(None, APP_TITLE)
        if handle:
            if user32.IsIconic(handle) or not user32.IsWindowVisible(handle):
                user32.ShowWindow(handle, _SW_RESTORE)
            user32.BringWindowToTop(handle)
            user32.SetForegroundWindow(handle)
            return True
        time.sleep(0.12)
    return False


def _single_instance_lock() -> int | None:
    """Возвращает handle мьютекса или None, если приложение уже запущено."""
    if sys.platform != "win32":
        return 0
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        if handle:
            kernel32.CloseHandle(handle)
        return None
    return handle


def main() -> int:
    mutex = _single_instance_lock()
    if mutex is None:
        # Второй экземпляр не нужен: показываем уже открытое окно.
        _focus_existing_window()
        return 0

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:  # noqa: BLE001
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ensure_dirs()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())

    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    icon_path = resource_path("assets", "icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window._instance_mutex = mutex  # держим handle до завершения процесса

    tray: TrayIcon | None = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = TrayIcon()
        window.attach_tray(tray)
        tray.show()
    window._tray_icon = tray  # держим ссылку, чтобы объект не собрал GC

    screen = app.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        window.move(
            geometry.center().x() - window.width() // 2,
            geometry.center().y() - window.height() // 2,
        )

    hotkey = GlobalHotkey(window.toggle_listen)
    app.installNativeEventFilter(hotkey)
    hotkey.register()
    app.aboutToQuit.connect(hotkey.unregister)
    app.aboutToQuit.connect(window.shutdown)
    window._hotkey = hotkey  # держим ссылку, чтобы объект не собрал GC

    window.show()
    return app.exec()

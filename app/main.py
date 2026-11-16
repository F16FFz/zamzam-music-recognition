"""Точка входа приложения Zamzam."""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from ctypes import wintypes
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QFont, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .config import (
    APP_ID,
    APP_NAME,
    APP_TITLE,
    APP_VERSION,
    DATA_DIR,
    ensure_dirs,
    resource_path,
)
from .ui.hotkeys import GlobalHotkey
from .ui.main_window import MainWindow
from .ui.theme import stylesheet
from .ui.tray import TrayIcon

log = logging.getLogger("zamzam")

_MUTEX_NAME = "Local\\Zamzam.SingleInstance"
_PIPE_NAME = "Zamzam.SingleInstance"
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9


# --------------------------------------------------------------------- логи
def _setup_logging() -> None:
    """Пишет лог в %LOCALAPPDATA%\\Zamzam\\zamzam.log, чтобы можно было разобрать проблемы."""
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    try:
        file_handler = RotatingFileHandler(
            DATA_DIR / "zamzam.log",
            maxBytes=512_000,
            backupCount=2,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception:  # noqa: BLE001
        pass

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    def excepthook(exc_type, exc, tb) -> None:
        log.critical("Необработанная ошибка", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = excepthook


# --------------------------------------------------------- один экземпляр
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


def _ask_existing_to_show(timeout: float = 3.0) -> bool:
    """Просит уже запущенный Zamzam показать окно через локальный сокет."""
    deadline = time.monotonic() + timeout
    while True:
        socket = QLocalSocket()
        socket.connectToServer(_PIPE_NAME)
        if socket.waitForConnected(350):
            socket.write(b"show\n")
            socket.waitForBytesWritten(400)
            socket.disconnectFromServer()
            socket.waitForDisconnected(200)
            return True
        socket.abort()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.2, remaining))


def _focus_existing_window(timeout: float = 1.5) -> bool:
    """Запасной путь: находит окно Zamzam через WinAPI и выводит его вперёд."""
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
        time.sleep(0.1)
    return False


def _warn_already_running() -> None:
    """Сообщает, что Zamzam уже запущен, но до него не достучались."""
    message = (
        "Zamzam уже запущен, но окно не отвечает.\n\n"
        "Закройте процесс Zamzam в Диспетчере задач и запустите приложение снова."
    )
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, 0x30)
            return
        except Exception:  # noqa: BLE001
            pass
    print(message)


def _start_ipc_server(window: MainWindow) -> QLocalServer | None:
    """Слушает запросы второго экземпляра: «покажи окно»."""
    QLocalServer.removeServer(_PIPE_NAME)
    server = QLocalServer()
    if not server.listen(_PIPE_NAME):
        log.warning("Не удалось запустить IPC-сервер: %s", server.errorString())
        return None

    def on_connection() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                continue
            log.info("Второй экземпляр попросил показать окно")
            window.show_window()
            connection.disconnected.connect(connection.deleteLater)
            connection.disconnectFromServer()

    server.newConnection.connect(on_connection)
    log.info("IPC-сервер слушает %s", _PIPE_NAME)
    return server


# ------------------------------------------------------------------- запуск
def main() -> int:
    ensure_dirs()
    _setup_logging()
    log.info("Запуск Zamzam %s (pid=%s)", APP_VERSION, os.getpid())

    mutex = _single_instance_lock()
    if mutex is None:
        # Второй экземпляр не нужен: показываем уже открытое окно.
        app = QCoreApplication(sys.argv)
        showed = _ask_existing_to_show()
        if not showed:
            showed = _focus_existing_window()
        if not showed:
            log.warning("Запущенный экземпляр не отвечает")
            _warn_already_running()
        del app
        return 0

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:  # noqa: BLE001
            pass

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
    window._ipc_server = _start_ipc_server(window)

    tray: TrayIcon | None = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        candidate = TrayIcon()
        window.attach_tray(candidate)
        candidate.show()
        if candidate.isVisible():
            log.info(
                "Трей доступен: icon=%s messages=%s",
                candidate.isVisible(),
                candidate.supportsMessages(),
            )
            tray = candidate
        else:
            log.warning("Значок в трее не появился — работаю без трея")
            candidate.hide()
            window.detach_tray()
    else:
        log.warning("Системный трей недоступен — работаю без трея")
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
    log.info("Окно показано")
    return app.exec()

"""Значок Zamzam в системном трее и его меню."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import i18n
from ..config import APP_NAME, resource_path


class TrayIcon(QSystemTrayIcon):
    """Иконка в трее: открыть окно, слушать, история, язык, выход."""

    open_requested = Signal()
    listen_requested = Signal()
    history_requested = Signal()
    language_requested = Signal(str)
    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        icon_path = resource_path("assets", "icon.ico")
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        super().__init__(icon, parent)
        self.setToolTip(APP_NAME)
        self._listening = False

        self._menu = QMenu()
        self._open = QAction(self._menu)
        self._open.triggered.connect(self.open_requested)
        self._listen = QAction(self._menu)
        self._listen.triggered.connect(self.listen_requested)
        self._history = QAction(self._menu)
        self._history.triggered.connect(self.history_requested)

        self._language_menu = QMenu(self._menu)
        self._language_group = QActionGroup(self)
        self._language_group.setExclusive(True)
        self._ru = QAction("Русский", self._language_menu)
        self._ru.setCheckable(True)
        self._ru.triggered.connect(lambda: self.language_requested.emit("ru"))
        self._en = QAction("English", self._language_menu)
        self._en.setCheckable(True)
        self._en.triggered.connect(lambda: self.language_requested.emit("en"))
        self._language_group.addAction(self._ru)
        self._language_group.addAction(self._en)
        self._language_menu.addAction(self._ru)
        self._language_menu.addAction(self._en)

        self._quit = QAction(self._menu)
        self._quit.triggered.connect(self.quit_requested)

        self._menu.addAction(self._open)
        self._menu.addAction(self._listen)
        self._menu.addAction(self._history)
        self._menu.addSeparator()
        self._menu.addMenu(self._language_menu)
        self._menu.addSeparator()
        self._menu.addAction(self._quit)
        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)
        self.retranslate()

    # ------------------------------------------------------------------ API
    def set_listening(self, listening: bool) -> None:
        self._listening = listening
        self.retranslate()

    def retranslate(self) -> None:
        self._open.setText(i18n.tr("Открыть Zamzam"))
        self._listen.setText(
            i18n.tr("Остановить") if self._listening else i18n.tr("Слушать")
        )
        self._history.setText(i18n.tr("История"))
        self._language_menu.setTitle(i18n.tr("Язык"))
        self._quit.setText(i18n.tr("Выход"))
        language = i18n.get_language()
        self._ru.setChecked(language == "ru")
        self._en.setChecked(language == "en")
        self.setToolTip(APP_NAME)

    def notify(self, title: str, message: str, msec: int = 6000) -> None:
        self.showMessage(
            title, message, QSystemTrayIcon.MessageIcon.Information, msec
        )

    # -------------------------------------------------------------- события
    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_requested.emit()

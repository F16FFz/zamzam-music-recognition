"""Глобальная горячая клавиша Ctrl+Alt+S через WinAPI."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312


class GlobalHotkey(QAbstractNativeEventFilter):
    def __init__(self, callback: Callable[[], None], hotkey_id: int = 0xE7A1) -> None:
        super().__init__()
        self._callback = callback
        self._id = hotkey_id
        self.registered = False

    def register(self) -> bool:
        user32 = ctypes.windll.user32
        self.registered = bool(
            user32.RegisterHotKey(
                None, self._id, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("S")
            )
        )
        return self.registered

    def unregister(self) -> None:
        if self.registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self._id)
            except Exception:  # noqa: BLE001
                pass
            self.registered = False

    def nativeEventFilter(self, event_type, message):  # noqa: N802, ANN001
        if event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
            except (TypeError, ValueError):
                return False, 0
            if msg.message == WM_HOTKEY and msg.wParam == self._id:
                self._callback()
                return True, 0
        return False, 0

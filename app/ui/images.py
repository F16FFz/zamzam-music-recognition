"""Асинхронная загрузка обложек с дисковым кешем."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from ..config import COVERS_DIR, ensure_dirs


class ImageLoader(QObject):
    """Скачивает обложки один раз и раздаёт их подписчикам."""

    loaded = Signal(str, QPixmap)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._memory: dict[str, QPixmap] = {}
        self._callbacks: dict[str, list[Callable[[QPixmap], None]]] = {}
        self._pending: set[str] = set()
        ensure_dirs()

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return COVERS_DIR / f"{digest}.png"

    def load(self, url: str, callback: Callable[[QPixmap], None] | None = None) -> QPixmap | None:
        """Возвращает картинку сразу (если есть) либо вызовет callback позже."""
        if not url:
            return None

        pixmap = self._memory.get(url)
        if pixmap is not None:
            if callback:
                callback(pixmap)
            return pixmap

        cache_file = self._cache_path(url)
        if cache_file.exists():
            pixmap = QPixmap(str(cache_file))
            if not pixmap.isNull():
                self._memory[url] = pixmap
                if callback:
                    callback(pixmap)
                return pixmap
            try:
                cache_file.unlink(missing_ok=True)
            except OSError:
                pass

        if callback:
            self._callbacks.setdefault(url, []).append(callback)

        if url not in self._pending:
            self._pending.add(url)
            request = QNetworkRequest(QUrl(url))
            request.setHeader(
                QNetworkRequest.KnownHeaders.UserAgentHeader,
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zamzam/1.1",
            )
            request.setAttribute(
                QNetworkRequest.Attribute.RedirectPolicyAttribute,
                QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
            )
            reply = self._manager.get(request)
            reply.finished.connect(lambda: self._finished(url, reply))
        return None

    def _finished(self, url: str, reply) -> None:
        self._pending.discard(url)
        pixmap = QPixmap()
        if reply.error() == reply.NetworkError.NoError:
            data = bytes(reply.readAll())
            if data:
                pixmap.loadFromData(data)
        reply.deleteLater()

        if pixmap.isNull():
            self._callbacks.pop(url, None)
            return

        self._memory[url] = pixmap
        try:
            pixmap.save(str(self._cache_path(url)), "PNG")
        except Exception:  # noqa: BLE001
            pass

        callbacks = self._callbacks.pop(url, [])
        for callback in callbacks:
            try:
                callback(pixmap)
            except RuntimeError:
                # виджет мог быть уничтожен, пока шла загрузка
                continue
        self.loaded.emit(url, pixmap)

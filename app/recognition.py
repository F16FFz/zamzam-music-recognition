"""Распознавание музыки через Shazam и подтягивание ссылок на площадки."""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from aiohttp_retry import ExponentialRetry
from PySide6.QtCore import QObject, Signal
from shazamio import HTTPClient, Shazam

from .models import Track

log = logging.getLogger(__name__)


class _LoopThread(threading.Thread):
    """Фоновый поток с постоянным asyncio-loop для запросов к Shazam."""

    def __init__(self) -> None:
        super().__init__(name="ZamzamAsync", daemon=True)
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()

    def run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.ready.set()
        self.loop.run_forever()


def _spotify_to_url(uri: str) -> str:
    uri = (uri or "").strip()
    if not uri:
        return ""
    if uri.startswith("spotify:search:"):
        query = unquote(uri[len("spotify:search:"):])
        return "https://open.spotify.com/search/" + quote_plus(query)
    if uri.startswith("spotify:track:"):
        return "https://open.spotify.com/track/" + uri[len("spotify:track:"):]
    if uri.startswith("http"):
        return uri
    return ""


def _clean_apple_url(url: str) -> str:
    """Оставляет ссылку на Apple Music с идентификатором трека (?i=...)."""
    try:
        parsed = urlparse(url)
        track_id = parse_qs(parsed.query).get("i", [""])[0]
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if track_id:
            clean += f"?i={track_id}"
        return clean
    except Exception:  # noqa: BLE001
        return url.split("?")[0]


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def parse_answer(answer: dict[str, Any]) -> Track | None:
    """Превращает ответ Shazam в Track (или None, если совпадения нет)."""
    track = answer.get("track") or {}
    if not track.get("title") or not answer.get("matches"):
        return None

    title = _first_text(track.get("title"))
    artist = _first_text(track.get("subtitle"))
    if not title:
        return None

    images = track.get("images") or {}
    cover = _first_text(images.get("coverarthq"), images.get("coverart"))

    album = year = genre = ""
    for section in track.get("sections") or []:
        if section.get("type") != "SONG":
            continue
        for meta in section.get("metadata") or []:
            key = (meta.get("title") or "").strip().lower()
            value = _first_text(meta.get("text"))
            if key == "album" and not album:
                album = value
            elif key in ("released", "release date") and not year:
                year = value[:4]
            elif key == "genre" and not genre:
                genre = value
    if not genre:
        genre = _first_text((track.get("genres") or {}).get("primary"))

    spotify_url = youtube_url = apple_url = ""
    hub = track.get("hub") or {}

    for provider in hub.get("providers") or []:
        kind = (provider.get("type") or "").upper()
        for action in provider.get("actions") or []:
            uri = _first_text(action.get("uri"))
            if not uri:
                continue
            if kind == "SPOTIFY" and not spotify_url:
                spotify_url = _spotify_to_url(uri)
            elif kind == "YOUTUBE" and not youtube_url:
                youtube_url = uri

    options = hub.get("options") or []
    if options:
        for action in options[0].get("actions") or []:
            uri = _first_text(action.get("uri"))
            if "music.apple.com" in uri or "itunes.apple.com" in uri:
                apple_url = _clean_apple_url(uri)
                break

    for section in track.get("sections") or []:
        if section.get("type") == "VIDEO":
            youtube_url = youtube_url or _first_text(section.get("youtubeurl"))

    key = track.get("key")
    shazam_url = f"https://www.shazam.com/track/{key}" if key else ""

    # Если Shazam не дал прямых ссылок — ведём на поиск по названию.
    query = f"{artist} {title}".strip()
    if not spotify_url:
        spotify_url = f"https://open.spotify.com/search/{quote_plus(query)}"
    if not youtube_url:
        youtube_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    yandex_url = f"https://music.yandex.ru/search?text={quote_plus(query)}"

    return Track(
        title=title,
        artist=artist,
        album=album,
        year=year,
        genre=genre,
        cover_url=cover,
        spotify_url=spotify_url,
        youtube_url=youtube_url,
        apple_url=apple_url,
        yandex_url=yandex_url,
        shazam_url=shazam_url,
    )


class RecognitionService(QObject):
    """Асинхронное распознавание без блокировки интерфейса."""

    matched = Signal(object)          # Track
    no_match = Signal()
    failed = Signal(str)              # текст ошибки для пользователя

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._loop_thread = _LoopThread()
        self._loop_thread.start()
        self._loop_thread.ready.wait(timeout=3)
        self._busy = False
        self._shazam: Shazam | None = None
        self._http: HTTPClient | None = None
        self._stopping = False

    # ------------------------------------------------------------ внутреннее
    def _client(self) -> Shazam:
        if self._shazam is None:
            http = HTTPClient(
                retry_options=ExponentialRetry(
                    attempts=3,
                    max_timeout=5,
                    statuses={429, 500, 502, 503, 504},
                )
            )
            self._http = http
            self._shazam = Shazam(
                language="en-US",
                endpoint_country="US",
                http_client=http,
            )
        return self._shazam

    async def _recognize(self, wav: bytes) -> dict[str, Any]:
        return await self._client().recognize(wav)

    def _done(self, future) -> None:
        self._busy = False
        try:
            answer = future.result()
        except Exception as exc:  # noqa: BLE001
            log.warning("Shazam error: %r", exc)
            self.failed.emit(self._friendly_error(exc))
            return

        try:
            track = parse_answer(answer)
        except Exception:  # noqa: BLE001
            log.exception("Не удалось разобрать ответ Shazam")
            self.failed.emit("Не удалось разобрать ответ сервиса")
            return

        if track is None:
            self.no_match.emit()
            return

        self.matched.emit(track)

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        name = exc.__class__.__name__
        text = str(exc)
        if "RateLimited" in name or "429" in text:
            return "Shazam временно ограничил запросы. Подождите минуту."
        if "Timeout" in name or "timeout" in text.lower():
            return "Сервер не ответил вовремя. Проверьте интернет."
        if "Connector" in name or "Connection" in name or "ClientConnector" in name:
            return "Нет подключения к интернету."
        if "Signature" in name:
            return "Не удалось обработать аудио. Попробуйте ещё раз."
        if len(text) > 120:
            text = text[:120] + "…"
        return f"Ошибка распознавания: {text or name}"

    # --------------------------------------------------------------- публично
    @property
    def busy(self) -> bool:
        return self._busy

    def recognize(self, wav: bytes) -> bool:
        """Запускает распознавание. False — сервис занят прошлым запросом."""
        if self._busy or self._stopping:
            return False
        self._busy = True
        future = asyncio.run_coroutine_threadsafe(
            self._recognize(wav), self._loop_thread.loop
        )
        future.add_done_callback(self._done)
        return True

    def shutdown(self) -> None:
        """Закрывает HTTP-сессию и останавливает фоновый asyncio-loop."""
        if self._stopping and self._loop_thread.loop.is_closed():
            return
        self._stopping = True
        loop = self._loop_thread.loop
        if not loop.is_closed():
            async def _close() -> None:
                if self._http is not None:
                    await self._http.close()

            try:
                asyncio.run_coroutine_threadsafe(_close(), loop).result(timeout=3)
            except Exception:  # noqa: BLE001
                pass
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass
        self._loop_thread.join(timeout=2)
        if not loop.is_closed():
            try:
                loop.close()
            except Exception:  # noqa: BLE001
                pass

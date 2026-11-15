"""Модель трека и локальная история распознаваний."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field, fields
from urllib.parse import quote_plus

from .config import HISTORY_FILE, ensure_dirs


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


@dataclass
class Track:
    title: str
    artist: str
    album: str = ""
    year: str = ""
    genre: str = ""
    cover_url: str = ""
    spotify_url: str = ""
    youtube_url: str = ""
    apple_url: str = ""
    yandex_url: str = ""
    shazam_url: str = ""
    recognized_at: float = field(default_factory=time.time)

    @property
    def query(self) -> str:
        return f"{self.artist} {self.title}".strip()

    @property
    def meta_line(self) -> str:
        parts = []
        if self.album:
            parts.append(self.album)
        if self.year:
            parts.append(self.year)
        if self.genre:
            parts.append(self.genre)
        return "  ·  ".join(parts)

    def search_spotify(self) -> str:
        return f"https://open.spotify.com/search/{quote_plus(self.query)}"

    def search_youtube(self) -> str:
        return f"https://www.youtube.com/results?search_query={quote_plus(self.query)}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "Track | None":
        if not isinstance(raw, dict):
            return None
        data = {f.name: raw.get(f.name, "") for f in fields(cls)}
        title = _clean(data.get("title"))
        artist = _clean(data.get("artist"))
        if not title:
            return None
        data["title"] = title
        data["artist"] = artist
        for key in ("album", "year", "genre", "cover_url", "spotify_url", "youtube_url",
                    "apple_url", "yandex_url", "shazam_url"):
            data[key] = _clean(data.get(key))
        try:
            data["recognized_at"] = float(data.get("recognized_at") or time.time())
        except (TypeError, ValueError):
            data["recognized_at"] = time.time()
        return cls(**data)


class HistoryStore:
    """История последних распознаваний в JSON-файле."""

    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self.items: list[Track] = []
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            items = [Track.from_dict(row) for row in raw if isinstance(row, dict)]
            self.items = [t for t in items if t is not None][: self.limit]
        except Exception:
            self.items = []

    def save(self) -> None:
        ensure_dirs()
        try:
            HISTORY_FILE.write_text(
                json.dumps([t.to_dict() for t in self.items], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def add(self, track: Track) -> None:
        # Одинаковые треки не дублируем — просто поднимаем наверх.
        self.items = [
            t for t in self.items
            if not (t.title.casefold() == track.title.casefold()
                    and t.artist.casefold() == track.artist.casefold())
        ]
        self.items.insert(0, track)
        self.items = self.items[: self.limit]
        self.save()

    def clear(self) -> None:
        self.items = []
        self.save()

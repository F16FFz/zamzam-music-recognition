"""Рендер превью интерфейса без запуска окна на экране."""
from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import i18n  # noqa: E402
from app.models import Track  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.theme import stylesheet  # noqa: E402

OUT = ROOT / "docs" / "screenshots"


def fetch_cover(url: str) -> QPixmap | None:
    try:
        import requests

        response = requests.get(url, timeout=10, headers={"User-Agent": "Zamzam"})
        response.raise_for_status()
        pixmap = QPixmap()
        pixmap.loadFromData(response.content)
        return None if pixmap.isNull() else pixmap
    except Exception:  # noqa: BLE001
        return None


def fetch_itunes_cover(query: str) -> QPixmap | None:
    try:
        import requests

        response = requests.get(
            "https://itunes.apple.com/search",
            params={"term": query, "entity": "song", "limit": 1},
            timeout=10,
            headers={"User-Agent": "Zamzam"},
        )
        results = response.json().get("results") or []
        if not results:
            return None
        artwork = results[0].get("artworkUrl100", "")
        if not artwork:
            return None
        return fetch_cover(artwork.replace("100x100bb", "600x600bb"))
    except Exception:  # noqa: BLE001
        return None


def compose(window: MainWindow, name: str) -> None:
    raw = window.grab()
    path = OUT / f"_{name}_raw.png"
    raw.save(str(path))
    shot = Image.open(path).convert("RGBA")

    canvas = Image.new("RGBA", (shot.width + 240, shot.height + 200))
    top = (22, 30, 15)
    bottom = (8, 10, 6)
    pixels = canvas.load()
    for y in range(canvas.height):
        t = y / max(1, canvas.height - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(canvas.width):
            pixels[x, y] = color
    canvas.alpha_composite(shot, (120, 100))
    canvas.convert("RGB").save(OUT / f"preview_{name}.png")
    try:
        path.unlink()
    except OSError:
        pass
    print("Saved:", f"preview_{name}.png")


def main() -> None:
    i18n.set_language("ru")
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())

    window = MainWindow()
    window.show()
    app.processEvents()

    now = time.time()
    demo_tracks = [
        Track(
            title="One More Time",
            artist="Daft Punk",
            album="Discovery",
            year="2001",
            genre="Electronic",
            spotify_url="https://open.spotify.com/track/0DiWol3AO6WpXZgp0goxAV",
            youtube_url="https://www.youtube.com/watch?v=FGBhQbmPwH8",
            apple_url="https://music.apple.com/album/one-more-time/697194953?i=697195324",
            yandex_url="https://music.yandex.ru/album/1234/track/5678",
            shazam_url="https://www.shazam.com/track/123",
            recognized_at=now,
        ),
        Track(
            title="Instant Crush",
            artist="Daft Punk, Julian Casablancas",
            album="Random Access Memories",
            year="2013",
            genre="Electronic",
            recognized_at=now - 3600,
        ),
        Track(
            title="Get Lucky",
            artist="Daft Punk, Pharrell Williams",
            album="Random Access Memories",
            year="2013",
            genre="Disco",
            recognized_at=now - 86400,
        ),
        Track(
            title="Starboy",
            artist="The Weeknd, Daft Punk",
            album="Starboy",
            year="2016",
            genre="R&B/Soul",
            recognized_at=now - 200000,
        ),
    ]

    cover = fetch_itunes_cover("Daft Punk One More Time")
    window._current_track = demo_tracks[0]
    window._display_track(
        demo_tracks[0], "НАЙДЕНО!", "ОТКРЫВАЙ НА УДОБНОЙ ПЛОЩАДКЕ"
    )
    if cover is not None:
        window.card.set_cover(cover)
    app.processEvents()
    compose(window, "listen")

    window.pulse._phase = 1.2
    window.pulse.set_listening(True)
    window.pulse.set_level(0.55)
    window.pulse.set_progress(0.58)
    window.waveform.set_active(True)
    window.waveform._bars = [
        0.15 + 0.7 * abs(math.sin(i * 0.42)) for i in range(56)
    ]
    window.status_title.setText("СЛУШАЮ…")
    window.status_hint.setText("СЛУШАЮ… ЕЩЁ 6 С")
    window.result_stack.setCurrentWidget(window.placeholder)
    app.processEvents()
    compose(window, "listening")

    window.pulse.set_listening(False)
    window.pulse.set_level(0.0)
    window.waveform.set_active(False)
    window.history.items = demo_tracks
    window._refresh_history()
    window.set_page(1)
    app.processEvents()
    compose(window, "history")

    window.shutdown()


if __name__ == "__main__":
    main()

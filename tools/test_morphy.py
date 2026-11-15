"""Проверка: 15-секундный фрагмент проблемного трека Morphy узнаётся приложением."""
from __future__ import annotations

import io
import os
import sys
import wave
from pathlib import Path

import av
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.recognition import RecognitionService  # noqa: E402
from app.ui.theme import stylesheet  # noqa: E402

PREVIEW = ROOT / "tools" / "_preview.m4a"
PREVIEW_TRACK_ID = "1798691641"  # Morphy — Твои поцелуи (Apple Music)


def ensure_preview() -> None:
    """Скачивает официальное 30-секундное превью, если его ещё нет."""
    if PREVIEW.exists():
        return
    import requests

    response = requests.get(
        "https://itunes.apple.com/lookup",
        params={"id": PREVIEW_TRACK_ID, "country": "ru"},
        timeout=20,
        headers={"User-Agent": "Zamzam"},
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results or not results[0].get("previewUrl"):
        raise RuntimeError("Не удалось найти превью трека в Apple Music")
    preview = requests.get(
        results[0]["previewUrl"], timeout=30, headers={"User-Agent": "Zamzam"}
    )
    preview.raise_for_status()
    PREVIEW.write_bytes(preview.content)
    print(f"downloaded preview: {PREVIEW}")


def load_mono(path: Path) -> np.ndarray:
    chunks: list[np.ndarray] = []
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=44100)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    return np.concatenate(chunks).astype(np.int16)


def to_wav(mono: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(mono.tobytes())
    return buffer.getvalue()


def main() -> None:
    ensure_preview()
    mono = load_mono(PREVIEW)
    window = mono[int(7.5 * 44100): int(22.5 * 44100)]  # 15 секунд из середины
    print(f"clip: {len(window) / 44100:.2f}s")

    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())

    service = RecognitionService()
    loop = QEventLoop()
    result: dict[str, object] = {}

    def on_matched(track) -> None:
        result["track"] = track
        loop.quit()

    def on_no_match() -> None:
        result["no_match"] = True
        loop.quit()

    def on_failed(message: str) -> None:
        result["error"] = message
        loop.quit()

    service.matched.connect(on_matched)
    service.no_match.connect(on_no_match)
    service.failed.connect(on_failed)

    QTimer.singleShot(0, lambda: service.recognize(to_wav(window)))
    QTimer.singleShot(70000, loop.quit)
    loop.exec()

    if "track" in result:
        track = result["track"]
        print("RESULT:", track.artist, "-", track.title)
        print("spotify:", track.spotify_url)
        print("youtube:", track.youtube_url)
    elif "no_match" in result:
        print("RESULT: NO MATCH")
    elif "error" in result:
        print("RESULT: ERROR", result["error"])
    else:
        print("RESULT: TIMEOUT")


if __name__ == "__main__":
    main()

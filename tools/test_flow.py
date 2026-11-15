"""Проверка конечного автомата прослушивания без реального микрофона."""
from __future__ import annotations

import io
import os
import sys
import tempfile
import time
import wave
from pathlib import Path

import miniaudio
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Тесты не должны засорять настоящую историю и настройки приложения.
os.environ["LOCALAPPDATA"] = str(Path(tempfile.gettempdir()) / "ZamzamTest")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import app.ui.main_window as main_window  # noqa: E402
from app.ui.theme import stylesheet  # noqa: E402


def deezer_preview(query: str) -> bytes:
    response = requests.get(
        "https://api.deezer.com/search",
        params={"q": query, "limit": 1},
        timeout=20,
        headers={"User-Agent": "Zamzam"},
    )
    item = response.json()["data"][0]
    preview = requests.get(item["preview"], timeout=30, headers={"User-Agent": "Zamzam"})
    return preview.content


def to_wav(mp3: bytes) -> bytes:
    decoded = miniaudio.decode(
        mp3,
        output_format=miniaudio.SampleFormat.SIGNED16,
        nchannels=1,
        sample_rate=44100,
    )
    samples = np.frombuffer(decoded.samples, dtype=np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(samples.tobytes())
    return buffer.getvalue()


class FakeRecorder:
    error = None
    level = 0.5
    peak = 0.7

    def __init__(self, mode: str = "system") -> None:
        self.mode = mode
        self._started = time.monotonic()

    def start(self) -> None:
        self._started = time.monotonic()

    def stop(self) -> None:
        pass

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started

    @property
    def duration(self) -> float:
        return self.elapsed

    def wav_bytes(self, seconds: float | None = None) -> bytes:
        return WAV


def main() -> None:
    global WAV
    WAV = to_wav(deezer_preview("Daft Punk One More Time"))
    main_window.Recorder = FakeRecorder

    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())

    window = main_window.MainWindow()
    window.show()
    window._start_listening()
    started = time.monotonic()

    def report() -> None:
        print("status:", window.status_title.text())
        print("hint:", window.status_hint.text())
        print("listening:", window._listening)
        print("attempts:", window._attempts)
        print("history:", [(t.artist, t.title) for t in window.history.items])
        print("elapsed:", round(time.monotonic() - started, 1))
        app.quit()

    QTimer.singleShot(26000, report)
    app.exec()


if __name__ == "__main__":
    main()

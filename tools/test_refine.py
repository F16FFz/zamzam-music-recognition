"""Проверка уточнения трека: ранний неверный матч заменяется поздним."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Тесты не должны засорять настоящую историю и настройки приложения.
os.environ["LOCALAPPDATA"] = str(Path(tempfile.gettempdir()) / "ZamzamTest")

from PySide6.QtWidgets import QApplication  # noqa: E402

import app.ui.main_window as main_window  # noqa: E402
from app.models import Track  # noqa: E402
from app.ui.theme import stylesheet  # noqa: E402


class FakeRecorder:
    error = None
    level = 0.4
    peak = 0.6

    def __init__(self, mode: str = "system") -> None:
        self.mode = mode

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @property
    def elapsed(self) -> float:
        return 5.0

    @property
    def duration(self) -> float:
        return 5.0

    def wav_bytes(self, seconds=None) -> bytes:
        return b""


def main() -> None:
    main_window.Recorder = FakeRecorder
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())

    window = main_window.MainWindow()
    window.show()
    window._start_listening()

    wrong = Track(title="Sexual Madness", artist="Erotic", shazam_url="https://x/1")
    right = Track(title="Oh wow wow", artist="YUNG TRAPPA", shazam_url="https://x/2")

    window._inflight_session = window._session
    window._in_flight = True
    window._on_matched(wrong)
    print("after early:", window.status_title.text(), "| history:", len(window.history.items))

    window._inflight_session = window._session
    window._in_flight = True
    window._on_matched(right)
    print("after refine:", window.status_title.text(), "| history:", len(window.history.items))
    window._finalize()
    print("final status:", window.status_title.text())
    print("final history:", [(t.artist, t.title) for t in window.history.items])
    print("listening:", window._listening)

    # повторный матч того же трека не должен давать тост «Уточнил трек»
    window._start_listening()
    window._inflight_session = window._session
    window._in_flight = True
    window._on_matched(right)
    window._inflight_session = window._session
    window._in_flight = True
    window._on_matched(right)
    print("same track status:", window.status_title.text())
    window._finalize(manual=True)

    # ручная остановка без матча
    window._start_listening()
    window._finalize(manual=True)
    print("manual stop:", window.status_title.text())


if __name__ == "__main__":
    main()

"""Проверка: ручная остановка раньше таймера всё равно распознаёт записанное."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import app.ui.main_window as main_window  # noqa: E402
import test_flow as tf  # noqa: E402
from app.ui.theme import stylesheet  # noqa: E402


def main() -> None:
    tf.WAV = tf.to_wav(tf.deezer_preview("Daft Punk One More Time"))
    main_window.Recorder = tf.FakeRecorder

    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())

    window = main_window.MainWindow()
    window.show()
    window._start_listening()
    started = time.monotonic()
    QTimer.singleShot(5000, window.toggle_listen)

    def report() -> None:
        print("status:", window.status_title.text())
        print("hint:", window.status_hint.text())
        print("listening:", window._listening, "attempts:", window._attempts)
        print("elapsed:", round(time.monotonic() - started, 1))
        app.quit()

    QTimer.singleShot(22000, report)
    app.exec()


if __name__ == "__main__":
    main()

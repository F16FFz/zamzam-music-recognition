"""Проверка геометрии интерфейса (без визуального просмотра)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from app.models import Track  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.theme import stylesheet  # noqa: E402


def rect_text(widget: QWidget) -> str:
    g = widget.geometry()
    return f"{g.x()},{g.y()} {g.width()}x{g.height()}"


def main() -> None:
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    w = MainWindow()
    w.show()
    app.processEvents()

    print("window:", w.width(), "x", w.height())
    print("root:", rect_text(w.root))
    print("pages:", rect_text(w.pages))
    print("pulse:", rect_text(w.pulse))
    print("status:", rect_text(w.status_title), "hint:", rect_text(w.status_hint))
    print("waveform:", rect_text(w.waveform))
    print("result_stack:", rect_text(w.result_stack))
    print("placeholder:", rect_text(w.placeholder))
    print("mode chips:", rect_text(w.chip_system), rect_text(w.chip_mic))

    track = Track(
        title="Very Long Track Title That Should Wrap Nicely Across Two Lines",
        artist="Some Artist With A Long Name, Another Artist",
        album="An Album With A Rather Long Title",
        year="2024",
        genre="Synthwave",
        spotify_url="https://open.spotify.com/track/x",
        youtube_url="https://youtube.com/watch?v=x",
        apple_url="https://music.apple.com/x",
        yandex_url="https://music.yandex.ru/x",
        recognized_at=time.time(),
    )
    w._current_track = track
    w._display_track(track, "НАЙДЕНО!", "ОТКРЫВАЙ НА УДОБНОЙ ПЛОЩАДКЕ")
    app.processEvents()

    print("card:", rect_text(w.card))
    print("cover:", rect_text(w.card.cover))
    print("title:", rect_text(w.card.title), "sizeHint:", w.card.title.sizeHint().width(), "x",
          w.card.title.sizeHint().height())
    print("artist:", rect_text(w.card.artist), "sizeHint:", w.card.artist.sizeHint().width())
    print("meta:", rect_text(w.card.meta), "sizeHint:", w.card.meta.sizeHint().width())
    chips = [
        ("spotify", w.card.btn_spotify),
        ("youtube", w.card.btn_youtube),
        ("apple", w.card.btn_apple),
        ("yandex", w.card.btn_yandex),
        ("copy", w.card.btn_copy),
    ]
    total = 0
    for name, chip in chips:
        print("chip", name, rect_text(chip), "visible:", chip.isVisible())
        total += chip.width() + 5
    print("chips total width:", total, "card inner:", w.card.width() - 28)

    w.history.items = [track] * 6
    w._refresh_history()
    w.set_page(1)
    app.processEvents()
    print("history page:", rect_text(w.pages.currentWidget()))
    rows = [
        w.history_layout.itemAt(i).widget()
        for i in range(w.history_layout.count())
        if w.history_layout.itemAt(i).widget() is not None
    ]
    for row in rows[:3]:
        print("row:", rect_text(row))
    print("history rows:", len(rows))

    # проверка выхода детей за пределы карточки
    for child in w.card.findChildren(QWidget):
        if not child.isVisible():
            continue
        br = child.geometry()
        if br.right() > w.card.width() - 2 or br.bottom() > w.card.height() - 2:
            print("OVERFLOW:", child.__class__.__name__, child.objectName(), br)

    for label in w.findChildren(QLabel):
        if label.isVisible() and label.text() and not label.wordWrap():
            if label.sizeHint().width() > label.width() + 1:
                print("CLIPPED LABEL:", label.objectName(), repr(label.text()[:40]),
                      label.width(), "<", label.sizeHint().width())

    for button in w.findChildren(QPushButton):
        if button.isVisible() and button.text():
            if button.sizeHint().width() > button.width() + 1:
                print("CLIPPED BUTTON:", button.objectName(), repr(button.text()),
                      button.width(), "<", button.sizeHint().width())


if __name__ == "__main__":
    main()

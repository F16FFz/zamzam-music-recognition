"""Виджеты интерфейса: кнопка прослушивания, волна, карточка трека, история."""
from __future__ import annotations

import math

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from ..config import resource_path
from ..models import Track
from . import icons


_LOGO_CACHE: QPixmap | None = None


def _logo_pixmap() -> QPixmap:
    global _LOGO_CACHE
    if _LOGO_CACHE is None:
        _LOGO_CACHE = QPixmap(str(resource_path("assets", "logo.png")))
    return _LOGO_CACHE


# --------------------------------------------------------------------- утилиты
def cover_pixmap(source: QPixmap, size: int, radius: int) -> QPixmap:
    """Квадратная обрезка обложки со скруглёнными углами."""
    scaled = source.scaled(
        size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    cropped = scaled.copy(x, y, size, size)

    result = QPixmap(size * 2, size * 2)
    result.setDevicePixelRatio(2.0)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return result


class ElidedLabel(QLabel):
    """QLabel, который сокращает длинный текст многоточием."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text or ""
        self._apply_elide()

    def fullText(self) -> str:  # noqa: N802
        return self._full_text

    def _apply_elide(self) -> None:
        available = max(0, self.width() - 2)
        if available <= 0:
            super().setText(self._full_text)
            return
        elided = self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, available)
        super().setText(elided)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_elide()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange):
            self._apply_elide()


def _fmt_history_time(ts: float) -> str:
    """Время для строки истории: 14:32 / вчера / 12 ноя."""
    return i18n.history_time(ts)


# ---------------------------------------------------------------- фон окна
class RootFrame(QFrame):
    """Скруглённая «афиша» приложения: тёмный фон, лаймовый свет и сетка точек."""

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 24, 24)
        painter.setClipPath(path)

        base = QLinearGradient(0, 0, 0, self.height())
        base.setColorAt(0.0, QColor("#0C1009"))
        base.setColorAt(0.55, QColor("#090C07"))
        base.setColorAt(1.0, QColor("#060805"))
        painter.fillRect(self.rect(), base)

        lime = QRadialGradient(
            QPointF(self.width() * 0.16, -60), self.width() * 0.95
        )
        lime.setColorAt(0.0, QColor(200, 247, 81, 46))
        lime.setColorAt(0.5, QColor(200, 247, 81, 13))
        lime.setColorAt(1.0, QColor(200, 247, 81, 0))
        painter.fillRect(self.rect(), lime)

        deep = QRadialGradient(
            QPointF(self.width() * 1.0, self.height() * 0.88), self.width() * 0.8
        )
        deep.setColorAt(0.0, QColor(96, 168, 30, 42))
        deep.setColorAt(1.0, QColor(96, 168, 30, 0))
        painter.fillRect(self.rect(), deep)

        # типографская сетка точек — «печатный» характер
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(242, 243, 227, 11))
        step = 18
        for y in range(9, self.height(), step):
            for x in range(9, self.width(), step):
                painter.drawEllipse(QPointF(x, y), 0.9, 0.9)

        vignette = QRadialGradient(
            QPointF(self.width() / 2, self.height() / 2), self.width() * 0.78
        )
        vignette.setColorAt(0.5, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 92))
        painter.fillRect(self.rect(), vignette)
        painter.end()


# ------------------------------------------------------------- бегущая строка
class TickerStrip(QFrame):
    """Тонкая типографская строка-тикер под вкладками."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("strip")
        self.setFixedHeight(24)
        self._text = text
        self._offset = 0.0
        self._gap = 56.0
        self._font = QFont("Cascadia Mono")
        self._font.setPixelSize(9)
        self._font.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        self._metrics = QFontMetrics(self._font)
        self._text_width = float(self._metrics.horizontalAdvance(text))
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_text(self, text: str) -> None:
        self._text = text
        self._text_width = float(self._metrics.horizontalAdvance(text))
        self._offset = 0.0
        self.update()

    def _tick(self) -> None:
        self._offset = (self._offset + 0.65) % (self._text_width + self._gap)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipRect(self.rect())
        painter.setFont(self._font)
        painter.setPen(QColor("#98A084"))
        metrics = painter.fontMetrics()
        baseline = (self.height() + metrics.ascent() - metrics.descent()) / 2
        period = self._text_width + self._gap
        x = -self._offset
        while x < self.width():
            painter.drawText(QPointF(x, baseline), self._text)
            x += period
        painter.end()


class LogoMark(QWidget):
    """Логотип Zamzam из assets/logo.png."""

    def __init__(self, size: int = 26, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        rect = QRectF(0, 0, self._size, self._size)
        pixmap = _logo_pixmap()
        if not pixmap.isNull():
            painter.drawPixmap(rect.toRect(), pixmap)
        else:
            path = QPainterPath()
            path.addRoundedRect(rect, self._size * 0.28, self._size * 0.28)
            painter.fillPath(path, QColor("#B8EC3F"))
            painter.setPen(QColor("#0B0E08"))
            font = QFont("Bahnschrift", int(self._size * 0.6))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, "Z")
        painter.end()


# --------------------------------------------------------- кнопка прослушивания
class PulseButton(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(196, 196)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._listening = False
        self._level = 0.0
        self._progress = 0.0
        self._phase = 0.0
        self._pressed = False
        self._mic_renderer = QSvgRenderer(
            QByteArray(icons.mic("#080A06").encode("utf-8"))
        )
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------ API
    def set_listening(self, listening: bool) -> None:
        self._listening = listening
        if not listening:
            self._progress = 0.0
        self.retranslate()
        self.update()

    def retranslate(self) -> None:
        self.setToolTip(
            i18n.tr("ОСТАНОВИТЬ") if self._listening else i18n.tr("СЛУШАТЬ · CTRL + ALT + S")
        )

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))
        if self._listening:
            self.update()

    def set_progress(self, value: float) -> None:
        """Доля прослушанного времени 0..1 — рисуется дугой вокруг кнопки."""
        self._progress = max(0.0, min(1.0, value))
        if self._listening:
            self.update()

    # ------------------------------------------------------------- анимация
    def _tick(self) -> None:
        self._phase += 0.016
        if self._listening:
            self.update()
        else:
            # лёгкое «дыхание» в покое — перерисовываем реже
            if int(self._phase * 10) % 3 == 0:
                self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        cx = self.width() / 2
        cy = self.height() / 2
        base = 58.0
        hovered = self.underMouse()
        t = self._phase
        breathe = math.sin(t * 1.4) * 2.4

        # лаймовое свечение-«софит»
        glow_radius = base + 46 + breathe
        glow = QRadialGradient(QPointF(cx, cy), glow_radius)
        strength = 96 if self._listening else (72 if hovered else 52)
        glow.setColorAt(0.0, QColor(200, 247, 81, strength))
        glow.setColorAt(0.5, QColor(200, 247, 81, int(strength * 0.34)))
        glow.setColorAt(1.0, QColor(200, 247, 81, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

        if self._listening:
            for index in range(3):
                progress = ((t * 0.55) + index / 3.0) % 1.0
                radius = base + 8 + progress * 46
                alpha = int(88 * (1.0 - progress) ** 1.5)
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(200, 247, 81, alpha), 1.6))
                painter.drawEllipse(QPointF(cx, cy), radius, radius)

            # шкала прослушивания: насечки + дуга цвета кости
            ring = base + 12.0
            ring_rect = QRectF(cx - ring, cy - ring, ring * 2, ring * 2)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(242, 243, 227, 30), 3.0, Qt.SolidLine, Qt.FlatCap))
            painter.drawEllipse(QPointF(cx, cy), ring, ring)
            painter.setPen(QPen(QColor(242, 243, 227, 46), 1.0))
            for tick in range(12):
                angle = math.radians(tick * 30 - 90)
                inner = ring + 5
                outer = ring + (9 if tick % 3 == 0 else 7)
                painter.drawLine(
                    QPointF(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner),
                    QPointF(cx + math.cos(angle) * outer, cy + math.sin(angle) * outer),
                )
            if self._progress > 0.001:
                painter.setPen(QPen(QColor(242, 243, 227, 235), 3.0, Qt.SolidLine, Qt.RoundCap))
                painter.drawArc(
                    ring_rect, 90 * 16, -int(round(self._progress * 360 * 16))
                )
                head = math.radians(90 - self._progress * 360)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(200, 247, 81))
                painter.drawEllipse(
                    QPointF(cx + math.cos(head) * ring, cy - math.sin(head) * ring),
                    2.8,
                    2.8,
                )

        radius = base - (2.5 if self._pressed else 0.0)

        # жёсткая офсетная тень — «наклейка», а не софт-глянец
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(4, 6, 3, 190))
        painter.drawEllipse(QPointF(cx + 3, cy + 6), radius, radius)
        painter.setBrush(QColor(29, 42, 16, 210))
        painter.drawEllipse(QPointF(cx + 2, cy + 4), radius, radius)

        gradient = QLinearGradient(cx, cy - radius, cx, cy + radius)
        gradient.setColorAt(0.0, QColor("#DAFF6E"))
        gradient.setColorAt(0.55, QColor("#C8F751"))
        gradient.setColorAt(1.0, QColor("#A9DC32"))
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#080A06"), 1.6))
        painter.drawEllipse(QPointF(cx, cy), radius - 0.8, radius - 0.8)

        # внутренняя тонкая линия — печатный контур
        painter.setPen(QPen(QColor(8, 10, 6, 60), 1.0))
        painter.drawEllipse(QPointF(cx, cy), radius - 8.0, radius - 8.0)

        if not self._listening:
            icon_size = 54
            target = QRectF(
                cx - icon_size / 2, cy - icon_size / 2 - 1, icon_size, icon_size
            )
            self._mic_renderer.render(painter, target)
        else:
            self._paint_equalizer(painter, cx, cy)
        painter.end()

    def _paint_equalizer(self, painter: QPainter, cx: float, cy: float) -> None:
        painter.setPen(Qt.NoPen)
        bars = 5
        bar_w = 8.0
        gap = 7.0
        total = bars * bar_w + (bars - 1) * gap
        x = cx - total / 2
        max_h = 48.0
        for index in range(bars):
            painter.setBrush(
                QColor(8, 10, 6, 245) if index != 2 else QColor(8, 10, 6, 255)
            )
            wobble = 0.55 + 0.45 * abs(math.sin(self._phase * 3.4 + index * 1.15))
            shape = 1.0 - abs(index - (bars - 1) / 2) / (bars * 1.1)
            height = 8.0 + max_h * (0.18 + self._level * 0.9) * wobble * (0.6 + shape)
            height = min(height, max_h + 6)
            painter.drawRoundedRect(
                QRectF(x, cy - height / 2, bar_w, height), 1.5, 1.5
            )
            x += bar_w + gap

    # -------------------------------------------------------------- события
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._pressed = False
            self.update()
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)


# ---------------------------------------------------------------- живая волна
class LiveWaveform(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(46)
        self._bars = [0.0] * 56
        self._target = 0.0
        self._active = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def set_level(self, level: float) -> None:
        self._target = max(0.0, min(1.0, level))

    def _tick(self) -> None:
        self._phase += 0.045
        self._bars.pop(0)
        if self._active:
            ripple = 0.35 + 0.65 * abs(math.sin(self._phase * 2.1))
            value = self._target * ripple
        else:
            value = 0.0
        self._bars.append(value)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        width = self.width()
        height = self.height()
        count = len(self._bars)
        step = width / count
        bar_w = max(2.0, step * 0.46)
        painter.setPen(Qt.NoPen)
        for index, value in enumerate(self._bars):
            if self._active:
                amplitude = 4.0 + value * (height - 10)
            else:
                amplitude = 4.0
            mix = index / max(1, count - 1)
            color = QColor(
                int(200 + (242 - 200) * mix),
                int(247 + (243 - 247) * mix),
                int(81 + (227 - 81) * mix),
                int(230 - 90 * mix) if self._active else 40,
            )
            painter.setBrush(color)
            x = index * step + (step - bar_w) / 2
            painter.drawRoundedRect(
                QRectF(x, height / 2 - amplitude / 2, bar_w, amplitude),
                1.0,
                1.0,
            )
        # базовая линия
        painter.setPen(QPen(QColor(242, 243, 227, 18), 1.0))
        painter.drawLine(0, height // 2, width, height // 2)
        painter.end()


# ------------------------------------------------------------- обложка трека
class CoverArt(QWidget):
    def __init__(self, size: int = 92, radius: int = 18, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self._radius = radius
        self._source: QPixmap | None = None
        self._rendered: QPixmap | None = None
        self.setFixedSize(size, size)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source = pixmap
        self._rendered = (
            cover_pixmap(pixmap, self._size, self._radius)
            if pixmap is not None and not pixmap.isNull()
            else None
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self._size, self._size)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.setClipPath(path)

        if self._rendered is not None:
            painter.drawPixmap(0, 0, self._rendered)
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor("#232D14"))
            gradient.setColorAt(1.0, QColor("#0E1209"))
            painter.fillPath(path, gradient)
            renderer = QSvgRenderer(QByteArray(icons.note("#C8F751").encode("utf-8")))
            icon_size = self._size * 0.34
            renderer.render(
                painter,
                QRectF(
                    (self._size - icon_size) / 2,
                    (self._size - icon_size) / 2,
                    icon_size,
                    icon_size,
                ),
            )

        painter.setClipping(False)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(242, 243, 227, 46), 1.0))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), self._radius, self._radius)
        painter.end()


# ------------------------------------------------------------- карточка трека
class TrackCard(QFrame):
    copied = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._track: Track | None = None
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self._animation = QPropertyAnimation(self._opacity, b"opacity", self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(14)
        self.cover = CoverArt(92, 18)
        top.addWidget(self.cover, 0, Qt.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        text_box.setContentsMargins(0, 2, 0, 0)
        self.title = QLabel("—")
        self.title.setObjectName("trackTitle")
        self.title.setWordWrap(True)
        self.title.setMaximumHeight(66)
        self.artist = ElidedLabel("")
        self.artist.setObjectName("trackArtist")
        self.meta = ElidedLabel("")
        self.meta.setObjectName("trackMeta")
        self.meta.setWordWrap(False)
        text_box.addWidget(self.title)
        text_box.addWidget(self.artist)
        text_box.addWidget(self.meta)
        text_box.addStretch(1)
        top.addLayout(text_box, 1)
        outer.addLayout(top)

        chips = QHBoxLayout()
        chips.setSpacing(5)
        self.btn_spotify = self._chip("Spotify", icons.make_icon(icons.spotify(), 14), "spotify")
        self.btn_youtube = self._chip("YouTube", icons.make_icon(icons.youtube(), 14), "youtube")
        self.btn_apple = self._chip("Apple", icons.make_icon(icons.apple(), 14), "apple")
        self.btn_yandex = self._chip("Яндекс", icons.make_icon(icons.yandex(), 14), "yandex")
        self.btn_spotify.clicked.connect(lambda: self._open("spotify_url"))
        self.btn_youtube.clicked.connect(lambda: self._open("youtube_url"))
        self.btn_apple.clicked.connect(lambda: self._open("apple_url"))
        self.btn_yandex.clicked.connect(lambda: self._open("yandex_url"))
        self.btn_copy = QPushButton()
        self.btn_copy.setObjectName("iconBtn")
        self.btn_copy.setIcon(icons.make_icon(icons.copy("#C8F751"), 15))
        self.btn_copy.setIconSize(QSize(15, 15))
        self.btn_copy.setFixedSize(30, 30)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setToolTip(i18n.tr("СКОПИРОВАТЬ НАЗВАНИЕ"))
        self.btn_copy.clicked.connect(self._copy)
        chips.addWidget(self.btn_spotify)
        chips.addWidget(self.btn_youtube)
        chips.addWidget(self.btn_apple)
        chips.addWidget(self.btn_yandex)
        chips.addStretch(1)
        chips.addWidget(self.btn_copy)
        outer.addLayout(chips)

    def _chip(self, text: str, icon: QIcon, brand: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("brand", brand)
        button.setIcon(icon)
        button.setIconSize(QSize(14, 14))
        button.setCursor(Qt.PointingHandCursor)
        return button

    def retranslate(self) -> None:
        self.btn_yandex.setText(i18n.tr("Яндекс"))
        self.btn_copy.setToolTip(i18n.tr("СКОПИРОВАТЬ НАЗВАНИЕ"))
        if self._track is not None:
            self.artist.setText(
                self._track.artist or i18n.tr("Неизвестный исполнитель")
            )

    # ------------------------------------------------------------------ API
    def set_track(self, track: Track) -> None:
        self._track = track
        self.title.setText(track.title)
        self.artist.setText(track.artist or i18n.tr("Неизвестный исполнитель"))
        self.meta.setText(track.meta_line)
        self.meta.setVisible(bool(track.meta_line))
        self.cover.set_pixmap(None)

        self.btn_spotify.setVisible(bool(track.spotify_url))
        self.btn_youtube.setVisible(bool(track.youtube_url))
        self.btn_apple.setVisible(bool(track.apple_url))
        self.btn_yandex.setVisible(bool(track.yandex_url))

        self.btn_spotify.setToolTip(track.spotify_url)
        self.btn_youtube.setToolTip(track.youtube_url)
        self.btn_apple.setToolTip(track.apple_url)
        self.btn_yandex.setToolTip(track.yandex_url)

    def _open(self, field: str) -> None:
        if not self._track:
            return
        url = getattr(self._track, field, "")
        if url:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl(url))

    def update_links(self, links: dict[str, str]) -> None:
        if not self._track:
            return
        for field, url in links.items():
            if hasattr(self._track, field) and url:
                setattr(self._track, field, url)
        for button, field in (
            (self.btn_spotify, "spotify_url"),
            (self.btn_youtube, "youtube_url"),
            (self.btn_apple, "apple_url"),
            (self.btn_yandex, "yandex_url"),
        ):
            url = getattr(self._track, field, "")
            button.setVisible(bool(url))
            button.setToolTip(url)

    def set_cover(self, pixmap: QPixmap) -> None:
        self.cover.set_pixmap(pixmap)

    def fade_in(self) -> None:
        self._animation.stop()
        self._opacity.setOpacity(0.0)
        self._animation.setDuration(260)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.start()

    def _copy(self) -> None:
        if not self._track:
            return
        from PySide6.QtWidgets import QApplication

        text = f"{self._track.artist} — {self._track.title}".strip(" —")
        QApplication.clipboard().setText(text)
        self.copied.emit()


# ------------------------------------------------------------- строка истории
class HistoryRow(QFrame):
    clicked = Signal(object)

    def __init__(
        self, track: Track, index: int = 1, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("historyRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(64)
        self._track = track

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 8, 12, 8)
        layout.setSpacing(10)

        number = QLabel(f"{index:02d}")
        number.setObjectName("historyIndex")
        number.setFixedWidth(24)
        number.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(number)

        self.cover = CoverArt(42, 9)
        layout.addWidget(self.cover)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = ElidedLabel(track.title)
        title.setObjectName("historyTitle")
        artist = ElidedLabel(track.artist or i18n.tr("Неизвестный исполнитель"))
        artist.setObjectName("historyArtist")
        text.addWidget(title)
        text.addWidget(artist)
        layout.addLayout(text, 1)

        moment = QLabel(_fmt_history_time(track.recognized_at))
        moment.setObjectName("historyTime")
        layout.addWidget(moment, 0, Qt.AlignTop)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit(self._track)
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------- тосты
class Toast(QLabel):
    """Короткое всплывающее уведомление внизу окна."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

    def show_message(self, text: str, msec: int = 1900) -> None:
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        if parent:
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 26
            self.move(max(8, x), max(8, y))
        self._animation.stop()
        self._effect.setOpacity(1.0)
        self.show()
        self.raise_()
        self._hide_timer.start(msec)

    def _fade_out(self) -> None:
        self._animation.stop()
        self._animation.setDuration(280)
        self._animation.setStartValue(self._effect.opacity())
        self._animation.setEndValue(0.0)
        self._animation.setEasingCurve(QEasingCurve.InCubic)
        self._animation.finished.connect(self._on_faded)
        self._animation.start()

    def _on_faded(self) -> None:
        try:
            self._animation.finished.disconnect(self._on_faded)
        except RuntimeError:
            pass
        self.hide()


class TitleBar(QWidget):
    minimize_requested = Signal()
    close_requested = Signal()
    language_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self._drag_offset = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 12, 4)
        layout.setSpacing(10)
        layout.addWidget(LogoMark(26))

        brand_box = QVBoxLayout()
        brand_box.setSpacing(-2)
        brand = QLabel("ZAMZAM")
        brand.setObjectName("brand")
        brand_font = QFont("Bahnschrift SemiCondensed")
        brand_font.setPixelSize(21)
        brand_font.setWeight(QFont.DemiBold)
        brand_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.8)
        brand.setFont(brand_font)
        sub = QLabel("СЛУШАЙ · ОПОЗНАВАЙ · 18 СЕК")
        sub.setObjectName("brandSub")
        sub_font = QFont("Cascadia Mono")
        sub_font.setPixelSize(8)
        sub_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
        sub.setFont(sub_font)
        self._sub = sub
        brand_box.addWidget(brand)
        brand_box.addWidget(sub)
        layout.addLayout(brand_box)
        layout.addStretch(1)

        self.lang_button = QPushButton("EN")
        self.lang_button.setObjectName("winBtn")
        self.lang_button.setFixedSize(36, 30)
        self.lang_button.setCursor(Qt.PointingHandCursor)
        lang_font = QFont("Cascadia Mono")
        lang_font.setPixelSize(10)
        lang_font.setBold(True)
        self.lang_button.setFont(lang_font)
        self.lang_button.clicked.connect(self.language_requested)
        layout.addWidget(self.lang_button)

        minimize = QPushButton()
        minimize.setObjectName("winBtn")
        minimize.setIcon(icons.make_icon(icons.minimize("#F2F3E3"), 15))
        minimize.setIconSize(QSize(15, 15))
        minimize.setFixedSize(30, 30)
        minimize.setCursor(Qt.PointingHandCursor)
        minimize.clicked.connect(self.minimize_requested)
        close = QPushButton()
        close.setObjectName("winBtn")
        close.setProperty("danger", "true")
        close.setIcon(icons.make_icon(icons.close("#F2F3E3"), 15))
        close.setIconSize(QSize(15, 15))
        close.setFixedSize(30, 30)
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.close_requested)
        self._minimize_button = minimize
        self._close_button = close
        layout.addWidget(minimize)
        layout.addWidget(close)
        self.retranslate()

    def retranslate(self) -> None:
        self._sub.setText(i18n.tr("СЛУШАЙ · ОПОЗНАВАЙ · 18 СЕК"))
        english = i18n.get_language() == "en"
        self.lang_button.setText("RU" if english else "EN")
        self.lang_button.setToolTip(
            i18n.tr("Переключить на русский" if english else "Переключить на английский")
        )
        self._minimize_button.setToolTip(i18n.tr("Свернуть в трей"))
        self._close_button.setToolTip(i18n.tr("Закрыть в трей"))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None

"""Векторные иконки интерфейса (без внешних файлов)."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_TPL = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">{body}</svg>'


def _svg(body: str) -> str:
    return _TPL.format(body=body)


def mic(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<rect x="9" y="2.4" width="6" height="11" rx="3" fill="{color}"/>'
        f'<path d="M5.6 11.4a6.4 6.4 0 0 0 12.8 0" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round"/>'
        f'<path d="M12 17.9V21" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>'
    )


def close(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<path d="M6.5 6.5l11 11M17.5 6.5l-11 11" stroke="{color}" stroke-width="1.9" '
        'stroke-linecap="round"/>'
    )


def minimize(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<path d="M6 12h12" stroke="{color}" stroke-width="1.9" stroke-linecap="round"/>'
    )


def copy(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<rect x="9" y="9" width="10.5" height="11.5" rx="2.6" stroke="{color}" '
        'stroke-width="1.7"/>'
        f'<path d="M15.2 6.2V5.6A2.6 2.6 0 0 0 12.6 3H6.1A2.6 2.6 0 0 0 3.5 5.6v6.3'
        f'a2.6 2.6 0 0 0 2.6 2.6h.6" stroke="{color}" stroke-width="1.7" '
        'stroke-linecap="round"/>'
    )


def trash(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<path d="M4.5 6.5h15M9.5 6.2V4.9c0-.8.6-1.4 1.4-1.4h2.2c.8 0 1.4.6 1.4 1.4v1.3" '
        f'stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>'
        f'<path d="M6.6 6.8l.8 12.1c0 1 .9 1.8 1.9 1.8h5.4c1 0 1.9-.8 1.9-1.8l.8-12.1" '
        f'stroke="{color}" stroke-width="1.7" stroke-linejoin="round"/>'
    )


def history(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<path d="M3.6 12a8.4 8.4 0 1 0 2.5-6" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round"/>'
        f'<path d="M3.4 3.9v4.4h4.4" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M12 7.8V12l3 1.8" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def spotify(color: str = "#1DB954") -> str:
    return _svg(
        f'<circle cx="12" cy="12" r="10" fill="{color}"/>'
        '<path d="M7.1 9.5c3.3-.9 6.9-.6 9.7.9" stroke="#08110C" stroke-width="1.8" '
        'stroke-linecap="round"/>'
        '<path d="M7.7 12.6c2.8-.7 5.7-.4 8 .9" stroke="#08110C" stroke-width="1.55" '
        'stroke-linecap="round"/>'
        '<path d="M8.3 15.5c2.2-.5 4.4-.3 6.3.7" stroke="#08110C" stroke-width="1.35" '
        'stroke-linecap="round"/>'
    )


def youtube(color: str = "#FF2D55") -> str:
    return _svg(
        f'<rect x="2.2" y="5.4" width="19.6" height="13.2" rx="4.2" fill="{color}"/>'
        '<path d="M10.2 9.2l4.9 2.8-4.9 2.8V9.2z" fill="#FFFFFF"/>'
    )


def apple(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<path d="M9.3 6.4V16c0 1.5-1.1 2.6-2.6 2.6S4 17.5 4 16s1.1-2.6 2.6-2.6c.4 0 .8.1 '
        f'1.1.2V5l9.5-2v9.7c0 1.5-1.1 2.6-2.6 2.6s-2.7-1.1-2.7-2.6 1.1-2.6 2.7-2.6c.4 0 '
        f'.8.1 1.1.2V4.5L9.3 6.4z" fill="{color}"/>'
    )


def yandex(color: str = "#FFCC00") -> str:
    return _svg(
        f'<circle cx="12" cy="12" r="10" fill="{color}"/>'
        '<path d="M10.4 17.5l3.2-4.7c.5-.8.8-1.4.8-2.3 0-1.4-1-2.2-2.5-2.2-1.2 0-2 .6-2.6 1.4'
        'L8 8.5c.8-1.2 2.2-2 4-2 2.5 0 4.1 1.4 4.1 3.7 0 1.3-.4 2.2-1.1 3.2l-2.7 4.1h-1.9z" '
        'fill="#111111"/>'
    )


def note(color: str = "#FFFFFF") -> str:
    return _svg(
        f'<path d="M9 17.2a2.7 2.7 0 1 1-2.7-2.7c.4 0 .7.1 1 .2V5.2l9.7-2v9.5a2.7 2.7 0 1 1-2.7-2.7'
        f'c.4 0 .7.1 1 .2V5.2L9 6.5v10.7z" fill="{color}"/>'
    )


def make_icon(svg: str, size: int = 18) -> QIcon:
    """Рендерит SVG в QIcon с удвоенным разрешением для чёткости на HiDPI."""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    scale = 2
    pixmap = QPixmap(QSize(size * scale, size * scale))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)

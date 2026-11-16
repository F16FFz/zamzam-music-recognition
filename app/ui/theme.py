"""Цвета, шрифты и общий стиль приложения Zamzam."""
from __future__ import annotations

INK = "#080A06"
INK_2 = "#0C0F08"
PANEL = "#10140B"
PANEL_2 = "#151A0E"
BONE = "#F2F3E3"
MUTED = "#98A084"
LIME = "#C8F751"
LIME_DEEP = "#8FBE24"
DEEP_GREEN = "#1D2A10"
DANGER = "#FF6A3D"

FONT_STACK = '"Segoe UI Variable Text", "Segoe UI", sans-serif'
DISPLAY_STACK = '"Bahnschrift SemiCondensed", "Bahnschrift", "Segoe UI Semibold"'
MONO_STACK = '"Cascadia Mono", "Consolas", monospace'


def stylesheet() -> str:
    return f"""
    * {{
        color: {BONE};
        font-family: {FONT_STACK};
        font-size: 13px;
        outline: none;
    }}

    #root {{
        border-radius: 24px;
        border: 1px solid rgba(242, 243, 227, 34);
        background: qlineargradient(x1:0, y1:0, x2:0.6, y2:1,
            stop:0 #0B0E08, stop:0.55 #090B06, stop:1 #060805);
    }}

    QLabel {{ background: transparent; }}

    #brand {{
        font-family: {DISPLAY_STACK};
        font-size: 21px;
        font-weight: 700;
        color: {BONE};
    }}
    #brandSub {{
        font-family: {MONO_STACK};
        font-size: 9px;
        color: {LIME};
    }}

    #winBtn {{
        background: transparent;
        border: none;
        border-radius: 7px;
    }}
    #winBtn:hover {{ background: rgba(242, 243, 227, 24); }}
    #winBtn[danger="true"]:hover {{ background: rgba(255, 106, 61, 190); }}

    #strip {{
        border-top: 1px solid rgba(242, 243, 227, 16);
        border-bottom: 1px solid rgba(242, 243, 227, 16);
        background: rgba(242, 243, 227, 3);
    }}
    #ticker {{
        font-family: {MONO_STACK};
        font-size: 9px;
        color: {MUTED};
    }}

    #segmentBar {{
        background: rgba(242, 243, 227, 7);
        border: 1px solid rgba(242, 243, 227, 22);
        border-radius: 13px;
    }}
    #segment {{
        background: transparent;
        border: none;
        border-radius: 9px;
        padding: 7px 4px;
        color: {MUTED};
        font-family: {DISPLAY_STACK};
        font-size: 12px;
        font-weight: 600;
    }}
    #segment:hover {{ color: {BONE}; }}
    #segment:checked {{
        background: {LIME};
        color: {INK};
    }}

    #statusTitle {{
        font-family: {DISPLAY_STACK};
        font-size: 18px;
        font-weight: 600;
    }}
    #statusHint {{
        font-family: {MONO_STACK};
        font-size: 10px;
        color: {MUTED};
    }}

    #card {{
        background: {PANEL};
        border: 1px solid rgba(242, 243, 227, 30);
        border-left: 3px solid {LIME};
        border-radius: 16px;
    }}
    #placeholder {{
        background: rgba(242, 243, 227, 3);
        border: 1px dashed rgba(242, 243, 227, 34);
        border-radius: 16px;
    }}
    #trackTitle {{
        font-family: {DISPLAY_STACK};
        font-size: 18px;
        font-weight: 600;
    }}
    #trackArtist {{
        font-size: 12px;
        color: {LIME};
        font-weight: 600;
    }}
    #trackMeta {{
        font-family: {MONO_STACK};
        font-size: 9px;
        color: {MUTED};
    }}

    #historyHeader {{
        font-family: {DISPLAY_STACK};
        font-size: 16px;
        font-weight: 600;
        color: {BONE};
    }}

    QPushButton[brand] {{
        border-radius: 7px;
        padding: 5px 8px;
        font-family: {MONO_STACK};
        font-size: 9px;
        font-weight: 600;
        border: 1px solid transparent;
    }}
    QPushButton[brand="spotify"] {{
        background: rgba(29, 185, 84, 16);
        border-color: rgba(29, 185, 84, 86);
        color: #8AE6A8;
    }}
    QPushButton[brand="spotify"]:hover {{ background: rgba(29, 185, 84, 56); }}
    QPushButton[brand="youtube"] {{
        background: rgba(255, 90, 60, 14);
        border-color: rgba(255, 90, 60, 86);
        color: #FFA08C;
    }}
    QPushButton[brand="youtube"]:hover {{ background: rgba(255, 90, 60, 52); }}
    QPushButton[brand="apple"] {{
        background: rgba(242, 243, 227, 10);
        border-color: rgba(242, 243, 227, 54);
        color: {BONE};
    }}
    QPushButton[brand="apple"]:hover {{ background: rgba(242, 243, 227, 30); }}
    QPushButton[brand="yandex"] {{
        background: rgba(255, 204, 0, 14);
        border-color: rgba(255, 204, 0, 78);
        color: #FFDF6B;
    }}
    QPushButton[brand="yandex"]:hover {{ background: rgba(255, 204, 0, 46); }}

    #iconBtn {{
        background: rgba(242, 243, 227, 10);
        border: 1px solid rgba(242, 243, 227, 30);
        border-radius: 7px;
    }}
    #iconBtn:hover {{ background: rgba(200, 247, 81, 34); border-color: {LIME}; }}

    #modeChip {{
        background: transparent;
        border: 1px solid rgba(242, 243, 227, 26);
        border-radius: 7px;
        padding: 5px 10px;
        font-family: {MONO_STACK};
        font-size: 9px;
        color: {MUTED};
    }}
    #modeChip:hover {{ color: {BONE}; border-color: rgba(242, 243, 227, 56); }}
    #modeChip:checked {{
        background: rgba(200, 247, 81, 20);
        border-color: rgba(200, 247, 81, 130);
        color: {LIME};
    }}

    #deviceChip {{
        background: rgba(242, 243, 227, 8);
        border: 1px solid rgba(242, 243, 227, 24);
        border-radius: 7px;
        padding: 2px 10px;
        font-family: {MONO_STACK};
        font-size: 9px;
        color: {MUTED};
    }}
    #deviceChip:hover {{
        background: rgba(200, 247, 81, 18);
        border-color: rgba(200, 247, 81, 120);
        color: {BONE};
    }}

    #footerHint {{
        font-family: {MONO_STACK};
        font-size: 9px;
        color: rgba(152, 160, 132, 170);
    }}

    #historyRow {{
        background: transparent;
        border: none;
        border-bottom: 1px solid rgba(242, 243, 227, 14);
        border-radius: 0px;
    }}
    #historyRow:hover {{
        background: rgba(242, 243, 227, 8);
        border-bottom: 1px solid rgba(200, 247, 81, 96);
    }}
    #historyIndex {{
        font-family: {MONO_STACK};
        font-size: 10px;
        color: {LIME};
    }}
    #historyTitle {{ font-family: {DISPLAY_STACK}; font-size: 14px; font-weight: 600; }}
    #historyArtist {{ font-size: 11px; color: {MUTED}; }}
    #historyTime {{ font-family: {MONO_STACK}; font-size: 9px; color: rgba(152, 160, 132, 170); }}

    #emptyTitle {{
        font-family: {DISPLAY_STACK};
        font-size: 16px;
        font-weight: 600;
        color: {BONE};
    }}
    #emptyHint {{ font-size: 12px; color: {MUTED}; }}
    #placeholderTag {{
        font-family: {MONO_STACK};
        font-size: 9px;
        color: rgba(200, 247, 81, 150);
    }}
    #historyCount {{
        font-family: {MONO_STACK};
        font-size: 9px;
        color: {MUTED};
        padding-top: 3px;
    }}

    #toast {{
        background: rgba(10, 13, 8, 248);
        border: 1px solid rgba(200, 247, 81, 170);
        border-radius: 8px;
        padding: 8px 14px;
        font-family: {MONO_STACK};
        font-size: 10px;
        color: {BONE};
    }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(242, 243, 227, 34);
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: rgba(200, 247, 81, 120); }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

    QToolTip {{
        background: #11160B;
        color: {BONE};
        border: 1px solid rgba(200, 247, 81, 110);
        border-radius: 6px;
        padding: 6px 9px;
        font-family: {MONO_STACK};
        font-size: 9px;
    }}

    QMessageBox {{
        background-color: #0E120A;
    }}
    QMessageBox QLabel {{
        color: {BONE};
        font-size: 13px;
    }}
    QMessageBox QPushButton {{
        background: rgba(242, 243, 227, 16);
        border: 1px solid rgba(242, 243, 227, 44);
        border-radius: 7px;
        padding: 6px 18px;
        min-width: 64px;
    }}
    QMessageBox QPushButton:hover {{
        background: rgba(200, 247, 81, 34);
        border-color: {LIME};
    }}
    """

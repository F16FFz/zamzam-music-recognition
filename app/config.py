"""Пути, настройки и константы приложения Zamzam."""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

APP_NAME = "Zamzam"
APP_TITLE = "Zamzam"
APP_VERSION = "1.3.0"
APP_ID = "Zamzam.Desktop.1"

DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
COVERS_DIR = DATA_DIR / "covers"
HISTORY_FILE = DATA_DIR / "history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

_OLD_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EchoTag"


def resource_path(*parts: str) -> Path:
    """Путь к ресурсу как при запуске из исходников, так и из собранного exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*parts)


def _migrate_old_data() -> None:
    """Один раз переносит историю и настройки из прежней папки EchoTag."""
    if DATA_DIR.exists() or not _OLD_DATA_DIR.exists():
        return
    try:
        shutil.copytree(_OLD_DATA_DIR, DATA_DIR)
    except Exception:  # noqa: BLE001
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass


def ensure_dirs() -> None:
    _migrate_old_data()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    input_mode: str = "system"  # "system" — звук компьютера, "microphone" — микрофон
    max_history: int = 100
    language: str = "ru"  # "ru" — русский, "en" — английский
    tray_hint_shown: bool = False

    @classmethod
    def load(cls) -> "Settings":
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            data = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
            settings = cls(**data)
        except Exception:
            settings = cls()
        if settings.input_mode not in ("system", "microphone"):
            settings.input_mode = "system"
        if settings.language not in ("ru", "en"):
            settings.language = "ru"
        return settings

    def save(self) -> None:
        ensure_dirs()
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

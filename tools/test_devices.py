"""Проверка списка устройств и сохранения выбранного устройства."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LOCALAPPDATA"] = str(Path(tempfile.gettempdir()) / "ZamzamDevicesTest")

from app.audio import capture_devices  # noqa: E402
from app.config import Settings  # noqa: E402


def main() -> int:
    failures = 0
    for mode in ("system", "microphone"):
        options, default_id = capture_devices(mode)
        print(f"[{mode}] devices={len(options)} default={default_id!r}")
        for device_id, name in options:
            marker = "*" if device_id == default_id else " "
            print(f"  {marker} {name}  ({device_id})")
        if mode == "system" and not options:
            print("  ! не найдено ни одного устройства воспроизведения")
            failures += 1

    settings = Settings()
    settings.set_device_for("system", "speaker-test")
    settings.set_device_for("microphone", "mic-test")
    settings.save()
    loaded = Settings.load()
    print("saved:", loaded.system_device, loaded.mic_device)
    if loaded.system_device != "speaker-test" or loaded.mic_device != "mic-test":
        print("! настройки устройств не сохраняются")
        failures += 1

    print("OK" if failures == 0 else f"FAILED ({failures})")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Иконки приложения Zamzam из исходного PNG (Pillow)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "source_icon.png"
SIZE = 1024


def build_icon() -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if bbox:
        source = source.crop(bbox)

    width, height = source.size
    side = max(width, height)
    margin = int(side * 0.05)
    canvas = Image.new("RGBA", (side + margin * 2, side + margin * 2), (0, 0, 0, 0))
    canvas.alpha_composite(
        source,
        ((side - width) // 2 + margin, (side - height) // 2 + margin),
    )
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.save(ASSETS / "logo.png")
    icon.save(
        ASSETS / "icon.ico",
        sizes=[
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon_256.png")
    print("Icons saved to", ASSETS)


if __name__ == "__main__":
    main()

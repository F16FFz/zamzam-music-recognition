"""Проверка: какие длительности/участки превью Shazam узнаёт."""
from __future__ import annotations

import asyncio
import io
import sys
import wave
from pathlib import Path

import av
import numpy as np
from shazamio import Shazam

ROOT = Path(__file__).resolve().parent.parent
PREVIEW = ROOT / "tools" / "_preview.m4a"
PREVIEW_TRACK_ID = "1798691641"  # Morphy — Твои поцелуи (Apple Music)


def ensure_preview() -> None:
    """Скачивает официальное 30-секундное превью, если его ещё нет."""
    if PREVIEW.exists():
        return
    import requests

    response = requests.get(
        "https://itunes.apple.com/lookup",
        params={"id": PREVIEW_TRACK_ID, "country": "ru"},
        timeout=20,
        headers={"User-Agent": "Zamzam"},
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results or not results[0].get("previewUrl"):
        raise RuntimeError("Не удалось найти превью трека в Apple Music")
    preview = requests.get(
        results[0]["previewUrl"], timeout=30, headers={"User-Agent": "Zamzam"}
    )
    preview.raise_for_status()
    PREVIEW.write_bytes(preview.content)
    print(f"downloaded preview: {PREVIEW}")


def decode(path: Path) -> tuple[np.ndarray, int]:
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        rate = stream.codec_context.sample_rate or 44100
        chunks = []
        resampler = av.AudioResampler(format="s16", layout="mono", rate=44100)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    return np.concatenate(chunks).astype(np.int16), 44100


def wav(mono: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(mono.tobytes())
    return buf.getvalue()


async def main() -> None:
    ensure_preview()
    mono, rate = decode(PREVIEW)
    total = len(mono) / rate
    print(f"preview: {total:.1f}s, {len(mono)} samples")

    cases = [
        ("full", 0.0, total),
        ("10.5s start", 0.0, 10.5),
        ("10.5s mid", total / 2 - 5.25, 10.5),
        ("10.5s end", max(0.0, total - 10.5), 10.5),
        ("15s start", 0.0, 15.0),
        ("15s end", max(0.0, total - 15.0), 15.0),
        ("20s start", 0.0, 20.0),
        ("5.5s mid", total / 2 - 2.75, 5.5),
        ("8s mid", total / 2 - 4.0, 8.0),
    ]

    sh = Shazam(language="en-US", endpoint_country="US")
    try:
        for name, start, dur in cases:
            start_i = int(start * rate)
            end_i = min(len(mono), start_i + int(dur * rate))
            clip = mono[start_i:end_i]
            try:
                ans = await asyncio.wait_for(sh.recognize(wav(clip)), timeout=45)
                tr = ans.get("track") or {}
                matches = ans.get("matches")
                print(
                    f"{name:14s} len={len(clip)/rate:5.1f}s matches={bool(matches)} "
                    f"-> {tr.get('title')!r} | {tr.get('subtitle')!r}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"{name:14s} len={len(clip)/rate:5.1f}s ERROR {type(exc).__name__}: {exc}")
            await asyncio.sleep(1.2)
    finally:
        await sh.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

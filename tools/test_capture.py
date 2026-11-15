"""Сквозная проверка: воспроизводим превью и ловим его системным loopback."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import miniaudio
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shazamio import Shazam  # noqa: E402

from app.audio import Recorder  # noqa: E402
from app.recognition import parse_answer  # noqa: E402


def deezer_preview(query: str) -> tuple[str, str, bytes]:
    response = requests.get(
        "https://api.deezer.com/search",
        params={"q": query, "limit": 1},
        timeout=20,
        headers={"User-Agent": "Zamzam"},
    )
    item = response.json()["data"][0]
    preview = requests.get(item["preview"], timeout=30, headers={"User-Agent": "Zamzam"})
    return item.get("title", ""), item.get("artist", {}).get("name", ""), preview.content


async def main() -> None:
    title, artist, audio = deezer_preview("Daft Punk One More Time")
    print("playing:", artist, "-", title)

    decoded = miniaudio.decode(
        audio,
        output_format=miniaudio.SampleFormat.SIGNED16,
        nchannels=2,
        sample_rate=44100,
    )
    samples = np.frombuffer(decoded.samples, dtype=np.int16).reshape(-1, 2)

    recorder = Recorder("system")
    recorder.start()
    time.sleep(0.4)

    device = miniaudio.PlaybackDevice(
        output_format=miniaudio.SampleFormat.SIGNED16,
        nchannels=2,
        sample_rate=44100,
    )
    device.start(
        miniaudio.stream_memory(
            audio,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=2,
            sample_rate=44100,
        )
    )
    time.sleep(8.0)
    device.close()

    peak = recorder.peak
    error = recorder.error
    recorder.stop()
    print("capture peak:", round(peak, 3), "error:", error, "duration:", round(recorder.duration, 2))
    if error:
        return

    wav = recorder.wav_bytes(8.0)
    async with Shazam() as shazam:
        answer = await shazam.recognize(wav)
    track = parse_answer(answer)
    print("RESULT:", (track.artist + " - " + track.title) if track else "NO MATCH")


if __name__ == "__main__":
    asyncio.run(main())

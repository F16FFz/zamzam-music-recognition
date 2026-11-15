"""Проверка распознавания на 30-секундном превью из Deezer."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shazamio import Shazam  # noqa: E402

from app.recognition import parse_answer  # noqa: E402


def deezer_preview(query: str) -> tuple[str, str, bytes]:
    response = requests.get(
        "https://api.deezer.com/search",
        params={"q": query, "limit": 1},
        timeout=20,
        headers={"User-Agent": "Zamzam"},
    )
    response.raise_for_status()
    item = response.json()["data"][0]
    preview = requests.get(
        item["preview"], timeout=30, headers={"User-Agent": "Zamzam"}
    )
    preview.raise_for_status()
    return item.get("title", ""), item.get("artist", {}).get("name", ""), preview.content


async def main() -> None:
    title, artist, audio = deezer_preview("Daft Punk One More Time")
    print("preview:", artist, "-", title, len(audio), "bytes")
    async with Shazam() as shazam:
        answer = await shazam.recognize(audio)
    print("matches:", len(answer.get("matches") or []))
    track = parse_answer(answer)
    if track is None:
        print("NO MATCH")
        return
    print("RESULT:", track.artist, "-", track.title)
    print("album:", track.album, "| year:", track.year, "| genre:", track.genre)
    print("cover:", track.cover_url[:100])
    print("spotify:", track.spotify_url)
    print("youtube:", track.youtube_url)
    print("apple:", track.apple_url)
    print("shazam:", track.shazam_url)


if __name__ == "__main__":
    asyncio.run(main())

"""Захват звука: системный микс (loopback) или микрофон, с уровнем сигнала."""
from __future__ import annotations

import io
import logging
import math
import threading
import time
import wave

import numpy as np
import soundcard as sc

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
BLOCK_FRAMES = 2048  # ~46 мс при 44.1 кГц


class RecorderError(RuntimeError):
    pass


class Recorder:
    """Пишет звук в фоне и отдаёт последние секунды в виде WAV."""

    def __init__(self, mode: str = "system") -> None:
        self.mode = mode
        self.error: str | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._level = 0.0
        self._peak = 0.0
        self._samples = 0
        self.started_at = 0.0

    # ------------------------------------------------------------------ поток
    def _pick_device(self):
        if self.mode == "microphone":
            device = sc.default_microphone()
            if device is None:
                raise RecorderError("Микрофон не найден")
            return device

        speaker = sc.default_speaker()
        if speaker is None:
            raise RecorderError("Устройство воспроизведения не найдено")
        try:
            return sc.get_microphone(speaker.id, include_loopback=True)
        except Exception as exc:  # noqa: BLE001
            raise RecorderError(
                "Не удалось открыть системный звук. Переключитесь на микрофон."
            ) from exc

    def start(self) -> None:
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="ZamzamRecorder", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            device = self._pick_device()
            channels = 2 if self.mode == "system" else 1
            with device.recorder(
                samplerate=SAMPLE_RATE, channels=channels, blocksize=BLOCK_FRAMES
            ) as mic:
                while not self._stop.is_set():
                    data = mic.record(numframes=BLOCK_FRAMES)
                    if data is None or len(data) == 0:
                        continue
                    frames = np.asarray(data, dtype=np.float32)
                    mono = frames.mean(axis=1) if frames.ndim > 1 else frames
                    self._track_level(mono)
                    pcm = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)
                    with self._lock:
                        self._chunks.append(pcm)
                        self._samples += len(pcm)
        except Exception as exc:  # noqa: BLE001
            log.exception("Ошибка захвата звука")
            self.error = str(exc) or exc.__class__.__name__
            self._stop.set()

    def _track_level(self, mono: np.ndarray) -> None:
        rms = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)) + 1e-12)
        # Нормализуем громкость в удобную для интерфейса шкалу 0..1.
        db = 20.0 * math.log10(max(rms, 1e-6))
        level = min(1.0, max(0.0, (db + 55.0) / 45.0))
        self._level = self._level * 0.6 + level * 0.4
        if level > self._peak:
            self._peak = level

    # ------------------------------------------------------------------ данные
    @property
    def level(self) -> float:
        return self._level

    @property
    def peak(self) -> float:
        return self._peak

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at if self.started_at else 0.0

    @property
    def duration(self) -> float:
        with self._lock:
            return self._samples / SAMPLE_RATE

    def wav_bytes(self, seconds: float | None = None) -> bytes:
        with self._lock:
            chunks = list(self._chunks)
        if not chunks:
            audio = np.zeros(int(SAMPLE_RATE * 0.5), dtype=np.int16)
        else:
            audio = np.concatenate(chunks)
        if seconds is not None:
            keep = max(1, int(seconds * SAMPLE_RATE))
            audio = audio[-keep:]

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(audio.tobytes())
        return buffer.getvalue()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._thread = None

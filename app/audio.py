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


def capture_devices(mode: str) -> tuple[list[tuple[str, str]], str]:
    """Устройства для режима: [(id, имя)] и id устройства по умолчанию."""
    try:
        if mode == "microphone":
            default = sc.default_microphone()
            devices = sc.all_microphones(include_loopback=False)
        else:
            default = sc.default_speaker()
            devices = sc.all_speakers()
    except Exception:  # noqa: BLE001
        log.exception("Не удалось получить список устройств (%s)", mode)
        return [], ""

    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    for device in devices or []:
        try:
            device_id = str(device.id)
            name = str(device.name)
        except Exception:  # noqa: BLE001
            continue
        if not device_id or device_id in seen:
            continue
        seen.add(device_id)
        options.append((device_id, name))
    default_id = str(default.id) if default is not None else ""
    return options, default_id


def _resample(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    """Пересэмплирует PCM16, чтобы WAV всегда был 44.1 кГц."""
    if source_rate == target_rate or audio.size == 0:
        return audio
    duration = audio.size / float(source_rate)
    target_size = max(1, int(round(duration * target_rate)))
    old_x = np.linspace(0.0, duration, num=audio.size, endpoint=False)
    new_x = np.linspace(0.0, duration, num=target_size, endpoint=False)
    return np.interp(new_x, old_x, audio.astype(np.float32)).astype(np.int16)


class Recorder:
    """Пишет звук в фоне и отдаёт последние секунды в виде WAV."""

    def __init__(self, mode: str = "system", device_id: str = "") -> None:
        self.mode = mode
        self.device_id = device_id or ""
        self.error: str | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._level = 0.0
        self._peak = 0.0
        self._samples = 0
        self._rate = SAMPLE_RATE
        self.started_at = 0.0

    # ------------------------------------------------------------------ поток
    def _pick_microphone(self):
        device = None
        if self.device_id:
            try:
                device = sc.get_microphone(self.device_id)
            except Exception:  # noqa: BLE001
                log.warning("Микрофон %s не найден, беру по умолчанию", self.device_id)
        if device is None:
            device = sc.default_microphone()
        if device is None:
            raise RecorderError("Микрофон не найден")
        return device

    def _pick_device(self):
        speaker = None
        if self.device_id:
            try:
                speaker = sc.get_speaker(self.device_id)
            except Exception:  # noqa: BLE001
                log.warning(
                    "Устройство воспроизведения %s не найдено, беру по умолчанию",
                    self.device_id,
                )
        if speaker is None:
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
            if self.mode == "microphone":
                try:
                    self._capture_soundcard_microphone()
                except Exception as exc:  # noqa: BLE001
                    with self._lock:
                        started = self._samples > 0
                    if started or self._stop.is_set():
                        raise
                    # Некоторые драйверы отдают формат, который soundcard
                    # не умеет открывать. Пробуем резервный движок miniaudio.
                    log.info(
                        "soundcard не смог открыть микрофон (%s), пробую miniaudio",
                        exc.__class__.__name__,
                    )
                    self._capture_miniaudio_microphone()
            else:
                self._capture_system()
        except Exception as exc:  # noqa: BLE001
            log.exception("Ошибка захвата звука")
            self.error = str(exc) or exc.__class__.__name__
            self._stop.set()

    def _consume(self, data) -> None:
        if data is None or len(data) == 0:
            return
        frames = np.asarray(data, dtype=np.float32)
        mono = frames.mean(axis=1) if frames.ndim > 1 else frames
        self._track_level(mono)
        pcm = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)
        with self._lock:
            self._chunks.append(pcm)
            self._samples += len(pcm)

    def _capture_system(self) -> None:
        device = self._pick_device()
        self._rate = SAMPLE_RATE
        with device.recorder(
            samplerate=SAMPLE_RATE, channels=2, blocksize=BLOCK_FRAMES
        ) as mic:
            while not self._stop.is_set():
                self._consume(mic.record(numframes=BLOCK_FRAMES))

    def _capture_soundcard_microphone(self) -> None:
        device = self._pick_microphone()
        self._rate = SAMPLE_RATE
        with device.recorder(
            samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK_FRAMES
        ) as mic:
            while not self._stop.is_set():
                self._consume(mic.record(numframes=BLOCK_FRAMES))

    # -------------------------------------------------- резервный микрофон
    def _capture_miniaudio_microphone(self) -> None:
        import miniaudio

        captures = miniaudio.Devices().get_captures()
        if not captures:
            raise RecorderError("Микрофон не найден")

        wanted = ""
        try:
            wanted = str(self._pick_microphone().name)
        except Exception:  # noqa: BLE001
            pass

        info = next((item for item in captures if item["name"] == wanted), None)
        if info is None and wanted:
            log.warning(
                "Микрофон %r не найден в резервном движке, беру по умолчанию",
                wanted,
            )
        if info is None:
            info = captures[0]

        fmt, rate, channels = self._miniaudio_format(miniaudio, info)
        self._rate = rate
        convert = self._sample_converter(fmt)
        generator = self._miniaudio_generator(convert, channels)
        next(generator)

        device = miniaudio.CaptureDevice(
            input_format=fmt,
            nchannels=channels,
            sample_rate=rate,
            device_id=info["id"],
            app_name="Zamzam",
        )
        log.info(
            "Микрофон через miniaudio: %s (%s Гц, %s кан.)",
            info["name"],
            rate,
            channels,
        )
        device.start(generator)
        try:
            while not self._stop.is_set():
                time.sleep(0.05)
        finally:
            device.stop()
            device.close()

    @staticmethod
    def _miniaudio_format(miniaudio, info):
        mapping = {
            "32-bit IEEE Floating Point": miniaudio.SampleFormat.FLOAT32,
            "16-bit Signed Integer": miniaudio.SampleFormat.SIGNED16,
            "24-bit Signed Integer": miniaudio.SampleFormat.SIGNED24,
            "32-bit Signed Integer": miniaudio.SampleFormat.SIGNED32,
        }
        choices = []
        for entry in info.get("formats", []):
            fmt = mapping.get(entry.get("format"))
            rate = int(entry.get("samplerate") or 0)
            channels = int(entry.get("channels") or 0)
            if fmt is None or rate <= 0 or channels <= 0:
                continue
            score = (fmt is not miniaudio.SampleFormat.FLOAT32, rate != SAMPLE_RATE)
            choices.append((score, fmt, rate, channels))
        if not choices:
            return miniaudio.SampleFormat.FLOAT32, SAMPLE_RATE, 1
        _, fmt, rate, channels = min(choices, key=lambda item: item[0])
        return fmt, rate, min(channels, 2)

    @staticmethod
    def _sample_converter(fmt):
        import miniaudio

        if fmt is miniaudio.SampleFormat.FLOAT32:
            return lambda raw: np.frombuffer(raw, dtype=np.float32).astype(np.float32)
        if fmt is miniaudio.SampleFormat.SIGNED16:
            return lambda raw: np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if fmt is miniaudio.SampleFormat.SIGNED32:
            return (
                lambda raw: np.frombuffer(raw, dtype=np.int32).astype(np.float32)
                / 2147483648.0
            )

        def convert_24(raw) -> np.ndarray:
            data = np.frombuffer(raw, dtype=np.uint8)
            usable = data.size - data.size % 3
            triples = data[:usable].reshape(-1, 3).astype(np.int32)
            values = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
            values = np.where(values & 0x800000, values - 0x1000000, values)
            return values.astype(np.float32) / 8388608.0

        return convert_24

    def _miniaudio_generator(self, convert, channels):
        def stream():
            while True:
                raw = yield
                if not raw or self._stop.is_set():
                    continue
                frames = convert(raw)
                if channels > 1:
                    frames = frames.reshape(-1, channels).mean(axis=1)
                self._consume(frames)

        return stream()

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
            return self._samples / float(self._rate or SAMPLE_RATE)

    def wav_bytes(self, seconds: float | None = None) -> bytes:
        with self._lock:
            chunks = list(self._chunks)
            rate = self._rate or SAMPLE_RATE
        if not chunks:
            audio = np.zeros(int(SAMPLE_RATE * 0.5), dtype=np.int16)
        else:
            audio = np.concatenate(chunks)
        if seconds is not None:
            keep = max(1, int(seconds * rate))
            audio = audio[-keep:]
        audio = _resample(audio, rate, SAMPLE_RATE)

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

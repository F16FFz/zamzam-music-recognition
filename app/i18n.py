"""Перевод интерфейса Zamzam (русский / английский).

Ключ перевода — русская строка исходника. Это позволяет вызывать ``tr()``
прямо в местах, где текст показывается, и переводить интерфейс «на лету»:
достаточно поменять язык и заново применить тексты.
"""
from __future__ import annotations

import time

LANGUAGES = {"ru": "Русский", "en": "English"}

_language = "ru"

# Английские варианты. Если строки нет в словаре, показывается исходная.
_EN: dict[str, str] = {
    # ---------------------------------------------------------- вкладки, шапка
    "СЛУШАТЬ": "LISTEN",
    "ИСТОРИЯ": "HISTORY",
    "ИСТОЧНИК": "SOURCE",
    "СИСТЕМНЫЙ ЗВУК": "SYSTEM AUDIO",
    "МИКРОФОН": "MICROPHONE",
    "CTRL + ALT + S — БЫСТРЫЙ ЗАПУСК": "CTRL + ALT + S — QUICK START",
    "СЛУШАЙ · ОПОЗНАВАЙ · 18 СЕК": "LISTEN · IDENTIFY · 18 SEC",
    "SHAZAM ENGINE  ·  ЗАХВАТ ЗВУКА КОМПЬЮТЕРА  ·  18 СЕКУНД  ·  "
    "SPOTIFY  ·  YOUTUBE  ·  APPLE MUSIC  ·  ЯНДЕКС МУЗЫКА  ·  ": (
        "SHAZAM ENGINE  ·  COMPUTER AUDIO CAPTURE  ·  18 SECONDS  ·  "
        "SPOTIFY  ·  YOUTUBE  ·  APPLE MUSIC  ·  YANDEX MUSIC  ·  "
    ),
    # ---------------------------------------------------------- главный экран
    "ГОТОВ СЛУШАТЬ": "READY TO LISTEN",
    "ВКЛЮЧИ МУЗЫКУ И ЖМИ НА КРУГ": "PLAY SOME MUSIC AND HIT THE CIRCLE",
    "НАЗВАНИЕ СКОПИРОВАНО": "TITLE COPIED",
    "// НЕТ СИГНАЛА": "// NO SIGNAL",
    "ЗДЕСЬ ПОЯВИТСЯ ТРЕК": "THE TRACK WILL APPEAR HERE",
    "Название, исполнитель и ссылки на Spotify, YouTube, Apple Music и Яндекс Музыку": (
        "Title, artist and links to Spotify, YouTube, Apple Music and Yandex Music"
    ),
    "Захватывает всё, что играет на компьютере": (
        "Captures everything that plays on the computer"
    ),
    "Слушает звук вокруг через микрофон": (
        "Listens to the sound around you through the microphone"
    ),
    # ---------------------------------------------------------- состояния
    "СЛУШАЮ…": "LISTENING…",
    "ЗАХВАТ {n} СЕК — НЕ ВЫКЛЮЧАЙ МУЗЫКУ": "CAPTURING {n} SEC — KEEP THE MUSIC PLAYING",
    "СЛУШАЮ… ЕЩЁ {n} С": "LISTENING… {n} S LEFT",
    "ЗВУК ОЧЕНЬ ТИХИЙ — ПРОВЕРЬ ГРОМКОСТЬ": "SOUND IS VERY QUIET — CHECK THE VOLUME",
    "УТОЧНЯЮ ТРЕК… ЕЩЁ {n} С": "REFINING TRACK… {n} S LEFT",
    "ЗАВЕРШАЮ УТОЧНЕНИЕ…": "FINISHING REFINEMENT…",
    "ЗАВЕРШАЮ РАСПОЗНАВАНИЕ…": "FINISHING RECOGNITION…",
    "РАСПОЗНАЮ…": "RECOGNIZING…",
    "ОТПРАВЛЯЮ ЗАПИСАННЫЙ ФРАГМЕНТ В SHAZAM": (
        "SENDING THE RECORDED CLIP TO SHAZAM"
    ),
    "ДОЖИДАЮСЬ ОТВЕТА SHAZAM": "WAITING FOR SHAZAM",
    "НЕТ ДОСТУПА К ЗВУКУ": "NO AUDIO ACCESS",
    "НАЙДЕНО!": "FOUND!",
    "ОТКРЫВАЙ НА УДОБНОЙ ПЛОЩАДКЕ": "OPEN IT ON YOUR FAVORITE PLATFORM",
    "ПОХОЖЕ, ЭТО…": "THIS LOOKS LIKE…",
    "СЛУШАЮ ДАЛЬШЕ — УТОЧНЯЮ ТРЕК": "STILL LISTENING — REFINING THE TRACK",
    "УТОЧНИЛ ТРЕК": "TRACK REFINED",
    "СЛУШАЮ ДАЛЬШЕ…": "STILL LISTENING…",
    "ОСТАНОВЛЕНО": "STOPPED",
    "ЖМИ НА КРУГ, ЧТОБЫ ПОПРОБОВАТЬ СНОВА": "PRESS THE CIRCLE TO TRY AGAIN",
    "НЕ УДАЛОСЬ РАСПОЗНАТЬ": "COULD NOT RECOGNIZE",
    "ЗВУК СЛИШКОМ ТИХИЙ — ПРОВЕРЬ ГРОМКОСТЬ ИЛИ ВКЛЮЧИ МИКРОФОН": (
        "SOUND IS TOO QUIET — CHECK THE VOLUME OR SWITCH TO MICROPHONE"
    ),
    "ПОПРОБУЙ ЕЩЁ РАЗ — ЛУЧШЕ ВСЕГО ЗВУЧИТ ПРИПЕВ": (
        "TRY AGAIN — THE CHORUS WORKS BEST"
    ),
    "СВЯЗЬ С SHAZAM ПРЕРВАЛАСЬ — ПРОБУЮ ЕЩЁ…": (
        "SHAZAM CONNECTION LOST — RETRYING…"
    ),
    "СЛУШАЮ ЗВУК КОМПЬЮТЕРА": "LISTENING TO COMPUTER AUDIO",
    "СЛУШАЮ МИКРОФОН": "LISTENING TO MICROPHONE",
    # ---------------------------------------------------------- карточка трека
    "Неизвестный исполнитель": "Unknown artist",
    "Из истории": "From history",
    "СКОПИРОВАТЬ НАЗВАНИЕ": "COPY TITLE",
    "Spotify": "Spotify",
    "YouTube": "YouTube",
    "Apple": "Apple",
    "Яндекс": "Yandex",
    # ---------------------------------------------------------- история
    "ПОКА ПУСТО": "NOTHING HERE YET",
    "Распознанные треки будут сохраняться здесь": (
        "Recognized tracks will be saved here"
    ),
    "Очистить историю": "Clear history",
    "Удалить все распознанные треки из истории?": (
        "Delete all recognized tracks from history?"
    ),
    "ИСТОРИЯ ОЧИЩЕНА": "HISTORY CLEARED",
    "ИСТОРИЯ УЖЕ ПУСТА": "HISTORY IS ALREADY EMPTY",
    # ---------------------------------------------------------- подсказки
    "ОСТАНОВИТЬ": "STOP",
    "СЛУШАТЬ · CTRL + ALT + S": "LISTEN · CTRL + ALT + S",
    "Переключить на английский": "Switch to English",
    "Переключить на русский": "Switch to Russian",
    # ---------------------------------------------------------- трей
    "Открыть Zamzam": "Open Zamzam",
    "Слушать": "Listen",
    "Остановить": "Stop",
    "История": "History",
    "Язык": "Language",
    "Выход": "Quit",
    "Zamzam свёрнут в трей": "Zamzam was minimized to the tray",
    "Приложение продолжает работать в фоне. Нажмите Ctrl + Alt + S, "
    "чтобы начать прослушивание.": (
        "The app keeps running in the background. Press Ctrl + Alt + S "
        "to start listening."
    ),
    "Трек распознан": "Track recognized",
    "Трек не распознан": "No match found",
    "Слушаю…": "Listening…",
    "Слушаю системный звук": "Listening to system audio",
    "Слушаю микрофон": "Listening to microphone",
    "Свернуть в трей": "Minimize to tray",
    "Закрыть в трей": "Close to tray",
    # ---------------------------------------------------------- ошибки
    "Микрофон не найден": "Microphone not found",
    "Устройство воспроизведения не найдено": "Playback device not found",
    "Не удалось открыть системный звук. Переключитесь на микрофон.": (
        "Could not open system audio. Switch to the microphone."
    ),
    "Не удалось разобрать ответ сервиса": "Could not parse the service response",
    "Shazam временно ограничил запросы. Подождите минуту.": (
        "Shazam temporarily rate-limited requests. Wait a minute."
    ),
    "Сервер не ответил вовремя. Проверьте интернет.": (
        "The server did not respond in time. Check your internet connection."
    ),
    "Нет подключения к интернету.": "No internet connection.",
    "Не удалось обработать аудио. Попробуйте ещё раз.": (
        "Could not process the audio. Try again."
    ),
    "Ошибка распознавания: {text}": "Recognition error: {text}",
}

_MONTHS_RU = (
    "янв", "фев", "мар", "апр", "мая", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
)
_MONTHS_EN = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def get_language() -> str:
    return _language


def set_language(code: str) -> None:
    global _language
    if code in LANGUAGES:
        _language = code


def tr(text: str) -> str:
    """Переводит строку на текущий язык (неизвестные строки не меняет)."""
    if _language == "en":
        return _EN.get(text, text)
    return text


def track_count(count: int) -> str:
    """Подпись количества треков: «03 ТРЕКА» / «3 TRACKS»."""
    if _language == "en":
        word = "TRACK" if count == 1 else "TRACKS"
    elif count % 10 == 1 and count % 100 != 11:
        word = "ТРЕК"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        word = "ТРЕКА"
    else:
        word = "ТРЕКОВ"
    return f"{count:02d} {word}"


def history_time(timestamp: float) -> str:
    """Время для строки истории: 14:32 / вчера / 12 ноя (или Nov 12)."""
    moment = time.localtime(timestamp)
    today = time.localtime()
    if (moment.tm_year, moment.tm_yday) == (today.tm_year, today.tm_yday):
        return time.strftime("%H:%M", moment)
    if (moment.tm_year, moment.tm_yday) == (today.tm_year, today.tm_yday - 1):
        return "yesterday" if _language == "en" else "вчера"
    months = _MONTHS_EN if _language == "en" else _MONTHS_RU
    if _language == "en":
        return f"{months[moment.tm_mon - 1]} {moment.tm_mday}"
    return f"{moment.tm_mday} {months[moment.tm_mon - 1]}"

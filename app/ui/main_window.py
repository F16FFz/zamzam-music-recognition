"""Главное окно Zamzam."""
from __future__ import annotations

import logging
import math
import time

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QActionGroup, QColor, QCursor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from ..audio import Recorder, capture_devices
from ..config import APP_NAME, Settings
from ..models import HistoryStore, Track
from ..recognition import RecognitionService
from . import icons
from .images import ImageLoader
from .tray import TrayIcon
from .widgets import (
    HistoryRow,
    LiveWaveform,
    PulseButton,
    RootFrame,
    TickerStrip,
    TitleBar,
    Toast,
    TrackCard,
)

log = logging.getLogger(__name__)


_TICKER_TEXT = (
    "SHAZAM ENGINE  ·  ЗАХВАТ ЗВУКА КОМПЬЮТЕРА  ·  18 СЕКУНД  ·  "
    "SPOTIFY  ·  YOUTUBE  ·  APPLE MUSIC  ·  ЯНДЕКС МУЗЫКА  ·  "
)


class MainWindow(QWidget):
    # Shazam уверенно узнаёт трек на фрагменте ~15 секунд: на 10 секундах
    # некоторые песни (например, с длинным вступлением или сэмплом) не находятся.
    # Отправляем всё накопленное аудио: первая попытка — ~15,5 с, вторая — 18 с.
    LISTEN_SECONDS = 18.0
    WINDOW_SECONDS = 18.0
    FINALIZE_MS = 21000
    HARD_TIMEOUT_MS = 29000

    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        i18n.set_language(self.settings.language)

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(488, 800)

        self.history = HistoryStore(self.settings.max_history)
        self.images = ImageLoader(self)
        self.recognition = RecognitionService(self)

        self.tray: TrayIcon | None = None
        self._device_mode: str | None = None
        self._device_options: list[tuple[str, str]] = []
        self._device_default = ""
        self._device_ready = False
        self._quitting = False
        self._shutdown_done = False
        self._tray_hint_shown = self.settings.tray_hint_shown
        self._status: tuple[str, str, dict[str, object]] = (
            "ГОТОВ СЛУШАТЬ",
            "ВКЛЮЧИ МУЗЫКУ И ЖМИ НА КРУГ",
            {},
        )

        self._recorder: Recorder | None = None
        self._listening = False
        self._in_flight = False
        self._inflight_session = -1
        self._attempts = 0
        self._max_attempts = 4
        self._retry_pending = False
        self._finalize_requested = False
        self._quiet_flag = False
        self._preliminary: Track | None = None
        self._current_track: Track | None = None
        self._session = 0

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(60)
        self._poll_timer.timeout.connect(self._tick_levels)

        # Страховка: если окно спрятано, а значка в трее почему-то нет,
        # возвращаем окно, чтобы приложение не осталось невидимым.
        self._tray_watch = QTimer(self)
        self._tray_watch.setInterval(5000)
        self._tray_watch.timeout.connect(self._check_tray_health)
        self._tray_watch.start()

        self._build_ui()
        self._connect_service()
        self._sync_mode_chips()
        self.retranslate()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(0)

        self.root = RootFrame()
        self.root.setObjectName("root")
        outer.addWidget(self.root)

        root_layout = QVBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.minimize_requested.connect(self.hide_to_tray)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.language_requested.connect(self.toggle_language)
        self.title_bar.context_requested.connect(self._show_window_menu)
        root_layout.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(22, 2, 22, 16)
        body_layout.setSpacing(12)
        root_layout.addWidget(body, 1)

        self.segment = QFrame()
        self.segment.setObjectName("segmentBar")
        self.segment.setFixedHeight(40)
        segment_layout = QHBoxLayout(self.segment)
        segment_layout.setContentsMargins(4, 4, 4, 4)
        segment_layout.setSpacing(4)

        self.btn_tab_listen = QPushButton("СЛУШАТЬ")
        self.btn_tab_listen.setObjectName("segment")
        self.btn_tab_listen.setCheckable(True)
        self.btn_tab_listen.setCursor(Qt.PointingHandCursor)
        self.btn_tab_history = QPushButton("ИСТОРИЯ")
        self.btn_tab_history.setObjectName("segment")
        self.btn_tab_history.setCheckable(True)
        self.btn_tab_history.setCursor(Qt.PointingHandCursor)

        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.btn_tab_listen)
        group.addButton(self.btn_tab_history)
        self.btn_tab_listen.setChecked(True)
        self.btn_tab_listen.clicked.connect(lambda: self.set_page(0))
        self.btn_tab_history.clicked.connect(lambda: self.set_page(1))
        segment_layout.addWidget(self.btn_tab_listen)
        segment_layout.addWidget(self.btn_tab_history)
        body_layout.addWidget(self.segment)

        self.ticker = TickerStrip(_TICKER_TEXT)
        body_layout.addWidget(self.ticker)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_listen_page())
        self.pages.addWidget(self._build_history_page())
        body_layout.addWidget(self.pages, 1)

        self.toast = Toast(self.root)

    def _build_listen_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addSpacing(4)
        pulse_row = QHBoxLayout()
        pulse_row.addStretch(1)
        self.pulse = PulseButton()
        self.pulse.clicked.connect(self.toggle_listen)
        pulse_row.addWidget(self.pulse)
        pulse_row.addStretch(1)
        layout.addLayout(pulse_row)

        layout.addSpacing(2)
        self.status_title = QLabel("ГОТОВ СЛУШАТЬ")
        self.status_title.setObjectName("statusTitle")
        self.status_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_title)

        self.status_hint = QLabel("ВКЛЮЧИ МУЗЫКУ И ЖМИ НА КРУГ")
        self.status_hint.setObjectName("statusHint")
        self.status_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_hint)

        layout.addSpacing(14)
        self.waveform = LiveWaveform()
        layout.addWidget(self.waveform)
        layout.addSpacing(16)

        self.result_stack = QStackedWidget()
        self.result_stack.setFixedHeight(190)
        self.placeholder = self._build_placeholder()
        self.card = TrackCard()
        self.card.copied.connect(
            lambda: self.toast.show_message(i18n.tr("НАЗВАНИЕ СКОПИРОВАНО"))
        )
        self.result_stack.addWidget(self.placeholder)
        self.result_stack.addWidget(self.card)
        self.result_stack.setCurrentWidget(self.placeholder)
        layout.addWidget(self.result_stack)

        layout.addStretch(1)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        mode_row.addStretch(1)
        source_label = QLabel("ИСТОЧНИК")
        source_label.setObjectName("footerHint")
        self.source_label = source_label
        mode_row.addWidget(source_label)
        mode_row.addSpacing(2)

        self.chip_system = QPushButton("СИСТЕМНЫЙ ЗВУК")
        self.chip_mic = QPushButton("МИКРОФОН")
        mode_group = QButtonGroup(self)
        mode_group.setExclusive(True)
        for chip, mode in ((self.chip_system, "system"), (self.chip_mic, "microphone")):
            chip.setObjectName("modeChip")
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)
            mode_group.addButton(chip)
            chip.clicked.connect(lambda _=False, m=mode: self._set_mode(m))
            mode_row.addWidget(chip)
        self.chip_system.setToolTip("Захватывает всё, что играет на компьютере")
        self.chip_mic.setToolTip("Слушает звук вокруг через микрофон")
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        layout.addSpacing(4)
        self.device_button = QPushButton()
        self.device_button.setObjectName("deviceChip")
        self.device_button.setCursor(Qt.PointingHandCursor)
        self.device_button.setFixedHeight(26)
        self.device_button.clicked.connect(self._show_device_menu)
        self.device_button.installEventFilter(self)
        layout.addWidget(self.device_button)

        layout.addSpacing(4)
        hint = QLabel("CTRL + ALT + S — БЫСТРЫЙ ЗАПУСК")
        hint.setObjectName("footerHint")
        hint.setAlignment(Qt.AlignCenter)
        self.hotkey_hint = hint
        layout.addWidget(hint)
        return page

    def _build_placeholder(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("placeholder")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(5)
        layout.addStretch(1)

        self.placeholder_dot = QLabel("// НЕТ СИГНАЛА")
        self.placeholder_dot.setObjectName("placeholderTag")
        self.placeholder_dot.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.placeholder_dot)
        layout.addSpacing(2)

        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        icon.setPixmap(icons.make_icon(icons.note("#C8F751"), 28).pixmap(QSize(28, 28)))
        layout.addWidget(icon)

        title = QLabel("ЗДЕСЬ ПОЯВИТСЯ ТРЕК")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignCenter)
        self.placeholder_title = title
        layout.addWidget(title)

        hint = QLabel(
            "Название, исполнитель и ссылки на Spotify, YouTube, Apple Music и Яндекс Музыку"
        )
        hint.setObjectName("emptyHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        self.placeholder_hint = hint
        layout.addWidget(hint)
        layout.addStretch(1)
        return frame

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 0, 0)
        title = QLabel("ИСТОРИЯ")
        title.setObjectName("historyHeader")
        self.history_title = title
        header.addWidget(title)
        self.history_count = QLabel("00 ТРЕКОВ")
        self.history_count.setObjectName("historyCount")
        header.addWidget(self.history_count)
        header.addStretch(1)
        self.btn_clear_history = QPushButton()
        self.btn_clear_history.setObjectName("iconBtn")
        self.btn_clear_history.setIcon(icons.make_icon(icons.trash("#F2F3E3"), 15))
        self.btn_clear_history.setIconSize(QSize(15, 15))
        self.btn_clear_history.setFixedSize(30, 30)
        self.btn_clear_history.setCursor(Qt.PointingHandCursor)
        self.btn_clear_history.setToolTip("Очистить историю")
        self.btn_clear_history.clicked.connect(self._clear_history)
        header.addWidget(self.btn_clear_history)
        layout.addLayout(header)

        self.history_content = QWidget()
        self.history_layout = QVBoxLayout(self.history_content)
        self.history_layout.setContentsMargins(0, 0, 4, 0)
        self.history_layout.setSpacing(8)
        self.history_layout.setAlignment(Qt.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.history_content)
        layout.addWidget(scroll, 1)
        return page

    # --------------------------------------------------------------- события
    def _connect_service(self) -> None:
        self.recognition.matched.connect(self._on_matched)
        self.recognition.no_match.connect(self._on_no_match)
        self.recognition.failed.connect(self._on_failed)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "device_button", None) and event.type() == QEvent.Resize:
            self._refresh_device_label()
        return super().eventFilter(obj, event)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Мягкая тень вокруг скруглённого окна."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(Qt.NoBrush)
        for index in range(14, 0, -1):
            alpha = int(8 * (1.0 - (index - 1) / 14.0) ** 1.5)
            painter.setPen(QPen(QColor(0, 0, 0, alpha), 1.0))
            radius = 26.0 + index * 1.4
            painter.drawRoundedRect(
                self.rect().adjusted(index, index, -index, -index), radius, radius
            )
        painter.end()

    def set_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.btn_tab_listen.setChecked(index == 0)
        self.btn_tab_history.setChecked(index == 1)

    # ---------------------------------------------------------- локализация
    def retranslate(self) -> None:
        """Заново применяет тексты на текущем языке без перезапуска."""
        self.setWindowTitle(APP_NAME)
        self.btn_tab_listen.setText(i18n.tr("СЛУШАТЬ"))
        self.btn_tab_history.setText(i18n.tr("ИСТОРИЯ"))
        self.ticker.set_text(i18n.tr(_TICKER_TEXT))
        self.source_label.setText(i18n.tr("ИСТОЧНИК"))
        self.chip_system.setText(i18n.tr("СИСТЕМНЫЙ ЗВУК"))
        self.chip_mic.setText(i18n.tr("МИКРОФОН"))
        self.chip_system.setToolTip(
            i18n.tr("Захватывает всё, что играет на компьютере")
        )
        self.chip_mic.setToolTip(i18n.tr("Слушает звук вокруг через микрофон"))
        self.hotkey_hint.setText(i18n.tr("CTRL + ALT + S — БЫСТРЫЙ ЗАПУСК"))
        self.placeholder_dot.setText(i18n.tr("// НЕТ СИГНАЛА"))
        self.placeholder_title.setText(i18n.tr("ЗДЕСЬ ПОЯВИТСЯ ТРЕК"))
        self.placeholder_hint.setText(
            i18n.tr(
                "Название, исполнитель и ссылки на Spotify, YouTube, "
                "Apple Music и Яндекс Музыку"
            )
        )
        self.history_title.setText(i18n.tr("ИСТОРИЯ"))
        self.btn_clear_history.setToolTip(i18n.tr("Очистить историю"))
        self._refresh_device_label()
        self.title_bar.retranslate()
        self.pulse.retranslate()
        self.card.retranslate()
        self._apply_status()
        self._refresh_history()
        if self.tray is not None:
            self.tray.retranslate()

    def _set_status(self, title: str, hint: str = "", **kwargs: object) -> None:
        self._status = (title, hint, kwargs)
        self._apply_status()

    def _apply_status(self) -> None:
        title, hint, kwargs = self._status
        self.status_title.setText(i18n.tr(title))
        self.status_hint.setText(i18n.tr(hint).format(**kwargs) if hint else "")

    def toggle_language(self) -> None:
        self.set_language("en" if i18n.get_language() == "ru" else "ru")

    def set_language(self, code: str) -> None:
        if code not in i18n.LANGUAGES:
            return
        i18n.set_language(code)
        self.settings.language = code
        self.settings.save()
        self.retranslate()
        self.toast.show_message("ENGLISH" if code == "en" else "РУССКИЙ")

    # ------------------------------------------------------------------- трей
    def attach_tray(self, tray: TrayIcon) -> None:
        self.tray = tray
        tray.open_requested.connect(self.show_window)
        tray.listen_requested.connect(self.toggle_listen)
        tray.history_requested.connect(self.show_history)
        tray.language_requested.connect(self.set_language)
        tray.quit_requested.connect(self.quit_app)
        tray.set_listening(self._listening)
        tray.retranslate()

    def detach_tray(self) -> None:
        self.tray = None

    def _tray_ready(self) -> bool:
        """Трей есть и действительно может показать значок."""
        return (
            self.tray is not None
            and self.tray.isVisible()
            and QSystemTrayIcon.isSystemTrayAvailable()
        )

    def _check_tray_health(self) -> None:
        """Не даёт приложению остаться невидимым без значка в трее."""
        if self._quitting or not self.isHidden():
            return
        if not self._tray_ready():
            log.warning("Окно скрыто, а трея нет — возвращаю окно")
            self.show_window()

    def show_window(self) -> None:
        log.info("Показываю окно")
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def show_history(self) -> None:
        self.show_window()
        self.set_page(1)

    def hide_to_tray(self) -> None:
        if not self._tray_ready():
            # Трей недоступен — обычное свёрнутое окно, чтобы не потеряться.
            log.warning("Трей недоступен — сворачиваю в панель задач")
            self.showMinimized()
            return
        log.info("Прячу окно в трей")
        self.hide()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.settings.tray_hint_shown = True
            try:
                self.settings.save()
            except Exception:  # noqa: BLE001
                pass
            assert self.tray is not None
            self.tray.notify(
                i18n.tr("Zamzam свёрнут в трей"),
                i18n.tr(
                    "Приложение продолжает работать в фоне. Значок — в области "
                    "уведомлений рядом с часами. Нажмите Ctrl + Alt + S, чтобы "
                    "начать прослушивание."
                ),
            )

    def _show_window_menu(self) -> None:
        """Правый клик по шапке: свернуть в трей или выйти."""
        menu = QMenu(self)
        hide_action = menu.addAction(i18n.tr("Свернуть в трей"))
        hide_action.triggered.connect(self.hide_to_tray)
        menu.addSeparator()
        quit_action = menu.addAction(i18n.tr("Выход"))
        quit_action.triggered.connect(self.quit_app)
        menu.exec(QCursor.pos())

    def _notify(self, title: str, message: str) -> None:
        if self.tray is None or self.isVisible():
            return
        self.tray.notify(i18n.tr(title), message)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if (
            event.type() == QEvent.WindowStateChange
            and self.isMinimized()
            and self._tray_ready()
            and not self._quitting
        ):
            self.hide_to_tray()

    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        log.info("Завершаю работу")
        self._stop_capture()
        if self.tray is not None:
            self.tray.hide()
        try:
            self.recognition.shutdown()
        except Exception:  # noqa: BLE001
            pass

    def quit_app(self) -> None:
        log.info("Выход по команде пользователя")
        self._quitting = True
        self.shutdown()
        QApplication.quit()

    # ------------------------------------------------------------ слушание
    def toggle_listen(self) -> None:
        if not self._listening:
            self._start_listening()
            return

        # Остановили вручную. Если запрос уже в полёте — дождёмся ответа,
        # чтобы не выбросить готовый результат.
        if self._in_flight:
            self._finalize_requested = True
            self._set_status("РАСПОЗНАЮ…", "ДОЖИДАЮСЬ ОТВЕТА SHAZAM")
            return

        recorder = self._recorder
        if (
            self._preliminary is None
            and recorder is not None
            and recorder.duration >= 4.0
        ):
            # Остановили раньше таймера — всё равно попробуем распознать
            # уже записанный фрагмент.
            self._finalize_requested = True
            self._set_status(
                "РАСПОЗНАЮ…", "ОТПРАВЛЯЮ ЗАПИСАННЫЙ ФРАГМЕНТ В SHAZAM"
            )
            self._attempt(self._session)
            if self._in_flight:
                return

        self._finalize(manual=True)

    def _start_listening(self) -> None:
        self._stop_capture()
        self._session += 1
        session = self._session
        self._attempts = 0
        self._in_flight = False
        self._inflight_session = -1
        self._retry_pending = False
        self._finalize_requested = False
        self._quiet_flag = False
        self._preliminary = None

        recorder = Recorder(
            self.settings.input_mode, self.settings.device_for(self.settings.input_mode)
        )
        recorder.start()
        self._recorder = recorder
        self._listening = True
        self._poll_timer.start()

        self.pulse.set_listening(True)
        self.pulse.set_progress(0.0)
        self.waveform.set_active(True)
        self._set_status(
            "СЛУШАЮ…",
            "ЗАХВАТ {n} СЕК — НЕ ВЫКЛЮЧАЙ МУЗЫКУ",
            n=int(self.LISTEN_SECONDS),
        )
        if self.tray is not None:
            self.tray.set_listening(True)
        self._notify(
            "Слушаю…",
            i18n.tr(
                "Слушаю системный звук"
                if self.settings.input_mode == "system"
                else "Слушаю микрофон"
            ),
        )

        QTimer.singleShot(700, lambda: self._check_audio(session))
        QTimer.singleShot(3200, lambda: self._quiet_hint(session))
        QTimer.singleShot(15500, lambda: self._attempt(session))
        QTimer.singleShot(18500, lambda: self._attempt(session))
        QTimer.singleShot(self.FINALIZE_MS, lambda: self._on_timeout(session))
        QTimer.singleShot(self.HARD_TIMEOUT_MS, lambda: self._hard_timeout(session))

    def _stop_capture(self) -> None:
        self._listening = False
        self._poll_timer.stop()
        recorder, self._recorder = self._recorder, None
        if recorder is not None:
            recorder.stop()
        if hasattr(self, "pulse"):
            self.pulse.set_listening(False)
            self.pulse.set_level(0.0)
            self.pulse.set_progress(0.0)
            self.waveform.set_active(False)
        if self.tray is not None:
            self.tray.set_listening(False)

    def _check_audio(self, session: int) -> None:
        if session != self._session or not self._listening:
            return
        recorder = self._recorder
        if recorder is not None and recorder.error:
            self._stop_capture()
            self._set_status("НЕТ ДОСТУПА К ЗВУКУ", recorder.error)

    def _quiet_hint(self, session: int) -> None:
        if session != self._session or not self._listening:
            return
        recorder = self._recorder
        self._quiet_flag = recorder is not None and recorder.peak < 0.04

    def _attempt(self, session: int) -> None:
        if session != self._session or not self._listening:
            return
        recorder = self._recorder
        if recorder is None:
            return
        if self._in_flight:
            self._retry_pending = True
            return
        if self._attempts >= self._max_attempts:
            return
        if recorder.duration < 2.5:
            self._retry_pending = True
            return

        wav = recorder.wav_bytes(seconds=min(self.WINDOW_SECONDS, recorder.duration))
        if not self.recognition.recognize(wav):
            # Сервис ещё занят прошлым запросом — повторим чуть позже.
            self._retry_pending = True
            if recorder.elapsed < self.LISTEN_SECONDS + 2.0:
                QTimer.singleShot(400, lambda: self._attempt(session))
            return

        self._attempts += 1
        self._inflight_session = session
        self._in_flight = True

    def _schedule_retry(self) -> None:
        if not self._listening or not self._retry_pending:
            return
        recorder = self._recorder
        if recorder is None or recorder.elapsed > self.LISTEN_SECONDS + 2.0:
            return
        self._retry_pending = False
        QTimer.singleShot(250, lambda: self._attempt(self._session))

    def _on_timeout(self, session: int) -> None:
        if session != self._session or not self._listening:
            return
        if self._in_flight:
            # Дадим последнему запросу доиграть и завершим сразу после ответа.
            self._finalize_requested = True
            return
        self._finalize()

    def _hard_timeout(self, session: int) -> None:
        if session != self._session or not self._listening:
            return
        self._finalize()

    def _finalize(self, manual: bool = False) -> None:
        if not self._listening:
            return
        track = self._preliminary
        recorder = self._recorder
        peak = recorder.peak if recorder is not None else 0.0

        self._stop_capture()
        self._finalize_requested = False
        self._retry_pending = False

        if track is not None:
            self._current_track = track
            self._display_track(
                track, "НАЙДЕНО!", "ОТКРЫВАЙ НА УДОБНОЙ ПЛОЩАДКЕ"
            )
            self.history.add(track)
            self._refresh_history()
            QApplication.alert(self)
            self._notify("Трек распознан", f"{track.artist} — {track.title}")
            return

        if manual:
            self._set_status(
                "ОСТАНОВЛЕНО", "ЖМИ НА КРУГ, ЧТОБЫ ПОПРОБОВАТЬ СНОВА"
            )
            return

        if peak < 0.05:
            self._set_status(
                "НЕ УДАЛОСЬ РАСПОЗНАТЬ",
                "ЗВУК СЛИШКОМ ТИХИЙ — ПРОВЕРЬ ГРОМКОСТЬ ИЛИ ВКЛЮЧИ МИКРОФОН",
            )
        else:
            self._set_status(
                "НЕ УДАЛОСЬ РАСПОЗНАТЬ",
                "ПОПРОБУЙ ЕЩЁ РАЗ — ЛУЧШЕ ВСЕГО ЗВУЧИТ ПРИПЕВ",
            )
        self._notify(
            "Трек не распознан",
            i18n.tr("ПОПРОБУЙ ЕЩЁ РАЗ — ЛУЧШЕ ВСЕГО ЗВУЧИТ ПРИПЕВ"),
        )

    # --------------------------------------------------------- ответы сервиса
    @staticmethod
    def _same_track(first: Track, second: Track) -> bool:
        if first.shazam_url and second.shazam_url:
            return first.shazam_url == second.shazam_url
        return (
            first.title.casefold() == second.title.casefold()
            and first.artist.casefold() == second.artist.casefold()
        )

    def _on_matched(self, track: Track) -> None:
        self._in_flight = False
        if self._inflight_session != self._session or not self._listening:
            self._schedule_retry()
            return

        previous = self._preliminary
        if previous is None:
            self._preliminary = track
            self._display_track(
                track, "ПОХОЖЕ, ЭТО…", "СЛУШАЮ ДАЛЬШЕ — УТОЧНЯЮ ТРЕК"
            )
            QApplication.alert(self)
        elif self._same_track(previous, track):
            self._preliminary = track
        else:
            # Более позднее окно дало другой трек — доверяем ему.
            self._preliminary = track
            self._display_track(track, "УТОЧНИЛ ТРЕК", "СЛУШАЮ ДАЛЬШЕ…")
            self.toast.show_message(i18n.tr("УТОЧНИЛ ТРЕК"))
            QApplication.alert(self)

        if self._finalize_requested:
            self._finalize()
            return
        self._schedule_retry()

    def _on_no_match(self) -> None:
        self._in_flight = False
        if self._finalize_requested and self._inflight_session == self._session:
            self._finalize()
            return
        self._schedule_retry()

    def _on_failed(self, message: str) -> None:
        self._in_flight = False
        if self._inflight_session != self._session or not self._listening:
            self._schedule_retry()
            return
        if self._finalize_requested:
            self._finalize()
            return
        # Одна неудачная попытка — не повод сдаваться: ждём остальные окна.
        self._set_status(
            self._status[0], "СВЯЗЬ С SHAZAM ПРЕРВАЛАСЬ — ПРОБУЮ ЕЩЁ…"
        )
        self._schedule_retry()

    # ------------------------------------------------------------- отображение
    def _display_track(self, track: Track, title: str, hint: str) -> None:
        self.card.set_track(track)
        self.result_stack.setCurrentWidget(self.card)
        self.card.fade_in()
        self._set_status(title, hint)
        self._attach_cover(self.card.cover, track.cover_url)

    def _attach_cover(self, widget, url: str) -> None:
        if not url:
            return

        def apply(pixmap: QPixmap) -> None:
            try:
                widget.set_pixmap(pixmap)
            except RuntimeError:
                pass

        self.images.load(url, apply)

    def _tick_levels(self) -> None:
        recorder = self._recorder
        if recorder is None:
            return
        level = recorder.level
        self.pulse.set_level(level)
        self.waveform.set_level(level)

        elapsed = max(0.0, min(self.LISTEN_SECONDS, recorder.elapsed))
        self.pulse.set_progress(elapsed / self.LISTEN_SECONDS)
        remaining = max(0, int(math.ceil(self.LISTEN_SECONDS - elapsed)))
        if remaining <= 0 or self._finalize_requested:
            if self._preliminary is not None:
                self._set_status(
                    self._status[0], "ЗАВЕРШАЮ УТОЧНЕНИЕ…"
                )
            else:
                self._set_status(
                    self._status[0], "ЗАВЕРШАЮ РАСПОЗНАВАНИЕ…"
                )
        elif self._preliminary is not None:
            self._set_status(
                self._status[0], "УТОЧНЯЮ ТРЕК… ЕЩЁ {n} С", n=remaining
            )
        elif self._quiet_flag and elapsed < 9.0:
            self._set_status(
                self._status[0], "ЗВУК ОЧЕНЬ ТИХИЙ — ПРОВЕРЬ ГРОМКОСТЬ"
            )
        else:
            self._set_status(self._status[0], "СЛУШАЮ… ЕЩЁ {n} С", n=remaining)

    # -------------------------------------------------------------- история
    def _refresh_history(self) -> None:
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        items = self.history.items
        count = len(items)
        self.history_count.setText(i18n.track_count(count))

        if not items:
            self.history_layout.addWidget(self._history_empty())
            self.history_layout.addStretch(1)
            return

        for index, track in enumerate(items[:40], start=1):
            row = HistoryRow(track, index)
            row.clicked.connect(self._on_history_click)
            self.history_layout.addWidget(row)
            self._attach_cover(row.cover, track.cover_url)
        self.history_layout.addStretch(1)

    def _history_empty(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 60, 0, 0)
        layout.setSpacing(6)
        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        icon.setPixmap(icons.make_icon(icons.history("#C8F751"), 32).pixmap(QSize(32, 32)))
        layout.addWidget(icon)
        title = QLabel(i18n.tr("ПОКА ПУСТО"))
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignCenter)
        hint = QLabel(i18n.tr("Распознанные треки будут сохраняться здесь"))
        hint.setObjectName("emptyHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)
        return widget

    def _on_history_click(self, track: Track) -> None:
        self.set_page(0)
        self._current_track = track
        self._display_track(
            track, track.title, track.artist or i18n.tr("Из истории")
        )

    def _clear_history(self) -> None:
        if not self.history.items:
            self.toast.show_message(i18n.tr("ИСТОРИЯ УЖЕ ПУСТА"))
            return
        answer = QMessageBox.question(
            self,
            i18n.tr("Очистить историю"),
            i18n.tr("Удалить все распознанные треки из истории?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.history.clear()
            self._refresh_history()
            self.toast.show_message(i18n.tr("ИСТОРИЯ ОЧИЩЕНА"))

    # ----------------------------------------------------------------- режим
    def _sync_mode_chips(self) -> None:
        self.chip_system.setChecked(self.settings.input_mode == "system")
        self.chip_mic.setChecked(self.settings.input_mode == "microphone")

    def _set_mode(self, mode: str) -> None:
        if mode == self.settings.input_mode:
            self._sync_mode_chips()
            return
        self.settings.input_mode = mode
        self.settings.save()
        self._sync_mode_chips()
        self._device_ready = False
        self._refresh_device_label()
        if self._listening:
            self._start_listening()
        self.toast.show_message(
            i18n.tr(
                "СЛУШАЮ ЗВУК КОМПЬЮТЕРА"
                if mode == "system"
                else "СЛУШАЮ МИКРОФОН"
            )
        )

    # ------------------------------------------------------------- устройства
    def _refresh_devices(self, force: bool = False) -> None:
        """Обновляет список устройств для текущего режима (с кэшем)."""
        mode = self.settings.input_mode
        if not force and self._device_ready and self._device_mode == mode:
            return
        options, default_id = capture_devices(mode)
        self._device_options = options
        self._device_default = default_id
        self._device_mode = mode
        self._device_ready = True

    def _current_device_id(self) -> str:
        return self.settings.device_for(self.settings.input_mode)

    def _device_name(self, device_id: str) -> str:
        for option_id, name in self._device_options:
            if option_id == device_id:
                return name
        return ""

    def _refresh_device_label(self) -> None:
        if not hasattr(self, "device_button"):
            return
        self._refresh_devices()
        device_id = self._current_device_id()
        name = self._device_name(device_id) or self._device_name(self._device_default)
        if not name:
            name = i18n.tr("Устройство по умолчанию")
        prefix = f"{i18n.tr('УСТРОЙСТВО')} · "
        suffix = "  ▾"
        width = max(120, (self.device_button.width() or 392) - 24)
        metrics = self.device_button.fontMetrics()
        available = width - metrics.horizontalAdvance(prefix) - metrics.horizontalAdvance(suffix)
        name_text = metrics.elidedText(name, Qt.ElideRight, max(48, available))
        self.device_button.setText(prefix + name_text + suffix)
        self.device_button.setToolTip(f"{i18n.tr('УСТРОЙСТВО')}: {name}")

    def _show_device_menu(self) -> None:
        self._refresh_devices(force=True)
        menu = QMenu(self)
        default_action = menu.addAction(i18n.tr("Устройство по умолчанию"))
        default_action.setCheckable(True)
        default_action.setChecked(not self._current_device_id())
        default_action.triggered.connect(lambda: self._select_device(""))

        if self._device_options:
            menu.addSeparator()
            group = QActionGroup(menu)
            group.setExclusive(True)
            current = self._current_device_id()
            for device_id, name in self._device_options:
                action = menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(device_id == current)
                action.triggered.connect(
                    lambda _=False, chosen=device_id: self._select_device(chosen)
                )
                group.addAction(action)
        else:
            menu.addSeparator()
            empty = menu.addAction(i18n.tr("Устройства не найдены"))
            empty.setEnabled(False)

        position = self.device_button.mapToGlobal(
            QPoint(0, -menu.sizeHint().height() - 6)
        )
        menu.exec(position)

    def _select_device(self, device_id: str) -> None:
        mode = self.settings.input_mode
        if self.settings.device_for(mode) == device_id:
            return
        self.settings.set_device_for(mode, device_id)
        self.settings.save()
        log.info("Выбрано устройство %s (%s)", device_id or "default", mode)
        self._device_ready = False
        self._refresh_device_label()
        if self._listening:
            self._start_listening()
        self.toast.show_message(i18n.tr("УСТРОЙСТВО ВЫБРАНО"))

    # ---------------------------------------------------------------- закрытие
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_device_label()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._tray_ready() and not self._quitting:
            # Крестик прячет окно в трей, приложение продолжает работать.
            event.ignore()
            self.hide_to_tray()
            return
        self._quitting = True
        self.shutdown()
        super().closeEvent(event)
        QApplication.quit()

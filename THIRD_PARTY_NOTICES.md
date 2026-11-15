# Сторонние компоненты

Zamzam использует следующие библиотеки. Полные тексты лицензий находятся в
пакетах и в их репозиториях.

| Компонент | Версия | Лицензия | Ссылка |
|---|---|---|---|
| PySide6 / Qt for Python | 6.12.0 | LGPL-3.0-only (или GPL) | https://www.qt.io/qt-for-python |
| soundcard | 0.4.6 | BSD-3-Clause | https://github.com/bastibe/SoundCard |
| NumPy | 2.5.4 | BSD-3-Clause | https://numpy.org |
| shazamio | 0.9.0 | MIT | https://github.com/dotX12/shazamio |
| shazamio-core | 2.0.0 | MIT | https://github.com/dotX12/shazamio-core |
| aiohttp | 3.14.5 | Apache-2.0 | https://github.com/aio-libs/aiohttp |
| Pillow | 13.0.0 | MIT-CMU | https://python-pillow.org |
| PyInstaller | 6.22.3 | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org |

## Qt / PySide6 (LGPL-3.0)

Собранный `Zamzam.exe` содержит библиотеки Qt, распространяемые по LGPL-3.0.
Исходный код приложения открыт, поэтому у пользователя есть возможность заменить
библиотеки Qt и пересобрать приложение (см. `build.ps1`). Текст LGPL-3.0:
https://www.gnu.org/licenses/lgpl-3.0.html

## Shazam

Zamzam не связан с Apple, Shazam Entertainment Limited или их аффилированными
лицами. «Shazam» является товарным знаком соответствующего правообладателя.
Распознавание выполняется через неофициальный клиент `shazamio`; использование
сервиса регулируется условиями Shazam.

# Сборка Zamzam.exe
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Создаю виртуальное окружение..."
    python -m venv .venv
}

Write-Host "Обновляю зависимости..."
& $python -m pip install --upgrade pip --quiet
& $python -m pip install -r requirements.txt --quiet

Write-Host "Готовлю иконки..."
& $python tools\make_icon.py

Write-Host "Собираю exe (это может занять несколько минут)..."
& $python -m PyInstaller --noconfirm --clean Zamzam.spec

Write-Host ""
Write-Host "Готово: $root\dist\Zamzam.exe"

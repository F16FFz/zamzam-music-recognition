# Установка Zamzam: копирует exe и создаёт ярлыки
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root "dist\Zamzam.exe"

if (-not (Test-Path $source)) {
    Write-Error "Не найден dist\Zamzam.exe. Сначала запусти build.ps1"
    exit 1
}

$targetDir = Join-Path $env:LOCALAPPDATA "Zamzam"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
$target = Join-Path $targetDir "Zamzam.exe"
Copy-Item $source $target -Force

$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"

foreach ($folder in @($desktop, $startMenu)) {
    $oldShortcut = Join-Path $folder "EchoTag.lnk"
    if (Test-Path $oldShortcut) {
        Remove-Item $oldShortcut -Force
    }
    $shortcutPath = Join-Path $folder "Zamzam.lnk"
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $target
    $shortcut.WorkingDirectory = $targetDir
    $shortcut.IconLocation = $target
    $shortcut.Description = "Zamzam - распознавание музыки"
    $shortcut.Save()
}

# Убираем старый exe, данные и историю не трогаем.
$oldExe = Join-Path $env:LOCALAPPDATA "EchoTag\EchoTag.exe"
if (Test-Path $oldExe) {
    Remove-Item $oldExe -Force
}

Write-Host "Установлено: $target"
Write-Host "Ярлыки Zamzam лежат на рабочем столе и в меню «Пуск»."

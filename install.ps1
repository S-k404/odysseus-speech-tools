<#
.SYNOPSIS
    Set up Odysseus Speech Tools on Windows 11.
.DESCRIPTION
    Checks Python 3.10+, installs CLI document dependencies (pymupdf,
    beautifulsoup4, ebooklib, requests) into .venv, ensures the Docker network
    odysseus_default exists, and starts Speaches (Kokoro + Whisper) if Docker is running.
#>
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$py = (Get-Command py -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $py) {
    $py = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
}
if (-not $py) {
    throw "Python 3.10+ not found. Install Python from https://www.python.org or `winget install Python.Python.3.12`."
}

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    if ($py -like "*py.exe") {
        & $py -3 -m venv .venv
    } else {
        & $py -m venv .venv
    }
}

& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install pymupdf beautifulsoup4 ebooklib requests --quiet

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $netExists = docker network ls --format "{{.Name}}" | Where-Object { $_ -eq "odysseus_default" }
    if (-not $netExists) {
        docker network create odysseus_default | Out-Null
    }
    Write-Host "Starting Speaches container..." -ForegroundColor Cyan
    docker compose -f docker-compose.yml.superseded-by-odysseus up -d
} else {
    Write-Host "Docker not found. Install Docker Desktop on Windows 11 to run the Speaches container." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done! Example usage:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\python.exe .\narrator.py .\test_docs\sample.md -o narration.mp3 --play"

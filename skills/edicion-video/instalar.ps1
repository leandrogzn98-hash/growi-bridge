# Instala lo que necesita la skill edicion-video en este PC (Windows 11). Sin administrador; no toca el Python global.
#   powershell -ExecutionPolicy Bypass -File skills\edicion-video\instalar.ps1
# 1. venv propio en %LOCALAPPDATA%\growi-video\venv con faster-whisper (Whisper local, CPU int8).
# 2. Copia la plantilla Remotion a %LOCALAPPDATA%\growi-video\remotion y hace npm install ahi (los node_modules no
#    caben en la carpeta de la skill: limite de 6 niveles). El primer render descarga Chrome Headless Shell.
# 3. Comprueba ffmpeg/ffprobe y node. El modelo de Whisper (small, ~460 MB) se baja solo en la primera transcripción.
$ErrorActionPreference = 'Stop'
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$datos = Join-Path $env:LOCALAPPDATA 'growi-video'
$venv = Join-Path $datos 'venv'
foreach ($b in 'ffmpeg', 'ffprobe', 'node', 'npm', 'python') {
    if (-not (Get-Command $b -ErrorAction SilentlyContinue)) { throw "Falta $b en el PATH (ffmpeg: winget install Gyan.FFmpeg; node: winget install OpenJS.NodeJS.LTS)" }
}
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) { python -m venv $venv }
& (Join-Path $venv 'Scripts\python.exe') -m pip install -q faster-whisper numpy
$rem = Join-Path $datos 'remotion'
New-Item -ItemType Directory -Force (Join-Path $rem 'src') | Out-Null
Copy-Item (Join-Path $aqui 'remotion\package.json') $rem -Force
Copy-Item (Join-Path $aqui 'remotion\src\*') (Join-Path $rem 'src') -Force
Push-Location $rem
try { npm install --no-audit --no-fund } finally { Pop-Location }
& (Join-Path $venv 'Scripts\python.exe') -c "import faster_whisper, numpy; print('faster-whisper', faster_whisper.__version__)"
Write-Host "Listo. Prueba: python $aqui\scripts\editar.py --crudo <crudo.mp4> --salida <carpeta>"

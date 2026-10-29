# Instala el supervisor local de Growi Bridge en Windows: entorno de Python propio (.venv junto a este script) y una
# tarea del Programador de tareas que lo corre cada N minutos (N = subgerente.intervalo_minutos del YAML).
# Corre oculto (pythonw.exe): no abre ventanas ni roba el foco. No necesita administrador.
#
#   powershell -ExecutionPolicy Bypass -File instalar-supervisor.ps1
#   powershell -ExecutionPolicy Bypass -File instalar-supervisor.ps1 -Config otra.yaml
#   powershell -ExecutionPolicy Bypass -File instalar-supervisor.ps1 -Desinstalar
param(
    [string]$Config = "",
    [switch]$Desinstalar
)
$ErrorActionPreference = "Stop"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Config) { $Config = Join-Path $Aqui "supervisor-config.yaml" }
$Config = (Resolve-Path $Config).Path
$Venv = Join-Path $Aqui ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$PyW = Join-Path $Venv "Scripts\pythonw.exe"
$Script = Join-Path $Aqui "supervisor.py"

if (-not (Test-Path $Py)) {
    $base = $null
    foreach ($c in @("py -3", "python")) {
        try {
            $v = & ([scriptblock]::Create("$c -c `"import sys; print(sys.version_info >= (3, 10))`"")) 2>$null
            if ($v -eq "True") { $base = $c; break }
        } catch {}
    }
    if (-not $base) { throw "Hace falta Python 3.10 o superior (https://www.python.org/downloads/windows/)." }
    Write-Host "Creando el entorno de Python en ${Venv} ..."
    & ([scriptblock]::Create("$base -m venv `"$Venv`""))
}
Write-Host "Instalando dependencias (keyring, pyyaml, requests) ..."
& $Py -m pip install -q -r (Join-Path $Aqui "requirements.txt")

$prog = (& $Py $Script --config $Config --programacion).Trim().Split(" ")
if ($LASTEXITCODE -ne 0) { throw "El YAML no es válido: corre «${Py} ${Script} --configurar»." }
$Minutos = [int]$prog[0]
$Nombre = $prog[1]

if ($Desinstalar) {
    if (Get-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false
        Write-Host "Tarea «${Nombre}» quitada. El entorno .venv y el log (~\.growi-supervisor) se quedan."
    } else { Write-Host "No había tarea «${Nombre}»." }
    exit 0
}

$accion = New-ScheduledTaskAction -Execute $PyW -Argument "`"$Script`" --config `"$Config`"" -WorkingDirectory $Aqui
$disparo = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutos)
$ajustes = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$quien = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparo -Settings $ajustes -Principal $quien `
    -Description "Supervisor local de Growi Bridge (subgerente): lee, juzga e informa. No corrige nada." -Force | Out-Null
Write-Host "Tarea «${Nombre}» programada cada ${Minutos} min (primera vez en 1 min). Comprueba todo con:"
Write-Host "  `"$Py`" `"$Script`" --config `"$Config`" --verificar"

$ErrorActionPreference = 'Stop'
# Vigila los dos carriles de Growi Bridge (ver share\outbox\ESTADO-DOS-CARRILES.md):
# carril A en 8787 y carril B en 8788. Relanza solo el que falte, cada uno con
# su propio tope anti-bucle (3 reinicios en 15 min) y su propio watchdog-state.
$wd  = 'C:\Users\forte\growi-bridge\watchdog'
$log = Join-Path $wd 'watchdog.log'
$lanes = @(
    @{ Name = 'A'; Port = 8787; Dir = 'C:\Users\forte\growi-bridge'
       State = 'C:\Users\forte\growi-bridge\watchdog\watchdog-state.json'
       Match = { param($c) $c -like '*growi-bridge.py*' -and $c -notlike '*growi-bridge-lane2*' } },
    @{ Name = 'B'; Port = 8788; Dir = 'C:\Users\forte\growi-bridge-lane2'
       State = 'C:\Users\forte\growi-bridge-lane2\watchdog\watchdog-state.json'
       Match = { param($c) $c -like '*growi-bridge-lane2*growi-bridge.py*' } }
)

function Log($msg) { Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg) }

function Test-Bridge($port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $c.BeginConnect('127.0.0.1', $port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(3000) -and $c.Connected) { $c.EndConnect($iar); return $true }
        return $false
    } catch { return $false } finally { $c.Close() }
}

$down = @()
foreach ($l in $lanes) {
    if (-not (Test-Path (Join-Path $l.Dir 'growi-bridge.py'))) { continue }
    if (Test-Bridge $l.Port) { Log ("ok carril {0} ({1})" -f $l.Name, $l.Port) } else { $down += $l }
}
if ($down.Count -eq 0) { exit 0 }

Start-Sleep -Seconds 60
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine })
$rc = 0
foreach ($l in $down) {
    $tag = "carril {0} ({1})" -f $l.Name, $l.Port
    if (Test-Bridge $l.Port) { Log "ok $tag (tras reintento)"; continue }
    # Gateway unificado: gateway.lock dice el pid del proceso unico. Si sigue
    # vivo no se relanza otra copia (la app corre elevada y, sin elevar, su
    # CommandLine sale vacia: antes eso relanzaba una segunda instancia).
    $lk = Join-Path $l.Dir 'gateway.lock'
    if (Test-Path $lk) {
        $lpid = 0
        try { $lpid = [int]((Get-Content $lk -Raw | ConvertFrom-Json).pid) } catch { $lpid = 0 }
        $lp = if ($lpid -gt 0) { Get-Process -Id $lpid -ErrorAction SilentlyContinue } else { $null }
        if ($lp -and $lp.ProcessName -like 'python*') { Log "$tag puerto sin respuesta pero el proceso unico sigue vivo (pid $lpid, gateway.lock); no se relanza"; continue }
    }
    $running = @($procs | Where-Object { & $l.Match $_.CommandLine })
    if ($running.Count -gt 0) { Log "$tag puerto sin respuesta pero el proceso python existe; no se relanza"; continue }

    $cut = (Get-Date).AddMinutes(-15)
    $list = @()
    if (Test-Path $l.State) {
        try { $list = @((Get-Content $l.State -Raw | ConvertFrom-Json).reinicios) } catch { $list = @() }
    }
    $recent = @($list | Where-Object { $_ -and ([datetime]$_) -gt $cut })
    if ($recent.Count -ge 3) { Log "$tag tope alcanzado, revision manual"; $rc = 1; continue }

    $recent += (Get-Date).ToString('o')
    @{ reinicios = $recent } | ConvertTo-Json -Compress | Set-Content -Path $l.State -Encoding UTF8
    Start-Process -FilePath (Join-Path $l.Dir 'iniciar-growi-bridge.bat') -WorkingDirectory $l.Dir -WindowStyle Hidden
    Log "$tag reinicio"
}
exit $rc

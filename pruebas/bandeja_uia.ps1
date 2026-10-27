# Lista (o pulsa) los botones de la bandeja de Windows 11 con UI Automation.
#   bandeja_uia.ps1 listar            botones de la barra de tareas (nombre, id, rect)
#   bandeja_uia.ps1 abrir_ocultos     pulsa el boton «^» (iconos ocultos) y lista lo que muestra
param([string]$accion = "listar")
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$ae = [System.Windows.Automation.AutomationElement]
$tw = $ae::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children,
    (New-Object System.Windows.Automation.PropertyCondition($ae::ClassNameProperty, "Shell_TrayWnd")))
$btn = New-Object System.Windows.Automation.PropertyCondition($ae::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
function Listar($raiz) {
    foreach ($b in $raiz.FindAll([System.Windows.Automation.TreeScope]::Descendants, $btn)) {
        $r = $b.Current.BoundingRectangle
        "{0} | id={1} | {2},{3},{4},{5}" -f $b.Current.Name, $b.Current.AutomationId, $r.X, $r.Y, $r.Width, $r.Height
    }
}
if ($accion -eq "listar") { Listar $tw; return }
if ($accion -eq "abrir_ocultos") {
    $chev = $tw.FindAll([System.Windows.Automation.TreeScope]::Descendants, $btn) |
        Where-Object { $_.Current.AutomationId -eq "SystemTrayIcon" -or $_.Current.Name -match "ocultos|hidden" } |
        Select-Object -First 1
    if (-not $chev) { "no encontre el boton de iconos ocultos"; return }
    $chev.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Start-Sleep -Milliseconds 800
    $over = $ae::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children,
        (New-Object System.Windows.Automation.PropertyCondition($ae::ClassNameProperty, "TopLevelWindowForOverflowXamlIsland")))
    if ($over) { "desborde abierto:"; Listar $over } else { "no se abrio el desborde" }
}
if ($accion -eq "json_ocultos") {
    # Abre el desborde (si hace falta) y devuelve sus iconos en JSON.
    $over = $ae::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children,
        (New-Object System.Windows.Automation.PropertyCondition($ae::ClassNameProperty, "TopLevelWindowForOverflowXamlIsland")))
    $items = if ($over) { $over.FindAll([System.Windows.Automation.TreeScope]::Descendants, $btn) } else { @() }
    if (-not $items -or $items.Count -eq 0) {
        $chev = $tw.FindAll([System.Windows.Automation.TreeScope]::Descendants, $btn) |
            Where-Object { $_.Current.Name -match "ocultos|hidden" } | Select-Object -First 1
        if ($chev) { $chev.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() }
        Start-Sleep -Milliseconds 900
        $over = $ae::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children,
            (New-Object System.Windows.Automation.PropertyCondition($ae::ClassNameProperty, "TopLevelWindowForOverflowXamlIsland")))
        $items = if ($over) { $over.FindAll([System.Windows.Automation.TreeScope]::Descendants, $btn) } else { @() }
    }
    $out = foreach ($b in $items) { $r = $b.Current.BoundingRectangle
        @{ name = $b.Current.Name; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height } }
    ConvertTo-Json -InputObject @($out) -Compress
}

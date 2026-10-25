@echo off
REM Instala Growi Bridge v2.0 (puente + runner + proxy + pantalla + mascota).
REM Reemplaza el servidor viejo (pc-server.py), el runner y la v1.0 de la app.
REM Para quitarlo: schtasks /delete /tn GrowiBridgeApp /f
set PUENTE=C:\Users\forte\growi-bridge
set ORIGEN=%~dp0growi-bridge-app
echo.
echo [1/5] Instalando dependencias (pystray, pillow)...
python -m pip install --quiet pystray pillow
if errorlevel 1 (
  echo.
  echo No se pudieron instalar las dependencias. Revisa tu conexion e intentalo de nuevo.
  pause
  exit /b 1
)
echo [2/5] Copiando archivos a %PUENTE%...
copy /y "%ORIGEN%\growi-bridge.py" "%PUENTE%\" >nul
copy /y "%ORIGEN%\growi.png" "%PUENTE%\" >nul
copy /y "%ORIGEN%\iniciar-growi-bridge.bat" "%PUENTE%\" >nul
copy /y "%ORIGEN%\probar-growi-bridge.bat" "%PUENTE%\" >nul
xcopy /y /e /i "%ORIGEN%\mascot" "%PUENTE%\mascot" >nul
echo [3/5] Cerrando el servidor viejo, el runner y la app v1.0 (si estan corriendo)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'pc-server\.py|runner\.py|growi-bridge\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo [4/5] Quitando las tareas viejas (GrowiBridge, GrowiRunner)...
schtasks /delete /tn GrowiBridge /f >nul 2>&1
schtasks /delete /tn GrowiRunner /f >nul 2>&1
echo [5/5] Creando arranque automatico con privilegios maximos (GrowiBridgeApp) y arrancando ahora...
schtasks /create /tn "GrowiBridgeApp" /tr "%PUENTE%\iniciar-growi-bridge.bat" /sc onlogon /rl highest /f
schtasks /run /tn "GrowiBridgeApp"
echo.
echo Listo. Busca mi foto en la bandeja del sistema (abajo a la derecha).
echo La primera vez, abre la ventana y configura el proxy (host, puerto, usuario, clave).
pause

@echo off
REM Instala Growi Bridge v2.0 (puente + runner + proxy + pantalla + mascota).
REM Reemplaza el servidor viejo (pc-server.py), el runner y la v1.0 de la app.
REM Para quitarlo: schtasks /delete /tn GrowiBridgeApp /f

REM --- Pedir administrador si hace falta (la tarea con /rl highest lo exige) ---
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Pidiendo permisos de administrador...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set PUENTE=C:\Users\forte\growi-bridge
REM --- Encontrar la carpeta de origen: el .bat puede estar dentro de
REM     growi-bridge-app\ o junto a ella (en el Inbox). Antes fallaba si
REM     se corría desde dentro de la carpeta. ---
if exist "%~dp0growi-bridge.py" (
  set ORIGEN=%~dp0
) else if exist "%~dp0growi-bridge-app\growi-bridge.py" (
  set ORIGEN=%~dp0growi-bridge-app\
) else (
  echo.
  echo No encuentro growi-bridge.py junto a este instalador.
  echo Copia la carpeta growi-bridge-app completa y vuelve a intentarlo.
  pause
  exit /b 1
)
echo Origen: %ORIGEN%
echo Destino: %PUENTE%
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
if not exist "%PUENTE%" mkdir "%PUENTE%"
copy /y "%ORIGEN%growi-bridge.py" "%PUENTE%\"
copy /y "%ORIGEN%growi.png" "%PUENTE%\"
copy /y "%ORIGEN%iniciar-growi-bridge.bat" "%PUENTE%\"
copy /y "%ORIGEN%probar-growi-bridge.bat" "%PUENTE%\"
if exist "%ORIGEN%mascot" (
  xcopy /y /e /i "%ORIGEN%mascot" "%PUENTE%\mascot"
) else (
  echo AVISO: no se encontro la carpeta mascot en %ORIGEN%
  echo La app funciona igual, solo que la mascota no tendra animacion de saludo.
)
if not exist "%PUENTE%\growi-bridge.py" (
  echo.
  echo ERROR: no se pudo copiar growi-bridge.py. Revisa la ruta de origen.
  pause
  exit /b 1
)
echo [3/5] Cerrando el servidor viejo, el runner y la app v1.0 (si estan corriendo)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'pc-server\.py|runner\.py|growi-bridge\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo [4/5] Quitando las tareas viejas (GrowiBridge, GrowiRunner)...
schtasks /delete /tn GrowiBridge /f >nul 2>&1
schtasks /delete /tn GrowiRunner /f >nul 2>&1
echo [5/5] Creando arranque automatico con privilegios maximos (GrowiBridgeApp) y arrancando ahora...
schtasks /create /tn "GrowiBridgeApp" /tr "%PUENTE%\iniciar-growi-bridge.bat" /sc onlogon /rl highest /f
if errorlevel 1 (
  echo.
  echo ERROR: no se pudo crear la tarea programada. Prueba de nuevo como administrador.
  pause
  exit /b 1
)
schtasks /run /tn "GrowiBridgeApp"
echo.
echo Listo. Busca mi foto en la bandeja del sistema (abajo a la derecha).
echo La primera vez, abre la ventana y configura el proxy (host, puerto, usuario, clave).
pause

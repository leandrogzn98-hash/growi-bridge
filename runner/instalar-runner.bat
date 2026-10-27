@echo off
REM Instala el Growi Runner para que arranque solo al iniciar sesion.
REM Se ejecuta una sola vez. Para quitarlo: schtasks /delete /tn GrowiRunner /f
cd /d "%~dp0"
schtasks /create /tn "GrowiRunner" /tr "\"%~dp0iniciar-runner-oculto.bat\"" /sc onlogon /rl limited /f
if errorlevel 1 (
  echo.
  echo No se pudo crear la tarea programada. Usa iniciar-runner.bat manual.
  pause
  exit /b 1
)
schtasks /run /tn "GrowiRunner"
echo.
echo Runner instalado y arrancado. Revisa runner.log si algo falla.
pause

@echo off
REM Prueba Growi Bridge en ventana visible (se ve lo que hace; Ctrl+C para parar).
REM Corre desde la carpeta donde esta este .bat (sirve en cualquier PC).
cd /d "%~dp0"
python growi-bridge.py
pause

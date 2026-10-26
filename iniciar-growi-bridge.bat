@echo off
REM Arranca Growi Bridge oculto (solo bandeja). Lo usa la tarea programada.
REM Corre desde la carpeta donde esta este .bat (sirve en cualquier PC).
cd /d "%~dp0"
start /b pythonw growi-bridge.py

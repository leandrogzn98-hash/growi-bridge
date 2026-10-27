@echo off
REM Arranca el Growi Runner oculto (lo usa la tarea programada).
cd /d "%~dp0"
start /b pythonw runner.py

@echo off
REM Inicia el Growi Runner en una ventana visible (Ctrl+C para parar).
cd /d "%~dp0"
echo ===============================================
echo  Growi Runner — ventana visible
echo  Cierra con Ctrl+C. Log en runner.log
echo ===============================================
python runner.py
pause

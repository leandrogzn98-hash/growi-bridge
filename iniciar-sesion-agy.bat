@echo off
rem Growi Bridge - iniciar sesion en agy (Gemini por Antigravity CLI) y probar el motor gemini.
rem Doble clic desde el Explorador (SIN "Ejecutar como administrador"). Gasto: $0 (free tier).
title Growi Bridge - sesion de agy (Gemini)
echo.
echo  1) Se abre agy. Elige iniciar sesion con Google y entra con jobsforleandro@gmail.com
echo     en el navegador. Cuando agy quede listo, escribe /quit y Enter.
echo  2) Luego esta ventana corre sola la prueba real del motor gemini.
echo.
pause
"C:\Users\forte\AppData\Local\agy\bin\agy.exe"
echo.
echo  Probando el motor gemini de verdad (agy --version, agy -p ... --output-format json, tarea real)...
python "C:\Users\forte\growi-bridge\_prueba-gemini\scripts\probar_gemini_real.py"
echo.
echo  Resultado en C:\Users\forte\growi-bridge\share\outbox\capturas-gemini\real\
pause

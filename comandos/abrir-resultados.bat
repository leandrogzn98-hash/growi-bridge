@echo off
:: @growi.titulo Abrir la carpeta de resultados
:: @growi.descripcion Abre share\outbox de Growi Bridge (lo que dejan las tareas) en el Explorador
:: @growi.modo silencioso
:: @growi.icono carpeta
:: @growi.paquete Growi
:: @growi.autor Plantilla de Growi Bridge (copiala y cambiala)
set "DESTINO=%~dp0..\share\outbox"
if not "%GROWI_BRIDGE_SHARE%"=="" set "DESTINO=%GROWI_BRIDGE_SHARE%\outbox"
if not exist "%DESTINO%" mkdir "%DESTINO%"
start "" explorer "%DESTINO%"

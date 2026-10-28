# Estado: comandos de script (t-comandos-script)

Rama `Claude`, 28 oct 2026. **LISTO.**

Tus scripts `.py`, `.bat`/`.cmd` y `.ps1` de la carpeta `comandos\` (junto a
`growi-bridge.py`) salen en la paleta Ctrl+K según su cabecera `@growi.*`,
como los Script Commands de Raycast. No hay aislamiento: un script es código
tuyo, y la app lo dice.

## Cabecera
En `.py`/`.ps1`, `# @growi.clave valor`; en `.bat`, `:: @growi.clave valor`
(o `REM`). Se leen las primeras 40 líneas.

| Clave | |
|---|---|
| `titulo` | **obligatoria** |
| `modo` | **obligatoria**: `silencioso` (aviso ✓/✗) · `ventana` (salida en una ventana) · `lista` |
| `descripcion`, `icono`, `paquete`, `autor`, `atajo` | opcionales (el autor se muestra; sin él: «sin autor en la cabecera») |
| `argumento1..3` | texto que se pregunta antes de ejecutar |
| `pide` | `borrar, red, gastar` (además, la app lo **detecta** en el código: `del /`, `Remove-Item`, `os.remove`, `rmtree`, `Invoke-WebRequest`, `curl`, `urllib`, `requests.`…) |

**Formato fijo del modo lista** (stdout, JSON):
`{"items": [{"titulo": "texto", "subtitulo": "opcional", "accion": {"tipo": "abrir" | "copiar", "valor": "ruta, URL o texto"}}]}`.
Si la salida no cumple el formato, se abre una ventana que lo dice.

## Código (`growi-bridge.py`, bloque «comandos de script» antes de `build_gui`)
- `comandos_descubrir()`: al arrancar (en un hilo) y con «Actualizar».
- `comandos_paleta_sync()`: se llama al abrir la paleta. La paleta vacía tiene
  una sección **«Mis comandos»**.
- `comando_ejecutar()` y, según el modo, `_cmd_mostrar` → `_cmd_ventana` /
  `_cmd_lista`.
- `_cmd_permiso()`: el aviso de lo delicado.
- `_cmd_aviso_ps()`: el aviso de ExecutionPolicy.
- `comandos_ui()` («Mis comandos»): Actualizar, Abrir la carpeta, y por
  script su autor, de dónde sale, lo que pide y **Activar/Desactivar**. Se
  abre desde Ajustes → Notificaciones y atajos → Mis comandos y desde la
  paleta («Mis comandos (scripts)»).
- Ajustes nuevos en `settings.json`: `comandos_off` (desactivados) y
  `comandos_permisos` (decisión por comando + hash del script: **si el script
  cambia, se vuelve a preguntar**).
- **Sin descarga desde internet:** la app no descarga ni instala nada. Un
  script con la marca de Windows «descargado de internet»
  (`archivo:Zone.Identifier`, ZoneId ≥ 3) **no se ejecuta** y no sale en la
  paleta. «Mis comandos» lo marca y dice cómo quitar la marca tras revisarlo
  (`Unblock-File`).
- **.ps1:** se ejecuta normal. Si PowerShell lo bloquea (se detecta en la
  salida: «la ejecución de scripts está deshabilitada…»), se muestra la
  salida con cómo desbloquearlo (`Unblock-File` en esa carpeta, o
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`) y un botón
  **«Ejecutar con -ExecutionPolicy Bypass -File»**, explícito y solo para ese
  archivo.

## Las 2 plantillas (en el repo, `comandos\`)
- `abrir-resultados.bat` (silencioso): abre `share\outbox`.
- `archivos-recientes.py` (lista): los 15 archivos más nuevos de Descargas y
  de outbox; Intro abre el elegido. Solo lee fechas: no borra ni usa la red.

## Verificación (app real en 8797, copia aislada; evidencia en `pruebas/evidencia/comandos/`)
`pruebas/prueba_comandos.py`

| | Prueba | Resultado |
|---|---|---|
| a | `.bat` y `.py` en la paleta | Sección «Mis comandos»: las 2 plantillas + Prueba silenciosa (.bat), Prueba ventana (.py), Prueba lista, Prueba delicada, Prueba PowerShell. «sin-cabecera.bat» no sale (le falta `@growi.titulo`/`modo`). El script descargado no sale |
| b | Cada modo | silencioso: salida 0, marca creada, aviso «✓ Prueba silenciosa». ventana: «hola desde la ventana» en la ventana «Prueba ventana» (captura 1). lista: «uno», «dos»; elegir «dos» → portapapeles **«valor-dos»** |
| c | Desactivar con clic de verdad en «Mis comandos» | El botón pasa a «Activar»; `comandos_off: ["prueba-ventana.py"]`; **ya no está en la paleta**; el archivo sigue ahí (captura 5) |
| d | Script que borra (`os.remove`, detectado sin declararlo) | La primera vez sale la ventana «El comando «Prueba delicada» pide algo delicado» con **el texto completo del script**, autor y ruta (captura 3); clic real en «Permitir este comando» → corre. **La segunda vez no pregunta**; decisión guardada con su hash |
| e | Las 2 plantillas corren | `archivos-recientes.py`: salida 0, 15 ítems (captura 2). `abrir-resultados.bat`: salida 0 (abre la carpeta) |
| f | .ps1 bloqueado (`PSExecutionPolicyPreference=Restricted` solo para el proceso de la prueba) | Detectado: «No se puede cargar el archivo … porque la ejecución de scripts está deshabilitada…». Aviso con cómo desbloquear + botón «Ejecutar con -ExecutionPolicy Bypass -File» (captura 4). Con Bypass: salida 0, «hola desde ps1», con `-ExecutionPolicy Bypass -File` a la vista en la línea de órdenes |
| 5 | Script con la marca de internet | No se ejecuta: «lleva la marca de descargado de internet… quita la marca (Unblock-File …)» |

Log sin tracebacks.

## FALTA / notas
- `@growi.atajo` se lee y se muestra, pero **no registra un atajo global**:
  eso sería otro paso, con el sistema de atajos.
- **Sin sandbox** (como Raycast y Flow Launcher): lo dice la ventana del
  permiso y «Mis comandos».

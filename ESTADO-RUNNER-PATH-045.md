# ESTADO — RUNNER-PATH-045 (claude no está en el PATH)

## Diagnóstico (causa raíz)
- `runner/runner.py::_build_cmd` lanzaba `["claude", "-p", ...]` (comando pelado): Windows lo resuelve con el PATH **del proceso**.
- La app instalada (`growi-bridge.py`) lo lanza igual vía `_resolve_binary` → `shutil.which("claude")`. La app decía "disponible" porque otra comprobación busca por ruta absoluta (`C:\Users\forte\.local\bin\claude.exe`).
- PATH Machine y User ya contienen `.local\bin` (verificado 28 oct 12:3x). Pero el proceso de la app (pid 15348, arrancado 12:16:41) se relanzó desde un PowerShell abierto antes del cambio y heredó el entorno viejo. Su padre ya no existe.
- Hay DOS lanzadores: el runner standalone (`share\inbox\runner\runner.py`, hoy no corre) y el runner interno de la app (`runner_loop` en `growi-bridge.py`), que es el que atiende la cola ahora.
- `ALLOWED_MODELS`/`motor:codex`: otro tema (0.6.0), no tocado.

## Qué se cambió
- `runner/runner.py` (repo): nuevas `CLAUDE_ABS` y `claude_exe()` (ruta absoluta `%USERPROFILE%\.local\bin\claude.exe`; respaldo `shutil.which`); `_build_cmd` usa esa ruta y registra en el log cuál se usó (`claude se lanza por ruta absoluta|PATH`); `main()` y `heartbeat()` (campo `claude_origen`) usan `claude_exe()`. Sigue `--output-format json`/stream-json y sin tocar modelo.
- `growi-bridge.py` (repo): nueva `_claude_abs()`; `_resolve_binary` usa la ruta absoluta cuando el binario es `claude` (respaldo PATH). Cubre todos los sitios del runner interno que pasan por `_resolve_binary`.
- App instalada: `share\inbox\runner\runner.py` parcheado con el MISMO cambio (.bak: `runner.py.pre-path-045.bak`). **No se copió el runner.py del repo**: el instalado es más nuevo (tiene `t-corr-rutas`) y se habría regresado. El repo va atrasado respecto al instalado en ese archivo (por sincronizar aparte).
- .bak en repo: `runner/runner.py.pre-path-045.bak`, `growi-bridge.py.pre-path-045.bak`.
- NO tocado: VERSION, secret.txt, cola, `growi-bridge.py` instalado.

## Cómo se probó
- `py_compile` OK en runner.py (repo e instalado) y growi-bridge.py.
- Copia aislada (fuera de 8787/8789), PATH filtrado sin `.local\bin`: `shutil.which("claude")` = no encontrado, aun así el runner arrancó "por ruta absoluta" y la tarea `t-path-prueba-2` terminó `status=ok`, resultado "listo" (23 s).
- Runner instalado: `claude_exe()` → `C:\Users\forte\.local\bin\claude.exe (ruta absoluta)`; `_build_cmd` arma el comando con esa ruta.

## LISTO
- Arreglo en repo (commit f00058e) + `runner.py` instalado parcheado.
- Parche aplicado al `growi-bridge.py` INSTALADO (28 oct ~13:10): solo `_claude_abs()` + 2 lineas en `_resolve_binary` (con respaldo PATH). .bak: `growi-bridge.py.pre-path-045.bak`. El resto del instalado, que difiere del repo, no se toco. `py_compile` OK; comprobado que `_resolve_binary({'binario':'claude'})` devuelve `C:\Users\forte\.local\bin\claude.exe` y que cae al PATH si la ruta absoluta no existe.
- App reiniciada (13:15:42): se detuvo solo el pid 15348 (ociosa, `current: null`) y se relanzo elevada (UAC aprobado por Leandro) con el PATH leido del registro (Machine+User). Pid nuevo **26016**; `runner-status.json` lo muestra (`pid: 26016`, claude disponible). Log de la app: arranque normal, `disponibilidad: ... claude ok`.

## FALTA / NO VERIFICADO
- `GET /gateway/salud` respondio **401** (no 200) en 8787: el gateway esta vivo pero pide token; no lei `secret.txt`. Compruebalo tu con el token. (Ojo: curl pasa por el proxy del sistema y da 500 falso; usar sin proxy.)
- El runner interno de la app no registra en el log que ruta uso (solo el runner standalone lo hace), asi que no hay linea "claude se lanza por ruta absoluta" para la app. Falta probarlo con una tarea claude real por la cola: debe terminar ok sin "claude no esta en el PATH". Luego reanudar t-lote-estados-030.
- El `runner.py` del repo va atrasado respecto al instalado (`t-corr-rutas`): sincronizar aparte.

## COMO REINICIAR (si hace falta otra vez)
1. Deten solo el pid de `pythonw.exe ... growi-bridge\growi-bridge.py` (por PID, no por ventana).
2. Lanzala elevada desde el Explorador o desde una terminal NUEVA (nunca vieja): `Start-Process pythonw.exe C:\Users\forte\growi-bridge\growi-bridge.py -Verb RunAs`.
3. Revisa `share\outbox\runner-status.json` (pid nuevo) y manda una tarea claude pequena.

# ESTADO — llama-server bajo demanda y apagado por inactividad (0.4.8, t-llama-ciclo-vida-048)

Rama `Claude`, 29-oct-2026. Lo que se pidió: que el motor local (llama-server, ~5,2 GB de RAM y 47 % de CPU al
arrancar con Hermes 3 8B) solo se encienda cuando alguien le pide algo y se apague solo cuando deja de usarse.

No se tocó `VERSION`, ni los flags CUDA, ni el modelo, ni la app instalada (`C:\Users\forte\growi-bridge\`). El
trabajo se empezó cuando `t-lote-estados-030-r8.result.json` ya decía `status: ok` (19:27).

## Primero, lo más importante: hoy no fue el llama-server del Bridge

Hoy el llama-server del Bridge **no arrancó ni una vez**: el log de la app instalada no tiene ningún «lo arranco
oculto» del 29 de octubre, y `llama\llama-server.log` es del 26. Los llama-server que se vieron en el Administrador
de tareas eran **el de Ollama**: `C:\Users\forte\AppData\Local\Programs\Ollama\lib\ollama\llama-server.exe`, hijo
de `ollama.exe serve`, que arranca con Windows (`Ollama.lnk` en la carpeta Inicio). Carga el mismo Hermes 3 8B
(5,6 GB, 4,2 GB en VRAM).

Quien se lo pide es **el revisor del runner**, al terminar cada tarea. Su cadena (`revision.orden`) prueba el
llama-server del Bridge, lo salta si está apagado (el revisor nunca lo arranca) y pasa a Ollama, que carga el modelo
y lo mantiene 5 min (`keep_alive` por defecto). Cargas de Ollama hoy, según su `server.log`: 14:14, 15:18, 15:20,
15:22, 18:12, 18:15, 18:20, 19:19, 19:27 (revisión del r8) y 19:41. Durante este trabajo volvió a pasar dos veces
(hacia las 19:46 y las 19:54); a las 19:48 `GET /api/ps` daba Hermes cargado con 4,2 GB de VRAM hasta las 19:51:36.

**Lo que se construyó en este spec no cambia eso**, porque Ollama es otro programa. Para que no vuelva a pasar hay
que decidir una de estas opciones (no la tomé porque cambia cómo se revisan las tareas):

1. Quitar `ollama` de `revision.orden` en engines.json, o ponerlo detrás de `claude`/`haiku`.
2. Que el revisor use el llama-server del Bridge con `ensure_llama_server()`: carga lo mismo, pero se apaga solo a
   los 15 min y es un solo programa con el modelo.
3. Dejar Ollama y bajarle la permanencia (`OLLAMA_KEEP_ALIVE=1m`, o `keep_alive` en la llamada del Bridge).
4. Desinstalar Ollama, que ya estaba previsto en ESTADO-LLAMA.md («Leandro desinstala Ollama cuando confirme que
   el motor directo funciona»).

## Auditoría de lanzadores (punto 1)

`grep` de todo el repo (`pruebas/prueba_llama_ciclo_vida.py auditoria`, evidencia en
`pruebas/evidencia/llama-ciclo-vida/auditoria.json`):

| Dónde | Qué hace | Cómo quedó |
|---|---|---|
| `growi-bridge.py`, `_ensure_llama_server_arrancar` | **El único `subprocess.Popen` del exe del servidor** | Solo lo llama `ensure_llama_server()` (comprobado por grep: 1 llamador) |
| `_run_http_engine` (tareas con motor `llama`) | Arranca el servidor si no responde y carga el modelo de la tarea | Pasa por `ensure_llama_server()` |
| `engine_status_rt(autostart=True)`: `probar_descriptor` («Probar motor») y tareas | Igual | Pasa por `ensure_llama_server()` |
| `_mem_llamar` (resúmenes de memoria con el modelo local) | Igual | Pasa por `ensure_llama_server()` |
| `_cmdia_llamar` (comando IA de la paleta) | Igual | Pasa por `ensure_llama_server()` |
| `_llm_accion`, botón **Modelos → Motor local → Arrancar** | Arranque manual | Pasa por `ensure_llama_server()`: el rearranque manual sigue ahí |
| `srv_cambiar_modelo` (cambiar de modelo con el servidor apagado) | Igual | Pasa por `ensure_llama_server()` |
| `_srv_reiniciar` (el router no ve un .gguf nuevo) | Lo para y lo vuelve a arrancar | Pasa por `ensure_llama_server()` |
| Revisor (`_llamar_juez`) | **No arranca nada**: si está apagado lo salta | Sin cambios (ver la sección de arriba) |
| Abrir la app | **No arranca nada** (ya era así en el repo; ahora está medido) | La salud de arranque dice «llama-server: apagado; se arranca solo al usarlo» |
| `oficina/mediciones/medir.py` | Lanza su propio llama-server en el **8091** para medir la Oficina 0.5.0 y lo para en su `finally` | **Excepción deliberada, sin tocar**: es un banco de medición aparte, no la app, y ya dio su veredicto. Ver FALTA |
| Antes: `_llama_ensure` / `_llama_arrancar` | Nombres viejos | Renombrados; el grep no encuentra ninguno |

## LISTO (verificado en este PC)

`python pruebas/prueba_llama_ciclo_vida.py` corre las tres partes; la evidencia está en
`pruebas/evidencia/llama-ciclo-vida/`.

- **(a) Un solo lanzador.** Un único `Popen` del servidor, y su único llamador es `ensure_llama_server()`
  (`auditoria.json`, `ok: true`).
- **(b) Arranque bajo demanda.** Con el servidor parado (sin nada en el puerto ni procesos del exe), una tarea por
  la ruta real (`_run_http_engine`) lo arrancó, esperó a que contestara, cargó el modelo y respondió «hola» en
  8,3 s. Detalle: «llama-server no respondía en 127.0.0.1:8097; el runner lo arrancó solo (pid 30452, listo en
  1,1 s); local listo: modelo Qwen3-0.6B-Q8_0 cargado en el router en 3,0 s» (`demanda.json`).
- **Una petición en curso no se mata.** Con la inactividad a 15 s, una petición de 3500 tokens duró 25,8 s y
  terminó bien; el servidor siguió vivo durante toda ella.
- **(c) Apagado por inactividad.** 17,6 s después de la última petición (límite de 15 s más la vuelta del
  vigilante), los dos procesos (el router y su hijo: 1037 MB y 199 MB) desaparecieron y el puerto quedó libre. La
  RAM libre pasó de 1351 a 2575 MB (+1,2 GB, lo que ocupaban).
- **Rearranque.** La petición siguiente lo volvió a levantar y respondió («adios») en 7,4 s.
- **(d) Abrir la app no arranca nada.** La app real se abrió oculta (`arnes_oculto`: ninguna ventana se mostró ni
  robó el foco) con el bloque `servidor` puesto en el 8098. Estuvo unos 3,5 min abierta (55 s solo en
  `build_gui`) con el runner, el panel de estado y la salud de arranque corriendo, y no hubo ningún llama-server.exe
  del Bridge ni antes, ni durante, ni después (`app-dentro.json`).
- **(e)** `python -m py_compile growi-bridge.py` sin errores; `pytest tests`: 9 OK y 1 omitido.

### Cómo funciona

- `ensure_llama_server(eng, model)` es la puerta única. Si el puerto no contesta, lanza el exe oculto con los args
  del descriptor (sin cambios: router, `--models-max 1`, preset con `n-gpu-layers = 99`). Antes evita una doble
  instancia y cierra los huérfanos (lo de la 0.3.0), espera hasta `espera_s` y, en modo router, carga el modelo.
- Cada llamada HTTP local (`_http_local` y `_http_local_stream`) a un servidor vigilado cuenta como petición en curso
  mientras dura y apunta la hora de la última. Solo cuentan los POST de inferencia (chat, completions, embeddings,
  `/models/load`). `/health`, `GET /models` y `/props` no cuentan: el panel de Modelos los consulta solo, y si
  contaran el servidor nunca se apagaría.
- Un hilo vigilante (uno solo) mira cada `min(30 s, inactividad/6)`. Con 0 peticiones en curso, nada cargándose y
  `inactividad_min` sin uso, pregunta a `GET /slots` si algún slot está generando (por si la petición viene de
  fuera, un curl por ejemplo). Si no lo está, lo para con `srv_parar`: solo el exe del descriptor en su puerto, con
  su árbol. Si el puerto lo tiene otro programa, no lo toca. Si justo llega una petición mientras apaga, esa petición
  espera a que termine, falla con «no responde» (un error transitorio) y el reintento lo vuelve a arrancar.
- `ensure_llama_server()` cuenta como uso al devolver «listo». Así el vigilante no lo apaga entre «listo» y la
  petición que viene detrás.

### Configuración: un solo sitio (punto 4)

Todo está en el bloque `servidor` del motor `llama` en `engines.json`, y lo lee `llama_cfg(eng)`:

| Qué | Clave | Valor |
|---|---|---|
| Exe | `servidor.exe` | `llama/llama-server.exe` |
| GGUF por defecto | `servidor.gguf` | `models/hermes-3-8b-q4_k_m.gguf` |
| Puerto y flags | `servidor.args` (`--port 8080`, `--models-max 1`…); capas en GPU y contexto de cada modelo en `models-preset.ini`, al que apunta `servidor.preset` | sin cambios |
| Tope de espera del arranque | `servidor.espera_s` | **120** (era 180; el spec pide 120 por defecto. El router contesta `/health` en ~1 s; la carga del modelo tiene su propio tope, `router.espera_carga_s` = 300) |
| Minutos sin peticiones para apagar | `servidor.inactividad_min` | **15** (0 = no apagar nunca) |
| Solo para pruebas | variables `GROWI_LLAMA_INACTIVIDAD_MIN` y `GROWI_LLAMA_ESPERA_S` | admiten decimales (0.25 = 15 s) |

El puerto aparece también en `base_url`, `url` y `healthcheck.url` del mismo descriptor, como ya pasaba antes.
Si se cambia, se cambia en los cuatro sitios del mismo bloque.

## FALTA

- **Probado con Hermes 3 8B, no.** La prueba usó el mismo `llama-server.exe` real de la app instalada, en modo
  router y con los flags del descriptor, pero con `Qwen3-0.6B-Q8_0` (el de `_prueba-semaforo`, enlazado sin copiar)
  y en el puerto 8097. El PC estaba en uso con **1,1 GB de RAM libre de 15,4**, y cargar Hermes (~5,2 GB) habría
  repetido el colapso. El ciclo de vida no depende del modelo, pero la medida de RAM liberada con Hermes no está
  hecha.
- **La app instalada no tiene esto.** El `growi-bridge.py` instalado (y sus copias en `share\inbox`, las que tocó el
  r8) es otro archivo, de 34 101 líneas, frente a las 45 182 del repo. El cambio está en el repo, rama `Claude`, y
  llega a `C:\Users\forte\growi-bridge\` cuando se despliegue el repo.
- **`oficina/mediciones/medir.py` sigue lanzando su propio llama-server** (puerto 8091, lo para al acabar). Es
  la única excepción al «todo pasa por `ensure_llama_server()`». Si se vuelve a usar y se quiere sin excepción, hay
  que pasarlo a importar el módulo como hace `prueba_llama_ciclo_vida.py`.
- **`GET /slots` en modo router**, para las peticiones que no pasan por el Bridge, no está probado con una petición
  externa real. Si el router no lo contesta, solo queda el contador de las peticiones del Bridge.
- **La decisión sobre Ollama y el revisor** (sección de arriba): es lo que de verdad colapsó el PC hoy.

## CÓMO PROBARLO

Todo de una vez (tarda ~6 min; necesita ~1,5 GB de RAM libre y que Ollama no tenga un modelo en la GPU):

```
cd C:\Users\forte\source\growi-bridge
python pruebas\prueba_llama_ciclo_vida.py              # auditoria + app + demanda; termina en RESULTADO {...}
python pruebas\prueba_llama_ciclo_vida.py demanda      # solo arranque bajo demanda + inactividad (~70 s)
```

A mano, con la app desplegada y Hermes:

1. Sin el motor encendido: `tasklist /FI "IMAGENAME eq llama-server.exe"` no muestra ninguno con ruta
   `growi-bridge\llama\` (el de `Ollama\lib\ollama\` es de Ollama).
2. Abre la app: siguen sin aparecer.
3. Manda una tarea con `"motor": "llama"`. En el log sale «llama-server no respondía…; el runner lo arrancó solo
   (pid …)», y luego «vigilante de inactividad … lo apago tras 15 min sin peticiones».
4. Comprueba que contesta: `curl --noproxy "*" http://127.0.0.1:8080/health`. Sin `--noproxy`, el proxy local
   devuelve un 500 falso.
5. A los 15 min sin usarlo, el log dice «llama-server parado (15 min sin peticiones: apagado por inactividad)» y el
   proceso desaparece del Administrador de tareas.
6. Para probar más rápido: `setx GROWI_LLAMA_INACTIVIDAD_MIN 1` y reabre la app. Para quitarlo:
   `reg delete HKCU\Environment /v GROWI_LLAMA_INACTIVIDAD_MIN /f` y vuelve a abrirla.

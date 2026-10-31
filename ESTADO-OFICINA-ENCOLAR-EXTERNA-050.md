# ESTADO t-oficina-encolar-externa-050 (spec 4 de 18, oficina 0.5.0)

**Resumen:** la duda 17 queda respondida con el código delante. Hoy «Pedirle algo» **no registra nada en cola.db ni aplica el guardrail**. Solo escribe un `.task.json` en `share\inbox\runner-tasks\`. El registro y el guardrail los pone después el **runner**, al recoger el archivo. Esa escritura estaba metida en la ventana (`_send_ask` lee los widgets) y desde otro proceso no se podía llamar. La saqué a una función sin ventana, `encolar_tarea()`, dentro de `growi-bridge.py`. La ventana ahora la llama, y la oficina la importa con un módulo nuevo (`oficina\encolar\encolar.py`). No añadí ningún endpoint ni ningún puerto.

Todo está **verificado en una instancia aislada** (`C:\Users\forte\growi-bridge\_prueba-encolar-externa\`), con el runner real del código y el motor local real (Hermes 3, $0). **No lo verifiqué contra el runner instalado**: la app instalada se cerró a las 09:45:34 (en `growi-bridge.log` se lee «saliendo de Growi Bridge... runner: parado... puente: parado»). Su `runner-status.json` sigue diciendo `alive: true` con `last_poll` 09:44:44, pero es un dato viejo. No la arranqué, porque el spec lo prohíbe. Ver FALTA.

## Archivos tocados (cada uno con su .bak)
| Archivo | .bak | Cambio |
|---|---|---|
| `C:\Users\forte\growi-bridge\growi-bridge.py` (instalada) | `growi-bridge.py.pre-encolar-externa.bak` | `criterios_de_texto()`, `_modelo_por_defecto()`, `encolar_tarea()`; `_send_ask()` la llama |
| `C:\Users\forte\growi-bridge\share\inbox\growi-bridge-app\growi-bridge.py` | `growi-bridge.py.pre-encolar-externa.bak` | el mismo parche, aplicado por separado (las dos copias siguen siendo distintas: la de growi-bridge-app conserva lo del lote-live) |
| NUEVO `C:\Users\forte\growi-bridge\share\inbox\oficina\encolar\encolar.py` | — | módulo importable de la oficina |

El parche es `_prueba-encolar-externa\scripts\parche_encolar.py`. Solo se aplica si encuentra el `_send_ask` original exacto, y conserva los CRLF. **No toqué** el `growi-bridge.py` del repo `C:\Users\forte\source\growi-bridge\` (es otra versión, de 45 361 líneas): lo integra quien una las copias, con ese mismo script. VERSION intacta en las dos carpetas (raíz `0.2.0-alpha` del 27 oct; growi-bridge-app `0.1.0-alpha` del 25 oct). `python -m py_compile` sin errores en las dos copias y en `encolar.py`.

Lo que **no** se tocó: `cola.db` real (mtime 09:37, antes de esta sesión), `settings.json` real (09:44), `runner-status.json` / `runner-live.json` reales, `runner-tasks\` real (sin tareas nuevas), `t-lote-live-050-r2` y `growi-bridge-browser\`. Una sola huella en la instalación: al medir el coste de importar la app (10:08:40), la importación escribió 2 líneas en el `growi-bridge.log` real («comandos-ia: 3 integrados», «asistentes: 3 perfiles»). Esas líneas las escribe el propio `growi-bridge.py` al cargarse. Todo lo demás corrió en la carpeta aislada.

## LISTO, por subfunción, con evidencia

### (a) Cómo encola hoy la app: leído en el código
Ruta: `C:\Users\forte\growi-bridge\growi-bridge.py`. Las líneas son de antes del parche; el parche las desplaza, así que hay que buscar por nombre.
- **Botón «Enviar» de «Pedirle algo»** (página Tareas, ~l. 35303-35344): `ttk.Button(..., command=_send_ask)`. **Ctrl+K → «Pedirle algo a Claude»** (`C("pedir", ...)`, ~l. 35452) no encola nada: abre Tareas y pone el foco en `ask_text`. **«Pedirle algo a Growi»** del estado vacío (`_tareas_pedir`, ~l. 26489) solo baja la página hasta la caja. Los tres caminos acaban en el mismo `_send_ask`.
- **`_send_ask()`** (l. 22048, pegada a la UI):
  1. Lee `ask_text`. Si el texto es «/nuevo» o «recuerda esto», es un comando de memoria y no se encola.
  2. Lee el motor del desplegable (`_ASK_ENGINES`: etiqueta → model). Valida el nombre de ollama y, si la nube está caída, cae al modelo local (`local_fallback_model`).
  3. Lee los criterios: una frase por línea, y una línea `{...}` cuenta como criterio tipado.
  4. Genera el id `t-YYYYmmdd-HHMMSS` (con `-1`, `-2`... si ya existe en `runner-tasks\`).
  5. Escribe **un único archivo**, `share\inbox\runner-tasks\<id>.task.json`, con `id, prompt, cwd (asis_cwd_envio), model | motor, timeout_min 30, allowed_tools, permission_mode, asistente, criterios`. Lo escribe con `write_text`, que no es atómico.
  6. Deja en el Registro `tareas: '<id>' enviado al runner (<motor>)`.
- **cola.db**: `_send_ask` no la toca. La registra el **runner**: `runner_loop` (l. ~15440) recorre `TASKS.glob("*.task.json")` cuando el archivo tiene ≥2 s y llama a `_cola_ver(p)` → `cola_registrar()` (l. 13659), que hace el INSERT `en_cola` en `tareas` y anota la prelación **antes** de recogerla. El hilo de pulso (`_runner_pulse_loop`) también apunta lo que llega mientras hay una tarea corriendo.
- **Guardrail**: tampoco está en `_send_ask`. Está en `_process_one_impl()` (l. ~15030): `_approval_needed(task)` según `guardrail_level()` (settings.json: siempre → pregunta desde R1, delicado → R2, nunca → R3) y `riesgos.json`. Si hay que preguntar, `_park_for_approval()` mueve el archivo a `runner-tasks\esperando\`, crea el pedido (`approval_id` + vencimiento) y `cola_set(estado="esperando_aprobacion")`.
- **Hallazgo:** la función estaba pegada a la UI (lee `_widgets`) y no se podía importar sin ventana. Pero lo que hace es solo escribir el archivo. El contrato real es «un `.task.json` en `runner-tasks\`», y el registro y el guardrail ya los pone el runner, sea quien sea el que escribe.

### (b) Función expuesta a otro proceso: elegí una función importable
- `encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app")` en `growi-bridge.py` devuelve `{ok, id, archivo, engine, data, error}`. Es **exactamente el cuerpo que tenía `_send_ask`** (mismos campos, mismo cwd, asistente, motor y permisos, mismo fallback). Dos mejoras que también aprovecha la ventana:
  - escritura **atómica y exclusiva**: `.tmp` (el runner no lo mira) + `os.rename`, que en Windows falla si el nombre ya existe;
  - el id se comprueba también en `processing\`, `done\` y `esperando\`.
- `_send_ask` ahora solo lee la ventana y pinta el resultado.
- `oficina\encolar\encolar.py`:
  - `cargar_app()` importa `growi-bridge.py` con importlib. No arranca la ventana, el puente ni el runner: `main()` está detrás de `if __name__ == "__main__"`, y después de importar el único hilo vivo es `MainThread`.
  - `encolar()` llama a `encolar_tarea(origen="oficina")`.
  - `estado(id)` lee cola.db en **solo lectura** (`?mode=ro`) y el `.result.json`.
  - `esperar(id)` sondea cada 2 s.
  - Por consola: `python encolar.py "encargo" --criterio ... --modelo ... --esperar 600`.
- **Por qué importable y no endpoint:** es lo más simple que funciona y no añade superficie de red. El INDICE fija «Transporte v1: archivos, no WebSocket». El 8787 actual tiene token y además escucha en la IP de Tailscale, y no hace falta tocarlo.
- Evidencia: el proceso pid 6672 (no la app) importó en 0,23 s y encoló `t-20261030-101730` con `ok: true` y `sockets_de_este_proceso: []` (`evidencia\encolar_e2e_salida.txt` y salida en pantalla). Coste medido: RSS ≈ 37 MB, import 0,23-0,5 s, CPU 0,02 % del PC mientras sondea (`evidencia\encolar_recursos_salida.txt`).

### (c) Mismo camino y mismo guardrail: comparación real
Instancia aislada con `guardrail: siempre` en **su** settings.json.
- **Desde la app:** la ventana real (`build_gui`), página Tareas. Escribí en «Pedirle algo», puse el criterio, elegí «Claude Haiku» y pulsé el botón «Enviar» con `invoke()`. Salió `t-20261030-101706` y la fila de estado decía «En cola: t-20261030-101706, esperando a que empiece (el runner está apagado)». Captura: `_prueba-encolar-externa\evidencia\app-pedirle-algo-enviado.png`.
- **Desde fuera:** el mismo encargo y criterio con `model="haiku"`, desde otro proceso, salió `t-20261030-101730`.
- Después arranqué el runner aislado (`runner_loop` real) y lo comparé con `evidencia\encolar_comparar_salida.txt`:
  - `task.json app == fuera (sin el id): True`, las claves en el mismo orden.
  - `fila cola.db app == fuera (sin id/horas/archivo/raiz): True` → `estado: esperando_aprobacion, intentos 0, reintentos 0, cortes 0, ronda 0`.
  - Las dos quedaron retenidas como **R2 «borrar archivos»** con su pedido (`apr-…-fa1c` y `apr-…-bf61`, `canal: app`, `estado: pendiente`), movidas a `runner-tasks\esperando\`, y las dos aparecen en la **cola visible** (`cola_pendientes()`: «en espera de aprobación»).
- Ni el módulo ni `encolar_tarea` abren `cola.db` para escribir. El módulo solo la lee con `mode=ro`. Ninguno de los dos toca `runner-live.json`, `runner-status.json`, `.revision.json`, `.orquestacion.json` ni `settings.json` (settings solo se lee para el asistente activo y el motor por defecto). Esos archivos de la instancia aislada los escribió su runner, no el encolador.

### (d) Plan B (escribir el .task.json a mano): probado, funciona
- `encolar_planb.py` escribió `t-planb-101739.task.json` con un `write_text` normal, sin la función. El runner lo apuntó en cola.db («cola: el runner toma t-planb-101739»), le aplicó el guardrail (R2 → `esperando_aprobacion`, pedido `apr-t-planb-101739-…-937b`) y aparece en la cola visible.
- **Pero no es igual que la app**: no lleva `asistente`, el `cwd` hay que inventarlo y no hay fallback local. Por eso el camino bueno es la función importable. El plan B queda solo como respaldo documentado.

### (e) Seguridad local: comprobada, no supuesta
`encolar_seguridad.py` hizo `psutil.net_connections` durante la prueba, con el runner y llama-server vivos (`evidencia\encolar_seguridad_salida.txt`):
- **Escuchas de los procesos de la prueba:** solo `127.0.0.1:8080` (llama-server, el motor de siempre, lanzado por el runner con `--host 127.0.0.1`).
- **Escuchas de la prueba fuera de loopback:** ninguna. El encolador tenía `net_connections() == []` al empezar y al terminar.
- Lo que escucha fuera de loopback en el PC es todo de Windows o ASUS y ya estaba antes (svchost 135, System 445/139/5357, lsass, ArmouryCrate 12177...).
- Sin token ni credenciales en el camino de encolado: el `.task.json` lleva solo encargo, carpeta, motor y criterios.
- No hay puerto nuevo.

### (f) Prueba end-to-end desde otro proceso, con su rastro
`encolar_desde_fuera.py` (proceso pid 27940, en %TEMP%) encoló con `model="motor:llama"`:
- **Encargo:** «Responde solo con esta frase exacta: hola desde la oficina».
- **Criterio:** «la respuesta contiene la frase hola desde la oficina».
- **Id:** `t-20261030-101824`.
- **Estados leídos de cola.db:** `null` (0 s) → `en_curso` (4 s) → `terminada` (52,7 s).
- **Resultado** (`runner-results\t-20261030-101824.result.json`): `estado: ok, motor: llama, cost_usd: 0.0`, texto «hola desde la oficina».
- **Revisión:** llama la aprobó («La aprobación se basa en el texto del resultado: no hay archivos que lo confirmen»).
- **Registro de la instancia:** llama-server arrancado bajo demanda (pid 29732, listo en 34,4 s), «terminado: ok duracion=40.8s costo=0.0».
- Al parar el runner aislado, `srv_al_salir()` paró llama-server y el 8080 quedó libre (comprobado con tasklist y netstat).

### Extra: concurrencia
Tres procesos encolaron en el mismo instante y salieron `t-20261030-102004`, `-1` y `-2`. Ningún archivo quedó pisado.

## FALTA
1. **Prueba contra el runner INSTALADO.** No se pudo hacer: la app instalada estaba cerrada desde las 09:45:34 (no fui yo, ya estaba así al empezar). Solo queda `pythonw` pid 11740, que escucha en `127.0.0.1:8788` (servidor del navegador). No la reinicié. Además, el `growi-bridge.py` instalado ya trae `encolar_tarea`, pero el proceso que Leandro arranque tiene que cargar este archivo nuevo. Pasos para Leandro en «COMO PROBARLO».
2. **Diferencias del encolado externo** frente a la ventana:
   - `local_fallback_model` mira `state` (nube caída / forzar local) **del proceso que llama**. En la oficina ese estado nunca se rellena, así que **desde fuera no cae solo al modelo local si la nube está caída**. La ventana sí.
   - En el Registro, el texto del motor es el model (`motor:llama`) y no la etiqueta («Local Hermes 3 directo $0»), porque `_ASK_ENGINES` solo se rellena con la ventana abierta.
   - «/nuevo» y «recuerda esto» se rechazan (`ok: false`) en vez de ejecutarse como memoria.
3. **Guardrail real = «nunca»** (settings.json de la instalación): solo retiene desde R3. Una petición R2 como «borra…» **se ejecutaría sin preguntar**, tanto desde la oficina como desde la app (comportamiento idéntico, como pide el spec). La retención la verifiqué con `siempre` en la instancia aislada, **no con el settings real**.
4. **Canal**: las tareas de la oficina no llevan campo `canal`, así que el runner las trata como `app`: un R3 se aparca esperando aprobación en la app. Si un spec posterior pusiera `canal: "oficina"`, `_park_for_approval` **denegaría al instante** cualquier R3 (trata todo canal distinto de `app` como remoto). Lo tiene que decidir t-oficina-protocolo-050 o t-oficina-telefono-050, sin improvisarlo.
5. **Importar la app escribe en su Registro**: 2 líneas por cada proceso que importa («comandos-ia…», «asistentes…») y 1 por tarea («…; pedido desde oficina»). Es inofensivo, pero queda escrito.
6. **Presupuestos §8**: el encolador está medido (RSS ≈ 37 MB, de los cuales ≈ 19 MB son la app importada; CPU 0,02 % sondeando; sin GPU, VRAM 0 propia). La oficina completa no existe todavía. La VRAM de llama-server es del motor, no de la oficina, y aquí no la medí.
7. **Fuentes ausentes**: `INVESTIGACION-0.5.0-oficina.md` (§2.6, §10 paso 3, §14 duda 17) y `PALETA-Y-SKINS.md` no están en este PC. Trabajé con `specs\opus-tasks-050\INDICE-OFICINA.md`, los ESTADO previos y el spec. Lo que diga §2.6 más allá de lo que cita el spec está **sin contrastar**.
8. **Archivos de prueba que dejé**: en `_prueba-encolar-externa\app\share\inbox\runner-tasks\` quedan 3 tareas de la prueba de concurrencia (`t-20261030-102004*`, R2 «borra…») y 3 en `esperando\`. Son de la carpeta aislada. No borré nada; Leandro puede borrar `_prueba-encolar-externa\` entera cuando quiera.
9. Solo la copia de growi-bridge-app lleva además el lote-live. **Integrar las copias** (raíz ↔ growi-bridge-app ↔ repo) sigue pendiente, como dicen los ESTADO del lote-live.

## COMO PROBARLO
Aislado (no toca la instalación). Los scripts están en `C:\Users\forte\growi-bridge\_prueba-encolar-externa\scripts\`. Usa `PYTHONIOENCODING=utf-8`.
```
python encolar_preparar_aislada.py siempre        # copia la app + settings con guardrail siempre
python encolar_desde_app.py "Borra el archivo viejo.txt de la carpeta de pruebas" "el archivo viejo.txt ya no existe" "Claude Haiku"
python encolar_desde_fuera.py "Borra el archivo viejo.txt de la carpeta de pruebas" "el archivo viejo.txt ya no existe" haiku
python encolar_planb.py
python encolar_runner_aislado.py 1500             # en otra consola; se para creando app\STOP
python encolar_comparar.py <id_app> <id_fuera> <id_planb>
python encolar_desde_fuera.py "Responde solo con esta frase exacta: hola desde la oficina" "la respuesta contiene la frase hola desde la oficina" motor:llama 900
python encolar_seguridad.py <pid_runner> <pid_encolador>
```
Contra la app instalada, lo hace Leandro:
1. Abrir Growi Bridge (`iniciar-growi-bridge.bat`). Ya carga el `growi-bridge.py` parcheado.
2. Comprobar que «Pedirle algo» sigue funcionando desde la ventana: enviar algo trivial y ver «✓ Enviado al runner».
3. Desde otra consola, con una prueba barata y local:
   `python C:\Users\forte\growi-bridge\share\inbox\oficina\encolar\encolar.py "Responde solo: hola desde la oficina" --criterio "la respuesta contiene hola desde la oficina" --modelo motor:llama --esperar 600`
   Tiene que devolver el id y `estado_final: terminada`, y la tarea tiene que verse en Tareas / cola visible.
4. Si algo falla, restaurar con `growi-bridge.py.pre-encolar-externa.bak`.

## Para t-oficina-protocolo-050 (API de encolado)
- `sys.path.insert(0, r"…\share\inbox\oficina\encolar")`; `import encolar`
- `encolar.encolar(prompt, criterios=[...], model=None|"sonnet"|"opus"|"haiku"|"motor:auto"|"motor:llama"|…)` devuelve `{"ok", "id", "archivo", "engine", "data", "error"}`. Nunca lanza por un encargo malo: devuelve `ok: False` + `error`. Sin model, usa el de Ajustes (settings `default_engine` / `motor`).
- `encolar.estado(id)` devuelve `{"estado": None|"en_cola"|"en_curso"|"esperando_aprobacion"|"esperando_leandro"|"terminada"|"fallida"|"necesita_decision"|…, "fila", "resultado", "error"}`. Lee cola.db con `mode=ro`. `estado: None` significa «todavía en la bandeja, el runner aún no lo apuntó» (tarda ≥2 s, más si el runner está ocupado o apagado): la oficina **no** debe pintarlo como «trabajando».
- `encolar.esperar(id, timeout_s, cada_s=2)` devuelve el último estado y los cambios `[(s, estado)]`.
- Carpeta de la app: `GROWI_BRIDGE_APP_DIR` o `ruta_app=`. Por defecto `%USERPROFILE%\growi-bridge`. Lanza `EncolarNoDisponible` (o devuelve `ok False`) si `growi-bridge.py` es anterior a este spec.
- Importar cuesta ≈ 0,5 s y ≈ 20 MB **una vez por proceso**: conviene hacerlo al arrancar la oficina, no en cada clic.
- La oficina **no** decide nada del guardrail. Si la tarea sale `esperando_aprobacion`, se aprueba en la app (Tareas) o por WhatsApp.
- Queda abierto lo del campo `canal` (FALTA 4).

## Actualización 30 oct 2026, 22:35: integrado en el repo (junto con el lote-live, specs 2+3)
- **FALTA 9 cerrada para el repo.** `growi-bridge.py` del repo lleva ahora:
  - El lote-live (`cola-live.json` + `oficina_estado_tarea()`). Es el diff de la copia `growi-bridge-app` (`.pre-oficina-live-050.bak` → `.pre-encolar-externa.bak`): 8 bloques que entran limpios con `patch --binary`, solo con desplazamiento. Guardado en `parches/lote_live_050.diff`.
  - `encolar_tarea()`. `oficina/encolar/parche_encolar.py` acepta ahora también la variante de `_send_ask` con proyectos (`proyecto_activo()`); `encolar_tarea()` guarda el proyecto igual que la ventana.
- **Verificado en instancia aislada** (`_prueba-lote-live-repo`, `pruebas/lote_live_repo/lote_live_repo.py`, evidencia `pruebas/evidencia/lote-live-repo/resultado.json`):
  - `cola-live.json` aparece a los 0,4 s de arrancar el runner y el pulso lo reescribe en ≤ 10 s sin cambios.
  - Una tarea encolada con `encolar_tarea` (motor:ollama, $0) se ve `en_cola → en_curso → terminada`, sin campos fuera del contrato.
  - `oficina/encolar/encolar.py` encola desde otro proceso contra el código del repo.
- **La app instalada sigue igual:** encolar sí, lote-live no. Instalar el `growi-bridge.py` del repo es cosa de Leandro (hay que reiniciar).

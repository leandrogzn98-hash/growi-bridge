# LOTES — Growi Bridge (27 oct 2026)

Agrupación en lotes de los 95 specs restantes del pipeline. Los 95 ya llevaban
etiqueta `model` por tier (29 Opus, 58 Sonnet, 8 Haiku — verificado) y el bloque
`MODO NO-INTERACTIVO` al inicio del prompt (bloque idéntico de 421 caracteres en
los 95; los 26 specs ya terminados de `opus-tasks-030` no lo llevan porque son
anteriores al re-etiquetado, y no forman parte de estos lotes).

## Reglas aplicadas

- Lote = 2 a 4 specs que comparten archivos y contexto (mismo módulo/página,
  mismos archivos a tocar, mismo tema) y que una sola sesión puede hacer junta
  sin releer los mismos archivos varias veces.
- Fusión solo si: (a) miembros pequeños y relacionados de verdad; (b) NINGÚN
  miembro depende de la salida o del ESTADO de otro miembro del mismo lote
  (si un prompt dice «lee primero el ESTADO de X» o «depende de Y», no se
  fusionan); (c) nunca `t-temas-oscuro-sistema` (ya enviado, Fase A detenida);
  (d) prompt combinado < ~30.000 caracteres; (e) criterios totales ≤ 12;
  (f) modelo del fusionado = tier más alto entre sus miembros.
- Cada fusionado es UN archivo nuevo `t-lote-<tema>-<fase>.task.json` en la
  misma carpeta: un solo bloque `MODO NO-INTERACTIVO` al inicio, seguido de los
  prompts de los miembros sin su bloque (texto íntegro, sin reescribir), cada
  uno precedido de un encabezado estructural `### PARTE n de 2 — <id>` para que
  la sesión vea que son dos tareas; `criterios` = concatenación exacta de los
  criterios de los miembros en orden; `timeout_min` = 90 (lotes de 2);
  `allowed_tools` = `Read,Write,Bash,Glob,Grep`; `permission_mode` =
  `acceptEdits`; `cwd` = el mismo de los miembros (idéntico en los 95).
- Los archivos originales de los miembros NO se borran: quedan como referencia.
  En la lista ORDEN de cada cadena solo va el lote, en la posición del primer
  miembro. Nada más cambió en los scripts de cadena (tope diario intacto).

## Resumen de fusiones (6 en total)

| Lote | Fase | Miembros | Modelo | Criterios | Prompt |
|---|---|---|---|---|---|
| `t-lote-estados-030` | 030 | t-estados-vacios + t-estados-error | sonnet | 10 | 15.995 |
| `t-lote-mascota-040` | 040 | t-mascota-estados + t-mascota-memoria-minima | sonnet | 7 | 12.759 |
| `t-lote-conectividad-040` | 040 | t-detector-avast + t-mapa-ampliado | sonnet | 9 | 13.027 |
| `t-lote-evaluar-modelos-040` | 040 | t-vision-gemma3-4b + t-evaluar-hermes4 | sonnet | 8 | 11.621 |
| `t-lote-tarjetas-045` | 045 | t-apis-tarjetas-045 + t-modelos-tarjetas-045 | sonnet | 12 | 15.876 |
| `t-lote-live-050` | 050 | t-oficina-cola-live-050 + t-oficina-consumo-vivo-050 | sonnet | 12 | 16.622 |

Efecto en envíos: 95 specs → **89 ítems a enviar** (030: 5→4 restantes;
040: 39→36; 040plus: 12→12; 045: 20→19; 050: 19→18, incluido t-qa-final-050
manual). En ORDEN: cadena-030 28→27, cadena-040 39→36, cadena-045 20→19,
cadena-050 18→17.

---

## Fase A — opus-tasks-030 (5 restantes)

### Lote A1 — FUSIONADO: `t-lote-estados-030`
- **Miembros:** `t-estados-vacios` (sonnet, 5 criterios) + `t-estados-error`
  (sonnet, 5 criterios). Total 10 criterios, prompt 15.995.
- **Por qué van juntos:** la matriz de estados por página (carga, vacío, error,
  contenido, sin conexión) en las mismas 5 páginas con listas (Tareas, Skills,
  Carpetas, Modelos, Registro), en el mismo archivo `growi-bridge.py`, con los
  mismos componentes y la misma regla «un fallo de carga nunca muestra el
  vacío, muestra el error».
- **Por qué es seguro fusionar:** el propio prompt de `t-estados-vacios` dice
  «eso lo construye t-estados-error, otro spec del mismo lote; si aun no esta,
  el vacio de error muestra el texto de error disponible» — la fusión hace
  cierta la primera rama: en la misma sesión se construyen los dos componentes
  y el criterio «un fallo de carga NO muestra el vacío sino el error» se
  verifica directamente. Ningún miembro necesita leer el ESTADO del otro: el
  ESTADO de cada uno se escribe al final, como siempre.
- **ORDEN:** `t-lote-estados-030` ocupa la posición de `t-estados-vacios`
  (tras `t-temas-oscuro-sistema`).

### Lote A2 — NO fusionado: plan visible + cola visible
- **Miembros:** `t-plan-visible-pausa` (opus, 6 criterios) + `t-cola-visible-030`
  (sonnet, 6 criterios).
- **Por qué van juntos como lote:** ambos tocan la pestaña Tareas y el ciclo de
  vida de la tarea en el runner (`growi-bridge.py`): el plan visible vive en la
  tarjeta de la tarea y la cola visible es la vista de en ejecución +
  pendientes con prelación.
- **Por qué NO se fusionan:** `t-plan-visible-pausa` es trabajo de seguridad
  (aprobación por paso R0–R3, pausa ante ambigüedad, parada ante login/2FA/
  CAPTCHA, slot libre mientras espera) en tier Opus; mezclarlo con una vista
  de presentación diluiría su verificación en una sola sesión. Comparten
  superficie (pestaña Tareas), no un subsistema. Van en secuencia, como están
  en ORDEN (posiciones 27 y 28).

### Solo — `t-temas-oscuro-sistema`
- Sin lote y sin fusión: ya enviado y atascado en el PC (Fase A detenida ahí).
  No se toca.

---

## Fase B — opus-tasks-040 (39 specs)

### Lote B1 — FUSIONADO: `t-lote-mascota-040`
- **Miembros:** `t-mascota-estados` (sonnet, 3 criterios) +
  `t-mascota-memoria-minima` (sonnet, 4 criterios). Total 7 criterios,
  prompt 12.759.
- **Por qué van juntos:** el mismo subsistema (la mascota en
  `growi-bridge.py`): estados/posturas y anti-molestia por un lado, memoria
  mínima (no repetir, no celebrar lo rutinario, clic = saludo, persistencia
  en disco) por otro. Adyacentes en ORDEN (27 y 28).
- **Por qué es seguro:** la única mención cruzada es la regla (3) de
  `t-mascota-estados` — «Nunca dos veces seguidas lo mismo (ver
  t-mascota-memoria-minima)» — una referencia a la regla del otro spec, no una
  dependencia de su salida: en la sesión fusionada ambas reglas se construyen
  juntas y la (3) se cumple con la memoria que se construye en la parte 2.
- **ORDEN:** `t-lote-mascota-040` ocupa la posición de `t-mascota-estados`.

### Lote B2 — FUSIONADO: `t-lote-conectividad-040`
- **Miembros:** `t-detector-avast` (sonnet, 5 criterios) + `t-mapa-ampliado`
  (sonnet, 4 criterios). Total 9 criterios, prompt 13.027.
- **Por qué van juntos:** salud de red y del túnel en `growi-bridge.py`: el
  detector vigila Avast VPN + Tailscale y registra las caídas del túnel con su
  causa; el mapa añade las 5 filas nuevas (registry.ollama.ai, huggingface.co,
  github.com, controlplane.tailscale.com, cloudflare.com) medidas directo y
  por proxy, y alimenta al router y al descargador. Adyacentes en ORDEN
  (30 y 31). Ninguno menciona al otro.
- **ORDEN:** `t-lote-conectividad-040` ocupa la posición de `t-detector-avast`.

### Lote B3 — FUSIONADO: `t-lote-evaluar-modelos-040`
- **Miembros:** `t-vision-gemma3-4b` (sonnet, 4 criterios) + `t-evaluar-hermes4`
  (haiku, 4 criterios). Total 8 criterios, prompt 11.621, modelo sonnet
  (tier más alto).
- **Por qué van juntos:** evaluación de modelos locales sobre llama-server con
  VRAM medida del log: Gemma 3 4B + mmproj como visión (capturas, OCR, ficha
  de qué puede y qué no) y A/B Hermes 3 vs Hermes 4 con 10 tareas fijas y
  veredicto. Los dos dependen de `t-catalogo-030` (que instala los modelos,
  posición 11, anterior a ambos), no entre sí. Adyacentes en ORDEN (36 y 37).
- **ORDEN:** `t-lote-evaluar-modelos-040` ocupa la posición de
  `t-vision-gemma3-4b` (primer miembro en ORDEN).

### Lote B4 — NO fusionado: estimado de gasto + pronóstico
- **Miembros:** `t-estimado-gasto-030` (opus, 5) + `t-gasto-pronostico`
  (opus, 5). Mismo tema (coste: estimado antes de ejecutar, tope por tarea,
  pronóstico «a este ritmo…», historial de 7 días por proyecto).
- **Por qué NO se fusionan:** `t-gasto-pronostico` dice explícito «Se apoya en
  el tope de t-estimado-gasto-030; si ese spec no lo dejó, este lo construye y
  lo anota» — dependencia directa de la salida del otro miembro (regla b).
  Van en secuencia en ORDEN (5 y 6).

### Lote B5 — NO fusionado: modelo por superficie + interruptor de motor
- **Miembros:** `t-modelo-por-superficie-auto` (sonnet, 4) +
  `t-interruptor-motor` (sonnet, 4). Mismo tema (pestaña Modelos: qué motor
  usa cada superficie, y activar/desactivar motores).
- **Por qué NO se fusionan:** dependencia cruzada. `t-interruptor-motor`
  exige que «si era el modelo por defecto de una superficie, esa superficie
  vuelve a su valor sensato con aviso» (la superficie es obra del otro spec)
  y `t-modelo-por-superficie-auto` exige que «un perfil no puede elegir un
  motor desactivado» (el interruptor es obra del otro spec). Cada uno necesita
  el comportamiento del otro ya verificado. Van en secuencia en ORDEN
  (19 y 21).

### Lote B6 — NO fusionado: memoria buscable + notas Obsidian
- **Miembros:** `t-memoria-buscable` (sonnet, 5) + `t-notas-obsidian-030`
  (opus, 6). Mismo tema (memoria y notas en Markdown plano, búsqueda por
  palabras + fecha).
- **Por qué NO se fusionan:** `t-notas-obsidian-030` dice «se apoya en
  t-memoria-buscable; si esa busqueda no existe aun, este spec deja la
  busqueda de notas como FALTA explicita» — dependencia explícita (regla b).
  Van en secuencia en ORDEN (7 y 8).

### Lote B7 — NO fusionado: reorg de Ajustes + reducir movimiento
- **Miembros:** `t-ajustes-reorg` (sonnet, 5) + `t-movimiento-contraste`
  (sonnet, 4). Mismo tema (página Ajustes).
- **Por qué NO se fusionan:** `t-movimiento-contraste` añade el ajuste
  «Reducir movimiento» «en Ajustes (grupo Apariencia, t-ajustes-reorg)» — el
  grupo Apariencia es obra del otro spec. Van en secuencia en ORDEN (23 y 26).

### Lote B8 — NO fusionado: reorg de Ajustes + BYOS visible
- **Miembros:** `t-ajustes-reorg` (sonnet, 5) + `t-byos-visible` (sonnet, 4).
  Mismo tema (página Ajustes: los 6 grupos reordenados; las filas de
  suscripción en «Modelos y suscripciones»).
- **Por qué NO se fusionan:** `t-byos-visible` coloca sus filas en la
  estructura que crea la reorg; además en ORDEN va ANTES (20) que la reorg
  (23), así que fusionar movería la reorg a la posición 20 y cambiaría el
  orden previsto del plan. Se dejan en secuencia.

### Lote B9 — NO fusionado: calculadora de paleta + teclado/foco
- **Miembros:** `t-calculadora-paleta` (sonnet, 4) + `t-teclado-foco`
  (sonnet, 5). Mismo tema (paleta Ctrl+K y teclado: cálculo aritmético en la
  paleta; Alt+1..8, lista de atajos con ?, flechas, foco visible, Esc).
- **Por qué NO se fusionan:** comparten solo la superficie (paleta/teclado),
  no un subsistema; `t-teclado-foco` depende del color de foco en oscuro
  «segun t-temas-oscuro-sistema» (Fase A, detenida); y no son adyacentes en
  ORDEN (24 y 33), así que fusionar reordenaría trabajo. Con el tope de 6
  fusiones se priorizaron lotes con más cohesión. Quedan en secuencia.

### Lote B10 — NO fusionado: motor OpenCode + verificar Groq/Gemini
- **Miembros:** `t-motor-opencode` (sonnet, 5) + `t-verificar-groq-gemini`
  (haiku, 4). Mismo tema (motores nuevos como descriptor genérico en
  `engines.json` v2 + credenciales en Credential Manager, con prueba corta
  real).
- **Por qué NO se fusionan:** son dos motores distintos con riesgos distintos
  (instalar OpenCode por vía oficial vs. llamadas reales a Groq y Gemini
  midiendo latencia/costo/límites); no comparten archivos más allá del
  esquema de descriptor. Con el tope de 6 fusiones se priorizaron lotes con
  más cohesión. Quedan en secuencia en ORDEN (13 y 15).

### Lote B11 — NO fusionado: memoria buscable + perfil «Sobre mí»
- **Miembros:** `t-memoria-buscable` (sonnet, 5) + `t-perfil-sobre-mi`
  (sonnet, 4). Mismo tema (memoria: búsqueda en MEMORY.md y notas; página
  «Sobre mí» que el runner inyecta en el prompt).
- **Por qué NO se fusionan:** cohesión moderada (leen/escriben archivos de
  memoria, pero son funciones distintas: buscar vs. perfil editable) y no
  adyacentes en ORDEN (7 y 9, con `t-notas-obsidian-030` entre medias, que
  depende de `t-memoria-buscable`). Con el tope de 6 fusiones se priorizaron
  lotes con más cohesión. Quedan en secuencia.

### Resto de Fase B — specs sueltos (sin lote)
Cada uno es un subsistema propio, sin compañero claro con el que compartir
archivos y contexto sin releer de más. Van solos, en su posición de ORDEN:
- `t-politicas-persistentes-030` (opus, 7) — politicas.json + editor + aprobación por paso.
- `t-router-fallbacks` (opus, 6) — cadena de fallbacks en engines.json.
- `t-dag-fases-030` (opus, 6) — depende_de / al_fallar por fase en SQLite.
- `t-rubrica-revisor-030` (opus, 5) — rúbrica fija del revisor + doble juez.
- `t-spike-whatsapp` (haiku, 4) — comparar Baileys / waeys / pyaileys en vivo.
- `t-catalogo-030` (sonnet, 4) — models-catalog.json con 7 modelos + instalación en orden. Depende de `t-semaforo-vram-v2` (Fase A); `t-embeddings-8081`, `t-evaluar-hermes4` y `t-vision-gemma3-4b` dependen de él, por eso no se fusionó con ninguno (su salida debe estar verificada antes).
- `t-embeddings-8081` (opus, 4) — segunda instancia llama-server en 8081. No se fusionó con nada anterior a `t-catalogo-030` (posición 11): depende del modelo instalado por el catálogo y fusionarlo antes lo dejaría como FALTA.
- `t-autocalibracion-vram` (sonnet, 4) — VRAM medida del log. Depende de `t-semaforo-vram-v2` y `t-ciclo-vida-llama` (Fase A).
- `t-transcribe-whisper` (sonnet, 5) — herramienta transcribe con faster-whisper; «depende de nada».
- `t-pedir-cosecha` (sonnet, 5) — botón «Pedir cosecha» (Apify por el puente).
- `t-comandos-script` (opus, 6) — carpeta comandos/ + paleta.
- `t-byos-visible` (sonnet, 4) — ver lote B8.
- `t-onboarding-fallos` (sonnet, 7) — planes A/B y salidas por rotura del onboarding.
- `t-carga-300ms` (sonnet, 5) — regla de 300 ms + esqueletos en las 5 páginas.
- `t-matriz-estados` (sonnet, 4) — matriz 6 páginas × 5 estados con evidencia por celda. Depende de `t-estados-vacios` y `t-estados-error` (Fase A, lote A1): los usa como checklist, no los reescribe; por eso va después del lote A1, en su posición.
- `t-automations` (opus, 5) — programador en SQLite + 5 automations. Depende de `t-gateway-unificado` y `t-memoria-pc` (Fase A).
- `t-panel-estado-gateway` (sonnet, 4) — pestaña Estado como panel. Depende de `t-gateway-unificado` (Fase A).
- `t-prueba-corte` (haiku, 4) — protocolo de prueba de corte + resiliencia.log.
- `t-voz-elevenlabs` (sonnet, 4) — ElevenLabs BYOK + contador de caracteres.
- `t-blender-herramienta` (sonnet, 4) — Blender como herramienta del runner (turntable + QC).

---

## Fase 040plus — manuales, sin cadena (12 specs)

Sin fusiones. Se documentaron los lotes; ninguno se fusionó (dependencias
cruzadas o criterios que suman más de 12, o cohesión insuficiente para el tope
de 6 fusiones). Se envían a mano, de uno en uno, en el orden del INDICE-040PLUS.

### Lote P1 — NO fusionado: canal WhatsApp + spike WhatsApp
- **Miembros:** `t-canal-whatsapp` (opus, 5, manual) + `t-spike-whatsapp`
  (haiku, 4, Fase B).
- **Por qué NO se fusionan:** `t-canal-whatsapp` implementa «la vía ganadora
  del spike» — depende del veredicto de `t-spike-whatsapp` (regla b), que
  además vive en otra fase y otra cadena. El canal se envía a mano solo
  cuando el spike esté verificado y Leandro haya decidido el número (ya
  decidido: su personal +58 414 5095810).

### Lote P2 — NO fusionado: agentes paralelos + paralelo seguro
- **Miembros:** `t-agentes-paralelos-030` (opus, 6) + `t-paralelo-seguro-030`
  (opus, 5). Mismo tema (paralelismo: orquestador con topes y worktrees;
  reglas de seguridad: máx. 2, sin solapes, merge explícito con test gate).
- **Por qué NO se fusionan:** `t-agentes-paralelos-030` referencia
  `t-paralelo-seguro-030` como base de sus reglas; el paralelo seguro es la
  red de seguridad sobre la que se apoya el orquestador. Además ambos son
  lógica de seguridad del runner (Opus) y cada uno merece su verificación
  propia. Van en secuencia manual.

### Lote P3 — NO fusionado: paralelo seguro + idempotencia/cuarentena
- **Miembros:** `t-paralelo-seguro-030` (opus, 5) +
  `t-idempotencia-cuarentena-030` (opus, 5). Mismo tema (seguridad de
  ejecución del runner: paralelismo sin pisarse; run_id + idempotencia_key +
  estado en_cuarentena).
- **Por qué NO se fusionan:** mecanismos distintos que solo comparten el
  tema «no perder ni duplicar trabajo»; `t-idempotencia-cuarentena-030`
  depende de `t-dag-fases-030` y `t-checkpoint-ronda-030`. Con el tope de 6
  fusiones y siendo ambos Opus de seguridad, quedan separados.

### Lote P4 — NO fusionado: brief de reunión + pendientes por persona
- **Miembros:** `t-brief-reunion` (sonnet, 4) + `t-pendientes-por-persona`
  (sonnet, 4). Mismo tema (resumen diario y memoria: brief de 30 segundos
  antes de la reunión; «qué falta por responder» por persona en el resumen
  de las 21:00).
- **Por qué NO se fusionan:** `t-brief-reunion` depende de
  `t-memoria-buscable` (Fase B) y `t-pendientes-por-persona` es una sección
  del resumen que también usa las tareas del runner; comparten fuentes pero
  no archivos a tocar. Con el tope de 6 fusiones se priorizaron lotes con
  más cohesión.

### Resto de 040plus — specs sueltos (sin lote)
- `t-claude-ai-custom-connector` (sonnet, 4) — primero resolver qué es
  «Muse.ai» antes de construir; si no se verifica, el spec se detiene y
  documenta la ambigüedad. Solo.
- `t-gadget-esp32` (opus, 4) — puerta USB/serie + protocolo mínimo + emulador.
  Solo.
- `t-mcp-streamable-http` (opus, 4) — diseño MCP + servidor en loopback +
  cliente + guardrail. Solo.
- `t-portapapeles` (sonnet, 5) — historial solo texto, 30 días, opt-in. Solo.
- `t-proxy-alquiler` (opus, 4) — túnel SSH por inquilino + alta/baja. Solo;
  bloqueado hasta fijar precio + tope + consulta legal (decisión de Leandro
  26 oct 2026: sin límite ni precio por ahora, solo entre conocidos).
- `t-proyectos` (opus, 5) — proyecto = tareas + chats + instrucciones +
  carpeta + guardrail; memoria por proyecto. Solo.

---

## Fase 045 — opus-tasks-045 (20 specs)

### Lote C1 — FUSIONADO: `t-lote-tarjetas-045`
- **Miembros:** `t-apis-tarjetas-045` (sonnet, 6 criterios) +
  `t-modelos-tarjetas-045` (sonnet, 6 criterios). Total 12 criterios,
  prompt 15.876.
- **Por qué van juntos:** la misma conversión a CustomTkinter con el mismo
  patrón en las dos páginas: tarjetas con esquinas 10 y colores de THEME,
  mismo comportamiento y manejadores, punto de estado + texto de estado real
  (nunca un verde inventado), respaldo clásico completo, foco de teclado
  visible, arranque medido, DPI 100% y 150%. Adyacentes en ORDEN (7 y 8).
  Ninguno menciona al otro.
- **ORDEN:** `t-lote-tarjetas-045` ocupa la posición de `t-apis-tarjetas-045`.

### Lote C2 — NO fusionado: secciones de Ajustes + matriz motor×permiso
- **Miembros:** `t-ajustes-secciones-045` (sonnet, 6) + `t-ajustes-matriz-045`
  (sonnet, 6). Mismo tema (página Ajustes en 0.4.5).
- **Por qué NO se fusionan:** `t-ajustes-matriz-045` dice «Depende de
  t-ajustes-secciones-045 (la pagina Ajustes ya tiene sus secciones)» —
  dependencia explícita (regla b). Van en secuencia en ORDEN (15 y 16).

### Lote C3 — NO fusionado: estadísticas de Tareas + detalle de tarea
- **Miembros:** `t-tareas-estadisticas-045` (sonnet, 6) +
  `t-tareas-detalle-045` (sonnet, 6). Mismo tema (página Tareas: fila de 3
  estadísticas + píldoras de filtro + tarea fijada; panel de detalle debajo
  de la tabla).
- **Por qué NO se fusionan:** `t-tareas-detalle-045` dice «Depende de
  t-tareas-estadisticas-045 (la tabla y sus filtros ya estan)» — dependencia
  explícita (regla b). Van en secuencia en ORDEN (4 y 10).

### Lote C4 — NO fusionado: detalle de tarea + compositor
- **Miembros:** `t-tareas-detalle-045` (sonnet, 6) + `t-tareas-compositor-045`
  (sonnet, 6). Mismo tema (página Tareas: detalle debajo de la tabla;
  compositor «Pedirle algo a Growi…» debajo del detalle).
- **Por qué NO se fusionan:** `t-tareas-compositor-045` dice «Depende de
  t-tareas-detalle-045 (el panel debajo de la tabla ya existe)» — dependencia
  explícita (regla b). Van en secuencia en ORDEN (10 y 11).

### Lote C5 — NO fusionado: compositor + campo Ctrl+K en Tareas
- **Miembros:** `t-tareas-compositor-045` (sonnet, 6) + `t-tareas-ctrlk-045`
  (sonnet, 6). Mismo tema (encolar desde Tareas: compositor con selector de
  motor; campo «Buscar o pedirle algo» en el encabezado).
- **Por qué NO se fusionan:** `t-tareas-ctrlk-045` encola «por el mismo camino
  de encolado del compositor (t-tareas-compositor-045)» — dependencia
  explícita del camino que construye el otro miembro (regla b). Van en
  secuencia en ORDEN (11 y 12).

### Lote C6 — NO fusionado: banner de nube + mapa de Estado
- **Miembros:** `t-estado-banner-nube-045` (sonnet, 6) + `t-estado-mapa-045`
  (haiku, 6). Mismo tema (página Estado: banner según el modelo real del
  runner; botón «Ver el mapa» con scroll + resaltado).
- **Por qué NO se fusionan:** comparten solo la página Estado; los mecanismos
  son distintos (probe conn_state fiel al runner vs. desplazamiento y
  resaltado de una tarjeta). Con el tope de 6 fusiones se priorizaron lotes
  con más cohesión. Adyacentes en ORDEN (2 y 3), van en secuencia.

### Lote C7 — NO fusionado: Carpetas CTk + onboarding CTk
- **Miembros:** `t-carpetas-ctk-045` (sonnet, 6) + `t-onboarding-piel-045`
  (sonnet, 6). Mismo tema (conversión a CustomTkinter con el patrón del
  piloto: respaldo clásico, foco, arranque medido, DPI).
- **Por qué NO se fusionan:** no son adyacentes en ORDEN (6 y 9, con el lote
  C1 entre medias) y cada conversión es autocontenida; el patrón ya está
  probado por el piloto, así que juntarlas añade poco. Con el tope de 6
  fusiones se priorizó el lote C1. Van en secuencia.

### Lote C8 — NO fusionado: tarjetas de Estado + consistencia de estado
- **Miembros:** `t-estado-tarjetas-045` (sonnet, 6) +
  `t-estado-consistencia-045` (sonnet, 6). Mismo tema (página Estado).
- **Por qué NO se fusionan:** `t-estado-consistencia-045` impone una única
  fuente de verdad y reescribe de dónde lee el banner («el banner queda
  leyendo del estado unico, no de la sonda directa») — depende de que las
  tarjetas y el banner existan primero. Van en secuencia en ORDEN (13 y 19).

### Lote C9 — NO fusionado: detalle de tarea + solape de la mascota
- **Miembros:** `t-tareas-detalle-045` (sonnet, 6) + `t-mascota-solape-045`
  (sonnet, 6). Mismo tema (el botón de cerrar del detalle tapado por la
  mascota al hacer scroll).
- **Por qué NO se fusionan:** `t-mascota-solape-045` dice «Depende de
  t-tareas-detalle-045 (el detalle con su boton de cerrar ya existe)» —
  dependencia explícita (regla b). Van en secuencia en ORDEN (10 y 17).

### Lote C10 — NO fusionado: mapa de Estado + tarjetas de Estado
- **Miembros:** `t-estado-mapa-045` (haiku, 6) + `t-estado-tarjetas-045`
  (sonnet, 6). Mismo tema (página Estado).
- **Por qué NO se fusionan:** `t-estado-tarjetas-045` dice que la tarjeta
  del mapa «conserva el comportamiento de resaltado de t-estado-mapa-045»
  — depende de que el resaltado exista primero (regla b). Van en secuencia
  en ORDEN (3 y 13).

### Resto de 045 — specs sueltos (sin lote)
- `t-tokens-raycast-045` (sonnet, 6) — tokens Raycast oscuros en THEME. Base
  de toda la 0.4.5; va primero (posición 1) y solo.
- `t-barra-lateral-045` (sonnet, 6) — barra fija de 232 px + contadores +
  medidor de consumo + tarjeta de guardrail. Solo.
- `t-historial-gasto-045` (sonnet, 6) — JSON diario de gasto + total
  acumulado + tabla por día. Solo.
- `t-recursos-graficos-045` (sonnet, 6) — selector de rango + gráficos de
  línea CPU/memoria + tarjetas de métrica. Solo.
- `t-auditoria-045` (haiku, 6) — auditoría final de las 5 pantallas a 100% y
  150% DPI con puntuación sobre 100. «Depende de los 19 specs anteriores de
  la 0.4.5» y «no reconstruye pantallas: audita, mide y reporta». Va último
  (posición 20) y solo, por definición.

---

## Fase 050 — opus-tasks-050 (19 specs, incluido t-qa-final-050)

### Lote D1 — FUSIONADO: `t-lote-live-050`
- **Miembros:** `t-oficina-cola-live-050` (sonnet, 6 criterios) +
  `t-oficina-consumo-vivo-050` (sonnet, 6 criterios). Total 12 criterios,
  prompt 16.622.
- **Por qué van juntos:** la capa viva que el runner publica para la oficina:
  `cola-live.json` (snapshot de la cola: guardrail, pendientes, por tarea
  id/estado/motor/ronda/…) y `runner-live.json` (tarea en curso cada ~5 s:
  task_id, motor, modelo, tokens, costo estimado). Mismo patrón en los dos:
  publicación por el runner, escritura atómica (tmp + renombrar), parseo
  tolerante en la oficina, honestidad de datos («sin dato», nunca 0 ni
  porcentaje inventado). Adyacentes en ORDEN (2 y 3). Ninguno menciona al
  otro.
- **ORDEN:** `t-lote-live-050` ocupa la posición de `t-oficina-cola-live-050`.

### Lote D2 — NO fusionado: mediciones + decisión de motor
- **Miembros:** `t-oficina-mediciones-050` (haiku, 6) + `t-oficina-motor-050`
  (opus, 6). Mismo tema (elegir Godot o Pygame-ce con cifras reales).
- **Por qué NO se fusionan:** `t-oficina-motor-050` dice «Lee
  ESTADO-t-oficina-mediciones-050.md y aplica» — lee primero el ESTADO del
  otro miembro (regla b, caso literal). Van en secuencia en ORDEN (1 y 6).

### Lote D3 — NO fusionado: arte base + skins (paper doll)
- **Miembros:** `t-oficina-arte-base-050` (opus, 7) + `t-oficina-skins-050`
  (opus, 7). Mismo tema (arte pixel de la oficina: paleta global de 24
  colores + esqueleto 32×48 + Gerente Growi; sistema paper doll + skin.json
  + 4 líderes).
- **Por qué NO se fusionan:** 7 + 7 = 14 criterios > 12 (regla e). Además
  `t-oficina-empleados-050` depende de los dos («esqueleto comun y sistema
  paper doll»), así que cada uno debe quedar verificado por separado antes.
  Van en secuencia en ORDEN (9 y 10).

### Lote D4 — NO fusionado: teléfono + llamadas
- **Miembros:** `t-oficina-telefono-050` (sonnet, 6) +
  `t-oficina-llamadas-050` (sonnet, 6). Mismo tema (llamar por teléfono en
  la oficina: UI del teléfono + animación de llamada por departamento).
- **Por qué NO se fusionan:** `t-oficina-llamadas-050` dice «Depende de
  t-oficina-telefono-050 (la llamada nace del telefono)» — dependencia
  explícita (regla b). Van en secuencia en ORDEN (12 y 13).

### Lote D5 — NO fusionado: encolar externo + teléfono
- **Miembros:** `t-oficina-encolar-externa-050` (opus, 6) +
  `t-oficina-telefono-050` (sonnet, 6). Mismo tema (encolar desde fuera de
  la app: función importable o endpoint loopback; el teléfono usa esa
  función).
- **Por qué NO se fusionan:** `t-oficina-telefono-050` dice «Depende de
  t-oficina-encolar-externa-050 (sin encolado externo no hay telefono real)»
  — dependencia explícita (regla b). Van en secuencia en ORDEN (4 y 12).

### Lote D6 — NO fusionado: plano + paseo
- **Miembros:** `t-oficina-plano-050` (sonnet, 6) + `t-oficina-paseo-050`
  (opus, 6). Mismo tema (moverse por la oficina: plano.json con
  departamentos/mesas/sillas/rejilla; caminar con WASD/clic + proximidad +
  hablar con agentes).
- **Por qué NO se fusionan:** `t-oficina-paseo-050` camina «segun plano.json»
  y usa sus obstáculos y puntos de interés — depende de la salida del otro
  miembro (regla b). Van en secuencia en ORDEN (7 y 14).

### Lote D7 — NO fusionado: estados + bocadillos
- **Miembros:** `t-oficina-estados-050` (opus, 7) + `t-oficina-bocadillos-050`
  (sonnet, 6). Mismo tema (lo que se ve en la oficina: derivar_estado() con
  24 transiciones; bocadillos encima del sprite).
- **Por qué NO se fusionan:** `t-oficina-bocadillos-050` dice «Depende de
  t-oficina-estados-050 (los bocadillos de estado salen de transiciones
  reales)» — dependencia explícita (regla b). Además 7 + 6 = 13 criterios >
  12 (regla e). Van en secuencia en ORDEN (8 y 16).

### Lote D8 — NO fusionado: rendimiento + ciclo de vida (cierre)
- **Miembros:** `t-oficina-rendimiento-050` (opus, 6) +
  `t-oficina-ciclo-vida-050` (opus, 6). Mismo tema (vida de la oficina:
  presupuestos + escalera de degradación + dormida; abrir/cerrar, heartbeat,
  autocierre, modo demo).
- **Por qué NO se fusionan:** `t-oficina-ciclo-vida-050` cierra la 0.5.0 y su
  criterio 6 dice «el ESTADO revisa que los 17 specs anteriores dejaron su
  ESTADO» — fusionarlo cambiaría la cuenta (los 17 anteriores serían 16) y
  el cierre debe quedar como spec propio y último. Van en secuencia en ORDEN
  (17 y 18, las dos últimas posiciones de la cadena).

### Lote D9 — NO fusionado: protocolo + decisión de motor
- **Miembros:** `t-oficina-protocolo-050` (opus, 6) + `t-oficina-motor-050`
  (opus, 6). Mismo tema (motor de la oficina: prototipo Pygame-ce que lee los
  JSON vivos; decisión Godot vs Pygame-ce fijada por escrito).
- **Por qué NO se fusionan:** `t-oficina-protocolo-050` deja anotado «qué
  falta para pasar este protocolo a Godot (o quedarse en Pygame-ce si el
  spec 6 lo decide)» — la decisión es del otro spec y el prototipo no debe
  decidirse a sí mismo en la misma sesión. La decisión queda separada del
  prototipo. Van en secuencia en ORDEN (5 y 6).

### Lote D10 — NO fusionado: llamadas + paseo
- **Miembros:** `t-oficina-llamadas-050` (sonnet, 6) + `t-oficina-paseo-050`
  (opus, 6). Mismo tema (interacción en la oficina: llamar a un departamento;
  caminar y hablar con un agente).
- **Por qué NO se fusionan:** comparten la escena pero son mecanismos
  distintos (lanzamiento real del motor + timbre/espera vs. movimiento,
  pathfinding y tabla por estado al hacer clic). Con el tope de 6 fusiones se
  priorizaron lotes con más cohesión. Adyacentes en ORDEN (13 y 14), van en
  secuencia.

### Resto de 050 — specs sueltos (sin lote)
- `t-oficina-mediciones-050` (haiku, 6) — medir C1/C2/C3 + respaldo Pygame-ce.
  Ver lote D2. Va primero (posición 1) y solo.
- `t-oficina-encolar-externa-050` (opus, 6) — ver lote D5. Solo.
- `t-oficina-protocolo-050` (opus, 6) — ver lote D9. Solo.
- `t-oficina-motor-050` (opus, 6) — ver lotes D2 y D9. Solo.
- `t-oficina-plano-050` (sonnet, 6) — ver lote D6. Solo.
- `t-oficina-estados-050` (opus, 7) — ver lote D7. Solo.
- `t-oficina-arte-base-050` (opus, 7) — ver lote D3. Solo.
- `t-oficina-skins-050` (opus, 7) — ver lote D3. Solo.
- `t-oficina-empleados-050` (sonnet, 8) — los 9 empleados por recoloreado +
  Runa + coordinador nocturno. 8 criterios: no se puede fusionar con ningún
  otro spec de 050 (todos tienen 6 o más; 8+6=14 > 12). Depende de arte-base
  y skins. Solo.
- `t-oficina-telefono-050` (sonnet, 6) — ver lotes D4 y D5. Solo.
- `t-oficina-llamadas-050` (sonnet, 6) — ver lotes D4 y D10. Solo.
- `t-oficina-paseo-050` (opus, 6) — ver lotes D6 y D10. Solo.
- `t-oficina-vagancia-050` (opus, 7) — 5 reglas de hierro + sistema de
  utilidad + 8 actividades + frases. 7 criterios: con cualquier otro spec de
  050 sumaría 13 o más. Depende de estados y skins. Solo.
- `t-oficina-bocadillos-050` (sonnet, 6) — ver lote D7. Solo.
- `t-oficina-rendimiento-050` (opus, 6) — ver lote D8. Solo.
- `t-oficina-ciclo-vida-050` (opus, 6) — ver lote D8. Solo; cierra la 0.5.0.
- `t-qa-final-050` (haiku, 6) — QA final manual de TODA la app (0.3.0,
  0.4.0, 0.4.5 y 0.5.0) con clics reales. No va en ninguna cadena. Solo, por
  definición.

---

## Validación (27 oct 2026, en VM)

- `json.load` de los 95 originales + los 6 fusionados nuevos: OK (101 archivos).
- ORDEN consistente: cada id de ORDEN existe como `*.task.json` en su carpeta;
  sin duplicados; ningún ORDEN referencia un spec inexistente; los 12 miembros
  fusionados siguen existiendo como archivos pero ya NO están en ORDEN.
- Criterios preservados: cada fusionado tiene exactamente la concatenación de
  los criterios de sus miembros (misma cantidad y mismo texto, verificada
  contra los originales).
- Tope diario intacto: `TOPE_DIARIO_USD = 40.0` y `gasto_hoy_usd` presentes en
  los 4 scripts; `diff` contra backup muestra que solo cambiaron líneas de
  ORDEN; `python3 -m py_compile` OK en los 4 scripts.
- Bloque `MODO NO-INTERACTIVO`: aparece exactamente UNA vez al inicio de cada
  prompt fusionado (verificado por conteo).
- Prompts fusionados < 30.000 caracteres y criterios ≤ 12 en los 6 lotes.

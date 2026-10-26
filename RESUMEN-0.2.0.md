# Growi Bridge — Alpha 0.2.0

## Resumen de todo lo que tenemos y lo que se logró

**25 de octubre de 2026, noche (00:55 – 01:30). Leandro Gzn.**

---

## Esta noche dejó la 0.2.0 con la investigación hecha, la extensión lista y cuatro tareas en cola — y un puente caído que hay que levantar en la mañana

Leandro se fue a dormir a las 00:56 y dejó tres horas de trabajo con una orden clara: investigar a fondo, decidir, y dejar la versión Alpha 0.2.0 lista con un PDF al final. Esto es lo que quedó.

Lo que sí se logró: la investigación completa (12 hilos, 673 líneas), la extensión de navegador construida y verificada por Opus, la visión escrita con cinco decisiones, y cuatro tareas de desarrollo listas para mandar. Lo que no se logró: instalar el build 2 en el PC. El install mató al puente a la 01:14 y la app no volvió a levantar. El PC quedó sin app hasta que Leandro la reinicie en la mañana.

Ese es el único atasco de la noche. Todo lo demás está hecho y guardado. Y el atasco tiene arreglo en dos minutos, con los pasos escritos al final de este documento.

---

## Lo que se logró: 12 hilos, una extensión que funciona y la visión escrita

### La investigación: 12 referentes en una noche

Un coordinador con 12 subagentes investigó en paralelo y dejó `INVESTIGACION-0.2.0.md`: 673 líneas, unas 77 KB, solo con búsqueda web y lectura de fuentes oficiales. Nada se probó en vivo en el PC salvo donde se indica. Los 12 hilos: Raycast, Ollama, OpenClaw, TokenBar/OhNine, AirJelly, ClippyAI, MCP, multi-CLI y multi-asistente, onboarding, Venezuela primero, UI/UX de escritorio, y el inventario de conectores que ya tenemos.

Tres hallazgos cambiaron el plan. Primero: la app Muse.ai de consumo no documenta ninguna forma de añadir un servidor MCP (verificado contra las páginas de Meta; Muse Code sí lo soporta). La integración con Muse va por Custom Connector contra API REST, y va en 0.3.0, no en 0.2.0. Segundo: Raycast ya está en beta pública para Windows desde noviembre de 2025 — Bridge compite contra el propio Raycast, no contra un hueco vacío. Tercero: Gemini sí lista a Venezuela en su API oficial. Es la segunda nube, no OpenAI, que no lista al país.

El inventario de conectores también corrigió un dato: Tripo tiene 370 créditos, no 970 como decía la memoria del 19 de octubre. Se gastaron unos 600. Quedan unos $3,70. Las generaciones de la biblioteca de modelos hay que contarlas.

### La extensión de navegador: construida y verificada

Opus construyó la extensión en 672 segundos (11 minutos), 35 turnos, $2,57. Chrome MV3 con servidor local en 127.0.0.1:8788, solo librería estándar, secreto del puente en cada petición. Ocho comandos: ver pestañas, leer una pestaña, navegar, hacer clic, escribir, abrir pestaña, cerrar pestaña y capturar pantalla.

Verificado en el PC: `py_compile` sin errores, `node --check` de los tres archivos JavaScript sin errores, `/ping` con secreto devuelve 200 y sin secreto 403, el servidor solo escucha en 127.0.0.1 (no en 0.0.0.0), y un comando sin extensión conectada devuelve "extension no conectada" a los 60 segundos. El secreto no aparece en ninguno de los 13 archivos revisados.

Falta lo manual: cargar la extensión en Chrome (modo desarrollador, "Cargar descomprimida") y pegar el secreto en su popup. Eso lo hace Leandro al despertar. La extensión queda lista para instalar en el Bridge, como pidió.

### La visión: cinco decisiones

`VISION.md` deja por escrito la app completa. La frase que la resume: el compañero de escritorio que deja que un venezolano use IA de verdad. Las cinco decisiones: el proxy es el producto (Venezuela primero); la paleta Ctrl+K es el centro; orquestación con revisión automática (un motor barato revisa contra criterios, máximo 3 rondas de corrección o avanzar de fase); un corredor con muchos motores descritos por JSON; y el gasto visible en la bandeja (un solo número, tres dineros siempre separados: $ real, $ equivalente de Max, $0 local).

### Cuatro tareas de desarrollo listas para mandar

Quedaron escritos y guardados cuatro specs de Opus, listos para enviar al PC en cuanto vuelva el puente: Modelos (librería local Ollama + APIs + fusión con OpenClaw + "Comprobar mi PC" + semáforo por VRAM), Orquestación (motores por JSON + revisión automática + rondas + fases + aprobación humana), Extensión–subida (el comando `tab.upload` para subir archivos desde el PC, caso Leonardo), y Onboarding–Venezuela (4 pasos + proxy central + mapa de disponibilidad + gasto en bandeja + DPI). En ese orden.

---

## Lo que se atascó: el install mató al puente a la 01:14 y el PC quedó sin app

El build 2 (3.226 líneas, 48 fotogramas de mascota sobre magenta, icono de bandeja transparente, 5 marcadores: MASCOT_SIZE, _run_ollama, OLLAMA_MODEL, _open_palette, _send_ask) llevaba dos intentos fallidos. El primero hizo rollback silencioso al build 1. El segundo (fix v1) paró correctamente: el archivo del Inbox tenía 3.226 líneas y no las 3.170 que esperaba, por el arreglo de la bandeja que se sumó después.

El tercer intento (fix2, enviado a la 01:11) corrigió el control: verificar los 5 marcadores, no el número de líneas. Llegó al paso de reiniciar la app. Ahí murió el puente.

La app es el servidor del puerto 8787. Al matarla para reiniciarla, el puente cayó con ella. El build 2 no volvió a levantar: último heartbeat 01:10:42, pid 27568, sin resultado del task, sin archivo de verificación, y el puente sigue dando "conexión cerrada sin respuesta" a las 01:21, pasado el timeout de 10 minutos. El archivo compila sin errores en la VM y los imports opcionales (tkinterdnd2, pystray, keyboard) tienen su try/except, así que no es un error de sintaxis ni un módulo faltante. Lo más probable: el reinicio mató también al proceso de Claude que ejecutaba el task (árbol de procesos) y la app nueva no arrancó, o el reinicio no se completó.

No hay forma de recuperar el PC desde la VM. El puente es la única vía de archivos y el runner la única vía de comandos. No hay SSH ni WinRM al PC. El PC no se apagó: no había forma de apagarlo sin el runner, y apagarlo sin la app levantada no arreglaba nada.

La lección quedó anotada: instalar matando al runner es frágil. El próximo install lo hace la app misma (auto-restart) o no mata al proceso que ejecuta el task. Va en el roadmap de 0.3.0.

---

## La visión: un venezolano puede usar IA porque el proxy es el producto

Claude y ChatGPT están bloqueados en Venezuela. Anthropic lista 185 países y Venezuela no está. OpenAI tampoco la lista. Por eso la app existe: para que un venezolano pueda usar IA.

El proxy propio (tinyproxy en el VPS 2.25.244.222:18080, $0 porque el VPS ya está pago) pasa de ser un ajuste a ser función central: onboarding de un clic ("Conectar"), estado en la bandeja (verde conectado, ámbar local, rojo sin conexión), cambio automático a Ollama local si cae, y mapa de disponibilidad con chequeos reales (Claude, ChatGPT, Gemini, Ollama local, proxy, internet). Y la app dice en voz alta el riesgo: usar Claude vía proxy puede suspender la cuenta; la vía sin ese riesgo es la API con clave propia o un modelo local. Por eso lleva botón de exportar conversaciones.

Offline-first no es un detalle: CANTV da 10/5 Mbps y los cortes de luz duran 4–6 horas. Cola de tareas en SQLite que sobrevive a apagones, reintentos con backoff, sync por diferencia (nunca re-subir un archivo entero), modelos locales como respaldo. Gasto $0 o mínimo: Max ya pagada + Ollama local + Tailscale personal + VPS existente.

La fusión, en una línea por referente: de Raycast, la paleta y su gramática; de Ollama, los modelos locales con semáforo por VRAM; de OpenClaw, un asistente con muchos canales y memoria en Markdown; de TokenBar, el gasto en un número; de AirJelly, la proactividad con freno (máximo 1 aviso al día); de ClippyAI, el plan visible con aprobación antes de lo irreversible. Lo que no se copia: ser lanzador general de Windows, Store de extensiones, mirar la pantalla siempre, cobrar por tokens, ni prometer que el proxy hace el uso "seguro".

---

## Qué entra en la 0.2.0 y qué queda fuera

Entra, en orden: (1) instalar el build 2 corregido y verificarlo; (2) pestaña Modelos; (3) extensión de navegador (+ `tab.upload`); (4) paleta Ctrl+K pulida; (5) proxy central + mapa de disponibilidad; (6) gasto visible en la bandeja; (7) cola persistente en SQLite + reintentos; (8) revisión automática del runner; (9) DPI y reglas P0 de UI/UX; (10) GitHub como canal de distribución (release + auto-update).

Queda fuera, y por qué: MCP por HTTP (fase 2; stdio basta para 0.2.0); integración con Muse.ai (no hay MCP documentado; Custom Connector en 0.3.0); Store de extensiones (sin usuarios no tiene sentido); alquiler del proxy ($2,50/mes: falta costear el VPS, resolver que BasicAuth viaja sin cifrar y resolver el cobro en Venezuela); Meshy como segundo generador 3D (Tripo basta; Meshy tiene $0 de saldo); mascota con más estados; lector de pantalla completo; descarga de modelos en segundo plano.

Solo tres conectores van dentro de la app: GitHub (distribución y releases), Tripo (generación 3D de la biblioteca) y Mobbin (referencia de diseño en desarrollo). Todo lo demás (Apify, Bright Data, Gemini, ElevenLabs, Resend, Hayai Space, Hostinger, Railway, Descript, Zenmux, Anthropic) lo usa solo el asistente desde la VM: llevan credenciales, gastan créditos o son sistemas internos. Meterlos en una app distribuida por GitHub expondría credenciales y costos.

---

## La interfaz: 62 de 100, y ya se sabe qué arreglar

Un revisor experto pasó el build 2 por la skill anti-vibe, las reglas P0 de la investigación y las notas de Mobbin. Auditoría anti-slop: **62/100**. El build tiene dirección real (brief, tokens con nombre, Mobbin con respaldo, mascota reactiva, sin gradientes ni datos inventados). Pero los dos tells de plantilla más reconocibles están en todas las páginas, el DPI no está resuelto y la paleta no tiene la gramática que promete.

Los cinco problemas graves, en orden de arreglo: (1) **DPI**: `tk scaling` solo agranda las fuentes; toda la geometría es fija (ventana 940×680, paleta 520×320, barra lateral 220 px) y a 150% el pie de la barra lateral desborda (necesita ~205 px, hay 188). Falta un factor SCALE = dpi/96 aplicado a cada medida. (2) **Paleta Ctrl+K**: filtro por subcadena (sin difusa), sin favoritos ni frecuentes al abrir, sin atajos por fila, sin acciones secundarias, sin rojo para lo destructivo, sin fallback a la IA — y Ctrl+K dos veces abre una segunda paleta encima. (3) **Cerrar por sorpresa**: la X minimiza a la barra de tareas y dispara el toast "sigue corriendo" cada vez; no hay ajuste "al cerrar: minimizar/salir". (4) **Olor a plantilla en el texto**: 14 "·" (meta-strings "A · B · C", 8 visibles) y 6 etiquetas de sección en MAYÚSCULAS de 9 px. (5) **Contraste**: verde #248A3D 4,40:1 y azul #007AFF 4,02:1 no llegan a 4,5:1; los valores correctos son #1F7A33 (5,40:1) y #0066CC (5,57:1).

Los cinco aciertos: la identidad la carga la foto de Growi; la mascota es reactiva, no ambiental; sin gradientes, sin stock, sin datos inventados; navegación de verdad estilo Mac con respaldo Mobbin; las acciones destructivas piden confirmación y el inicio automático es opt-in. Con los 4 P0 corregidos el build subiría a ~80. El informe completo (tabla P0/P1/P2 con archivo, línea y arreglo concreto) está en `REVISION-UIUX-0.2.0.md`.

---

## El camino: 0.3.0 y el gadget

En 0.3.0: servidor MCP por HTTP en localhost + cliente MCP, integración con Muse.ai por Custom Connector (o Muse Code como cliente), Codex como segundo motor, descarga de modelos en segundo plano, túnel cifrado para el proxy, panel de alquiler del proxy (si se costea), mascota con más estados, atajos personalizables, comandos de IA guardados y "¿qué me falta por responder?" por persona.

Más allá: el gadget físico ESP32 con el Muse Gadget SDK (firmware + SDK Linux, Apache 2.0). La app deja la puerta abierta a la conexión local por USB/serial; el hardware se construye después, con plaquitas baratas traídas de China. Lo que se construye ahora es el terreno en software para que la gente conecte esa plaquita a su PC. También quedan para después: Store de extensiones propio (solo con usuarios suficientes), WhatsApp como canal del asistente, memoria con búsqueda vectorial y soporte completo de lector de pantalla.

---

## Lo que no está verificado

Doce dudas quedaron marcadas en la investigación, y ninguna se promete como hecho: Gemini en Venezuela desde IP venezolana (la lista oficial lo incluye, el comportamiento real no está probado); pago del Max con tarjeta venezolana; cuota restante de Max (no hay API pública); Hermes 3 8B en la RTX 3060 de 6 GB con contexto útil (las fuentes dicen que pide ~8 GB de VRAM; solo una prueba en el PC lo confirma); reanudación de `ollama pull` con un corte real; acceso a registry.ollama.ai y Hugging Face desde Venezuela sin proxy; costo mensual del VPS y cómo cobrar el alquiler del proxy; implicaciones legales de alquilar el proxy; Raycast (paridad Windows/Mac, plan Free, tool-calling con Ollama); OpenClaw (Windows nativo vs WSL2); multi-CLI (Gemini CLI, Grok Build en Windows, flags de Meshy, Copilot CLI); MCP (si el SDK Python v2 renombró FastMCP); Bright Data (sin zonas activas no sirve).

---

## Próximos pasos

1. **Leandro, al despertar (25 oct, mañana):** doble clic en `C:\Users\forte\growi-bridge\iniciar-growi-bridge.bat` (o reiniciar el PC: la tarea programada GrowiBridgeApp arranca la app al iniciar sesión). Esto levanta la app y el puente.
2. **Growi, al volver el puente:** verificar el install del build 2 (5 marcadores + prueba Ollama) y confirmar qué build corre. Si el build 2 no quedó instalado, reinstalar con el fix2 ya preparado.
3. **Growi, después:** mandar los cuatro tasks de Opus en orden (Modelos → Orquestación → Upload → Onboarding–Venezuela), verificar cada uno, y publicar la release Alpha 0.2.0 en GitHub (`leandrogzn98-hash/growi-bridge`).
4. **Leandro, después:** cargar la extensión en Chrome (modo desarrollador → "Cargar descomprimida" → `C:\Users\forte\growi-bridge\browser\extension\`) y pegar el secreto en su popup. Luego Growi prueba `tabs.list` y `tab.upload` en Leonardo con una imagen real.

Responsable de los pasos 2 y 3: Growi. Responsable de los pasos 1 y 4: Leandro.

---

*Fuentes: `INVESTIGACION-0.2.0.md` (12 hilos, tabla de fuentes al final), `VISION.md`, resultados del runner en `~/workspace/shared/inbox/runner-results/`, repo `leandrogzn98-hash/growi-bridge` (último commit 6f1c9f6). Firmado: Leandro Gzn.*

---

## Estado a 25 oct 11:24 (después del apagón)

Lo que se hizo en la mañana del 25 oct, verificado en vivo:

- **Pestaña Modelos (Opus, 29 min, $8,60):** Hermes 3 8B listado (naranja, ~93% VRAM), catálogo de 20 modelos con semáforo, "Comprobar mi PC", conexiones API con botón Probar. Instalada en la raíz (5.021 líneas).
- **Hermes 3 sin Ollama:** llama-server instalado (GGUF en `growi-bridge\models\`, puerto 8080, ~61 tok/s, 33/33 capas en GPU). Leandro desinstala la app de Ollama a mano; falta verificar que llama-server siga respondiendo después.
- **Orquestación (Opus, 27 min, $7,98):** motores por JSON, revisión automática con Hermes, rondas máx. 3, fases encadenadas, botón Parar real, aprobación por tarea. 20 comprobaciones + 6 verificaciones. Sin probar de verdad: Codex, Meshy, revisión con Haiku.
- **Vigilante del puente (sonnet, 6 min, $0,38):** frames working v4 (tapa + logo "growi") en `mascot\`, tarea programada cada 3 min, ya corrió sola con "ok". Reinicio real sin probar.
- **Mascota working v4:** tapa gris oscura con solo el logo "growi" blanco en minúsculas; la cara es la correcta (sin nariz). El set v3 (pantalla con código) quedó descartado por Leandro.
- **Extensión de navegador v1:** cargada en Chrome por Leandro (ID `abooohjmpggblaghehhajgkpndalppcm`); icono genérico, fix pendiente de su OK.

Lo que queda en la cola (specs escritos y validados, listos para enviar cuando vuelva la luz):

1. **Arreglo mascota + icono (sonnet, 30 min):** el cuadro blanco sale sobre todo al mover la mascota (la ventana queda en 192×192 y su fondo no es magenta); el icono de la barra falla por iconbitmap silencioso + iconphoto que lo pisa + falta AppUserModelID.
2. **Consumo en vivo (Opus, 60 min):** ver por tarea y por modelo cuánto se va gastando mientras trabaja, no solo al terminar.
3. **Router automático (Opus, 60 min):** opción "Automático (recomendado)" en "Quién responde" que elige el motor más eficiente según la petición (reglas, $0, con motivo visible).
4. **Upload de archivos para la extensión (Opus, 45 min):** comando `tab.upload` (subir a Leonardo.ai y otros).
5. **Onboarding + Venezuela primero (Opus, 60 min)** y **Monitor de recursos (Opus, 60 min)**.
6. **Release Alpha 0.2.0 en GitHub.** Ojo: el auto-update está activado; no publicar ninguna versión sin estos cambios antes de la 0.2.0.

**Apagón 25 oct 11:21:** se fue la luz en casa de Leandro. PC y puente caídos; el diagnóstico de la mascota se perdió (hay que sustituirlo por el task de arreglo, ya escrito). Nada de los specs se perdió: todo vive en `~/workspace/shared-bridge/opus-tasks/`.

---

## Estado a 25 oct 20:26 (cola 0.2.0 en curso, 3/9)

La luz volvió y la cola corre desde las 18:54 (guardrail en «Hazlo sin preguntar» desde las 18:53, tras 1,5 h perdida en espera de aprobación). Orden real LIFO (la última que entra corre primero). Costo acumulado de la cola: **$20,47**.

- **Cola SQLite (Opus, 19 min, $5,04):** terminada 19:32, revisión aprobada. La cola vive en `cola.db`, no en archivos sueltos.
- **Pulir paleta (Opus, 17 min, $5,17):** terminada 19:32. Revisión de la paleta de la app.
- **Monitor de recursos (Opus, 54 min, $10,26, 177 turns):** terminado 20:25, revisión aprobada. Pestaña Recursos con 4 tarjetas vivas (CPU, RAM, GPU con VRAM por nvidia-smi, disco libre) + Mis procesos con columna «Lanzado por» + cerrar proceso con confirmación (críticos de Windows bloqueados, incluido wininit). 26/26 verificaciones a 100 % y 150 %, regresión de paleta 28/28. La app instalada sigue con el código viejo hasta reiniciar. OJO: la copia de prueba escuchó en el 8787 ~30 s a las 20:22 (Windows deja compartir el puerto) — fallo preexistente del puente, sin daño observado.
- **Onboarding + Venezuela primero (Opus, 60 min):** en curso desde ~20:25.

Quedan en la cola (LIFO): upload de la extensión, router automático, consumo en vivo, arreglo mascota + icono, diagnóstico de la mascota (haiku, ~10 min). ETA ~22:00–22:30 con el PC encendido.

Después de la cola: **segundo carril** (`t-dos-carriles-020`, spec escrito 20:10, opus 60 min) y luego la **Fase A 0.3.0** (30 specs, plan de envío en `opus-tasks-030/PLAN-ENVIO-FASE-A.md`, uno por uno con verificación; bloqueados #2 aprobación-WhatsApp y #19 relay-ssh). Las 7 skills semilla (prerrequisito del spec #8) ya están listas en la VM desde las 20:25 (76.086 bytes, 0 FALTA, 24 huecos reales marcados `[PENDIENTE: dato]`).

También hoy (fuera de la cola): investigación 0.5.0 oficina de agentes entregada 19:59 (860 líneas, 18 specs) + paleta «Oficina Growi» y 5 sprites de prueba propuestos 20:19 (pendiente el OK de Leandro al estilo). Y en Aqualine: PR #5 mergeado a producción ~20:30 (rediseño + reconciliación main → dev, merge `f21def47`, producción sana).

---

## Estado a 25 oct 21:41 (cola 0.2.0: 6/9, $34,29)

- **Onboarding + Venezuela primero (Opus, 26,5 min, $7,96, aprobada):** configuración inicial de 4 pasos + capa Venezuela primero + estado del proxy en barra/bandeja + mapa de disponibilidad con chequeos reales (Claude y ChatGPT bloqueados desde Venezuela, responden con el proxy). Cuota Max «no disponible» (Anthropic no publica forma oficial de leerla). **AVISO: al abrir la app sale la configuración inicial una vez — si en el paso 3 se pulsa Siguiente con el nivel por defecto, el guardrail pasa de «Hazlo sin preguntar» a «Preguntarme siempre»; para mantenerlo, «Saltar por ahora».**
- **Upload de la extensión (Opus, 9,2 min, $2,49, aprobada):** `tab.upload` hecho (endpoint GET /file con secreto, DataTransfer + change, sin clic en el input). Verificado sin Chrome real; NO probado en Leonardo ni en Chrome de verdad. El servidor espera hasta 60 s si el archivo aún no llegó al inbox; máximo 20 MB. El agente escribió su propia versión (los archivos del PC no coinciden con el borrador de Growi en la VM) — no está confirmado que el borrador ahorrara tiempo.
- **Router automático (Opus, 12,7 min, $3,37, aprobada):** «Automático (recomendado)» primera opción del desplegable; reglas en `engines.json` (3D → Meshy, arquitectura/investigación larga → Opus, código → Sonnet, pregunta corta → Hermes $0, resto → Sonnet); $0, <10 ms; cada resultado lleva `motor_elegido` + `motivo_eleccion`; Tareas muestra «Auto → Sonnet».
- **En curso:** consumo en vivo (desde ~21:13). Quedan: arreglo mascota + icono y diagnóstico de la mascota (haiku, ~10 min). ETA corregida ~22:45–23:00 (la de 22:00–22:30 se quedó corta).
- La app instalada sigue con el código viejo hasta reiniciar (bandeja → Salir → abrir).

---

## Estado a 25 oct 22:07 (cola 0.2.0: 9/9, $45,32)

La cola de la tarde cerró completa, las 9 aprobadas:

- **Consumo en vivo (Opus, 39,9 min, $10,24, aprobada):** Tareas muestra cada ~5 s tiempo, tokens de entrada/salida y costo mientras corre; al terminar, el costo del vivo coincide exacto con el del resultado ($0,302794). Columnas nuevas Motor/modelo, Tiempo y Tokens; tarjeta «Consumo de hoy por modelo». Probado en carpeta aparte (`_prueba-vivo`), sin tocar la cola real.
- **Arreglo mascota + icono (Sonnet, 3,8 min, $0,53, aprobada):** causa real del cuadro blanco = la ventana no tenía `bg` magenta (las otras dos hipótesis eran falsas: no hay `192` en el código y los 48 PNG ya eran magenta). Ahora la ventana lleva `bg=MASCOT_MAGIC` y se fuerza a 128x128 al soltar tras arrastrar. Icono de la barra arreglado con AppUserModelID. Queda un borde fino rosado en el contorno por el suavizado al reducir el PNG (no es el cuadro blanco).
- **Diagnóstico mascota + icono (Haiku, 7,9 min, $0,26, aprobada):** NO pudo escribir `DIAG-MASCOTA-ICONO.md` (permiso no concedido para el outbox); sus conclusiones quedaron en el resultado. La mascota está apagada en `settings.json` (`"mascot": false`) y no hay ninguna ventana de mascota viva. `growi.png` y `growi-header.png` tienen fondo (243,243,243), no magenta — el único candidato a «cuadro blanco» que encuentra.

**Duda por confirmar antes de la release:** el diag dice que el proceso arrancó a las 21:56:52 con el código actual (archivo modificado 21:56:37), pero fix y consumo dijeron que la app sigue con el código viejo y hay que reiniciar (bandeja → Salir → abrir).

**Siguiente (22:07):** `t-dos-carriles-020` enviado al runner (segundo carril: copia de la app en otra carpeta + puerto propio + guardia que solo acepta tasks que no tocan los archivos del carril A). Después: release Alpha 0.2.0 en GitHub y Fase A (30 specs, plan en `opus-tasks-030/PLAN-ENVIO-FASE-A.md`, skills semilla listas 7/7).

---

## Estado a 26 oct 00:13 (cola 0.2.0 cerrada + dos carriles + icono + mascota; piloto en curso)

La 0.2.0 está completa en el PC. Coste acumulado de la noche: cola $45,32 + dos carriles $4,33 + icono $9,44 + mascota $0,98 + piloto $7,46 = **$67,53**.

- **Dos carriles (Opus, 16,4 min, $4,33, aprobada):** carril B = copia completa de la app en `growi-bridge-lane2\`, puerto 8788, su propia cola y su tarea programada; el vigilante cubre los dos puertos. Guardia: solo acepta tasks con `"lane": "b"` + lista de archivos, rechaza lo que toque el carril A; sin fusión automática. 19/19 pruebas de guardia. El carril A se reinició una vez con el código nuevo (patrón diferido) y quedó verificado con las columnas nuevas en Tareas (Motor/modelo, Ronda, Tiempo, Tokens).
- **Icono de la barra (Opus, $7,36 + reintento $2,08 = $9,44, las dos aprobadas):** la pluma de Tk estaba pegada al AppUserModelID viejo. Arreglo: IDs nuevos por carril (`...GrowiBridge.CarrilA` / `.CarrilB`), icono lo primero al crear la ventana, sin `iconphoto`, propiedades de ventana (icono + nombre + comando de relanzamiento) y `growi.ico` nuevo sobre azul noche. El reinicio diferido dejó el botón del carril A en 0 px azul noche: causa raíz medida, la caché de iconos de Explorer guardaba el `.ico` viejo de esa ruta; el reintento lo resolvió con `SHCNE_ASSOCCHANGED` + rehacer el botón sin reiniciar. Verificado: carril A 288 px azul noche (calibración Growi = 288), ahora se llama «Growi Bridge» (antes «Python»); carril B 281 px. Bandeja: dos Growis, el del carril B con «B» violeta y tooltip «Growi Bridge — carril B». Aviso: sin verificar tras reiniciar el PC o Explorer; si vuelve el fondo blanco, `ie4uinit.exe -show` + cerrar y abrir Growi.
- **Mascota working v5-final (Sonnet, $0,33 + $0,65, aprobada):** Leandro aprobó la cara final a las 22:50 tras 4 rondas (cara grande y plana, ojos redondos pequeños, sonrisa pequeña, rubor tenue, audífonos negros, laptop con «growi»). El primer intento no instaló: el aprobado era 1 imagen 1440x1712 con fondo rosa-magenta no exacto y el working son 16 fotogramas 256x256 con magenta puro. Producción en la VM ($0): recorte cuadrado, resize a 256, fondo forzado a (255,0,255) exacto con erosión de 1 px (sin halo). Instalados 16/16 con md5 verificado; reinicio diferido a las 00:00 y 3 capturas en vivo con diferencia 0.0 contra el fotograma v5-final. En reposo (idle) la mascota sigue siendo la anterior: solo cambió working. Revertir: copiar `mascot\_respaldo-v4\working-*.png` sobre `mascot\` y reiniciar.
- **Piloto CustomTkinter (Opus, 30,8 min, $7,46, aprobada):** rediseño de la pantalla Ajustes con CustomTkinter 6.0.0, reversible, con capturas antes/después a 100% y 150% DPI. **Veredicto: SEGUIR con CustomTkinter, superficie por superficie, siempre con la página clásica como respaldo; no convertir toda la app de una vez.** Medido: aspecto más cerca de Raycast (tarjetas redondeadas, secciones apagadas, filas con subtítulo, píldoras); DPI es lo que más mejora (al 150% todo escala junto; 0 desbordes); arranque +0,42 s. Pruebas: clics reales 22/22, persistencia 4/4 al 150%, respaldo en 4 casos sin errores. Convertir primero: Carpetas, APIs, tarjetas de Modelos, configuración inicial y pie de la barra lateral. No convertir: tablas, Registro, botón grande, mascota ni Ctrl+K. CTk no trae blur/liquid glass ni lector completo (eso sería PySide6). El piloto ya está en el código (Ajustes CTk) pero se activa al reiniciar la app. El instalador ahora instala `customtkinter==6.0.0` (si falla, la app usa la Ajustes clásica).
- **Lo que sigue (automatizado, sin preguntar):** release Alpha 0.2.0 en GitHub con este documento y la cadena de la Fase A 0.3.0 (28 specs, ~$150–250, ~28 h de runner). Después: Fase B (0.4.0), 0.4.5 (rediseño UI) y 0.5.0 (Oficina). La revisión automática del runner quedó endurecida esta noche: los specs ahora llevan criterios de aceptación de nivel superior, porque sin ellos la revisión aprobaba por longitud del resultado aunque el task dijera que no había terminado.

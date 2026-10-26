# Growi Bridge — Investigación para Alpha 0.2.0

**Fecha:** 25 oct 2026. **Método:** 12 hilos de investigación en paralelo, solo con búsqueda web y lectura de fuentes (documentación oficial, GitHub, artículos). Nada de esto se probó en vivo en el PC salvo donde se indica. Lo no verificado va marcado como tal.
**Regla del documento:** solo investigar y sintetizar. No se tocó el runner, no se mandaron tasks al PC, no se gastó dinero en APIs.

---

## Resumen en 10 líneas — las 5 decisiones más importantes

1. **Venezuela primero: el proxy ES el producto.** Claude y ChatGPT están bloqueados en Venezuela; la app existe para que un venezolano pueda usar IA. El proxy propio (VPS) debe ser función central y visible —estado en la bandeja, mapa de disponibilidad con chequeos reales, cambio automático a Ollama local si cae— y nunca un ajuste escondido.
2. **La paleta Ctrl+K es el centro de la app.** Gramática Raycast: Enter = acción principal, Ctrl+K = resto de acciones; favoritos arriba con la búsqueda vacía, alias cortos, ranking por frecuencia, búsqueda difusa y fallback a la IA cuando nada coincide. Apertura en menos de 100 ms percibidos.
3. **Orquestación con revisión automática.** Cuando el corredor termina una tarea, Growi la revisa contra el encargo y decide: corregir (ronda nueva) o avanzar de fase. Sin revisión automática no hay "orquestación", solo lanzamiento de comandos.
4. **Un corredor, muchos motores.** El runner acepta motores descritos por un archivo JSON (Claude Code, Ollama local, Codex, Meshy, APIs). Motor principal: Claude Code con la sesión Max. Respaldo $0: Ollama local. Nunca atarse a un solo CLI.
5. **El gasto se ve en la bandeja, no en un panel.** Un solo número en el icono (porcentaje de la ventana semanal de Max que más aprieta), con tres dineros siempre separados: $ real gastado, $ equivalente de Max y $0 local. Sin modelo de créditos propio: gratis con modelos locales + trae tu propia clave.

---

## 1. Raycast

**Qué hace bien (fuentes: manual.raycast.com, raycast.com, changelog oficial)**

- **Una sola entrada para todo.** La barra de búsqueda es el punto de partida: busca en tiempo real en apps, comandos, archivos, ajustes y extensiones. Atajo global configurable, foco inmediato en el buscador. ([search-bar](https://manual.raycast.com/search-bar))
- **Gramática de dos teclas.** Escribes unas letras, Enter ejecuta la acción principal, Ctrl+K abre todo lo demás. Cada resultado tiene su propio menú de acciones (abrir, copiar, favorito, alias, deshabilitar, resetear ranking). Enter = principal, Ctrl+Enter = secundaria, Ctrl+Mayús+Enter = terciaria. ([keyboard-shortcuts](https://manual.raycast.com/keyboard-shortcuts))
- **Ranking que aprende.** Orden de Root Search: coincidencia exacta de alias, prefijo de alias, puntuación difusa del título, coincidencias en subtítulo/palabras clave, y frecuencia (mezcla de frecuencia y recencia). Se puede borrar el aprendizaje por comando. Búsqueda difusa: `msg` encuentra Messages, `slk` encuentra Slack.
- **Vista vacía útil.** Con la búsqueda vacía muestra favoritos, archivos recientes y eventos del día. Modo compacto: solo la barra cuando no hay texto.
- **Quick AI.** Pregunta rápida en la paleta: escribes, pulsas Tab, la respuesta se transmite en la misma ventana; Enter la pega en la app enfocada. Se puede configurar como comando de reserva: cualquier texto sin coincidencia va a la IA. ([quick-ai](https://manual.raycast.com/ai/quick-ai))
- **AI Chat con proyectos y memoria.** Chats de varios turnos, ramificación, resumen de turnos antiguos, proyectos que agrupan chats con instrucciones compartidas y directorio de trabajo. AI Commands: prompts guardados que actúan sobre el texto seleccionado.
- **AI Extensions con `@`.** La IA actúa sobre las extensiones instaladas; el usuario ve qué herramientas tiene la IA y puede revisarlas en Ajustes. Modo agente (v2): elabora un plan, usa extensiones, escribe y ejecuta código, comprueba resultados, pregunta cuando necesita una decisión.
- **Modelos: muchos proveedores + Ollama.** OpenAI, Anthropic, Google, Perplexity, Mistral, xAI, DeepSeek y otros; selector de modelo por superficie (Quick AI, AI Chat, AI Commands); modo Auto (Lightweight/Balanced/Flagship); Bring Your Own Key y Bring Your Own Subscription (conectar la suscripción de Claude o ChatGPT); Ollama local gratis incluso en el plan gratuito. Ojo: el propio changelog advierte que las AI Extensions con Ollama eran experimentales y "puede ser poco fiable".
- **Extensiones por script.** Cualquier script ejecutable con cabecera de metadatos (`@raycast.title`, `@raycast.mode`) se convierte en comando buscable. Store con miles de extensiones (cifra oficial: "miles"; terceros hablan de 2.500+, con 500–800 activamente mantenidas según una estimación).
- **Onboarding de 4 gestos.** Abrir con el atajo, lanzar una app, buscar un archivo, hacer una operación matemática. Permisos solo cuando hacen falta. Reemplazar Spotlight con el mismo atajo (memoria muscular).
- **Rapidez medida por un tercero.** Benchmark de un competidor (Asyar) en Mac M4 Max, Raycast 2.6.2: atajo → ventana visible, mediana 22,2 ms; arranque en frío 2.129 ms; reposo 451,5 MB. Dato de tercero interesado, orden de magnitud, no oficial.
- **Precios (página oficial, 25 oct 2026):** Free $0 (sin Raycast AI), Pro $10/mes ($96/año), Plus $20/mes, Max $50/mes, con 500 / 3.000 / 7.500 créditos de IA al mes. Aviso: Raycast entró en beta pública para Windows el 20 nov 2025 — Growi Bridge ya no compite contra un hueco vacío, sino contra el propio Raycast en Windows, aunque todavía en beta. ([wikipedia](https://en.wikipedia.org/wiki/Raycast_(software)))

**Qué debe tomar Growi Bridge**

1. Enter = acción principal, Ctrl+K = resto de acciones, para las 21 acciones actuales.
2. Favoritos fijados arriba con la búsqueda vacía (las 3–5 acciones que más usa el usuario).
3. Alias cortos por acción (`cc` corredor, `oll` modelos, `ext` extensión); el alias exacto gana siempre.
4. Ranking por frecuencia + "resetear ranking" por acción.
5. Búsqueda difusa de verdad (`mdl` → modelos, `crd` → corredor).
6. Atajos globales por acción para las 3 principales, configurables desde el panel de acciones.
7. Fallback a la IA: si nada coincide, Enter manda el texto como pregunta al asistente.
8. Tres capas de IA: pregunta rápida (Tab en la paleta) / chat con proyectos y memoria / comandos de IA guardados sobre el texto seleccionado.
9. Que la IA pueda llamar a las acciones del Bridge, con lista visible de herramientas permitidas e interruptor para apagarlo.
10. Modo agente visible: plan con pasos, qué paso va, y pregunta de opción múltiple cuando falte un dato, en vez de inventarlo.
11. Trae tu propia clave / suscripción; selector de modelo por superficie.
12. Comandos por script (`.py` / `.bat` / `.ps1` con cabecera simple) como vía de extensibilidad barata.
13. Onboarding de 4 gestos, no un manual.
14. Medir la latencia interna (atajo → ventana visible, tecla → resultados) y aspirar a <100 ms para abrir la paleta.

**Qué NO copiar**

- No intentar ser un lanzador general de Windows (indexar todo el disco, apps, ajustes). El valor es orquestar al asistente, no abrir el Bloc de notas más rápido. Si indexa archivos, solo los del trabajo del asistente.
- No copiar la Store de miles de extensiones: sin miles de usuarios y revisores, una Store con 4 extensiones da peor imagen que no tenerla.
- No copiar el modelo de créditos de IA ni el pago por uso. Para un usuario individual en Venezuela con asistente propio y Ollama local, cobrar por crédito es fricción.
- No copiar lo específico de macOS (reemplazar Spotlight, Hyper Key, comandos de barra de menús, estética Mac).
- No copiar dictado, Focus ni Notes como productos aparte: dispersan.
- No copiar la sincronización en la nube ni Teams: Bridge es de un usuario y su PC.
- No meter la mascota dentro de la paleta: la paleta es texto, teclado y velocidad. Mascota en la bandeja/escritorio.

**Dudas sin verificar:** atajo por defecto en Mac (el manual v1 dice Alt+Espacio, la página actual dice Cmd+Espacio); si el plan Free actual incluye algún mensaje de IA (el changelog v1.96.0 decía 50 gratis/mes; la página de precios actual dice que no); paridad de Windows frente a Mac; número exacto de extensiones; si el tool-calling con Ollama ya es estable en la v2.6.

---

## 2. Ollama

**Qué hace bien (fuentes: docs oficiales de Ollama, ollama.com)**

- **API local sin autenticación en `http://localhost:11434`.** Endpoints: `/api/version`, `/api/tags` (lista modelos; `size` = disco, no VRAM), `/api/ps` (qué está cargado, `size_vram`, `expires_at`), `/api/show`, `/api/pull` (streaming NDJSON, reanuda por blobs), `/api/delete`, `/api/generate`, `/api/chat` (recomendado; hay que enviar todo el historial), `/api/embed`, `/v1/chat/completions` (compatible OpenAI).
- **Funciona 100% offline una vez descargado el modelo** (sin suscripción, sin costo por mensaje). La descarga es lo único que exige internet. ([runlocal](https://runlocal.laftel.io/posts/does-ollama-work-offline))
- **CLI simple:** `ollama list/pull/run/rm/show/ps/stop/cp/serve/create`.
- **Modelos para 6 GB de VRAM (Q4_K_M):** llama3.2:1b 1,3 GB (sobrado), llama3.2:3b 2,0 GB (cómodo), qwen3:4b 2,5 GB (cómodo), phi4-mini 2,5 GB, gemma3:4b 3,3 GB (visión), qwen2.5-coder:1.5b ~1,0 GB, qwen2.5-coder:3b 1,9 GB, mistral:7b 4,4 GB (justo), qwen2.5-coder:7b 4,7 GB (código recomendado, justo), llama3.1:8b 4,9 GB (va justo, ~6,5 GB con contexto 4K), Hermes 3 8B 4,9 GB (ya instalado, va justo), qwen3:8b 5,2 GB (muy justo), deepseek-r1:8b 5,2 GB (muy justo). **No caben:** gemma3:12b, qwen2.5-coder:14b, qwen3:14b, phi4 14B, gpt-oss:20b, deepseek-r1:14b/32b, llama3.3:70b, qwen3:32b.
- **Reglas de funcionamiento:** un solo modelo grande cargado a la vez (`OLLAMA_MAX_LOADED_MODELS=1`; `keep_alive` 5 min por defecto); si no cabe, Ollama parte a CPU (lento); contexto por defecto 4.096 tokens (<24 GiB VRAM); no usar `:latest`; distinguir modelos `:cloud` (no locales).
- **El modelo Hermes 3 8B pide ~8 GB de VRAM según tablas de referencia; la RTX 3060 tiene 6 GB.** El modelo cabe justo en pesos, pero el contexto (KV cache) se suma encima. Con contexto grande (32–64k) hay riesgo real de desbordar a RAM o fallar. Solo una prueba en el PC lo confirma.

**Qué debe tomar la pestaña Modelos de Growi Bridge**

1. Estado en 3 estados (no instalado / instalado / cargado), con detección por PATH + `%LOCALAPPDATA%\Programs\Ollama`, versión, `/api/tags` como fuente de verdad y `/api/ps` para lo cargado.
2. `nvidia-smi` para VRAM libre y **semáforo por modelo**: verde ≤80% VRAM (cabe holgado), naranja 80–100% (va justo, con confirmación), rojo >100% VRAM o sin disco (botón Instalar desactivado). Sin GPU usa la RAM (verde ≤50%, naranja 50–90%, rojo >90%). Ejemplos con la RTX 3060 6 GB: Gemma 3 4B verde, Hermes 3 8B naranja (~83%), Phi-4 14B rojo.
3. Instalar con progreso real (`ollama pull` por streaming) + comprobar disco antes + verificar después del pull (la reanudación no es perfecta: hay reportes de modelos parciales rotos que exigen `ollama rm` y volver a bajar).
4. Catálogo corto y curado (8–10 modelos), no la lista entera de Ollama.
5. Borrar con confirmación; no borrar el motor activo.
6. Botón "Comprobar mi PC": detecta GPU/VRAM/RAM/CPU/disco, guarda `pc-specs.json`, corre solo la primera vez.
7. Botón "Descargar de memoria" (sacar un modelo de VRAM sin borrarlo) y selector de motor (qué modelo responde por defecto).
8. Aviso "va justo" y aviso "mitad en CPU" cuando el modelo no cabe entero en VRAM.
9. No exponer el puerto 11434 a la red (solo localhost). Botón "Probar" (una pregunta corta al modelo elegido).
10. En el runner, Ollama por API (`/api/chat` con `stream:false`), no por CLI `ollama run`.

**Qué NO copiar**

- No listar todos los modelos de Ollama: catálogo curado o el usuario se pierde.
- No prometer "modo local con contexto de 128k" en 6 GB sin haberlo medido.
- No asumir que el tool-calling local funciona igual que con Claude/GPT (Raycast mismo lo marca como experimental con Ollama).
- No meter el modelo de ~4,7 GB dentro del instalador: descarga aparte, opcional, con progreso y reanudación.
- No usar `:latest` (cambia bajo los pies) ni modelos `:cloud` como si fueran locales.

**Dudas sin verificar:** changelog de Ollama 0.40.10; si `/api/pull` usa `model` o `name` (la doc dice `model`); tokens/s reales en la RTX 3060 Laptop; si Hermes 3 expone `tools` en `/api/show`; si `registry.ollama.ai` es rápido/estable desde IP venezolana sin proxy.

---

## 3. OpenClaw

**Qué hace bien (fuentes: repo y documentación oficial de OpenClaw, openclaw.ai)**

- **Gateway único, siempre encendido.** Un proceso que es la única fuente de verdad; panel local en `http://127.0.0.1:18789/`.
- **Un agente, muchos canales.** 20+ canales (WhatsApp vía Baileys con QR, Telegram, Discord, Slack, Signal…). Sesiones por canal, reset diario a las 4 AM.
- **Skills como carpetas con `SKILL.md`.** Frontmatter con `name`, `description`, `version`, `metadata.openclaw.requires`; descubrimiento por `description`; distribución por ClawHub.
- **Modelo principal + fallbacks con hot-reload.** Ruteo por tipo de trabajo: modelo principal, heartbeat barato/local, sub-agentes con modelo distinto. Ollama como proveedor nativo contra `http://127.0.0.1:11434` **sin `/v1`** (la ruta `/v1` pierde tool-calling). Aviso: los modelos locales pequeños no saben llamar herramientas.
- **Memoria en dos capas, en Markdown legible.** Memoria corta + larga, compaction con memory flush. Workspace `~/.openclaw/` con `AGENTS.md`, `SOUL.md`, `USER.md`, `MEMORY.md` + `memory/`.
- **Comandos mínimos:** `/new`, `/compact`, `/status`, `/btw`, `/usage`. Tareas programadas (heartbeat).
- **Config en un solo archivo** `openclaw.json` (modelo + fallbacks, canales, herramientas, gateway).

**Qué debe tomar Growi Bridge para su capa de orquestación**

1. Gateway único siempre encendido (el runner + la app como un solo proceso coordinador, no servicios sueltos).
2. Un asistente, muchos canales: WhatsApp primero, solo el dueño por defecto, pairing para desconocidos. La app es la cara del asistente en el PC; WhatsApp es la cara en el teléfono.
3. Skills con frontmatter + vista de "qué le falta a cada skill" (dependencias, permisos).
4. Modelo principal + fallbacks sin reiniciar (Claude → Ollama local cuando se acaba la cuota o cae el proxy).
5. Ollama de primera clase (sin `/v1`, por la ruta nativa).
6. Memoria en Markdown legible (la que ya existe: `MEMORY.md` + notas diarias), con compaction que no borre decisiones.
7. Sesiones por canal; comandos mínimos (`/nuevo`, `/estado`, `/uso`).
8. Tareas programadas (heartbeat): el resumen diario de las 21:00 ya es un heartbeat.
9. Panel de control local (la pestaña Estado de la app).

**Qué NO copiar**

- Nada de JSON al usuario; nada de Node/npm/terminal en la cara del usuario.
- Nada de marketplace de skills sin curaduría: ataque ClawHavoc (feb 2026): 341 de 2.857 skills maliciosas (~12%), incluido un infostealer (AMOS).
- Nada de pairing abierto por defecto; nada de exponer el puerto del gateway; nada de claves en texto plano.
- Nada de shell sin permiso visible; nada de multi-agente con bindings (complejidad que no se necesita).
- Nada de prometer WhatsApp Business (Baileys no da plantillas ni botones).
- Nada de cargar toda la memoria en cada sesión.
- Riesgos a tener presentes: CVE-2026-25253 (CVSS 8.8, parcheado); el prompt injection no tiene solución arquitectónica.

**Dudas sin verificar:** Windows nativo vs WSL2; harness por defecto (Pi) no verificado; nombres de modelos en los ejemplos no contrastados.

---

## 4. TokenBar / OhNine

**Qué hace bien (fuentes: tokenbar.app, CodexBar en GitHub, Tokenscope, TokenTray)**

- **Un solo número, siempre visible.** TokenBar es una app macOS (Swift) en la barra de menú; Pro $15 de por vida, macOS 14+. Muestra uso en vivo en 20+ proveedores, costo por modelo, totales diarios/semanales, qué sesión quema más, límites semanales/mensuales, cuenta atrás de reinicio, indicador de ritmo (pace), alertas de uso, estado del proveedor. Todo local, sin telemetría, sin cuenta.
- **Muestra lo que queda, no solo lo gastado.** Avisos, no ruido. Salida CLI. Fuentes de datos: CLI tokens, OAuth, API keys, local file probes.
- **Antecedente open source: CodexBar (MIT, ~22.759 estrellas).** Icono de doble barra (sesión + semanal), intervalo configurable, caché; para Claude Code ejecuta `/usage` y `/status` en PTY.
- **Referencias en Windows:** Tokenscope (gratis, MIT), Burnt, AI Token Monitor, Nowdex, Claude Usage Monitor, TokenTray (Python + PyQt6, la referencia técnica más cercana), Bumeter, usage (AGPL).

**Qué debe tomar Growi Bridge**

1. **Un solo dato en el icono de la bandeja:** % de la ventana semanal de Max que más aprieta. Verde <75%, naranja ≥75%, rojo ≥90%.
2. Tooltip de 3 líneas: Hoy $ real / $ equivalente Max; Max 5h A% · Semana B% · Opus C% — reinicio; Local $0 · N tareas.
3. Clic = desglose en la pestaña "Tareas" (por tarea, por proyecto, por motor).
4. Todo local; actualizar cada 5 min con caché y marca "desactualizado".
5. Avisos una sola vez por ventana (75% y 90%); indicador de ritmo semanal; cuenta atrás de reinicio; alerta de pico (≥2× promedio).
6. **Separar siempre tres dineros:** $ real / $ equivalente / $0 local. Nunca mostrar el $ equivalente de Max como gasto real.
7. Historial corto de 7 días + por proyecto; ahorro de caché aparte.
8. Aviso de cuota Max antes de que se acabe, para pasar trabajo al modelo local *antes* de quedarse sin Claude a mitad de tarea.

**Qué NO copiar**

- Pixel Agents / mascotas / animaciones en el medidor; leaderboards / Wrapped / social.
- 20+ proveedores de entrada: Bridge tiene 3 dineros (Max, APIs, local).
- Temas visuales / panel grande; scraping por cookies del navegador.
- Prometer "tiempo real": el consumo se actualiza cada 5 min con caché.

**Duda central no resuelta:** la cuota restante de Max solo vive en respuestas del servidor (no hay API pública; `claude-usage-plg` lo dice explícito). Vías no oficiales: endpoint OAuth no documentado `GET https://api.anthropic.com/api/oauth/usage` (token de `~/.claude/.credentials.json`; riesgo: puede cambiar, no refrescar el token, sondear cada 5 min con backoff ante 429) o `claude -p "/usage"` / statusline (`rate_limits.five_hour`, `rate_limits.seven_day`). El consumo local sí se mide con los JSONL de `~/.claude/projects/` (ccusage, Tokenscope, Burnt) pero no da la cuota restante. El uso fuera del PC no aparece en logs locales.

---

## 5. AirJelly

**Qué hace bien (fuentes: airjelly.ai, centro de ayuda, The Agent Times, Product Hunt)**

- **Ciclo mirar → recordar → actuar.** Watches / Remembers / Acts.
- **Captura por tecla Enter** (~300 capturas/día vs ~1.500, cifra autorreportada, sin benchmark independiente).
- **Memoria dual (Entidades + Tareas)** con búsqueda vectorial + keywords + decaimiento temporal; línea de tiempo buscable + Rewind + Memory editable.
- **Auto-captura de tareas con fecha y fuente; Deadline Alert; umbral de notificación; People; Conversation Review; Grow** (rutinas → SOP → Skill).
- **Precio $0**, descarga gratuita (Mac Apple Silicon, Windows 10+ x64).
- **Privacidad declarada:** capturas cifradas en local, pausa, exclusión de apps, no lee campos de entrada segura.

**Qué debe tomar Growi Bridge (que ya tiene resumen diario y mascota)**

1. Captura de tareas desde el contexto con fuente adjunta, con confirmación de un clic ("¿Qué me falta por responder?" por persona).
2. Brief antes de una reunión/cita (qué se habló la última vez con esa persona).
3. Memoria consultable con origen visible (cada dato dice de dónde salió).
4. Detección de rutinas → sugerir atajos (Grow: rutina → SOP → skill).
5. Umbral de aviso: máximo 1 aviso al día al principio.
6. Resumen diario con lo pendiente por persona (ya existe el de las 21:00; añadirle "qué falta por responder").

**Qué NO copiar**

- Mirar la pantalla siempre: su marketing dice "100% local" pero su política de privacidad admite envío de contenido a la nube (Vertex AI, OpenRouter, AWS).
- Captura por Enter sin adaptar: en Windows no está documentado; falla en lectura larga, vídeo y llamadas.
- Alertas sin freno; "todo guardado para siempre"; Autopilot sin supervisión; memoria opaca.
- La integración con Codex y Claude Code dice "Coming soon": mecanismo no verificado.

**Dudas sin verificar:** mecanismo de integración con Codex/Claude Code; Enter en Windows; valor del umbral; si el procesado en nube se puede apagar; retención de capturas; precio futuro; precisión real.

---

## 6. ClippyAI

**Qué hace bien (fuentes: clippyai.app, clippyai.app/security, clippyai.app/changelog, clawdcursor.com)**

- **Loop preguntar → planear con aprobación → actuar con reporte.** Plan visible con paso "Awaiting your approval".
- **Aprobación con nombre propio y timeout 25 s = Deny.** Niveles de guardrail: Cautious / Standard / Trusted.
- **Regla anti-éxito-inventado:** si ninguna acción destructiva tuvo éxito real, decir "I tried but couldn't confirm it worked".
- **Ejecución visible:** banner + brillo ámbar, doble clic para parar. Sleep que mata lo en curso.
- **Pausa ante login / 2FA / CAPTCHA.**
- **Contexto por árbol de accesibilidad antes que por captura** (ClawdCursor, motor open-source, verificación por paso con `expect`, una sola puerta `safety.evaluate()`).
- **Precios:** Free $0 (100K tokens/mes, sin automatización), Power $19,99/mes (5M), Max $39,99/mes (20M).

**Qué debe tomar Growi Bridge**

1. Plan visible con aprobación por paso (el plan del corredor se muestra antes de ejecutar; el usuario aprueba, edita o rechaza cada paso sensible).
2. Approve / Deny con el texto completo de lo que se va a hacer (nunca "¿confías en mí?" genérico).
3. Reporte honesto: qué se hizo, qué falló, qué quedó sin confirmar. Nunca inventar éxito.
4. Parada que mata lo en curso (un botón "Parar" que de verdad detiene el runner, no solo esconde la ventana).
5. Niveles de guardrail en palabras normales ("Pregúntame siempre" / "Pregúntame solo lo delicado" / "Hazlo sin preguntar" — este último difícil de activar, nunca por defecto).
6. Pausa automática ante login / 2FA / CAPTCHA (el runner se detiene y avisa, no intenta resolverlo solo).
7. Accesibilidad antes que captura: leer el estado por la estructura de la app, no por capturas de pantalla, cuando se pueda.
8. Proactivo con interruptor (la mascota sugiere, no impone); borrador antes de enviar (nada se envía sin que el usuario lo vea).
9. Chequeo de seguridad de solo lectura (opcional): antes de ejecutar, listar qué archivos/cuentas toca la tarea.

**Qué NO copiar**

- Proactivo cada 5 min por defecto.
- Modo Trusted fácil (un clic para "haz todo sin preguntar").
- Sin interruptor para capturas.
- Contexto de pantalla a backend en la nube.
- Cobro por tokens / muro de pago por actuar.
- La lección del Clippy original (ver §11): sugerir sin ejecutar, aparecer sin invitación, repetir el mismo error, animaciones en reposo que distraen.

---

## 7. MCP (Model Context Protocol)

**Cómo funciona (fuentes: modelcontextprotocol.io, spec 2026-07-28; SDK oficial de Python)**

- Estándar abierto de Anthropic (nov 2024, donado a la Agentic AI Foundation en dic 2025). Tres papeles: host / cliente / servidor. JSON-RPC 2.0.
- Transportes: **stdio** (local, sin red ni auth — el recomendado para empezar) y **Streamable HTTP** (remoto, con auth; SSE está deprecado).
- Primitivas: tools (acciones), resources (datos) y prompts (plantillas). Sesión con `server/discover` + `tools/list`. Tasks opcional para operaciones largas.
- Servidor local recomendado: stdio primero (FastMCP, `pip install "mcp[cli]"`, `@mcp.tool()`; nunca `print()` en stdio — logs a stderr). Streamable HTTP en `127.0.0.1:8765/mcp` como fase 2. Nunca exponer 0.0.0.0 sin auth. En Windows, al desconectar un servidor stdio Claude Code lo mata a los ~300 ms.
- **Herramientas v1 propuestas para el Bridge:** `bridge_send_message`, `bridge_read_inbox`, `bridge_list_files`, `bridge_read_file` (sin `..`), `runner_submit_task`, `runner_task_status`, `ollama_list_models`, `ollama_pull_model`, `ollama_chat`, `bridge_status`. Recursos: `bridge://inbox`, `bridge://outbox`, `bridge://tasks`, `bridge://models`. Prompts: `revisar_puente`, `nueva_task_claude_code`.
- **Cliente a otros MCP:** usar el cliente del SDK oficial (`ClientSession`, `stdio_client` / `streamablehttp_client`); config `mcp_servers.json` con formato `mcpServers` portable; claves en Credential Manager, nunca en JSON. La vía más simple es que Claude Code ya es cliente MCP (`claude mcp add`).

**Hallazgo clave (verificado contra las páginas de Meta al 26 sep 2026): la app Muse.ai de consumo NO documenta ninguna forma de añadir un servidor MCP.** Muse se conecta por "Muse Connectors" / "Custom Connectors" contra API o CLI, no MCP. **Muse Code sí soporta MCP completo** (bloque `mcp_servers`, stdio y Streamable HTTP, OAuth 2.1, skill `/migrate`). Meta AI Connectors (preview cerrada) sí admite MCP. Vías realistas para conectar el Bridge con Muse: Custom Connector contra una API REST pública (túnel o VPS) o Muse Code / Claude Code como clientes.

**Qué necesita Growi Bridge**

- **(a) Como servidor MCP local:** un servidor stdio en Python (FastMCP) que exponga las 10 herramientas de arriba. Es el paso que permite que Claude Code (y cualquier cliente MCP) use el puente como herramienta: mandar mensajes, leer el inbox, lanzar tasks del runner, listar y usar modelos Ollama. Fase 2: Streamable HTTP en localhost para clientes que no soportan stdio.
- **(b) Como cliente de otros MCP:** no reinventar el cliente — usar el del SDK oficial dentro del runner, con `mcp_servers.json` editable desde la app en palabras normales ("Conectar otra herramienta"). Las claves van en Credential Manager. Y la vía práctica a corto plazo: que Claude Code sea el cliente (`claude mcp add`), con el Bridge como uno más de sus servidores.
- **(c) Con Muse.ai:** no prometer MCP directo. La integración con Muse pasa por un Custom Connector contra la API del Bridge (vía túnel o VPS), o por Muse Code. Esto va en 0.3.0, no en 0.2.0.

**Riesgos:** las herramientas MCP no están en sandbox (cita de Meta); tool poisoning (una herramienta que miente sobre lo que hace); prompt injection indirecta (datos que traen instrucciones); claves en archivos de config; fijar versiones de paquetes `npx`.

**Dudas sin verificar:** el SDK Python v2.0.0 habría renombrado `FastMCP` a `MCPServer` según fuentes secundarias (no verificado en vivo); la afirmación de parallel.ai sobre Muse construyendo un cliente MCP no es documentación de Meta.

---

## 8. Multi-CLI y multi-asistente

**Qué CLIs existen y cómo se invocan (verificado en docs oficiales, 25 oct 2026)**

| CLI | Invocación no interactiva | Notas verificadas |
|---|---|---|
| **Claude Code** | `claude -p "<prompt>" --output-format json` (+ `--resume`, `--max-budget-usd`) | El motor actual del runner. Sesión Max de Leandro; los $ de los resultados son costo estimado, cuentan para el límite de Max. |
| **Codex CLI (OpenAI)** | `codex exec --json` | Sandbox `workspace-write`; exige repo git salvo `--skip-git-repo-check`. Segundo motor recomendado. |
| **Gemini CLI** | `gemini -p --output-format json` | Capa gratuita: 60 req/min, 1.000 req/día. |
| **Grok Build** | `grok -p --output-format streaming-json` | Beta; requiere SuperGrok; Windows no verificado. |
| **OpenCode** | `opencode run --format json` | 75+ proveedores; la sintaxis cambió de v1 a v2. |
| **Aider** | Sin salida JSON verificada | Edita archivos + git; no sirve como motor del runner sin JSON. |
| **Copilot CLI** | No verificado en docs oficiales | No contar con él hasta verificarlo. |
| **Ollama (por API)** | `POST /api/chat` con `stream:false` | Por API, no por CLI `ollama run`. |
| **Meshy CLI** | `meshy make --json` | Flags no verificados. Como API es asíncrona en dos pasos (crear tarea → consultar estado → descargar; estados PENDING / IN_PROGRESS / SUCCEEDED / FAILED / CANCELED; URLs caducan, archivos 3 días; verificar el tamaño del .glb al descargar). |

**Diseño del corredor genérico**

Cada motor se describe por un archivo JSON, no por código:

```json
{
  "id": "claude",
  "tipo": "cli_sincrono",
  "comando": ["claude", "-p", "{prompt}", "--output-format", "json"],
  "prompt_via": "argv",
  "modelo_por_defecto": "sonnet",
  "permisos": "allowed_tools",
  "sesion": "--resume {session_id}",
  "lectura_resultado": {"texto": "result", "costo": "cost_usd", "turnos": "num_turns"},
  "timeout_min": 30,
  "variables_entorno": ["HTTPS_PROXY"],
  "directorio_trabajo": "{cwd}",
  "artefactos": ["*.result.json"],
  "healthcheck": "claude --version"
}
```

- **Tipos:** `cli_sincrono` (Claude, Codex, Gemini, Grok, OpenCode) y `api_asincrona` (Meshy, Tripo: crear tarea → sondear estado → descargar).
- **Resultado normalizado único** para todos los motores: `id`, `status` (ok/error/timeout), `started_at`, `finished_at`, `duration_s`, `exit_code`, `result` (≤20.000 caracteres), `cost_usd`, `num_turns`, `session_id`, `stderr`, `error`. El mismo esquema que ya usa el runner v1.1.
- **Modo seguro por defecto.** Nunca `bypassPermissions` / `--yolo` como default. Los permisos se piden por tarea, no por motor.
- **Prioridad:** Codex como segundo motor (tras Claude); Ollama por API; Meshy como motor asíncrono separado (ejemplo de CLI especializado, no motor de texto).
- **Multi-asistente en el onboarding:** el usuario elige su asistente principal (Muse / Claude Code / Grok / Dot / Codex / Otro personalizado). El motor elegido es el que responde en la paleta y en el chat; los demás quedan como motores secundarios elegibles por tarea.

**Dudas sin verificar:** si Gemini CLI fue reemplazado por Antigravity (18 jun 2026); Grok Build en Windows; flags de `meshy make`; Copilot CLI.

---

## 9. Onboarding de instalación

**Qué hacen bien los referentes (fuentes: OpenClaw `openclaw onboard`, manual de Raycast, `claude doctor`)**

- **OpenClaw:** aviso de seguridad → QuickStart/Manual → proveedor → modelo → canal → skills → `--install-daemon`. QuickStart fija el gateway en 127.0.0.1:18789, token autogenerado, workspace `~/.openclaw/workspace`. Verificación con `openclaw gateway status`.
- **Raycast/Alfred:** atajo primero, primera victoria en minutos, permisos en contexto (no todos al instalar), no instalar decenas de extensiones al principio.
- **Claude Code:** primer arranque = autenticación por navegador; `claude doctor` como comprobación; permisos graduales en `.claude/settings.json`; MCP con `claude mcp add`.

**Flujo recomendado para Growi Bridge (4 pasos, en orden)**

0. **Detección silenciosa (antes de preguntar nada).** Qué CLIs hay instalados y sus versiones, si Ollama está y qué modelos tiene, si hay sesión de Claude, qué carpetas existen. Sin bloquear si falta algo: lo que falta se ofrece después, no se exige.
1. **Paso 1 — Elegir asistente.** Muse / Claude Code / Grok / Dot / Codex / Otro. Preseleccionar el detectado. En palabras normales, sin tecnicismos.
2. **Paso 2 — Conectar.** Inicio de sesión por navegador o clave, con "¿Dónde consigo mi clave?" y "Lo haré más tarde" siempre disponible. Nunca bloquear sin clave.
3. **Paso 3 — Carpetas, con 3 niveles.** "Solo mirar" / "Mirar y cambiar" / "Preguntarme siempre" (este último por defecto). El usuario elige qué carpetas ve el asistente.
4. **Paso 4 — Comprobación en vivo.** 3 pruebas con ✓/✗ estilo `claude doctor` (proxy, motor, carpetas). Y "Empezar a hablar" con un ejemplo concreto.

**Después (no en el onboarding):** MCPs, proxy/VPN (solo si falla una conexión), más modelos, arranque automático.

**12 qué-no-hacer:** no preguntar todo al inicio; no bloquear sin clave; no tecnicismos ("MCP", "gateway", "endpoint", "quantization", "context window", "JSON", "config" — todo en palabras normales: "modelo", "habilidad", "canal", "regla"); no tour de 10 pasos; no pantalla vacía; siempre "Saltar por ahora"; no esconder la configuración; no pedir permisos que no se usan todavía; no instalar decenas de cosas; no exigir cuenta en la nube; no prometer lo que no está verificado; no dejar al usuario sin una primera victoria en los primeros 2 minutos.

**Dudas sin verificar:** auth de Grok/Dot; OpenClaw eliminó OAuth en ene 2026 según una fuente (contradictorio); detección de proxy en Windows no fiable; Meshy CLI como binario no verificado; dónde guarda Windows las credenciales (DPAPI / Credential Manager) no verificado.

---

## 10. Venezuela primero (requisito de diseño, no un detalle)

**Tesis: Growi Bridge es valioso justo porque resuelve el problema venezolano de acceso a la IA.**

### (a) Qué está bloqueado y cómo se salta cada bloqueo

| Servicio | Estado en Venezuela | Cómo se salta |
|---|---|---|
| **Anthropic / Claude (web y API)** | **No disponible.** La lista oficial tiene 185 países; Venezuela no está ("Iran, Syria, North Korea, Cuba, Venezuela — No / No"). ([madrobot](https://madrobot.blog/2026/09/29/is-claude-available-in-my-country-supported-countries-not-available-fix/)) | Proxy propio en VPS que sale por EEUU (ya existe: 2.25.244.222:18080, tinyproxy). O modelos locales. |
| **OpenAI / ChatGPT** | **No disponible.** Venezuela no figura en la lista oficial de países soportados por la API (la lista salta de Vanuatu a Vietnam). OpenAI advierte que acceder desde fuera de la lista "puede resultar en bloqueo o suspensión". ([lista oficial](https://help.openai.com/en/articles/5347006-openai-api-supported-countries-and-territories)) | Proxy propio. No usar como respaldo principal: está bloqueado igual que Claude, sin la suscripción Max que justifique el proxy. |
| **Google Gemini (API / AI Studio)** | **Disponible.** La lista oficial de regiones de la API de Gemini incluye a Venezuela. ([lista oficial](https://ai.google.dev/gemini-api/docs/available-regions)) | Directo, sin proxy. Es la única ruta de IA en la nube legalmente disponible desde Venezuela entre los tres grandes. **Matiz:** esto es la API; no garantiza que Google AI Pro de pago ni todos los productos funcionen igual, ni que el pago pase desde Venezuela. Verificar en vivo antes de afirmar nada. |
| **DeepSeek / Qwen / Groq** | Sin bloqueo publicado encontrado | No afirmar que funcionan sin verificar en vivo desde IP venezolana. |

**Riesgo que la app debe decir en voz alta:** usar Claude desde un país no soportado vía VPN/proxy incumple la política de regiones de Anthropic; las cuentas pueden suspenderse en cualquier momento, las apelaciones tienen muy baja tasa de éxito, y en oct 2026 hubo una oleada de suspensiones (Rusia ~1 oct, Hong Kong ~2 oct, usuarios con VPN tras meses de uso). Si Anthropic cancela por violación de términos, no hay reembolso. La app NO debe prometer "con el proxy, Claude funciona seguro". Debe decir: "el proxy te conecta; tu cuenta puede ser suspendida si el proveedor detecta la región. La vía sin ese riesgo es la API con key propia o un modelo local". Y debe **exportar/respaldar las conversaciones** para que un baneo no borre meses de trabajo.

**Por qué proxy propio y no VPN comercial:** las VPN comerciales están bloqueadas en Venezuela (VE Sin Filtro: 148 dominios con restricciones, 30 de anticensura/VPN; Espacio Público: 17 herramientas de VPN bloqueadas). Un proxy privado en una IP que solo conoce el usuario no está en esas listas. Además el proxy es selectivo (solo el tráfico de la app pasa por él, no todo el sistema).

### (b) El proxy como función CENTRAL de la app

1. **Onboarding de un clic ("Conectar").** La app prueba el proxy del VPS y muestra "Conectado — sales por EEUU" o el error exacto con la ruta que sí anda (local). Cero campos a rellenar en el camino feliz.
2. **Estado siempre visible:** en la bandeja (distintivo verde = conectado, ámbar = local, rojo = sin conexión) y en la ventana principal. Botón "Probar proxy". Si cae, cambio automático a Ollama + aviso, nunca un error críptico.
3. **Alquiler del proxy a otros por $2,50/mes:** técnicamente viable — tinyproxy soporta `BasicAuth usuario clave` por línea; revocar = borrar la línea y reiniciar. Pero antes de venderlo hacen falta: un script de alta/baja (la revocación manual no escala), dimensionar `MaxClients`, resolver que **BasicAuth viaja sin cifrar** (usuario:clave en base64 en cada petición; riesgo real en red venezolana — valorar túnel SSH/TLS antes de escalar), y **costear el VPS** (sin su costo mensual y ancho de banda no se puede afirmar que $2,50 cubra costos). El alquiler es de *infraestructura de red*, no de cuentas: cada usuario usa su propia cuenta y su propia API key (compartir cuentas está prohibido por los proveedores). El cobro en Venezuela (Pago Móvil, USDT) no se investigó.
4. **Ajustes avanzados aparte:** host, puerto, usuario, clave, "probar conexión", "usar proxy del sistema" o "sin proxy". No en el onboarding.

### (c) Offline-first: nada se rompe si se va la luz o el internet

El entorno real: encuesta Meganálisis (sep 2026): 24,6% de hogares sin luz todos los días, 22,8% seis días por semana; 29,4% sufre cortes de 4–5 horas y 28,3% de 5–6 horas; en Lara "los cortes son diarios por varias horas". Velocidad: fibra privada 100–175 Mbps, pero **CANTV: 10,39 Mbps bajada / 5,03 subida** (Ookla Q1–Q2 2026). El diseño de referencia es CANTV 10/5 Mbps y cortes de 4–6 horas.

1. **Modo sin conexión visible y automático:** 🟢 Claude (nube) / 🟡 Local (Ollama) / 🔴 Sin conexión. Cambio automático a local cuando falla Claude o el proxy, con aviso ("Sin internet: trabajando con Hermes 3 local, calidad menor").
2. **Cola de tareas persistente en SQLite (WAL + `synchronous=FULL`).** Toda tarea se escribe a disco *antes* de ejecutarse, con estado pendiente/en curso/hecha/fallida e intentos. Al arrancar, la app reencola lo que quedó a medias. Lo que queda en `running` al reiniciar se reencola. Con `NORMAL` puede haber rollback tras apagón; con `FULL` lo confirmado sobrevive.
3. **Reintentos automáticos con aviso.** Backoff exponencial con jitter (1s → 2s → 4s → 8s → 16s, tope ~60s, máximo 5 intentos) solo para errores transitorios (429, 408, 5xx, errores de red). Los 401/403/400 no se reintentan: se muestran. Cada reintento queda en un registro visible ("Reintentando 2/5…"). Las tareas que agotan intentos quedan "en espera de conexión" y se disparan solas cuando vuelve internet.
4. **No depender de Claude para lo básico.** Ver estado, listar tareas, leer archivos, encolar trabajo: todo funciona sin internet y sin proxy.
5. **Sync por diferencia, nunca por archivo completo.** Solo lo cambiado (hash o tamaño+fecha; si el archivo es grande, por bloques estilo rsync con `--partial`). Los archivos ya presentes en la VM no se vuelven a tocar. A 5 Mbps de subida, re-subir un archivo entero por un corte es inaceptable.
6. **Hermes 3 8B como respaldo, con plan B de VRAM.** Probar en la RTX 3060 de 6 GB con contexto moderado (8k–16k, no 64k de entrada) y medir si cabe o se desborda a RAM. Si va justo: cuantización menor (Q4_K_M → Q4_0/Q3) o `hermes3:3b` (2 GB) como respaldo del respaldo.

### (d) Gasto $0 o mínimo

- El stack $0 es: suscripción Max (ya pagada) + Ollama local (gratis) + Tailscale personal (gratis) + VPS existente. Cualquier API de pago queda fuera por defecto.
- **Pagar desde Venezuela es el cuello de botella:** las tarjetas de bancos venezolanos no se aceptan en muchas plataformas internacionales aunque tengan logo Visa/Mastercard; Stripe no opera en Venezuela. No verificado si Anthropic acepta la Tarjeta Internacional del BDV para cobrar el Max. La app debe avisar antes de que se corte el acceso por fallo de pago.
- Max: Pro $20/mes, Max 5x $100/mes, Max 20x $200/mes, solo facturación mensual. Tope por sesión de 5 horas y tope semanal aparte; agotar el semanal deja sin Claude aunque la sesión tenga margen. Cuando se acaba la cuota, Ollama sigue.
- **Gemini como segunda nube, no OpenAI** (Gemini sí lista a Venezuela; OpenAI no). Pendiente verificar cuota gratuita y pago.

### (e) Ancho de banda bajo y qué pesa cada cosa

- Hermes 3 8B: ~4,7 GB de descarga. A 10 Mbps (CANTV), ~1 hora en el mejor caso; a 5 Mbps de subida, subirlo tardaría ~2 horas. **El modelo se descarga una sola vez y nunca se re-sube.** La descarga es reanudable por blobs (la doc de Ollama lo afirma) pero hay reportes de modelos parciales rotos: verificar después del pull.
- Instalador empaquetado (PyInstaller, app Tkinter simple): 15–80 MB, Python incluido, sin necesidad de instalar Python ni pip. Los modelos (GB) no van dentro.
- Capturas y adjuntos, ligeros por defecto: bajar resolución y comprimir (JPEG) salvo que el usuario pida calidad completa. Preferir texto (logs, diffs) a imágenes.
- Tailscale personal gratuito: el tráfico PC↔VM va directo peer-to-peer por WireGuard; si falla la directa cae a relé DERP (45–300 Mbps según la fuente), que sobra para archivos de texto.

### (f) Mapa de disponibilidad dentro de la app

Una pantalla (o sección principal) con una tabla viva, verificada por la propia app con chequeos reales, no con texto estático:

| Fila | Cómo lo sabe la app | Acción |
|---|---|---|
| Claude (API) | Ping real con y sin proxy | Usar / Ver por qué |
| ChatGPT (API) | Ping real con y sin proxy | Usar / Ver por qué |
| Gemini (API) | Ping real sin proxy; si falla, por proxy | Usar / Ver por qué |
| Ollama local | `localhost:11434` + modelo descargado | Descargar modelo |
| Proxy VPS | Chequeo al arrancar y cada X minutos (+ latencia) | Reintentar |
| Internet | Chequeo simple de conectividad | — |

Cada fila con una frase honesta cuando algo falla ("Claude no responde desde IP venezolana; con el proxy sí. Tu cuenta puede ser suspendida: exporta tus chats."). Se re-verifica al arrancar y bajo demanda ("Volver a comprobar"). **Nunca mostrar un error técnico sin la ruta que sí anda.** Y nunca hardcodear la disponibilidad: las listas de países cambian; debe ser configuración, no código fijo.

**Qué NO hacer (Venezuela):** no usar OpenAI como respaldo; no hacer que la app muera si cae internet o el proxy; no guardar la cola solo en memoria; no re-subir archivos completos ni re-descargar modelos; no reintentar sin backoff ni sin límite; no meter el modelo en el instalador; no asumir fibra de 100 Mbps; no gastar en servicios nuevos sin OK explícito; no prometer que el proxy hace el uso "seguro" o "legal".

---

## 11. UI/UX de escritorio

**Qué hacen bien los referentes (fuentes: Microsoft Learn, manual.raycast.com, destiner.io, thejaymo.net, noirbook.org, dev.to)**

### (a) Mascotas: la lección de Clippy

- **Qué funcionó de Clippy:** humanizar la ayuda tenía base (Stanford: el personaje con ojos resultaba el más "confiable y entrañable"); a los usuarios les gustaba "tener a alguien con ellos y no estar solos".
- **Qué lo mató (3 errores a no repetir):** (1) sin memoria ni contexto — trataba al usuario como principiante cada vez; (2) intrusivo y sin modales — aparecía sin invitación, interrumpía a mitad de frase, repetía el mismo error; (3) distracción constante — sus animaciones en reposo estaban diseñadas para parecer vivo, pero eran "una distracción constante y molesta". Y además: **sugería pero no hacía nada** — un compañero debe ejecutar, no solo sugerir.
- **Mascotas actuales que sí funcionan:** Duolingo (Duo) aparece **solo en momentos con significado** (al completar, al esperar, al recordar la racha), no flotando sin parar. Su fuerza está en la reacción al estado del usuario, no en la presencia continua.
- **El patrón opuesto (qué evitar):** Desktop Goose / Shimeji caminan por la pantalla, roban el cursor, tapan ventanas; "divertidos pero se vuelven una molestia". Error fatal de Desktop Goose: **no tenía forma de apagarlo temporalmente** (había que matar el proceso o mantener ESC).
- **Regla destilada:** la mascota de Growi debe ser **reactiva, no ambiental**: quieta en reposo, anima solo ante eventos (clic, arrastre, tarea terminada). Y debe tener un apagado de un clic, visible, sin castigo. (Ya decidido en el build 2: respiro corto de 6 fotogramas cada 8–15 s; anima de verdad solo al hacer clic, al arrastrar, al terminar una tarea y mientras Claude trabaja.)

### (b) Paleta de comandos

- Atajo estándar: **Ctrl+K** en Windows (Cmd+K en Mac). "On the web, ⌘+K is the de-facto standard, and you need a convincing reason not to use it." ([destiner.io](https://destiner.io/blog/post/designing-a-command-palette/))
- Búsqueda difusa, no subcadena exacta: `ssmd` debe encontrar "Set Syntax: Markdown". Fuzzy + alias/palabras clave por acción (p. ej. "sincronizar", "sync", "subir").
- Al abrir, mostrar algo útil, no un input vacío: recientes, frecuentes y sugerencias. (Sublime muestra todos los comandos alfabéticamente: "equally useless".)
- Favoritos / más usados primero: el usuario usa 4–5 comandos el 50% del tiempo; más usados + favoritos con atajos Ctrl+1..9.
- Mostrar los atajos en cada fila y permitir reasignarlos desde la paleta.
- Acciones secundarias: Ctrl+K abre el panel de acciones del ítem; Enter = primaria, Ctrl+Enter = secundaria; se puede escribir para filtrar acciones. Las destructivas van en rojo.
- Velocidad es la función: "keyboard-first, minimal, results in milliseconds". Un solo punto de entrada (no varias paletas con atajos distintos). Conmutable: el atajo de nuevo cierra la paleta; Esc cierra siempre.
- 21 acciones es un buen tamaño (cabe sin paginación pesada), pero no incluir cada preferencia: solo "abrir la pantalla de ajustes".

### (c) Bandeja del sistema

- El icono controla la app: doble clic restaura, clic abre el menú. El menú debe tener siempre **Salir**.
- Cerrar a bandeja debe ser explícito y opt-in ("Al cerrar, mantener en la bandeja"), no una sorpresa; siempre debe haber forma clara de salir de verdad.
- Icono 16×16 nítido; no poner texto dentro del icono (no escala). El distintivo debe ser un punto o forma simple, no un número pequeño ilegible. (El fix ya aplicado — personaje 56×56 con distintivo de 28 px — va en esta dirección.)
- **Toasts (Microsoft Learn, fuente oficial):** informativos y valiosos, nunca ruidosos; "shouldn't distract or create more work". Si la notificación no requiere alerta, va silenciosa al Centro de notificaciones. Respetar Focus Sessions (No molestar). Al hacer clic, la app abre en el contexto de la notificación. Limpiar las notificaciones viejas cuando el usuario ya vio el contenido en la app. ([toast-ux-guidance](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/toast-ux-guidance))
- Texto corto: título 1 línea, cuerpo 1–2 líneas; <40–50 caracteres; 3–5 toasts por sesión como máximo; agrupar los relacionados.
- La app debe ser descubrible sin la bandeja: Windows oculta iconos inactivos; atajo global + entrada en el menú Inicio. Consumo en reposo <1% CPU.

### (d) Micro-interacciones

- Duraciones: micro-interacciones 100–300 ms; transiciones 200–500 ms; nunca más de 1 s.
- Feedback en 100–200 ms tras la acción. Nunca easing lineal: ease-out al entrar, ease-in al salir, ease-in-out al moverse.
- Test funcional vs decorativo: "Would the interface be confusing without this animation? Yes → keep it. No → reconsider."
- Máximo 2 micro-interacciones simultáneas por segundo; consistencia de tiempos; respetar la preferencia de reducir movimiento.
- Estados de carga: spinner o esqueleto mientras se espera; nunca una pantalla congelada sin señal.

### (e) Accesibilidad y legibilidad en Windows

- Contraste mínimo **4.5:1** texto normal, 3:1 texto grande (Microsoft Learn; la guía de software inclusivo apunta a 5:1). **Nunca transmitir información solo con color** (~7% de hombres tienen alguna deficiencia de visión de color).
- Tipografía Windows 11: una sola fuente, Segoe UI Variable; mínimos **14 px Semibold / 12 px Regular**; sentence case, no TODO EN MAYÚSCULAS; alinear a la izquierda.
- Teclado completo: todo el flujo principal solo con teclado; Tab en orden lógico; foco visible siempre; atajos documentados.
- **DPI/escalado (crítico en tkinter):** tkinter **no es DPI-aware por defecto** y el texto sale borroso en 125%/150%/200%. Llamar `SetProcessDpiAwareness(2)` (per-monitor V2) **antes** de crear la ventana. Ojo: Tk escala las fuentes automáticamente pero **NO el layout** — los tamaños en píxeles fijos no escalan y el texto se sale de sus cajas en 150%. Escalar el layout con el mismo factor (`winfo_fpixels('1i')/96`).
- Modo oscuro/claro siguiendo el sistema; en alto contraste, no usar colores fijos sino recursos del sistema.
- Si hay animación, la información debe estar disponible también sin animación.

### Reglas concretas de UI/UX para Growi Bridge 0.2.0

**P0 — Sin esto, 0.2.0 no sale**

1. Proxy central y visible (ver §10).
2. Mapa de disponibilidad con chequeos reales.
3. Ollama como respaldo real (detección, descarga con progreso y reanudación en el onboarding, cambio automático).
4. Honestidad sobre el baneo + botón de exportar conversaciones.
5. Paleta Ctrl+K: apertura <100 ms percibidos, fuzzy + alias en español, al abrir muestra recientes/frecuentes, Enter ejecuta, Esc cierra, Ctrl+K de nuevo la cierra, atajos visibles en cada fila, acciones secundarias con Ctrl+Enter, destructivas en rojo.
6. DPI: `SetProcessDpiAwareness(2)` antes de crear la ventana + escalar layout. Probar en 125% y 150% antes de entregar.
7. Bandeja: menú corto (Abrir, Paleta Ctrl+K, Estado del proxy, Pausar mascota, Salir). Doble clic abre. Siempre "Salir". Nunca cerrar a bandeja por sorpresa sin el ajuste explícito.
8. Toasts solo para lo que importa (tarea terminada, proxy caído, sincronización fallida). Máx. 1 por evento, texto <50 caracteres, clic abre el contexto exacto. Nada de toast por cada sincronización correcta.

**P1 — Importante, en 0.2.0 si da tiempo**

9. Mascota reactiva, no ambiental; clic derecho o botón en bandeja = "Descansar" (ocultar) inmediato.
10. Mascota con memoria mínima: que no repita el mismo mensaje dos veces seguidas; que no celebre lo que el usuario ya hizo 100 veces.
11. Micro-interacciones con presupuesto: 100–300 ms, ease-out al entrar, sin easing lineal, máximo 2 simultáneas. Feedback inmediato en cada clic (<200 ms) y spinner visible en cada espera >300 ms.
12. Contraste y texto: verificar 4.5:1; mínimo 12 px regular / 14 px semibold; Segoe UI; sentence case; estado nunca solo por color (icono + texto, p. ej. "● Conectado").
13. Teclado completo en la ventana principal; foco visible; Ctrl+K global; atajos listados en la paleta.
14. Modo oscuro/claro siguiendo el sistema; probar en alto contraste.
15. Alquiler del proxy solo si se costea antes (script de alta/baja en tinyproxy, credenciales por usuario, revocación en un clic). No prometer $2,50/mes en la app hasta tener el costo del VPS.

**P2 — Pulido**

16. Ventana principal: barra lateral con secciones claras, un solo nivel de navegación, sin tarjetas idénticas (regla anti-vibe ya vigente).
17. Sonidos: ninguno por defecto.
18. Arranque con Windows: opt-in explícito en el onboarding, no por defecto silencioso.

**QUÉ NO HACER (UI/UX)**

- NO animaciones en reposo de la mascota ni movimientos aleatorios por la pantalla.
- NO pop-ups no solicitados de la mascota ("Parece que estás escribiendo…").
- NO prometer "Claude/ChatGPT funcionan seguro".
- NO vender el proxy sin costear el VPS ni sin resolver que BasicAuth viaja sin cifrar.
- NO toast por cada sincronización correcta; NO más de 1 toast por evento.
- NO texto <12 px, NO TODO EN MAYÚSCULAS, NO información solo por color.
- NO gradientes, NO tarjetas idénticas, NO eyebrow en mayúsculas, NO meta-strings (anti-vibe, ya vigente).
- NO liquid glass (no factible en tkinter — ya decidido).
- NO bloquear la app si el proxy cae: degradar a local.

**Qué queda para 0.3.0 (UI/UX):** panel de gestión del alquiler del proxy (falta costear VPS, cobro en Venezuela, cifrado); túnel cifrado para el proxy; descarga de modelos Ollama en segundo plano con reanudación robusta; mascota con más estados (primero validar que la mínima no molesta); atajos personalizables desde la paleta; soporte completo de lector de pantalla (tkinter lo hace difícil — evaluar cambio de toolkit); detección automática de Focus Sessions para suprimir toasts.

---

## 12. Conectores que ya tenemos — inventario y qué aporta cada uno

Investigación leyendo los `CONNECTOR.md` de `~/workspace/custom-connectors/` y `/opt/hatch/connectors/` y los helpers en `bin/`. Dos lecturas gratuitas en vivo: `GET /repos/leandrogzn98-hash/growi-bridge` y `tripo.py status`. No se tocó el runner ni el PC.

| Conector | Qué hace | Aporta a Growi Bridge / esta noche | En 0.2.0 |
|---|---|---|---|
| **GitHub** | Repo `leandrogzn98-hash/growi-bridge` (público, verificado en vivo). Helper `bin/github_api.py` (wrapper REST con PAT); MCP oficial de sistema con OAuth. | Canal de distribución del build 2 y de las releases; versionar runner y extensión; auto-update del PC desde el release; registro de issues/bugs que reporte la app. | **SÍ, núcleo** |
| **Apify** | API v2, usuario `leandrogzn`, plan FREE ($5/mes), acceso a todos los Store Actors. Helper `status/search/run/run-get/dataset`. Scraper TikTok `GdWCkxBtKWOsKjdch`. | Cosecha de TikTok/IG para el pipeline Summit Maker (radar de contenido → briefs). Cada run gasta créditos: solo con OK explícito. | **NO en la app** — solo VM; el Bridge no necesita scrapear |
| **Mobbin** | MCP `api.mobbin.com`, OAuth2, cuenta Pro. 3 herramientas de solo lectura: `search_screens` (600.000+ pantallas reales), `search_flows`, `search_sections`. | LA fuente de referencia para rediseñar la UI del Bridge (tkinter) y la extensión: buscar pantallas reales de "desktop app settings", "model library grid", "extension popup" y extraer el ADN (no copiar capturas). Insumo anti-vibe. | **SÍ, en diseño** |
| **Tripo** | API `openapi.tripo3d.ai`, Bearer `tsk_...`. Helper `bin/tripo.py` (`status/task/text3d/image3d/multiview3d`). **Saldo verificado en vivo: 370,0 créditos (no 970 como decía la memoria del 19 oct; se gastaron ~600).** A 1 crédito = $0,01 quedan ~$3,70. | Generador 3D por defecto de la biblioteca de modelos (multiview con 4 fotos, formato verificado contra el SDK oficial). El Bridge cataloga los `.glb`, su task_id y su costo. | **SÍ** |
| **Meshy** | API `api.meshy.ai`, helper `bin/meshy.py` (`text3d/image3d/multi3d --pbr/status/task/list`). Modelos retenidos máx. 3 días: descargar siempre al terminar. Sin endpoint público de saldo. | Segundo generador 3D (fallback cuando Tripo no resuelve una forma). $0 de saldo documentado. | **Después** — dos generadores 3D en la misma versión es scope de más |
| **Bright Data** | SERP API + Web Unlocker, helper `bin/brightdata.py`. Saldo $50 (29 sep 2026). | Nada hoy: la cuenta `hl_241ab6de` está activa pero **sin zonas activas → `can_make_requests: false`**. Sin zona no hay scraping. | **NO, bloqueado** hasta que Leandro cree una zona en el panel |
| **Gemini** | Helper `bin/gemini.py` (`ask`, `transcribe`), modelo por defecto `gemini-3.8-flash`. | Transcribir audios/notas de voz del puente y preguntas rápidas sin gastar cuota de Muse ni del presupuesto Anthropic. Herramienta del asistente. | **Solo VM** |
| **ElevenLabs** | TTS en español, helper `bin/elevenlabs.py` (`status/voices/history/tts`, `eleven_multilingual_v2` por defecto). Plan free: 10.000 caracteres/mes; `tts` gasta y exige autorización. | Narración de videos del Bridge o del asistente (voz en español para demos/tutoriales). | **Después de 0.2.0** |
| **Resend** | Correo transaccional, helper `bin/resend_api.py` (`domains/send/get`). Dominios verificados: hayai.com.ve, summitmaker.co, mariaalejandramancebo.com, grupojall.com. | Notificaciones por correo ("build 2 listo", "render terminado"). Cada `send` exige aprobación explícita. | **NO en la app** — solo VM |
| **Hayai Space** | API interna `space.hayai.com.ve/api/v1`, solo lectura (`finanzas/clientes/proyectos/gastos/tareas/buscar/notificaciones`). Escritura existe pero es sistema compartido: confirmar con Leandro. | Registrar tareas/avances del Bridge como tareas de HAYAI Space; consultar finanzas/clientes para priorizar. | **NO en 0.2.0** — gestión interna, no funcionalidad del Bridge |
| **Hostinger / Railway** | Hostinger: doc mínimo, VPS `hayai-vps` (root@2.25.244.222) gestionado por SSH, no por el conector. Railway: GraphQL `backboard.railway.com/graphql/v2`, `bin/railway_api.py`; rotación de secretos pendiente + correo que nombra sus dos workspaces como de interés para un atacante. | Infra que sostiene el puente (VPS/proxy) y los despliegues (Aqualine, Hayai Space). | **Soporte, NO dentro de la app** |
| **Descript** | API `descriptapi.com/v1`, helper `bin/descript_api.py` (`status/projects/project/transcript/jobs/job`). Transcript gratis y síncrono. Drive actual: Summit Maker. | Transcripciones de los videos de Summit Maker y del material del Bridge. | **Después** |
| **Zenmux / legacy-anthropic** | Zenmux: gateway OpenAI-compatible, `bin/zenmux_chat.py`, modelo por defecto `openai/gpt-6-luna`. Anthropic: API de Claude con key de pago, presupuesto **$50/mes**, `bin/anthropic_chat.py` + `bin/spend.py` (aviso al 80%, bloqueo al 100%), modelo por defecto `claude-haiku-5-5`; Opus y Fable prohibidos sin OK explícito. | Motor barato del trabajo de esta noche: resúmenes largos, procesamiento por lotes, borradores, sin quemar la cuota semanal de Muse. Zenmux primero (plan ya pagado), Haiku para lo que necesite calidad Claude barata. | **Solo VM, no app** |
| **Claude Code (sesión Max)** | No es un conector: no tiene `CONNECTOR.md`. Es el motor que corre **en el PC** (sesión Max de Leandro, Opus para el trabajo pesado). | El ejecutor. El Bridge lo orquesta (prompts por el puente de archivos, recoge resultados), no lo "conecta" vía API. | **El ejecutor** |

**Conectores que NO van dentro de la app (solo los usa el asistente desde la VM):** Apify, Bright Data, Gemini, ElevenLabs, Resend, Hayai Space, Hostinger, Railway, Descript, Zenmux, Anthropic. Razón común: llevan credenciales del asistente, gastan créditos/dinero por uso, o son sistemas internos de HAYAI. Meterlos en una app de escritorio distribuida por GitHub expondría credenciales y costos. El Bridge solo necesita: **GitHub** (distribución/updates), **Tripo** (generación 3D para la biblioteca — y aun así, mejor vía el puente: la VM genera y el PC cataloga) y **Mobbin** como referencia de diseño en tiempo de desarrollo, no en runtime.

**Combinaciones que valen la pena:** Mobbin + GitHub (referencias → Opus rediseña UI → release versionado); Tripo + GitHub (`.glb` y catálogo versionados); Apify + Gemini (cosecha TikTok → transcribe audio → brief Summit); Descript + ElevenLabs (transcribe/edita → voz en español); Zenmux/Haiku + GitHub (borradores de docs y changelogs baratos); Hayai Space + Resend (tarea completada → correo al cliente, con aprobación).

**Extras encontrados:** `custom.magicpatterns` (generador de prototipos UI con IA, API REST v3, cuenta `jallgroupai@gmail.com`, plan Starter de pago; flujo `create → wait → prompt → read → publish`) — alternativa/complemento a Mobbin para prototipar la UI del Bridge; gasta créditos por creación. `custom.framer`: carpeta existe pero `bin/` vacío y sin doc leído — no afirmar nada de él.

**Advertencias:** Tripo: saldo real 370 créditos, no 970 — contar las generaciones de la biblioteca de modelos. Docs en plantilla sin rellenar (Tripo, GitHub custom, Gemini, Hostinger, Railway): lo que vale es el helper en `bin/`, no el doc. Bright Data inutilizable hoy. Claude Code Max no tiene conector: no buscarle uno.

---

## Arquitectura recomendada: orquestación (detección de fin de tarea → revisión → corrección o avance de fase)

**Idea central:** el runner no es un lanzador de comandos; es un bucle cerrado. Cada tarea pasa por los mismos pasos, y el paso de revisión decide si se corrige o se avanza. Nada se da por hecho sin verificar el resultado contra el encargo.

### Pasos concretos

1. **El usuario (o Growi desde el chat) pide una tarea en palabras normales.** La app la convierte en un `*.task.json` con: `id`, `prompt` (el encargo completo, con criterios de aceptación escritos), `cwd`, `motor` (claude / ollama / codex / meshy / api…), `modelo`, `timeout_min`, `allowed_tools`, `permission_mode`, `session_id` (para continuar).
2. **El runner ejecuta un motor y recoge el resultado normalizado** (`status`, `result`, `cost_usd`, `num_turns`, `session_id`, `stderr`, `error`). El heartbeat se congela mientras el motor trabaja: es normal, no un fallo.
3. **Detección automática de fin de tarea.** El motor termina cuando: devuelve su JSON de salida, el proceso sale (exit_code), o salta el timeout. El runner escribe `<id>.result.json` en `outbox/runner-results/` y marca la tarea como terminada. Si el resultado viene vacío o con error, la tarea se marca como fallida, no como terminada.
4. **Revisión automática (el paso que hoy no existe).** Al terminar, el runner (o Growi) lanza una **revisión** con un motor barato (Haiku por API o Hermes local): compara el `result` y los archivos tocados contra los criterios de aceptación del encargo. La revisión devuelve: `aprobado` (sí/no), `qué falta` (lista concreta) y `evidencia` (archivos/líneas que lo demuestran).
5. **Decisión:**
   - **Aprobado → avanzar de fase.** Si la tarea era la fase N de un plan, se encola la fase N+1 con el contexto de lo ya hecho (y el `session_id` para continuar la conversación si el motor lo soporta).
   - **No aprobado y quedan rondas → ronda de corrección.** Se crea una tarea nueva con el mismo `session_id` y un prompt que es solo la lista de "qué falta", sin repetir todo el encargo. Máximo 3 rondas por defecto; después se para y se avisa al usuario con el reporte honesto ("intenté X, no pude confirmar Y").
   - **No aprobado y no quedan rondas → avisar al usuario.** La tarea queda en "necesita decisión" con el plan visible y la pregunta de opción múltiple (estilo Raycast modo agente: parar, preguntar, continuar).
6. **Visibilidad durante todo el bucle.** La app muestra: plan con pasos, qué paso va, qué motor trabaja, costo acumulado de la tarea, rondas usadas (1/3). Banner visible mientras el motor trabaja + botón "Parar" que mata lo en curso de verdad. Toast al terminar (solo 1, con el resultado).
7. **Persistencia.** Cada tarea, cada ronda y cada revisión quedan en la cola SQLite (ver §10c): si se va la luz a mitad de la ronda 2, al arrancar se reanuda desde donde quedó, no desde cero.
8. **Aprobación humana en lo sensible.** Antes de ejecutar un paso que borra, publica, gasta o envía algo, el plan se muestra y el usuario aprueba ese paso (loop de ClippyAI: plan visible → aprobación → actuar → reporte). Niveles de guardrail en palabras normales; por defecto "Preguntarme siempre".

### Qué se revisa y cómo (criterios de aceptación)

- Cada encargo lleva sus criterios escritos ("el archivo X existe y tiene Y líneas", "los 5 marcadores del build 2 están presentes", "el .glb pesa lo que declara su header"). La revisión los comprueba uno por uno contra archivos reales, no contra lo que el motor dice que hizo.
- Regla anti-éxito-inventado: si ninguna acción tuvo éxito real verificable, el reporte dice "lo intenté pero no pude confirmar que funcionara".

---

## Arquitectura recomendada: MCP y multi-CLI (resumen operativo)

- **MCP servidor (0.2.0, fase 1):** servidor stdio en Python (FastMCP) con las 10 herramientas del §7. Es lo que permite que Claude Code use el puente como herramienta. Fase 2: Streamable HTTP en `127.0.0.1:8765/mcp`.
- **MCP cliente (0.2.0, fase 1):** no reinventar el cliente; usar el del SDK oficial dentro del runner, con `mcp_servers.json` editable en palabras normales. Claves en Credential Manager. Vía práctica inmediata: Claude Code como cliente (`claude mcp add`).
- **Muse.ai (0.3.0):** no hay MCP documentado en la app de consumo. Integración por Custom Connector contra la API del Bridge (túnel o VPS) o por Muse Code. No prometerlo en 0.2.0.
- **Multi-CLI (0.2.0):** motores descritos por JSON (§8), resultado normalizado único, modo seguro por defecto. Claude Code primero, Codex segundo, Ollama por API, Meshy como motor asíncrono separado.
- **Multi-asistente (0.2.0):** elegido en el onboarding (Muse / Claude Code / Grok / Dot / Codex / Otro). El elegido responde en la paleta y el chat; los demás quedan como motores secundarios por tarea.

---

## Alcance recomendado para Alpha 0.2.0 (qué entra ahora, realista para una noche)

**Entra (en orden):**

1. **Instalar el build 2 corregido y verificarlo** (copiar del Inbox a la raíz, verificar los 5 marcadores antes de reiniciar, sin rollback silencioso; prueba Ollama como confirmación de que corre el build 2). Sin esto, todo lo demás se construye sobre el build 1.
2. **Pestaña Modelos (Ollama):** estado en 3 estados, catálogo curado, semáforo por VRAM con "Comprobar mi PC", instalar con progreso real, borrar con confirmación, selector de motor, motor `ollama:<modelo>` en el runner. (Task Opus Modelos, ya preparado.)
3. **Extensión de navegador** (task Opus ya enviado, en curso): carpeta `growi-bridge-browser/`, servidor local 127.0.0.1:8788, comandos tabs.list/read/navigate/click/type/new/close/screenshot. Lista para instalar en modo desarrollador.
4. **Paleta Ctrl+K pulida (P0 de Raycast):** Enter/Ctrl+K, favoritos arriba, alias cortos, ranking por frecuencia, búsqueda difusa, fallback a la IA.
5. **Proxy central + mapa de disponibilidad (§10):** estado en la bandeja, onboarding de un clic, cambio automático a Ollama, tabla viva con chequeos reales, honestidad sobre el baneo + exportar conversaciones.
6. **Gasto visible en la bandeja (§4):** un solo número (% ventana semanal Max), tooltip de 3 líneas, tres dineros separados.
7. **Cola persistente en SQLite + reintentos con backoff (§10c):** ninguna tarea se pierde por un apagón.
8. **Revisión automática del runner (pasos 3–5 de la orquestación):** al menos la revisión con motor barato y una ronda de corrección. Sin esto no hay orquestación.
9. **DPI y reglas P0 de UI/UX (§11):** `SetProcessDpiAwareness(2)` + layout escalado, contraste 4.5:1, textos ≥12 px, bandeja con menú corto y "Salir", toasts solo para lo que importa.
10. **GitHub como canal de distribución:** release del build 2 con instalador; auto-update del PC desde el release.

**No entra (y por qué):** servidor MCP Streamable HTTP (fase 2; stdio basta para 0.2.0); integración con Muse.ai (no hay MCP documentado; va por Custom Connector en 0.3.0); Store de extensiones (sin usuarios no tiene sentido); alquiler del proxy (falta costear VPS, resolver cifrado y cobro); Meshy como segundo generador 3D (Tripo basta; Meshy tiene $0 de saldo); panel de gestión del proxy; mascota con más estados; lector de pantalla completo; descarga de modelos en segundo plano con reanudación robusta (en 0.2.0, descarga guiada en el onboarding).

---

## Roadmap

### 0.3.0

- Servidor MCP en Streamable HTTP (localhost) + cliente MCP con `mcp_servers.json` en palabras normales.
- Integración con Muse.ai por Custom Connector (API del Bridge vía túnel/VPS) o Muse Code como cliente MCP.
- Codex como segundo motor del runner (tras verificar `codex exec --json` en el PC).
- Descarga de modelos Ollama en segundo plano con reanudación robusta.
- Túnel cifrado para el proxy (SSH/TLS) en vez de BasicAuth en claro.
- Panel de gestión del alquiler del proxy (si se costea el VPS y se resuelve el cobro en Venezuela).
- Mascota con más estados (celebra rachas, informe diario) — solo tras validar que la mínima no molesta.
- Atajos personalizables desde la paleta.
- Comandos de IA guardados (prompts reutilizables sobre el texto seleccionado).
- "¿Qué me falta por responder?" por persona (AirJelly, P1).

### Más allá (0.4.0+)

- Gadget físico ESP32 con el Muse Gadget SDK (firmware + SDK Linux, Apache 2.0): la app deja la puerta abierta a la conexión local por USB/serial; el hardware se construye después, con plaquitas baratas.
- Store de extensiones propio (solo cuando haya usuarios suficientes para curarlo).
- WhatsApp como canal del asistente (OpenClaw: Baileys con QR; solo el dueño por defecto).
- Memoria con búsqueda vectorial + decaimiento temporal (AirJelly) — solo si la memoria en Markdown se queda corta.
- Soporte completo de lector de pantalla (puede exigir evaluar cambio de toolkit: tkinter lo hace difícil).
- Detección automática de Focus Sessions para suprimir toasts.

---

## Dudas sin verificar (recopiladas de los 12 hilos)

1. **Gemini en Venezuela:** las listas oficiales de Google incluyen a Venezuela para la app web y la API, pero no está verificado el comportamiento real desde IP venezolana ni si Google AI Pro se puede pagar desde Venezuela. Comprobar en vivo desde el PC (con y sin proxy) antes de escribir nada en el mapa.
2. **Pago del Max con tarjeta venezolana (BDV Internacional u otra):** no hay fuente fiable. Es el riesgo de continuidad nº 2 después de la suspensión por región.
3. **Cuota restante de Max:** no hay API pública. Las vías no oficiales (endpoint OAuth no documentado, `claude -p "/usage"`, statusline) no están verificadas en el PC.
4. **Hermes 3 8B en la RTX 3060 de 6 GB con contexto útil:** las fuentes dicen que pide ~8 GB de VRAM; solo una prueba en el PC lo confirma.
5. **Reanudación de `ollama pull`:** la doc dice que reanuda; algunas guías dicen que deja modelos rotos. Solo una prueba con un corte real lo resuelve.
6. **Acceso a registry.ollama.ai y Hugging Face desde Venezuela sin proxy:** no verificado.
7. **Raycast:** paridad de Windows frente a Mac; si el plan Free actual incluye mensajes de IA; si el tool-calling con Ollama ya es estable en v2.6.
8. **OpenClaw:** Windows nativo vs WSL2; OAuth eliminado en ene 2026 según una fuente (contradictorio).
9. **Multi-CLI:** si Gemini CLI fue reemplazado por Antigravity; Grok Build en Windows; flags de `meshy make`; Copilot CLI.
10. **MCP:** si el SDK Python v2.0.0 renombró `FastMCP` a `MCPServer`.
11. **Proxy:** latencia real, `MaxClients` y si el tinyproxy actual tiene auth activada; costo mensual del VPS (imprescindible antes de prometer $2,50/mes); cómo cobrar en Venezuela (Pago Móvil, USDT); implicaciones legales de alquilar el proxy (no investigado).
12. **Bright Data:** sin zonas activas no sirve; no contar con él hasta que Leandro cree la zona.

---

## Fuentes consultadas

| Fuente | Qué aportó |
|---|---|
| https://manual.raycast.com/search-bar | Paleta: ranking, fuzzy, favoritos, vista vacía, modo compacto |
| https://manual.raycast.com/keyboard-shortcuts | Panel de acciones, Enter/Ctrl+Enter, atajos |
| https://manual.raycast.com/extensions | Sistema de extensiones, Store, modos de comando, Teams |
| https://manual.raycast.com/ai/quick-ai | Quick AI, fallback, modelos por superficie |
| https://manual.raycast.com/new-in-v2 | AI Chat, proyectos, memoria, modo agente, indexador Rust |
| https://www.raycast.com/pricing | Precios vigentes Pro $10 / Plus $20 / Max $50 |
| https://www.raycast.com/changelog/1-96-0 | 50 mensajes gratis de IA (contradice precios actuales) |
| https://www.raycast.com/changelog/1-100-0 | Bring Your Own Key, MCP experimental, Ollama |
| https://en.wikipedia.org/wiki/Raycast_(software) | Beta pública de Windows (20 nov 2025) |
| https://github.com/Xoshbin/asyar | Benchmark de latencia de Raycast (22,2 ms mediana) |
| https://newsletter.bearliu.com/p/how-to-tell-if-your-paid-feature | Escala del Store (2.500+ extensiones, 500–800 mantenidas) |
| https://ollama.com (docs oficiales) | API local, endpoints, CLI |
| https://runlocal.laftel.io/posts/does-ollama-work-offline | Ollama 100% offline tras la descarga |
| https://openclaw.ai (repo y docs oficiales) | Gateway, skills, canales, modelos, memoria |
| https://tokenbar.app | TokenBar: qué muestra, precios, diseño "siempre visible" |
| https://github.com (CodexBar) | Antecedente open source, doble barra, PTY `/usage` |
| https://airjelly.ai | Ciclo mirar → recordar → actuar, memoria dual, precio $0 |
| https://clippyai.app, /security, /changelog | Loop con aprobación, guardrails, precios |
| https://clawdcursor.com | Verificación por paso, `safety.evaluate()` |
| https://modelcontextprotocol.io | Spec MCP 2026-07-28, transportes, primitivas |
| https://docs.anthropic.com / https://claude.com (vía Meta) | Muse.ai no documenta MCP; Muse Code sí |
| https://madrobot.blog/2026/09/29/is-claude-available-in-my-country-supported-countries-not-available-fix/ | Venezuela fuera de la lista de Anthropic (185 países) |
| https://help.openai.com/en/articles/5347006-openai-api-supported-countries-and-territories | Venezuela fuera de la lista oficial de OpenAI |
| https://ai.google.dev/gemini-api/docs/available-regions | Venezuela SÍ en la lista de la API de Gemini |
| https://www.scmp.com/tech/tech-war/article/3369526/hong-kong-users-caught-offguard-anthropic-tightens-vpn-access-claude | Oleada de suspensiones por VPN (oct 2026) |
| https://www.ookla.com/s/media/2026/09/Q1Q2-26-Venezuela-Fastest-Fixed-Network-Report-2.pdf | Velocidades: fibra 100–175 Mbps, CANTV 10,39/5,03 Mbps |
| https://notiespartano.com/cortes-de-electricidad-duran-entre-4-y-6-horas-en-la-mayoria-de-los-hogares-venezolanos-segun-meganalisis/ | Cortes de luz 4–6 h, 24,6% de hogares sin luz a diario |
| https://elestimulo.com/opinion/2026-09-28/la-crisis-electrica-en-serio/ | Cortes diarios en Lara (Barquisimeto) |
| https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/toast-ux-guidance | Toasts: informativos, nunca ruidosos, respetar No molestar |
| https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography | Segoe UI Variable, mínimos 14 px Semibold / 12 px Regular |
| https://learn.microsoft.com/en-us/windows/uwp/design/accessibility/designing-inclusive-software | Contraste 4.5:1 / 5:1, no solo color |
| https://destiner.io/blog/post/designing-a-command-palette/ | Ctrl+K estándar, fuzzy, vista vacía útil, favoritos |
| https://thejaymo.net/2025/08/12/clippy-a-history/ | Qué mató a Clippy: sin memoria, intrusivo, distracción |
| https://dev.to/arsh_singh_93174c38ca7cc6/tk-scales-your-fonts-for-high-dpi-but-not-your-layout-hii | Tk escala fuentes pero NO el layout (DPI) |
| https://noirbook.org/topics/interaction-design | Micro-interacciones 100–300 ms, easing |
| https://man.archlinux.org/man/extra/tinyproxy/tinyproxy.conf.5.en | Tinyproxy BasicAuth por usuario, revocación |
| https://dev.to/arthurpro/you-probably-dont-need-redis-put-the-job-queue-in-your-sqlite-file-624 | Cola durable en SQLite |
| https://avi.im/blag/2025/sqlite-fsync/ | SQLite WAL + `synchronous=FULL` sobrevive a apagones |
| https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/retry-strategy | Backoff exponencial con jitter, solo errores transitorios |
| https://blog.cloudarc.io/p/rsync-streamlining-data-transfer | Sync por diferencia (rsync, `--partial`) |
| https://www.abc.com.py/internacionales/2026/09/28/ong-contabiliza-en-venezuela-77-dominios-desbloqueados-y-148-con-restricciones-en-internet/ | VPN bloqueadas en Venezuela (VE Sin Filtro) |
| https://github.com/facebookincubator/muse-gadget-sdk | Muse Gadget SDK (ESP32, Apache 2.0) — para después, no 0.2.0 |
| `~/workspace/custom-connectors/` (CONNECTOR.md + bin/) | Inventario de conectores: GitHub, Apify, Mobbin, Meshy, Tripo, Bright Data, Gemini, ElevenLabs, Resend, Hayai Space, Hostinger, Railway, Descript, Zenmux, legacy-anthropic |
| `/opt/hatch/connectors/github/CONNECTOR.md` | MCP oficial de GitHub (sistema) |
| `~/workspace/shared-bridge/growi-bridge-app/DESIGN.md` y `notas-mobbin.md` | Estado actual del build 2 y notas de diseño Mobbin |
| `~/workspace/custom-skills/local-anti-vibe/SKILL.md` | Reglas anti-vibe vigentes para la UI |

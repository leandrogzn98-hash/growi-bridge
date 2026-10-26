# Growi Bridge — Visión de la app completa

**Versión:** Alpha 0.2.0 (en construcción, noche del 25 oct 2026)
**Investigación base:** `INVESTIGACION-0.2.0.md` (12 hilos, 673 líneas, solo búsqueda web; lo no verificado va marcado)

---

## Qué es Growi Bridge, en una frase

**El compañero de escritorio que deja que un venezolano use IA de verdad**: un solo programa en la bandeja del sistema que orquesta a tu asistente (Claude Code, Ollama local, Codex, el que elijas), te deja hablarle por la paleta Ctrl+K, por WhatsApp o por la mascota, usa tu navegador y tus archivos cuando hace falta, y te muestra lo que gastas sin que tengas que preguntarlo.

No es un lanzador de apps. No es un chatbot. Es el cerebro (tu asistente) con manos (tu PC) y cara (la mascota).

---

## Las 5 decisiones

1. **Venezuela primero: el proxy ES el producto.** Claude y ChatGPT están bloqueados en Venezuela. La app existe para que un venezolano pueda usar IA. El proxy propio (VPS) es función central y visible — estado en la bandeja, mapa de disponibilidad con chequeos reales, cambio automático a Ollama local si cae — nunca un ajuste escondido. Y la app dice en voz alta el riesgo: usar Claude vía proxy puede suspender la cuenta; la vía sin ese riesgo es la API con key propia o un modelo local. Exportar las conversaciones para que un baneo no borre meses de trabajo.
2. **La paleta Ctrl+K es el centro de la app.** Gramática Raycast: Enter = acción principal, Ctrl+K = resto de acciones; favoritos arriba con la búsqueda vacía, alias cortos, ranking por frecuencia, búsqueda difusa y fallback a la IA cuando nada coincide. Apertura en menos de 100 ms percibidos. La paleta es texto, teclado y velocidad; la mascota no va dentro.
3. **Orquestación con revisión automática.** Cuando el corredor termina una tarea, se revisa el resultado contra los criterios de aceptación (con un motor barato: Haiku por API o Hermes local) y se decide: corregir en una ronda nueva (máx. 3) o avanzar de fase. Sin revisión automática no hay orquestación, solo lanzamiento de comandos.
4. **Un corredor, muchos motores.** Cada motor se describe por un archivo JSON (Claude Code, Ollama por API, Codex, Meshy asíncrono, APIs), con un resultado normalizado único. Motor principal: Claude Code con la sesión Max. Respaldo $0: Ollama local. Nunca atarse a un solo CLI. El asistente principal se elige en el onboarding (Muse / Claude Code / Grok / Dot / Codex / Otro personalizado); los demás quedan como motores secundarios por tarea.
5. **El gasto se ve en la bandeja, no en un panel.** Un solo número en el icono (% de la ventana semanal de Max que más aprieta), con tres dineros siempre separados: $ real gastado / $ equivalente de Max / $0 local. Sin modelo de créditos propio: gratis con modelos locales + trae tu propia clave.

---

## De qué está hecha (lo mejor de cada referente)

| Referente | Qué toma Growi Bridge |
|---|---|
| **Raycast** | Paleta Ctrl+K con gramática Enter/Ctrl+K, favoritos, alias, ranking por frecuencia, fuzzy, Quick AI (Tab), chat con proyectos y memoria, comandos de IA guardados, trae tu propia clave, comandos por script. No copia: ser lanzador general de Windows, Store de miles de extensiones, créditos de IA, nube/Teams. Aviso: Raycast ya está en beta pública para Windows — Bridge compite contra el propio Raycast, no contra un hueco vacío. |
| **Ollama** | Modelos locales con estado en 3 estados, catálogo curado (8–10), semáforo por VRAM, "Comprobar mi PC", instalar con progreso real, selector de motor. Para 6 GB VRAM: Gemma 3 4B verde, Hermes 3 8B naranja (~83%), Phi-4 14B rojo. |
| **OpenClaw** | Gateway único siempre encendido, un asistente con muchos canales (WhatsApp primero, solo el dueño), skills con frontmatter, modelo principal + fallbacks sin reiniciar, Ollama nativo sin `/v1`, memoria en Markdown legible, heartbeat (el resumen diario ya lo es). No copia: marketplace de skills sin curaduría, claves en texto plano, JSON al usuario. |
| **TokenBar / OhNine** | Un solo número en el icono de bandeja, tooltip de 3 líneas, desglose por tarea al hacer clic, avisos una sola vez por ventana (75% y 90%), indicador de ritmo, cuenta atrás de reinicio. No copia: 20+ proveedores, leaderboards, prometer "tiempo real". Duda central: la cuota restante de Max no tiene API pública. |
| **AirJelly** | Captura de tareas con fuente y confirmación de un clic, "¿qué me falta por responder?" por persona, brief antes de reuniones, memoria con origen visible, detección de rutinas → atajos, máx. 1 aviso/día. No copia: mirar la pantalla siempre, alertas sin freno, Autopilot sin supervisión. |
| **ClippyAI** | Plan visible con aprobación por paso, Approve/Deny con el texto completo, reporte honesto (regla anti-éxito-inventado), parada que mata lo en curso, guardrails en palabras normales, pausa ante login/2FA/CAPTCHA, borrador antes de enviar. No copia: proactividad cada 5 min, modo Trusted fácil, cobro por tokens. |

---

## Venezuela primero (requisito de diseño)

- **Bloqueos verificados:** Anthropic/Claude no disponible en Venezuela; OpenAI/ChatGPT tampoco. Google Gemini (API) SÍ lista a Venezuela: es la segunda nube, no OpenAI. DeepSeek/Qwen/Groq sin bloqueo publicado, sin verificar en vivo.
- **Proxy central:** onboarding de un clic ("Conectar"), estado en bandeja (verde = conectado, ámbar = local, rojo = sin conexión), botón "Probar proxy", cambio automático a Ollama + aviso si cae. Ajustes avanzados aparte (host, puerto, usuario, clave).
- **Alquiler del proxy ($2,50/mes):** técnicamente viable (BasicAuth por línea, revocable), pero NO se promete en la app hasta costear el VPS, resolver que BasicAuth viaja sin cifrar (túnel SSH/TLS antes de escalar) y resolver el cobro en Venezuela (Pago Móvil, USDT). Es alquiler de infraestructura de red, no de cuentas: cada usuario usa su propia cuenta y su propia key.
- **Offline-first:** modo sin conexión visible y automático (🟢 nube / 🟡 local / 🔴 sin conexión). Cola de tareas persistente en SQLite (WAL + `synchronous=FULL`): toda tarea se escribe a disco antes de ejecutarse; al arrancar se reencola lo que quedó a medias. Reintentos con backoff exponencial y jitter (solo errores transitorios; 401/403/400 no se reintentan). Sync por diferencia (hash o tamaño+fecha), nunca por archivo completo. Diseño de referencia: CANTV 10/5 Mbps y cortes de 4–6 h.
- **Gasto $0 o mínimo:** el stack $0 es Max (ya pagada) + Ollama local + Tailscale personal + VPS existente. Pagar desde Venezuela es el cuello de botella (tarjetas venezolanas no se aceptan en muchas plataformas; Stripe no opera en Venezuela).
- **Mapa de disponibilidad en la app:** tabla viva con chequeos reales (Claude, ChatGPT, Gemini, Ollama local, proxy, internet), cada fila con una frase honesta cuando algo falla y la ruta que sí anda. Nunca un error técnico sin la ruta que sí anda. Nunca hardcodear la disponibilidad: es configuración, no código fijo.

---

## Orquestación (el bucle cerrado)

1. El usuario (o Growi desde el chat) pide una tarea en palabras normales. La app la convierte en un `*.task.json` con: `id`, `prompt` (con criterios de aceptación escritos), `cwd`, `motor`, `modelo`, `timeout_min`, `allowed_tools`, `permission_mode`, `session_id`.
2. El runner ejecuta un motor y recoge el resultado normalizado (`status`, `result`, `cost_usd`, `num_turns`, `session_id`, `stderr`, `error`). El heartbeat se congela mientras el motor trabaja: es normal, no un fallo.
3. **Detección automática de fin de tarea.** El motor termina cuando devuelve su JSON de salida, el proceso sale, o salta el timeout. El runner escribe `<id>.result.json` y marca la tarea como terminada. Si el resultado viene vacío o con error, se marca como fallida, no como terminada.
4. **Revisión automática.** Al terminar, una revisión con un motor barato (Haiku por API o Hermes local) compara el `result` y los archivos tocados contra los criterios de aceptación. Devuelve: `aprobado` (sí/no), `qué falta` (lista concreta) y `evidencia` (archivos/líneas).
5. **Decisión:** aprobado → avanzar de fase (se encola la fase N+1 con el contexto y el `session_id`); no aprobado y quedan rondas → ronda de corrección (prompt con solo la lista de "qué falta", máx. 3 rondas); no aprobado y no quedan rondas → avisar al usuario con el reporte honesto y pregunta de opción múltiple.
6. **Visibilidad:** plan con pasos, qué paso va, qué motor trabaja, costo acumulado, rondas usadas (1/3). Banner visible mientras el motor trabaja + botón "Parar" que mata lo en curso de verdad. Toast al terminar (solo 1).
7. **Persistencia:** cada tarea, ronda y revisión quedan en la cola SQLite: si se va la luz a mitad de la ronda 2, al arrancar se reanuda desde donde quedó.
8. **Aprobación humana en lo sensible:** antes de ejecutar un paso que borra, publica, gasta o envía algo, el plan se muestra y el usuario aprueba ese paso. Guardrails en palabras normales; por defecto "Preguntarme siempre".

**Criterios de aceptación:** cada encargo lleva los suyos escritos ("el archivo X existe y tiene Y líneas", "los 5 marcadores están presentes", "el .glb pesa lo que declara su header"). La revisión los comprueba uno por uno contra archivos reales, no contra lo que el motor dice que hizo. Regla anti-éxito-inventado: si nada tuvo éxito real verificable, el reporte dice "lo intenté pero no pude confirmar que funcionara".

---

## Motores, MCP y multi-asistente

- **Motores (JSON por motor, resultado normalizado único):** `cli_sincrono` (Claude `claude -p --output-format json`, Codex `codex exec --json`, Gemini `gemini -p`, Grok Build, OpenCode) y `api_asincrona` (Meshy, Tripo: crear tarea → sondear → descargar). Modo seguro por defecto, nunca `bypassPermissions` como default. Prioridad: Codex segundo motor; Ollama por API; Meshy como motor asíncrono separado (ejemplo de CLI especializado).
- **MCP servidor (0.2.0, fase 1):** servidor stdio en Python (FastMCP) con 10 herramientas (`bridge_send_message`, `bridge_read_inbox`, `bridge_list_files`, `bridge_read_file`, `runner_submit_task`, `runner_task_status`, `ollama_list_models`, `ollama_pull_model`, `ollama_chat`, `bridge_status`). Fase 2: Streamable HTTP en `127.0.0.1:8765/mcp`.
- **MCP cliente (0.2.0, fase 1):** usar el cliente del SDK oficial dentro del runner, con `mcp_servers.json` editable en palabras normales. Claves en Credential Manager. Vía práctica inmediata: Claude Code como cliente (`claude mcp add`).
- **Muse.ai (0.3.0, NO en 0.2.0):** la app de consumo NO documenta forma de añadir un servidor MCP (verificado contra páginas de Meta; Muse Code sí). La integración va por Custom Connector contra la API del Bridge (túnel o VPS) o por Muse Code. No prometerlo en 0.2.0.
- **Multi-asistente:** elegido en el onboarding. El elegido responde en la paleta y el chat; los demás quedan como motores secundarios por tarea.

---

## Onboarding (4 pasos, en orden)

0. **Detección silenciosa** (antes de preguntar nada): qué CLIs hay y sus versiones, si Ollama está y qué modelos tiene, si hay sesión de Claude, qué carpetas existen. Sin bloquear si falta algo.
1. **Elegir asistente:** Muse / Claude Code / Grok / Dot / Codex / Otro. Preseleccionar el detectado. En palabras normales.
2. **Conectar:** inicio de sesión por navegador o clave, con "¿Dónde consigo mi clave?" y "Lo haré más tarde" siempre disponible. Nunca bloquear sin clave.
3. **Carpetas, con 3 niveles:** "Solo mirar" / "Mirar y cambiar" / "Preguntarme siempre" (por defecto). El usuario elige qué carpetas ve el asistente.
4. **Comprobación en vivo:** 3 pruebas con ✓/✗ estilo `claude doctor` (proxy, motor, carpetas). Y "Empezar a hablar" con un ejemplo concreto.

Después (no en el onboarding): MCPs, proxy/VPN (solo si falla una conexión), más modelos, arranque automático. Sin tecnicismos en la cara del usuario ("MCP", "gateway", "endpoint", "quantization", "context window", "JSON", "config" — todo en palabras normales: "modelo", "habilidad", "canal", "regla"). Siempre "Saltar por ahora". Primera victoria en los primeros 2 minutos.

---

## UI/UX (reglas P0 para 0.2.0)

- **Mascota reactiva, no ambiental** (lección de Clippy): quieta en reposo, anima solo ante eventos (clic, arrastre, tarea terminada). Respiro corto de 6 fotogramas cada 8–15 s. Apagado de un clic, visible, sin castigo. Que no repita el mismo mensaje dos veces seguidas.
- **Paleta:** apertura <100 ms percibidos, fuzzy + alias en español, al abrir muestra recientes/frecuentes, Enter ejecuta, Esc cierra, Ctrl+K de nuevo la cierra, atajos visibles en cada fila, acciones secundarias con Ctrl+Enter, destructivas en rojo.
- **Bandeja:** menú corto (Abrir, Paleta Ctrl+K, Estado del proxy, Pausar mascota, Salir). Doble clic abre. Siempre "Salir". Nunca cerrar a bandeja por sorpresa sin el ajuste explícito.
- **Toasts solo para lo que importa** (tarea terminada, proxy caído, sincronización fallida). Máx. 1 por evento, texto <50 caracteres, clic abre el contexto exacto. Nada de toast por cada sincronización correcta.
- **DPI:** `SetProcessDpiAwareness(2)` antes de crear la ventana + escalar el layout (Tk escala fuentes pero NO el layout). Probar en 125% y 150% antes de entregar.
- **Contraste y texto:** 4.5:1 mínimo, ≥12 px regular / 14 px semibold, Segoe UI, sentence case, estado nunca solo por color (icono + texto, p. ej. "● Conectado").
- **Micro-interacciones:** 100–300 ms, ease-out al entrar, sin easing lineal, máximo 2 simultáneas. Feedback inmediato en cada clic (<200 ms), spinner visible en cada espera >300 ms.
- **Teclado completo** en la ventana principal; foco visible; Ctrl+K global. Modo oscuro/claro siguiendo el sistema.
- **Anti-vibe vigente:** sin gradientes, sin tarjetas idénticas, sin eyebrow en mayúsculas, sin meta-strings. Sin liquid glass (no factible en tkinter).

---

## Alcance Alpha 0.2.0 (entra, en orden)

1. **Instalar el build 2 corregido y verificarlo** (5 marcadores antes de reiniciar, sin rollback silencioso; prueba Ollama como confirmación).
2. **Pestaña Modelos (Ollama):** estado en 3 estados, catálogo curado, semáforo por VRAM con "Comprobar mi PC", instalar con progreso real, borrar con confirmación, selector de motor, motor `ollama:<modelo>` en el runner.
3. **Extensión de navegador:** carpeta `growi-bridge-browser/`, servidor local 127.0.0.1:8788, comandos tabs.list/read/navigate/click/type/new/close/screenshot + `tab.upload` (subir archivos desde el PC, caso Leonardo). Lista para instalar en modo desarrollador.
4. **Paleta Ctrl+K pulida (P0 de Raycast).**
5. **Proxy central + mapa de disponibilidad.**
6. **Gasto visible en la bandeja.**
7. **Cola persistente en SQLite + reintentos con backoff.**
8. **Revisión automática del runner** (revisión con motor barato + una ronda de corrección).
9. **DPI y reglas P0 de UI/UX.**
10. **GitHub como canal de distribución:** release del build 2 con instalador; auto-update del PC desde el release.

**No entra (y por qué):** MCP Streamable HTTP (fase 2; stdio basta); integración con Muse.ai (no hay MCP documentado; Custom Connector en 0.3.0); Store de extensiones (sin usuarios no tiene sentido); alquiler del proxy (falta costear VPS, resolver cifrado y cobro); Meshy como segundo generador 3D (Tripo basta; Meshy tiene $0 de saldo); panel de gestión del proxy; mascota con más estados; lector de pantalla completo; descarga de modelos en segundo plano con reanudación robusta (en 0.2.0, descarga guiada en el onboarding).

**Conectores en 0.2.0 (solo 3):** GitHub (distribución/releases/auto-update), Tripo (generación 3D de la biblioteca — saldo real 370 créditos, ~$3,70; contar las generaciones) y Mobbin (referencia de diseño en desarrollo, no en runtime). Todo lo demás (Apify, Bright Data, Gemini, ElevenLabs, Resend, Hayai Space, Hostinger, Railway, Descript, Zenmux, Anthropic) lo usa solo el asistente desde la VM: llevan credenciales, gastan créditos o son sistemas internos; meterlos en una app distribuida por GitHub expondría credenciales y costos.

---

## Roadmap

### 0.3.0
- Servidor MCP en Streamable HTTP (localhost) + cliente MCP con `mcp_servers.json` en palabras normales.
- Integración con Muse.ai por Custom Connector (API del Bridge vía túnel/VPS) o Muse Code como cliente MCP.
- Codex como segundo motor del runner (tras verificar `codex exec --json` en el PC).
- Descarga de modelos Ollama en segundo plano con reanudación robusta.
- Túnel cifrado para el proxy (SSH/TLS) en vez de BasicAuth en claro.
- Panel de gestión del alquiler del proxy (si se costea el VPS y se resuelve el cobro en Venezuela).
- Mascota con más estados (solo tras validar que la mínima no molesta).
- Atajos personalizables desde la paleta. Comandos de IA guardados.
- "¿Qué me falta por responder?" por persona (AirJelly, P1).

### Más allá (0.4.0+)
- **0.5.0 — La oficina de agentes** (ver `INVESTIGACION-0.5.0-oficina.md`): personitas pixeladas por departamento (Claude, Codex, Gemini, Local), con el gerente Growi orquestando y el dueño (Leandro) paseando por la oficina. Departamentos = plataformas, líderes = la plataforma, empleados = submodelos y skills. Cada animación es un evento real del runner y la cola (máquina de estados de 10 estados y 21 transiciones; si no se puede leer, «sin señal», nunca «trabajando»). Vagancia honesta solo en espera real (café, charlar, celular: sistema de utilidad local, $0, sin LLM, con modo «oficina seria»). El teléfono al gerente es un prompt real; la llamada del gerente al departamento es la invocación real del agente por terminal; hablarle a un agente es un prompt real a ese motor (pregunta → respuesta en bocadillo; tarea → «me pongo en ello» + tarea encolada de verdad). Motor: Godot 4 Compatibility, condicionado a mediciones C1–C3 en el PC real (respaldo Pygame-ce). Pixel art original 32×48, 8 FPS, Pixelorama, skins como datos. Presupuesto duro: VRAM ≤128 MB, RAM ≤350 MB, CPU ≤2 % en reposo, FPS 30/15/0, escalera de degradación en 6 niveles. La oficina nunca aprueba, nunca escribe en la cola y cede siempre ante llama-server y Claude Code. Todo local, $0, offline-first.
  - Specs (en orden de dependencia): `t-oficina-mediciones-050`, `t-oficina-cola-live-050`, `t-oficina-consumo-vivo-050`, `t-oficina-encolar-externa-050`, `t-oficina-protocolo-050`, `t-oficina-motor-050`, `t-oficina-plano-050`, `t-oficina-estados-050`, `t-oficina-arte-base-050`, `t-oficina-skins-050`, `t-oficina-empleados-050`, `t-oficina-telefono-050`, `t-oficina-llamadas-050`, `t-oficina-paseo-050`, `t-oficina-vagancia-050`, `t-oficina-bocadillos-050`, `t-oficina-rendimiento-050`, `t-oficina-ciclo-vida-050`.
- **Gadget físico ESP32 con el Muse Gadget SDK** (firmware + SDK Linux, Apache 2.0): la app deja la puerta abierta a la conexión local por USB/serial; el hardware se construye después, con plaquitas baratas traídas de China. Lo que se construye ahora es el terreno en software para que la gente conecte esa plaquita a su PC.
- Store de extensiones propio (solo cuando haya usuarios suficientes para curarlo).
- WhatsApp como canal del asistente (OpenClaw: Baileys con QR; solo el dueño por defecto).
- Memoria con búsqueda vectorial + decaimiento temporal (solo si la memoria en Markdown se queda corta).
- Soporte completo de lector de pantalla (puede exigir evaluar cambio de toolkit).
- Detección automática de Focus Sessions para suprimir toasts.

---

## Lo que no está verificado (no prometerlo)

- Gemini en Venezuela desde IP venezolana (la lista oficial lo incluye, el comportamiento real no está probado).
- Pago del Max con tarjeta venezolana (BDV Internacional u otra).
- Cuota restante de Max (no hay API pública; las vías no oficiales no están verificadas en el PC).
- Hermes 3 8B en la RTX 3060 de 6 GB con contexto útil (las fuentes dicen ~8 GB de VRAM; solo una prueba en el PC lo confirma).
- Reanudación de `ollama pull` con un corte real.
- Acceso a registry.ollama.ai y Hugging Face desde Venezuela sin proxy.
- Costo mensual del VPS y cómo cobrar el alquiler del proxy en Venezuela.
- Bright Data: sin zonas activas no sirve.

---

*Documento de decisiones. La investigación completa (fuentes, qué no copiar, dudas) vive en `INVESTIGACION-0.2.0.md`.*

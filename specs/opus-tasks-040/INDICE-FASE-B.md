# Índice — Fase B de Growi Bridge 0.3.x (39 ítems de §10 + nota de conteo)

**Fecha:** 26 oct 2026. **Fuente:** `~/workspace/growi-bridge-repo/INVESTIGACION-0.3.0.md` §10 (Fase B), §12 (conteo), §14 (adenda: dos reglas que mandan), §9 (decisiones), §13 (dudas). **Carpeta:** `~/workspace/shared-bridge/opus-tasks-040/` — 39 archivos `.task.json`, todos `model: opus`, `permission_mode: acceptEdits`, `allowed_tools: "Read,Write,Bash,Glob,Grep"`, `cwd: C:\Users\forte\growi-bridge\share\inbox`, prompts en español de 5.079 a 8.196 caracteres, validados con `json.load` (claves exactas, prompt >1500).

**Pre-requisito (no es Fase B, es cerrarla antes):** la Fase A completa (30 specs de `opus-tasks-030/` verificados + `CADENA-ESTADO.json` en fase `completa`). Todos los specs asumen la Fase A terminada y construyen encima; ninguno toca VERSION. La cadena `cadena-040.py` no envía nada hasta que su propio estado diga fase `fase-b` Y el estado de la Fase A diga `completa`.

## Discrepancia de conteo: 38 vs 39

**§12 de la investigación dice 38 specs en Fase B, pero la lista visible de §10 tiene 39 nombres.** Contados uno por uno, la lista de §10 trae 39: t-politicas-persistentes-030, t-router-fallbacks, t-dag-fases-030, t-rubrica-revisor-030, t-estimado-gasto-030, t-gasto-pronostico, t-memoria-buscable, t-notas-obsidian-030, t-perfil-sobre-mi, t-spike-whatsapp, t-catalogo-030, t-embeddings-8081, t-verificar-groq-gemini, t-autocalibracion-vram, t-motor-opencode, t-transcribe-whisper, t-pedir-cosecha, t-comandos-script, t-modelo-por-superficie-auto, t-byos-visible, t-interruptor-motor, t-onboarding-fallos, t-ajustes-reorg, t-teclado-foco, t-carga-300ms, t-movimiento-contraste, t-mascota-estados, t-mascota-memoria-minima, t-matriz-estados, t-detector-avast, t-mapa-ampliado, t-prueba-corte, t-calculadora-paleta, t-automations, t-panel-estado-gateway, t-vision-gemma3-4b, t-evaluar-hermes4, t-voz-elevenlabs, t-blender-herramienta.

El desglose por hilo confirma los 39: hilo 1 aporta 4 (políticas, rúbrica, estimado, DAG), hilo 2 aporta 4 (router-fallbacks, spike-whatsapp, automations, panel-estado), hilo 3 aporta 6 (catálogo, embeddings, verificar-groq-gemini, evaluar-hermes4, autocalibración, visión-gemma3), hilo 4 aporta 5 (opencode, transcribe, pedir-cosecha, voz-elevenlabs, blender), hilo 5 aporta 4 (comandos-script, modelo-por-superficie, byos, interruptor), hilo 6 aporta 5 (gasto-pronóstico, memoria-buscable, perfil-sobre-mi, calculadora, mascota-memoria-mínima), hilo 7 aporta 3 (detector-avast, mapa-ampliado, prueba-corte), hilo 8 aporta 7 (onboarding-fallos, ajustes-reorg, teclado-foco, carga-300ms, movimiento-contraste, mascota-estados, matriz-estados), más t-notas-obsidian-030 añadido después por pedido de Leandro. Total: 4+4+6+5+4+5+3+7+1 = **39**. El 38 de §12 es anterior a ese añadido: **38 + t-notas-obsidian-030 = 39**. Se escribió un spec por cada uno de los 39 nombres reales; ninguno de relleno.

**Dos reglas que mandan (adenda §14):**
1. **«Ni flojo ni a medias» = función completa con subfunciones.** Cada spec enumera función principal + subfunciones obligatorias y la verificación cubre CADA una por separado. Entregar solo la principal es fallar la aceptación.
2. **Motor universal, no lista cerrada.** Ningún spec se ata solo a los CLI actuales de Leandro. Todo motor nuevo entra por descriptor (`t-motor-generico`); la ficha de cada motor muestra lo que NO puede, nunca se finge.

## Orden de ejecución

El orden de §10, sin saltos. Dentro de ese orden, respetar las dependencias de la tabla.

| # | Spec | Timeout | Depende de | Decisión de Leandro que lo bloquea / nota |
|---|---|---|---|---|
| 1 | `t-politicas-persistentes-030` | 60 | t-vencimiento-aprobacion-030 (Fase A; la aprobacion remota por WhatsApp NO existe, t-aprobacion-whatsapp-030 bloqueado por §13.1) | Niveles R0–R3; ninguna política la crea una tarea. |
| 2 | `t-router-fallbacks` | 60 | t-motor-generico, t-motor-gemini-agy, t-codex-verificar, t-criterios-tipados-030 (Fase A) | Fusión de los fallbacks de los hilos 1, 2 y 3. Cadena claude → gemini → llama; revisor llama → ollama → Haiku. |
| 3 | `t-dag-fases-030` | 60 | t-checkpoint-ronda-030 (Fase A) | DAG mínimo, sin motor de grafos. |
| 4 | `t-rubrica-revisor-030` | 60 | t-criterios-tipados-030 (Fase A) | Mide el costo/tiempo real de una revisión Haiku, no lo estima. |
| 5 | `t-estimado-gasto-030` | 60 | t-consumo-vivo (0.2.0) | Umbral propuesto $1/tarea, $5/plan. Sin API de cuota: nunca cuenta atrás inventada. |
| 6 | `t-gasto-pronostico` | 60 | t-estimado-gasto-030, t-consumo-vivo (0.2.0) | Pronóstico sobre acumulado, nunca sobre cuota restante. |
| 7 | `t-memoria-buscable` | 60 | t-memoria-pc (Fase A) | Búsqueda por texto primero; vectores solo si hace falta. Decaimiento solo ordena, nunca borra. |
| 8 | `t-notas-obsidian-030` | 60 | t-memoria-pc (Fase A), t-memoria-buscable | **El ítem 39 (añadido 25 oct por pedido de Leandro).** Nube opcional Muse Link como espejo, nunca original. |
| 9 | `t-perfil-sobre-mi` | 45 | t-memoria-pc (Fase A) | Perfil vacío = sin invención. |
| 10 | `t-spike-whatsapp` | 45 | — | **Spike, no construcción.** No usa el número personal para vincular nada permanente. |
| 11 | `t-catalogo-030` | 60 | t-semaforo-vram-v2, t-descargador-gguf (Fase A) | 7 modelos; instalar en orden Qwen2.5-Coder-7B, Gemma 3 4B, Qwen3-Embedding-0.6B Q8_0. ~18 GB; comprobar disco antes de cada descarga. |
| 12 | `t-embeddings-8081` | 60 | t-catalogo-030, t-router-llama-server (Fase A) | Embedder único Qwen3-Embedding-0.6B Q8_0; cambiarlo exige re-indexar. |
| 13 | `t-verificar-groq-gemini` | 45 | t-credenciales-keyring (Fase A) | Verificación con llamadas reales; sin clave, FALTA (no se inventa). No entra al router hasta verificar. |
| 14 | `t-autocalibracion-vram` | 45 | t-semaforo-vram-v2, t-ciclo-vida-llama (Fase A) | VRAM medida del log, no estimada. |
| 15 | `t-motor-opencode` | 60 | t-motor-generico (Fase A) | Verificar binario `opencode` vs `opencode2` en vivo. Sintaxis v2. |
| 16 | `t-transcribe-whisper` | 60 | — | faster-whisper local, $0, offline, español. Descript Free (1 h/mes) no cubre producción. |
| 17 | `t-pedir-cosecha` | 45 | — | **FALTA previa: `TIKTOK_MS_TOKEN` (la pone Leandro).** Sin token, no se envía pedido que va a fallar. Apify Free $5/mes ≈ 1.350 resultados. |
| 18 | `t-comandos-script` | 60 | — | Sin descarga desde internet. Aviso la primera vez que un script pide algo delicado. |
| 19 | `t-modelo-por-superficie-auto` | 60 | t-motor-generico (Fase A) | Auto visible como rápido / equilibrado / potente. |
| 20 | `t-byos-visible` | 45 | — | Duda Plus $20/mes vs API key (Codex) queda como constancia; el gasto BYOS es $ equivalente Max, nunca $ real. |
| 21 | `t-interruptor-motor` | 45 | t-motor-generico (Fase A) | Desactivar no borra el descriptor. El principal no se apaga sin sustituto. |
| 22 | `t-onboarding-fallos` | 60 | — | Plan B sin internet; checklist persistente post-onboarding. |
| 23 | `t-ajustes-reorg` | 60 | t-atajos-personalizables, t-temas-oscuro-sistema, t-credenciales-keyring (Fase A) | Sin añadir ajustes nuevos. Fuera: idioma, sonidos, claves de la VM, colores personalizados. |
| 24 | `t-teclado-foco` | 45 | — | Alt+1..8, `?` con lista buscable, foco único. |
| 25 | `t-carga-300ms` | 45 | t-descargador-gguf (Fase A, progreso real) | Esqueleto en listas, spinner en botones, progreso real en descargas. |
| 26 | `t-movimiento-contraste` | 45 | — | Probar una vez en alto contraste (Night Sky) con notas de lo que se rompe. |
| 27 | `t-mascota-estados` | 60 | — | 4 estados (proxy caído, sin internet, esperando aprobación, tarea fallida) + 6 reglas anti-molestia + validación de una semana. |
| 28 | `t-mascota-memoria-minima` | 45 | — | Solo la primera tarea del día se celebra; clic = saludo, no cajita. |
| 29 | `t-matriz-estados` | 60 | t-estados-vacios, t-estados-error (Fase A) | Auditoría página por página con capturas; no mostrar el vacío cuando lo que pasó fue un error. |
| 30 | `t-detector-avast` | 45 | t-ip-estable (Fase A) | **Fusionado en Fase A como subfunción 6 de t-ip-estable.** El spec empieza leyendo su ESTADO y solo construye lo que falte; no duplica. Nombre exacto del servicio: buscar en vivo. |
| 31 | `t-mapa-ampliado` | 45 | — | 5 filas nuevas (registry.ollama.ai, huggingface.co, github.com, controlplane.tailscale.com, cloudflare.com), con y sin proxy. |
| 32 | `t-prueba-corte` | 45 | t-checkpoint-ronda-030, t-descargador-gguf (Fase A) | **Procedimiento, no código.** Corte real mensual + `resiliencia.log`. El corte lo provoca Leandro, nunca el agente. |
| 33 | `t-calculadora-paleta` | 45 | — | Evaluación segura (sin `eval()` abierto). Sin conversor de divisas en vivo ni científica. |
| 34 | `t-automations` | 60 | t-gateway-unificado, t-memoria-pc (Fase A) | Modelo barato/local siempre; máx. 1 aviso proactivo al día al principio. El brief pre-reunión es de 0.4.0. |
| 35 | `t-panel-estado-gateway` | 60 | t-gateway-unificado (Fase A) | Datos reales o «sin datos», nunca verde falso. |
| 36 | `t-vision-gemma3-4b` | 60 | t-catalogo-030 | Gemma 3 4B + mmproj (~4,5 GB a 8k est.); medir el total real y el mmproj exacto. |
| 37 | `t-evaluar-hermes4` | 60 | t-catalogo-030, t-semaforo-vram-v2 (Fase A) | **Evaluación, no cambio de modelo.** A/B con 10 tareas fijas; tamaños Q4_K_M leídos en HF. |
| 38 | `t-voz-elevenlabs` | 60 | t-credenciales-keyring (Fase A) | BYOK; Free 10.000 caracteres/mes; aprobación por uso; aviso al 80%. |
| 39 | `t-blender-herramienta` | 45 | — | Herramienta del runner (turntable/QC por CLI), no motor conversacional. QC con laterales puros (lección del Obelisco). |

## Fusiones aplicadas (un solo spec, no dos)

- `t-router-fallbacks` fusiona los specs de fallback de los hilos 1, 2 y 3 (ejecutor + revisor, una sola cadena con sus reglas).
- `t-detector-avast` se fusionó en Fase A como subfunción 6 de `t-ip-estable`; este spec de Fase B solo verifica y completa lo que falte.
- `t-notas-obsidian-030` construye ENCIMA de `t-memoria-pc` y `t-memoria-buscable`; no los duplica.

## Ítems con FALTA documentada en el propio spec (no se finge)

- `t-pedir-cosecha`: sin `TIKTOK_MS_TOKEN` no hay cosecha real (la pone Leandro).
- `t-verificar-groq-gemini`: sin claves Groq/Gemini guardadas no hay llamadas reales; límites vivos del free tier de Gemini sin publicar (los muestra AI Studio).
- `t-detector-avast`: si la Fase A ya lo dejó hecho, el spec solo verifica.
- `t-catalogo-030` / `t-vision-gemma3-4b` / `t-evaluar-hermes4`: tamaños exactos de Hermes 4 y Qwen3.5-9B se leen en HF (las fuentes se contradicen); mmproj exacto de Gemma 3 4B sin verificar.
- `t-spike-whatsapp`: si no hay número de pruebas, el spike llega hasta donde se puede sin vincular el personal y lo deja como FALTA.
- `t-prueba-corte`: la primera prueba real la provoca Leandro; si no cabe, queda como FALTA con fecha propuesta (nunca simulada vendida por real).

## Qué NO se hace en Fase B (de §11, recordatorio para quien encole)

Paralelo real entre tareas (0.4.0), canal WhatsApp con Baileys (0.4.0, tras spike + decisión del número), alquiler del proxy (sin cifrado, precio, tope y consulta legal no se vende nada), Store/marketplace de skills, control de escritorio por clics (nunca), captura de pantalla siempre encendida (nunca), resolver logins/2FA/CAPTCHAs (nunca), Meshy como segundo generador, Grok Build, Copilot/Cursor CLI, LM Studio, vídeo generativo, migrar de toolkit (no en 0.3.x), memoria vectorial, gadget ESP32.

## Cómo encolar

1. Cerrar la Fase A (30 specs + `CADENA-ESTADO.json` en fase `completa`) antes de enviar el primer spec de esta fase.
2. El coordinador pone `opus-tasks-040/CADENA-ESTADO-040.json` en fase `fase-b` (hoy está en `espera-fase-a`); la cadena `cadena-040.py` solo actúa con esa fase Y la Fase A completa.
3. Enviar en el orden de la tabla, de uno en uno, verificando cada `ESTADO-*.md` en `share\outbox\` antes de enviar el siguiente.
4. Cada spec escribe su `ESTADO-<TEMA>.md` con LISTO / FALTA / COMO PROBARLO en `share\outbox\`.

## Fusiones en lotes (27 oct 2026, ver LOTES.md)
- **t-lote-mascota-040** fusiona `t-mascota-estados` + `t-mascota-memoria-minima` (subsistema mascota: estados + memoria anti-repetición; 7 criterios, sonnet).
- **t-lote-conectividad-040** fusiona `t-detector-avast` + `t-mapa-ampliado` (salud de red/túnel: detector Avast+Tailscale + filas del mapa de disponibilidad; 9 criterios, sonnet).
- **t-lote-evaluar-modelos-040** fusiona `t-vision-gemma3-4b` + `t-evaluar-hermes4` (evaluación de modelos locales en llama-server con VRAM medida; 8 criterios, sonnet).
- Los archivos originales quedan como referencia; en `cadena-040.py` (ORDEN) solo van los lotes, cada uno en la posición de su primer miembro.

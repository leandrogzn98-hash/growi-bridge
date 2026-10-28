# Índice — 0.4.0+ de Growi Bridge (12 ítems, para decidir en la mañana)

**Fecha:** 26 oct 2026. **Fuente:** `~/workspace/growi-bridge-repo/INVESTIGACION-0.3.0.md` §10 (0.4.0+) y §12 (conteo), §14 (adenda: dos reglas que mandan). **Carpeta:** `~/workspace/shared-bridge/opus-tasks-040plus/` — 12 archivos `.task.json`, todos `model: opus`, `permission_mode: acceptEdits`, `allowed_tools: "Read,Write,Bash,Glob,Grep"`, `cwd: C:\Users\forte\growi-bridge\share\inbox`, prompts en español de 5.290 a 7.694 caracteres, validados con `json.load` (claves exactas, prompt >1500).

**Estos NO van en ninguna cadena.** Son para después de la Fase B, a decidir en la mañana. Ninguno se envía automáticamente; cada uno se envía a mano cuando el coordinador lo decida, en el orden de la tabla o en el que se acuerde entonces.

**Decisión de Leandro 26 oct 2026, 17:49: los 12 van tras la Fase B y antes de la 0.5.0** (intercalados con la escritura de los specs 0.4.5). La 0.5.0 no arranca hasta que estos 12 estén enviados.

**Pre-requisito:** la 0.3.0 (Fase A + Fase B) terminada. Todos los specs asumen la 0.3.0 construida y no tocan VERSION.

## Conteo: 12 ítems

§12 dice 12 ítems en 0.4.0+ (9 de los hilos + 3 añadidos en la síntesis). Reconciliación: los hilos propusieron 9 (t-idempotencia-cuarentena-030, t-paralelo-seguro-030, t-canal-whatsapp, t-proyectos, t-portapapeles, t-brief-reunion, t-pendientes-por-persona, t-proxy-alquiler, t-piloto-customtkinter). De esos 9, **t-piloto-customtkinter NO está aquí**: ya tiene su spec en `opus-tasks-030/t-piloto-customtkinter-030.task.json` y se envía a mano antes de la cadena de la Fase A (ver `PLAN-ENVIO-FASE-A.md`). Quedan 8 + t-agentes-paralelos-030 (añadido en §10 por pedido de Leandro) + los 3 de la síntesis (MCP Streamable HTTP + cliente MCP, Muse.ai por Custom Connector, gadget ESP32) = **12**.

**Dos reglas que mandan (adenda §14):**
1. **«Ni flojo ni a medias» = función completa con subfunciones.** Cada spec enumera función principal + subfunciones obligatorias y la verificación cubre CADA una por separado.
2. **Motor universal, no lista cerrada.** Ningún spec se ata solo a los CLI actuales de Leandro. Todo motor nuevo entra por descriptor (`t-motor-generico`); la ficha de cada motor muestra lo que NO puede, nunca se finge.

## Orden propuesto

| # | Spec | Timeout | Depende de | Decisión de Leandro que lo bloquea / nota |
|---|---|---|---|---|
| 1 | `t-canal-whatsapp` | 60 | t-spike-whatsapp (Fase B) | **Decisión 26 oct 17:49: después (deferido por Leandro).** Sin número de pruebas el spike queda en FALTA y el canal no avanza hasta entonces. Solo el dueño; pairing; grupos cerrados; reset 4 AM. |
| 2 | `t-idempotencia-cuarentena-030` | 60 | t-dag-fases-030 (Fase B), t-checkpoint-ronda-030 (Fase A) | `run_id` + `idempotencia_key` por efecto; estado `en_cuarentena`. |
| 3 | `t-paralelo-seguro-030` | 60 | t-checkpoint-ronda-030 (Fase A), t-dag-fases-030, t-politicas-persistentes-030 (Fase B) | Máx. 2, worktree por tarea de código, merge explícito con test gate. Nunca paralelizar código sin worktree. |
| 4 | `t-agentes-paralelos-030` | 60 | t-paralelo-seguro-030, t-motor-generico, t-checkpoint-ronda-030, t-cola-visible-030 | Tope 2; contabilidad de VRAM; contexto mínimo por agente; deduplicación por `task_id`. No es lanzar 10 Claudes sin control ni agentes que se hablen sin orquestador (eso es 0.5.0). |
| 5 | `t-proyectos` | 60 | t-asistentes-perfiles (Fase A), t-memoria-buscable, t-gasto-pronostico (Fase B) | Proyectos por cliente (Aqualine, Summit Maker, HAYAI) con instrucciones, carpeta y guardrail propios. Perfiles por usuario: NO. |
| 6 | `t-portapapeles` | 60 | — | Solo texto, 30 días, excluyendo contraseñas. **Opt-in explícito, apagado por defecto.** Todo local. |
| 7 | `t-brief-reunion` | 45 | t-memoria-buscable (Fase B) | Solo fuentes que Leandro controla (calendario, MEMORY.md, tareas). Sin captura de pantalla ni lectura de chats. |
| 8 | `t-pendientes-por-persona` | 45 | Resumen 21:00 (t-automations, Fase B) | Solo con lo que pasó por el Bridge. Nunca inferir pendientes leyendo chats privados. |
| 9 | `t-proxy-alquiler` | 60 | — | **BLOQUEADO: sin precio+tope decididos, sin túnel cifrado, sin consulta legal con Angelis y sin plan exacto del VPS, NO se construye nada**; el spec solo documenta qué se haría. |
| 10 | `t-mcp-streamable-http` | 60 | — | **FALTA de investigación: §12 solo lo nombra, sin diseño.** El spec produce el diseño como propuesta con fuentes reales (espec MCP vigente) y marca lo propuesto como propuesto. Loopback + token + validar Origin. |
| 11 | `t-claude-ai-custom-connector` | 60 | t-motor-generico (Fase A), t-credenciales-keyring (Fase A) | **FALTA de investigación: «Muse.ai» no está definido.** El spec resuelve la definición antes de construir; si no se resuelve, se detiene y lo documenta. Descriptor genérico + BYOK en Credential Manager. |
| 12 | `t-gadget-esp32` | 60 | — | **FALTA de investigación: solo «la app deja la puerta USB/serial abierta».** Solo puerta en software + protocolo mínimo + emulador. **Ningún hardware en este spec**: no se compra, no se pide, no se diseña. |

## Ítems con FALTA documentada en el propio spec (no se finge)

- `t-mcp-streamable-http`, `t-claude-ai-custom-connector`, `t-gadget-esp32`: sin diseño en la investigación 0.3.0; cada spec dice qué falta y qué hace en su lugar (proponer con fuentes / resolver la definición / solo la puerta en software).
- `t-canal-whatsapp`, `t-proxy-alquiler`: bloqueados hasta la decisión de Leandro; los specs no construyen lo bloqueado.

## Qué NO se hace en 0.4.0+ (de §11, recordatorio)

Store/marketplace de skills, control de escritorio por clics (nunca), captura de pantalla siempre encendida (nunca), resolver logins/2FA/CAPTCHAs (nunca), memoria que la IA recoge sola sin mostrarla (nunca), cuenta atrás de cuota inventada (nunca), multi-agente con agentes que se hablen entre ellos sin orquestador (eso es 0.5.0, si acaso).

## Cómo encolar (cuando toque)

1. Terminar la Fase B antes de enviar el primero.
2. Enviar a mano, de uno en uno, verificando cada `ESTADO-*.md` en `share\outbox\` antes de enviar el siguiente.
3. Los specs 1 (canal WhatsApp) y 9 (proxy-alquiler) NO se envían hasta que su condición se cumpla.
4. Cada spec escribe su `ESTADO-<TEMA>.md` con LISTO / FALTA / COMO PROBARLO en `share\outbox\`.

## Lotes (27 oct 2026, ver LOTES.md)
- Sin fusiones: los 12 specs manuales se documentaron en lotes en LOTES.md pero ninguno se fusionó (dependencias cruzadas entre miembros o criterios que suman más de 12). Se envían a mano, de uno en uno, como antes.

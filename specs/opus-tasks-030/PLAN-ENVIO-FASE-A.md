# Plan de envío — Fase A 0.3.0 (pre-estadio, 25 oct 2026 20:20)

Fuente: `opus-tasks-030/INDICE-FASE-A.md` (orden de §10 + corrección §14.2).

## Protocolo (del índice, no se negocia)

- Cerrar la 0.2.0 (9 tasks + release) ANTES del primer spec de esta fase.
- **Antes de la Fase A va `t-dos-carriles-020`** (segundo carril, spec en `opus-tasks/t-dos-carriles-020.task.json`, opus 60 min). NO enviarlo mientras la cola 0.2.0 corra: LIFO lo pondría primero y su reinicio mataría la tarea en curso.
- **Después de la release y ANTES de la cadena va `t-piloto-customtkinter-030`** (piloto CustomTkinter, spec en `opus-tasks-030/t-piloto-customtkinter-030.task.json`, opus 60 min, aprobado por Leandro 22:29). Una sola superficie (Ajustes), reversible, con veredicto. Se envía A MANO (no va en la cadena: la cadena solo manda los 28 de la tabla). Si el piloto sale bien, los specs de Fase A que tocan la interfaz se ajustan a CustomTkinter; si sale mal, la cadena sigue en tkinter. El spec busca `ejemplo-ui.*` en el inbox: si Leandro manda su ejemplo antes de que corra, es el objetivo visual.
- Enviar **de uno en uno, en el orden de la tabla, verificando cada `ESTADO-*.md` en `share\outbox\` antes de enviar el siguiente**. No hay envío en bloque: el orden LIFO + la verificación por task lo impiden.
- Los specs 2 y 19 NO se envían hasta que su condición se cumpla.

## Orden de envío (30 specs)

| Pos | Spec | Timeout | Nota |
|---|---|---|---|
| 0 | t-motor-generico | 60 | Va primero. Descriptor con base_url + credencial_ref. |
| 1 | t-guardrail-visible | 60 | Subfunción 7: icono de bandeja con distintivo ámbar (18:56). Subfunción 6: popup de aviso al arrancar. |
| 2 | t-aprobacion-whatsapp-030 | 60 | **BLOQUEADO** hasta resolver §13.1 (¿puede el runner distinguir con certeza que el archivo de decisión lo escribió Muse tras un WhatsApp de Leandro?). NO implementar la aprobación remota si no se resuelve. R3 nunca por WhatsApp. |
| 3 | t-vencimiento-aprobacion-030 | 60 | — |
| 4 | t-checkpoint-ronda-030 | 60 | Depende de t-cola-sqlite (0.2.0). Subfunción 6: lanzamiento oculto de motores, sin terminales negros (19:05). |
| 5 | t-criterios-tipados-030 | 60 | Medir costo/tiempo real de una revisión Haiku, no estimarlo. |
| 6 | t-gateway-unificado | 60 | Depende de t-motor-generico + t-cola-sqlite. Resuelve credencial_ref. |
| 7 | t-skills-nativas | 60 | Formato nativo: frontmatter name/description/version/requires. |
| 8 | t-skills-semilla | 60 | **PRERREQUISITO: Growi deja las 7 skills en `share\inbox\skills-semilla\` ANTES de que corra.** Ver estado abajo. |
| 9 | t-memoria-pc | 60 | — |
| 10 | t-credenciales-keyring | 60 | Reescrito 18:45: URL base + varias claves por plataforma, una entrada DPAPI por CLAVE. |
| 11 | t-motor-gemini-agy | 60 | Depende de t-motor-generico + t-credenciales-keyring. Verificar si agy pierde stdout bajo pipe. |
| 12 | t-codex-verificar | 45 | Depende de t-motor-generico. Si falla, se retira de engines.json. |
| 13 | t-semaforo-vram-v2 | 60 | Primero leer el models-catalog.json real del PC y verificar el -np efectivo. |
| 14 | t-descargador-gguf | 60 | Medir si Hugging Face responde directo desde el PC. |
| 15 | t-router-llama-server | 60 | Depende de t-motor-generico. |
| 16 | t-ciclo-vida-llama | 60 | Depende de t-router-llama-server + t-motor-generico. |
| 17 | t-ollama-decidir | 45 | **La decisión ES el task.** Sin marcador de decisión, solo ejecuta la parte segura (quitar el motor fantasma del selector). |
| 18 | t-saldo-tripo | 45 | Depende de t-credenciales-keyring. Sin clave guardada: «no en vivo» con el último verificado (370, 25 oct 2026). No gasta créditos. |
| 19 | t-relay-ssh | 60 | **BLOQUEADO: «solo si Leandro dice que sí».** Sin marcador, NO construye nada; solo documenta. |
| 20 | t-exportar-chats | 60 | — |
| 21 | t-ip-estable | 60 | Fusiona t-detector-avast como subfunción. Nombre exacto del servicio de Avast: se busca en vivo. |
| 22 | t-atajos-personalizables | 60 | — |
| 23 | t-comandos-ia-guardados | 60 | — |
| 24 | t-asistentes-perfiles | 60 | Ningún perfil puede bajar el guardrail sin escribir SIN PREGUNTAR. |
| 25 | t-temas-oscuro-sistema | 60 | Contraste 4,5:1 verificado; #FF6363 solo en oscuro. |
| 26 | t-estados-vacios | 60 | — |
| 27 | t-estados-error | 60 | — |
| 28 | t-plan-visible-pausa | 60 | Depende de t-aprobacion-whatsapp-030 (#2, bloqueado) + t-vencimiento-aprobacion-030. Si #2 no corre, su dependencia queda como FALTA explícita. |
| 29 | t-cola-visible-030 | 60 | Depende de t-consumo-vivo + t-cola-sqlite (0.2.0). Dos listas + prelación cambiable + barra % honesta. |

## Prerrequisito #8 — skills semilla (estado 25 oct 20:25: LISTAS 7/7)

- Coordinador + 5 subagentes entregaron 20:25 las 7 en `~/workspace/shared-bridge/skills-semilla/` + INFORME.md. Verificado por Growi: 7/7 con frontmatter válido, ≤256 KB, sin secretos, 76.086 bytes en total, 0 FALTA. 24 huecos reales marcados `[PENDIENTE: dato]` (precios Aqualine sin precio, plantillas de mensaje Meta Ads, fecha del próximo taller Summit, tabla oficial Tripo, ruta de Blender en el PC). La versión «Blender 5.2.2 LTS en el PC» viene de `investigacion-ai-blender/SKILL-claude-arena-blender.md` (no inventada). Advertencia: el helper Tripo del PC vive bajo `openclaw-skills\tripo\` — si se desinstala OpenClaw esa ruta puede desaparecer; el task debería copiar el script dentro de `skills\tripo\`.
- NO subirlas al PC hasta que toque el spec #8; la subida va a `share\inbox\skills-semilla\` y se hace antes de enviar el spec #8, no antes.

## Decisiones de Leandro que bloquean specs

- Relay VPS sí/no → bloquea #19 (t-relay-ssh).
- Número de WhatsApp + duda §13.1 → bloquea #2 (t-aprobacion-whatsapp-030) y arrastra #28.
- Ollama: reinstalar o retirar → lo decide el propio #17, no bloquea el envío.
- ¿Paga ChatGPT Plus? (Codex $0 vs $20/mes) → constancia en #12, decisión posterior al resultado.

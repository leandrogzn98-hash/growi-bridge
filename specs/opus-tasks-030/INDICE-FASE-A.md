# Índice — Fase A de Growi Bridge 0.3.0 (28 ítems de §10 + t-motor-generico + t-cola-visible-030)

**Fecha:** 25 oct 2026. **Fuente:** `~/workspace/growi-bridge-repo/INVESTIGACION-0.3.0.md` §10 (Fase A), §14 (adenda: dos reglas que mandan), §9 (decisiones), §13 (dudas). **Carpeta:** `~/workspace/shared-bridge/opus-tasks-030/` — 30 archivos `.task.json`, todos `model: opus`, `permission_mode: acceptEdits`, `allowed_tools: "Read,Write,Bash,Glob,Grep"`, `cwd: C:\Users\forte\growi-bridge\share\inbox`, prompts en español de 5.379 a 13.148 caracteres, validados con `json.load` (claves exactas, prompt >1500).

**Pre-requisito (no es 0.3.0, es cerrarla):** los 9 tasks en cola de la 0.2.0 terminados + release Alpha 0.2.0 publicada en GitHub. Todos los specs asumen la 0.2.0 cerrada y construyen encima; ninguno toca VERSION.

**Dos reglas que mandan (adenda §14):**
1. **«Ni flojo ni a medias» = función completa con subfunciones.** Cada spec enumera función principal + subfunciones obligatorias y la verificación cubre CADA una por separado. Entregar solo la principal es fallar la aceptación.
2. **Motor universal, no lista cerrada.** Ningún spec se ata solo a los CLI actuales de Leandro. Todo motor nuevo entra por descriptor (`t-motor-generico`); la ficha de cada motor muestra lo que NO puede, nunca se finge.

## Orden de ejecución

El orden de §10 con una corrección de §14.2: **el descriptor genérico va primero** (posición 0), luego los 28 ítems de §10 en su orden. Dentro de ese orden, respetar las dependencias de la tabla.

| # | Spec | Timeout | Depende de | Decisión de Leandro que lo bloquea / nota |
|---|---|---|---|---|
| 0 | `t-motor-generico` | 60 | — (va primero) | El descriptor incluye `base_url` y `credencial_ref` por motor (corrección 18:45). |
| 1 | `t-guardrail-visible` | 60 | — | Subfunción 6: popup de aviso «N tareas están esperando por su aprobación» al arrancar y al entrar una nueva en espera, con anti-spam (corrección 18:46). |
| 2 | `t-aprobacion-whatsapp-030` | 60 | — | **BLOQUEADO hasta resolver la duda §13.1** (¿puede el runner distinguir con certeza que el archivo de decisión lo escribió Muse tras un WhatsApp de Leandro?). El spec ordena NO implementar la aprobación remota si no se resuelve. R3 nunca por WhatsApp. |
| 3 | `t-vencimiento-aprobacion-030` | 60 | — | — |
| 4 | `t-checkpoint-ronda-030` | 60 | t-cola-sqlite (0.2.0, asumida terminada) | Duda §13.8 (¿el session_id sobrevive a la compactación?): el spec guarda resumen además del id. |
| 5 | `t-criterios-tipados-030` | 60 | — | Fusiona el revisor del hilo 3 (un solo spec, no dos). Duda §13.10: medir costo/tiempo real de una revisión Haiku, no estimarlo. |
| 6 | `t-gateway-unificado` | 60 | t-motor-generico, t-cola-sqlite (0.2.0) | El gateway resuelve `credencial_ref` a la clave activa y muestra por motor su credencial (etiqueta + últimos 4) y su base URL (corrección 18:45). |
| 7 | `t-skills-nativas` | 60 | — | — |
| 8 | `t-skills-semilla` | 60 | **Growi deja las 7 skills en `share\inbox\skills-semilla\` ANTES de que corra el task** | Si falta alguna, el task la lista como FALTA y NO inventa su contenido (Blender, Tripo, Meta Ads, Aqualine y Summit Maker no existen como skills en la VM). |
| 9 | `t-memoria-pc` | 60 | — | — |
| 10 | `t-credenciales-keyring` | 60 | — | **Reescrito 18:45:** URL base por credencial + varias claves por plataforma (proveedor + etiqueta + base URL + clave + activa/inactiva). Una entrada DPAPI por CLAVE (`GrowiBridge/anthropic-personal`); en settings.json solo proveedor, etiqueta, base_url, últimos 4 y cuál está activa. Subfunciones: guardar, URL base, probar sin gastar contra esa URL, selector de activa, gasto por clave, revocar por clave, nunca en JSON/logs/git. Duda §13.7 (¿keyring funciona dentro de PyInstaller?): el spec exige verificarlo, con respaldo DPAPI directo con `ctypes`. |
| 11 | `t-motor-gemini-agy` | 60 | **t-motor-generico + t-credenciales-keyring** | Duda §13.16 (¿agy pierde stdout bajo pipe?): verificar en vivo; si lo pierde, no fingir consumo en vivo. El descriptor lleva `base_url` + `credencial_ref` a la clave Gemini activa (corrección 18:45). |
| 12 | `t-codex-verificar` | 45 | t-motor-generico | Si falla, se retira de `engines.json`. **RESUELTO 26 oct 2026: Leandro YA tiene ChatGPT Plus ($20/mes)** — Codex corre con la suscripción Plus, $0 marginal; el spec verifica que el CLI use esa sesión. |
| 13 | `t-semaforo-vram-v2` | 60 | — | **Primero leer el `models-catalog.json` real del PC** (duda §13.3) y verificar el `-np` efectivo (duda §13.4: si es 4, el contexto real es 2.048, no 8.192). Sin leerlo, la corrección es teoría. |
| 14 | `t-descargador-gguf` | 60 | — | Duda §13.14 (¿Hugging Face responde directo desde el PC?): medirlo antes de diseñar el flujo final. |
| 15 | `t-router-llama-server` | 60 | **t-motor-generico** | Si aún no hay segundo modelo instalado, el cambio entre dos modelos reales queda como FALTA explícita, no se finge. |
| 16 | `t-ciclo-vida-llama` | 60 | **t-router-llama-server + t-motor-generico** | — |
| 17 | `t-ollama-decidir` | 45 | — | **DECIDIDO 26 oct 2026: Bridge usa Hermes local vía Ollama (OK de Leandro). Ollama 0.40.10 + Hermes 3 8B YA instalada y respondiendo en 11434 (verificado por t-motor-generico): no se instala de cero, se formaliza.** |
| 18 | `t-saldo-tripo` | 45 | t-credenciales-keyring | Sin clave guardada, el saldo se muestra como «no en vivo» con el último verificado (370, 25 oct 2026). La verificación no gasta créditos. Usa la credencial Tripo ACTIVA (entrada por clave, `GrowiBridge/tripo-<etiqueta>`) y el registro anota la etiqueta que lanzó cada generación (corrección 18:45). |
| 19 | `t-relay-ssh` | 60 | — | **DESBLOQUEADO 26 oct 2026, 07:23: Leandro dijo SÍ con condición de cifrado (solo Growi entra). Diseño aprobado: keypair DEDICADO en la VM (ed25519, huella SHA256:zKT1DblLfxBHEf7abuCuQIE/Tl31zH1DaU44wjxDIKc; privada solo en ~/.ssh/ de la VM), OpenSSH en el PC solo por clave, ProxyJump por el VPS, firewall 22 solo desde 2.25.244.222, verificación de cada paso. El diseño anterior (túnel reverso PC→VPS:18787) queda SUSTITUIDO. Va A MANO tras la Fase A (no en la cadena, que lo salta por diseño). La pública ya está en el inbox del PC (relay-clave-publica.txt). Si un paso exige elevación, se anota para la mañana, no se fuerza. |
| 20 | `t-exportar-chats` | 60 | — | — |
| 21 | `t-ip-estable` | 60 | — | Fusiona `t-detector-avast` (Fase B) como subfunción. Dudas: nombre exacto del servicio de Avast (se busca en vivo, no se asume); IP 2.25.244.222 en listas de datacenter (§13.18). |
| 22 | `t-atajos-personalizables` | 60 | — | — |
| 23 | `t-comandos-ia-guardados` | 60 | — | — |
| 24 | `t-asistentes-perfiles` | 60 | — | Ningún perfil puede bajar el guardrail sin escribir SIN PREGUNTAR. Perfiles por usuario: NO. |
| 25 | `t-temas-oscuro-sistema` | 60 | — | Fusiona `t-modo-oscuro-medido` (hilo 8). Contraste 4,5:1 verificado; #FF6363 solo en oscuro. |
| 26 | `t-estados-vacios` | 60 | — | — |
| 27 | `t-estados-error` | 60 | — | — |
| 28 | `t-plan-visible-pausa` | 60 | t-aprobacion-whatsapp-030, t-vencimiento-aprobacion-030 (no duplica su trabajo) | — |
| 29 | `t-cola-visible-030` | 60 | t-consumo-vivo + t-cola-sqlite (0.2.0) | **Ítem 30 de la Fase A (corrección 18:47).** Dos listas («En ejecución» + «Pendientes»), prelación visible Y cambiable (prioridad alta/normal/baja + posición, guardada en cola.db), barra % honesta (por tarea «estimado» con lo medible, general exacta terminadas/total), estados por tarea en palabras. La vista lee runner-live.json y cola.db; si no han corrido, muestra «sin datos», nunca inventa. |

## Correcciones del usuario 25 oct 18:45–18:47 (aplicadas a los specs, no solo anotadas)

- **18:45 — Credenciales: URL base + varias claves por plataforma.** La pantalla de APIs de la 0.2.0 (nombre + clave) era incompleta. `t-credenciales-keyring` se reescribió: cada credencial lleva proveedor + etiqueta + URL base editable (con valor por defecto sensato por proveedor y validación de formato) + clave + activa/inactiva; varias claves por proveedor; selector de activa, gasto por clave, revocar por clave; una entrada DPAPI por CLAVE (`GrowiBridge/anthropic-personal`); en settings.json solo proveedor, etiqueta, base_url, últimos 4 y cuál está activa. El descriptor de motor (`t-motor-generico`) ahora incluye `base_url` y `credencial_ref`, y `t-motor-gemini-agy`, `t-gateway-unificado` y `t-saldo-tripo` se corrigieron para usarlos (el medidor Tripo usa la credencial activa y anota su etiqueta en el registro). Revisados los 30 specs: ningún otro asumía «una clave por proveedor» (t-codex-verificar usa la sesión propia del CLI, no una clave Bridge; t-criterios-tipados-030 revisa con la sesión Max).
- **18:46 — Popup de aprobación en `t-guardrail-visible`.** Subfunción 6 obligatoria: al arrancar con tareas en espera, popup con el número exacto («3 tareas están esperando por su aprobación» / «1 tarea está esperando...»); también cuando entra una nueva en espera. Botón «Ver tareas» abre Tareas en la tarjeta de aprobación. Anti-spam: máx. 1 popup por evento (se agrupan), no repetir el mismo aviso, no sonar si el usuario está en Tareas viendo la lista. El contador sigue; el popup es el aviso.
- **18:47 — Nuevo spec `t-cola-visible-030` (ítem 30).** Ver fila 29 de la tabla.

## Fusiones aplicadas (un solo spec, no dos)

- `t-criterios-tipados-030` fusiona criterios tipados + revisor-checklist del hilo 3.
- `t-credenciales-keyring` fusiona los specs de credenciales de los hilos 2, 4 y 5.
- `t-descargador-gguf` fusiona descargador GGUF + descarga reanudable del hilo 7.
- `t-ciclo-vida-llama` fusiona ciclo de vida + llama-autostart del hilo 7.
- `t-temas-oscuro-sistema` fusiona temas + modo oscuro medido del hilo 8.
- `t-ip-estable` fusiona el detector de Avast (ítem de Fase B) como subfunción 6.
- `t-router-fallbacks` (cadena `claude → gemini → llama`) queda para Fase B; no es parte de Fase A.

## Ítems inviables o duplicados

**Ninguno.** Los 30 specs se escribieron; no hizo falta ningún spec de relleno. Dos FALTA condicionadas que los specs dejan explícitas en vez de fingir:
- El cambio entre dos modelos reales (t-router-llama-server, t-ciclo-vida-llama) depende de que `t-catalogo-030` (Fase B) instale un segundo modelo.
- `t-skills-semilla` depende de que Growi entregue las 7 skills en el inbox antes de correr el task.

## Qué NO se hace en Fase A (de §11, recordatorio para quien encole)

Paralelo real entre tareas (0.4.0), canal WhatsApp con Baileys (0.4.0, tras spike + decisión del número), alquiler del proxy (sin cifrado, precio, tope y consulta legal no se vende nada), Store/marketplace de skills, control de escritorio por clics (nunca), captura de pantalla siempre encendida (nunca), resolver logins/2FA/CAPTCHAs (nunca), Meshy como segundo generador, Grok Build, Copilot/Cursor CLI, LM Studio, vídeo generativo, migrar de toolkit (no en 0.3.0), memoria vectorial, gadget ESP32.

## Cómo encolar

1. Cerrar la 0.2.0 (9 tasks + release) antes de enviar el primer spec de esta fase.
2. Enviar en el orden de la tabla, de uno en uno, verificando cada `ESTADO-*.md` en `share\outbox\` antes de enviar el siguiente.
3. Los specs 2 (aprobación WhatsApp) y 19 (relay) NO se envían hasta que su condición se cumpla; el resto no necesita decisión previa de Leandro salvo lo anotado en la tabla.
4. Cada spec escribe su `ESTADO-<TEMA>.md` con LISTO / FALTA / COMO PROBARLO en `share\outbox\`.

## Fusiones en lotes (27 oct 2026, ver LOTES.md)
- **t-lote-estados-030** fusiona `t-estados-vacios` + `t-estados-error` (matriz de estados: vacíos y errores en las mismas 5 páginas; 10 criterios, sonnet). Los archivos originales quedan como referencia; en `cadena-030.py` (ORDEN) solo va el lote, en la posición de `t-estados-vacios`.

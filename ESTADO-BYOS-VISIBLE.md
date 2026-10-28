# Estado: BYOS visible (t-byos-visible)

Rama `Claude`, 28 oct 2026. **LISTO.**

Las suscripciones se ven como tales: hay filas en Ajustes con el estado
detectado en vivo, el selector de modelo va por secciones, la fila de Max
lleva el aviso de riesgo y el botón de exportar, y el gasto se etiqueta como
equivalente.

## Código (`growi-bridge.py`)
| Pieza | Qué hace |
|---|---|
| `suscripciones_estado()` | **En vivo y sin leer tokens.** Claude: `claude` en el PATH + sesión OAuth en `~/.claude/.credentials.json` (solo se mira que exista) + `_claude_plan()` (solo el tipo de plan). ChatGPT: `codex login status` («Logged in using ChatGPT» → suscripción; «API key» → clave, no suscripción). Sin sesión: **«no detectada»**, nunca «conectada». Caché de 5 min |
| `engine_choices_secciones()` / `_selector_valores()` | El selector de Tareas y Modelos se agrupa en **Automático / Mi suscripción / Mis claves / Local / Otros motores**, con cabeceras «── … ──» que no se pueden elegir (`_selector_saltar_cabecera` pasa al primer modelo). Solo sale lo disponible: los Claude van en «Mi suscripción» con sesión Max/Pro, en «Mis claves» con `ANTHROPIC_API_KEY`, y **no salen** si no hay ninguna de las dos |
| Ajustes → grupo **«Motores, modelos y suscripciones»** (antes «Motores y modelos») | «Suscripción: Claude Max» y «Suscripción: ChatGPT» con estado, detalle y plan, rellenados en un hilo. La fila de Max lleva el aviso en naranja y el botón **Exportar conversaciones**. Nada de «conexión segura» ni «protegido» |

## Verificación (con lo que hay en este PC)
`pruebas/prueba_byos.py` usa la app real, copia aislada en 8797. Evidencia en
`pruebas/evidencia/byos/`.

| | Prueba | Resultado |
|---|---|---|
| a | Estado real detectado en vivo | «Claude Max — conectada. Claude Code con sesión Max (OAuth del propio programa). Plan: max.» · «ChatGPT — conectada. Codex con Logged in using ChatGPT. Plan: sesión de ChatGPT.» Esto **resuelve la duda de t-codex-verificar**: Codex corre con la sesión de ChatGPT, no con clave de API. Caso sin sesión (`no-detectada.json`): «Claude Max — no detectada (Claude Code está, pero no hay sesión…)», «ChatGPT — no detectada (Codex no está instalado)» |
| b | Selector por secciones | Valores: «── Automático ──», Automático (recomendado), «── Mi suscripción ──», Claude Sonnet/Opus/Haiku, Codex. En la copia de prueba no hay modelos locales ni claves, así que «Local» y «Mis claves» no salen (solo lo disponible). Elegir una cabecera deja «Automático (recomendado)». Sin sesión, los Claude no aparecen |
| c | Aviso y exportar en la fila de Max | «⚠ Usar la sesión Max por un proxy desde Venezuela puede hacer que Anthropic suspenda la cuenta. Exporta tus conversaciones de vez en cuando…» + botón «Exportar conversaciones» (`export_guia_ui`) |
| d | Gasto como equivalente | Ya existía y se comprobó: «Hoy $0.00 real / $0.00 equivalente Max» (`_money_kind`: motor claude con plan Max → `equiv`), y la fila de Max lo repite: «se cuenta como $ equivalente de Max, nunca como $ real» |

Captura: `1-ajustes-suscripciones.png`. Log de la prueba sin tracebacks.

## FALTA / notas
- **Gemini (agy)** también tiene sesión propia, pero su comprobación (`agy
  models`) tarda ~40 s. No se añadió como fila; queda para otro paso.
- El gasto de **Codex** con sesión ChatGPT no tiene precio en su salida: se
  muestra «sin dato», no como $ real. No se inventa un equivalente.

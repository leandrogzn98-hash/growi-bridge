# Estado: modelo por superficie + niveles del modo Automático (t-modelo-por-superficie-auto)

Rama `Claude`, 28 oct 2026. **LISTO.**

## Qué se hizo (`growi-bridge.py`)
| Pieza | Qué hace |
|---|---|
| **Modelo por superficie** (`superficie_modelo` / `superficie_poner`, `settings.json → modelo_superficie`) | 4 superficies con su modelo: **pregunta rápida** (paleta «Pedírselo a la IA» y cajita), **chat de Tareas**, **comandos de IA guardados** (los que no traen motor propio) y **revisión del runner** (el modelo elegido va primero en la cadena de jueces). Cambiar una no toca las demás. Selectores en **Ajustes → Motores, modelos y suscripciones** (`ttk.Combobox`: un `CTkOptionMenu` cuesta ~2,8 s en crearse en este PC) |
| **Sin motor fantasma** | `superficie_modelo` comprueba el modelo cada vez que se usa. Si su motor está apagado, ya no está en el selector o perdió la clave, la superficie **vuelve a «Automático»**, se guarda y avisa («X ya no está: uso Automático»). Automático elige uno que sí esté (Hermes local si no hay nube). `motor_activar` revisa las superficies al apagar o encender un motor |
| **Niveles del modo Automático** (`auto_nivel`, `settings.json → auto_nivel`) | **Rápido** (local o barato primero: baja un escalón de la escalera del router y no sube), **Equilibrado** (el de siempre) y **Potente** (el mejor disponible primero: sube un escalón). Aplicado en `route_task` y explicado en el motivo. **Visible y elegible:** control en Ajustes, 3 acciones en la paleta (el actual con ✓) y una línea en el menú de la bandeja («Auto: Equilibrado (clic: cambiar)») |
| **Modelo por perfil** | Ya existía (`asis_motor_tarea`, fase A). Ahora `asis_motor_ok` **rechaza un motor desactivado**, así que el perfil usa el de por defecto de su superficie |

## Verificación (app real en 8797; `pruebas/prueba_modelo_superficie.py` → `pruebas/evidencia/modelo-superficie/`)
| | Prueba | Resultado |
|---|---|---|
| a | Selectores y guardado independiente | Los 4 selectores en Ajustes (captura `1-selectores.png`). Elegir Codex para el chat → `{"chat": "motor:codex"}`; luego Haiku para la revisión → `{"chat": "motor:codex", "revision": "haiku"}`, **el chat no cambió**. El chat de Tareas abre ahora con «Codex (por internet)» |
| b | El nivel cambia la decisión real (mismo encargo de código) | **Rápido** → llama, y como no estaba encendido, respondió ollama: «nivel Rápido: baja un escalón (sonnet → llama)». **Equilibrado** → sonnet. **Potente** → **opus**: «nivel Potente: sube un escalón (sonnet → opus)». En la paleta: «Auto: Rápido…», «Auto: Equilibrado… ✓», «Auto: Potente…» |
| c | Perfil con modelo propio | Perfil con `codex` → usa `codex`. Con codex desactivado → `None` (va el de la superficie / por defecto) |
| d | Apagar el modelo elegido | El chat tenía `motor:codex`: al desactivar codex → **`motor:auto`** con aviso. La revisión (`haiku`) no se tocó |

Log sin tracebacks.

## FALTA / notas
- En la copia de prueba, el mapa marcó el proxy en rojo al arrancar, así que
  sonnet y opus salieron «no disponibles» (la regla de oro del mapa). Lo
  probado es la **elección** de cada nivel, que es lo que pide el spec.
- El selector de un perfil de asistente sigue en su editor (fase A); aquí solo
  se impide que apunte a un motor apagado.

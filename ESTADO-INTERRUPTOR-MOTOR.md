# Estado: interruptor por motor (t-interruptor-motor)

Rama `Claude`, 28 oct 2026. **LISTO.**

Cada motor se activa o se desactiva desde **Modelos → Motores**: eliges el
motor en el desplegable y pulsas «Desactivar este motor» / «Activar este
motor», junto a su ficha honesta. **Desactivar no borra ni toca el descriptor
de `engines.json`:** el motor se aparta con `settings.json → motores_off`.

## Código (`growi-bridge.py`)
| Pieza | Qué hace |
|---|---|
| `motores_apagados()` / `motor_activar(mid, on, sustituto)` | Apaga o enciende. Al encender dice la verdad: «activado: disponible» o «activado: **no disponible** (motivo)» |
| `engine_status` y `_router_available` | Un motor apagado → «desactivado por ti». Así queda fuera del **router**, de la **cadena de jueces / fallback** y de todo lo que pregunta disponibilidad |
| `engine_choices` | El **selector** no lista los modelos de un motor apagado (Claude Sonnet/Opus/Haiku si claude, Codex, Hermes directo, Ollama) |
| `validate_task` | Una tarea que pide un motor apagado se rechaza: «el motor 'codex' está desactivado (actívalo en Modelos → Motores)» |
| **Principal** | `default_motor()` lee primero `settings.json → motor_principal`. Apagar el principal **sin sustituto activo** se rechaza con un mensaje claro; con sustituto, este pasa a principal. Si «Preguntar» usaba ese motor como modelo por defecto, vuelve a «Automático» con aviso |
| UI | Botón + estado bajo la ficha (`_mot_onoff_ui`, `_mot_pintar_onoff`). Al apagar el principal pregunta cuál queda en su lugar |

## Verificación (app real en 8797, ratón de verdad; evidencia en `pruebas/evidencia/interruptor-motor/`)
`pruebas/prueba_interruptor_motor.py`

| | Prueba | Resultado |
|---|---|---|
| a | Elegir codex y **clic** en «Desactivar este motor» | El botón pasa a «Activar este motor»; estado «Desactivado por ti (el descriptor sigue en engines.json, intacto)». Selector: antes `…, motor:codex`, después **sin codex**. `engine_status` y router: «desactivado por ti». Una tarea con `motor: codex` se rechaza. Captura `1-codex-desactivado.png` |
| b | Descriptor intacto | sha256 de `engines.json` **idéntico** antes y después; `codex` sigue en `engine_ids()` con su descriptor |
| c | **Clic** otra vez = reactivar | Botón «Desactivar este motor», «Activo», codex vuelve al selector. Reactivar con el binario «desinstalado» (simulado): «activado: **no disponible** (no está instalado: no encuentro 'codex' en el PATH)» |
| d | Apagar el principal (claude) | Sin sustituto: **rechazado**: ««claude» es el motor principal: antes de apagarlo elige cuál queda como principal (codex, …). Nunca dejo la app sin motor principal.» Con sustituto codex: principal = codex; el modelo por defecto de Preguntar (sonnet) **vuelve a «Automático»** con aviso; claude sale del selector |

Log sin tracebacks.

## FALTA / notas
- **Cambio frente al spec:** el interruptor vive en `settings.json`
  (`motores_off`), no como campo dentro del descriptor. Así `engines.json`
  queda intacto (es lo que pide la verificación b) y no se pelea con la
  recarga en caliente ni con los descriptores que trae cada versión.
- El sustituto del principal se pide con un cuadro de texto, no con un
  desplegable.

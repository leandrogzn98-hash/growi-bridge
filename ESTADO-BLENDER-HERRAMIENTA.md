# Estado: Blender como herramienta del runner (t-blender-herramienta)

Rama `Claude`, 28 oct 2026. **LISTO.**

Blender es una **herramienta** del runner, no un motor. Está declarada en
`HERRAMIENTAS_DEF` de `growi-bridge.py`, no en `engines.json` → `motores`, así
que no aparece en el selector de modelos ni en la cadena de fallback.

## Código (`growi-bridge.py`)
| Pieza | Qué hace |
|---|---|
| `HERRAMIENTAS_DEF["blender"]` | Operaciones `turntable` (`template_turntable.py`) y `qc` (`template_qc_views.py`), lo que **no hace** y el timeout (900 s) |
| `_blender_buscar()` | Busca la ruta **en vivo**: el PATH y, si no, el `Blender*/blender.exe` más nuevo de Program Files\Blender Foundation |
| `herramienta_ficha()` | Versión medida con `blender --version`, ruta, plantillas encontradas o «falta … en skills\blender», y `no_hace`. Sin Blender: `disponible: false` + motivo |
| `herramienta_de_tarea(task)` | Detecta el pedido: campo `"herramienta": {"operacion": "turntable"\|"qc", "modelo": "x.glb", "frames": N, "salida": …}`, o la frase del encargo («tornamesa/turntable …», «QC / vistas de control …» + una ruta `.glb/.gltf/.obj/.fbx/.blend`) |
| `herramienta_correr()` | `blender --background --python <plantilla> -- MODEL_PATH=… OUT_DIR=…` y deja las imágenes en `<modelo>_turntable\` o `<modelo>_qc\`, junto al modelo (la carpeta del proyecto). Resultado como el de un motor, con `cost_usd 0.0` y `herramienta` |
| `run_engine` | Si la tarea pide tornamesa o QC, la hace Blender; si no, el motor de siempre |
| `validate_task` | Deja pasar el campo `herramienta` |
| Ajustes → Motores y modelos | Fila «Herramienta: Blender (no es un motor)» con versión, ruta, qué hace y qué no, rellenada en un hilo (`blender --version` no frena la ventana) |

## Verificación (con Blender de verdad)
`pruebas/prueba_blender.py` usa una copia aislada y dos tareas reales por
`_process_one_impl`. El modelo es `volante.glb` (1,8 MB) copiado a una
carpeta de proyecto temporal; las plantillas se copian (lectura) de la app
instalada. Evidencia en `pruebas/evidencia/blender/`.

| | Prueba | Resultado |
|---|---|---|
| a | Ruta y versión reales | `Blender 5.2.2 LTS` en `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`; las dos plantillas encontradas. `engine_ids()` = claude, codex, llama, ollama, meshy, gemini: **Blender no está** en el selector |
| b | «Haz una tornamesa de volante.glb» (8 frames) | `status ok`, `motor «blender (herramienta)»`, exit 0, $0, 29,1 s → `proyecto\volante_turntable\frame_0001..0008.png` |
| c | «QC de volante.glb: vistas de control» | `status ok`, 20,7 s → `qc_frontal`, `qc_tres-cuartos`, **`qc_lateral-derecho` (az=90)**, **`qc_lateral-izquierdo` (az=270)** y `qc_trasera`. Muestras en la evidencia |
| d | Ficha honesta y sin Blender | La ficha dice qué no hace («no genera modelos 3D (eso es Tripo o Meshy)», «no decide el diseño», «no sustituye a Tripo»). Simulando un PC sin Blender: `disponible: false`, «no encuentro blender.exe (ni en el PATH ni en Program Files\Blender Foundation)», y la tarea falla con ese motivo, sin inventar nada |

## FALTA / notas
- Las plantillas se buscan en `skills\blender\` (y en
  `share\inbox\skills-semilla\blender\`). En el repo no hay carpeta `skills\`:
  en la app instalada sí están. Si faltan, la ficha lo dice con la ruta.
- La tornamesa deja frames PNG; video no (la plantilla no lo hace).
- No se probó la ficha dentro de la ventana con captura. Se probó la función
  que la rellena, y la fila está en Ajustes → Motores y modelos.

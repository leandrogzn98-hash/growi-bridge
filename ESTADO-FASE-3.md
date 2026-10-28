# Estado de la fase 3: 0.4.0 fase B (en curso)

Orden de la lista de Leandro. Cada spec terminado tiene su `ESTADO-*.md` en la
raíz y su commit.

| # | Spec | Estado | Commit / motivo |
|---|---|---|---|
| 01 | t-ajustes-reorg | **LISTO** (FALTA: densidad, reducir movimiento, 4 avisos y borrar datos, que no existían) | `fab58af`, `ESTADO-AJUSTES-REORG.md` |
| 02 | t-autocalibracion-vram | **SALTADO (bloqueo de hardware)** | La verificación pide cargar un modelo real. La GPU (RTX 3060 6 GB) tiene 4,2 GB ocupados por el llama-server de Ollama del usuario: cargar Hermes 8B (5 GB) aquí fallaría o le quitaría memoria. Además, el log real de llama-server (`llama\llama-server.log`, nivel por defecto) **no trae** los «buffer size = X MiB»: solo `n_ctx_slot`. Hace falta `-v` o medir con nvidia-smi. Retomar con la GPU libre |
| 03 | t-automations | **LISTO** | `2490f08`, `ESTADO-AUTOMATIONS.md` |
| 04 | t-blender-herramienta | **LISTO** (Blender 5.2.2 real, tornamesa y QC) | `50cd345`, `ESTADO-BLENDER-HERRAMIENTA.md` |
| 05 | t-byos-visible | **LISTO** (Max y ChatGPT conectadas, detectadas en vivo) | `478265f`, `ESTADO-BYOS-VISIBLE.md` |
| 06 | t-calculadora-paleta | **LISTO** | `e8f3ed7`, `ESTADO-CALCULADORA-PALETA.md` |
| 07 | t-carga-300ms | **LISTO** (FALTA: esqueleto en Tareas, Carpetas y Registro, que hoy cargan en síncrono y no esperan) | `24cdec9`, `ESTADO-CARGA-300MS.md` |
| 08 | t-catalogo-030 | **SALTADO (bloqueo)** | Pide leer en Hugging Face los tamaños y sha256 reales, descargar ~10 GB (Qwen2.5-Coder-7B, Gemma 3 4B, Qwen3-Embedding) y hacer la carga de prueba en llama-server. La GPU está ocupada por el Ollama del usuario (4,2 de 6 GB) y descargar a la carpeta de la app instalada no está permitido. **También quedan bloqueados los que dependen de él:** 12 t-embeddings-8081, 14 t-evaluar-hermes4 y 41 t-vision-gemma3-4b |
| 09 | t-comandos-script | **LISTO** | `2fc2345` + `c1735fc` (arreglo de mypy que marcó el gate), `ESTADO-COMANDOS-SCRIPT.md` |

**Prerrequisito general:** la fase A (opus-tasks-030) no está completa en la
cadena: 24 de 28 enviados, parada en `t-temas-oscuro-sistema`. Cada spec
construye sobre lo que sí existe en el código.

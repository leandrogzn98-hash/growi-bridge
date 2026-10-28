# Estado de la fase 3: 0.4.0 fase B (en curso)

Orden de la lista de Leandro. Cada spec terminado tiene su `ESTADO-*.md` en la
raíz y su commit.

| # | Spec | Estado | Commit / motivo |
|---|---|---|---|
| 01 | t-ajustes-reorg | **LISTO** (FALTA: densidad, reducir movimiento, 4 avisos y borrar datos, que no existían) | `fab58af`, `ESTADO-AJUSTES-REORG.md` |
| 02 | t-autocalibracion-vram | **SALTADO (bloqueo de hardware)** | La verificación pide cargar un modelo real. La GPU (RTX 3060 6 GB) tiene 4,2 GB ocupados por el llama-server de Ollama del usuario: cargar Hermes 8B (5 GB) aquí fallaría o le quitaría memoria. Además, el log real de llama-server (`llama\llama-server.log`, nivel por defecto) **no trae** los «buffer size = X MiB»: solo `n_ctx_slot`. Hace falta `-v` o medir con nvidia-smi. Retomar con la GPU libre |
| 03 | t-automations | **LISTO** | `2490f08`, `ESTADO-AUTOMATIONS.md` |

**Prerrequisito general:** la fase A (opus-tasks-030) no está completa en la
cadena: 24 de 28 enviados, parada en `t-temas-oscuro-sistema`. Cada spec
construye sobre lo que sí existe en el código.

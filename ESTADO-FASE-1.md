# Estado de la fase 1: el gate de calidad

| Spec | Estado | Commit | ESTADO |
|---|---|---|---|
| t-gate-stop-hook-calidad | **LISTO** | `ac16513`, `09656dc`, `7a0c519` | `ESTADO-GATE-CALIDAD.md` |

- **Hecho:** `gate-calidad.py` ($0, solo lo cambiado, sale 0/2), registrado como Stop
  hook en `.claude/settings.json`. Se probó con un `claude -p` real:
  FALLA → el agente corrige → PASA. El log llega al prompt del juez.
- **Pendiente:** al integrar, copiar el bloque `hooks` al `.claude\settings.json`
  de la app instalada (las tareas corren con cwd `share\inbox`).
- **Hallazgo:** `build_gui` espera de forma síncrona `agy models` (~40 s), que
  retrasa el arranque de la app. Queda para un fix aparte.
- **Saltado:** nada.

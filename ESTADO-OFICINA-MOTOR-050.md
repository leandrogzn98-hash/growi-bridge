# ESTADO — t-oficina-motor-050 (Oficina 0.5.0, spec 6 de 18)

**Fecha:** 30 oct 2026. **Veredicto:** LISTO. Motor fijado: **Godot 4.7.2-stable, Compatibility**. Decisión en `oficina/DECISION-MOTOR.md`.

## LISTO
| # | Subfunción | Evidencia |
|---|---|---|
| 1 / a | Regla con cifras reales | `DECISION-MOTOR.md` cita las del ESTADO de mediciones, no las de la investigación. C1: 26,3 MiB de VRAM propia y 5697 MiB en total con Hermes cargado. C2: 152,8 MiB de RAM. C3: OpenGL 3.3 NVIDIA, 0 tirones con llama generando. Pasan las tres. |
| 2 / b | Versión exacta | `Godot_v4.7.2-stable_win64_console.exe --version` → `4.7.2.stable.official.ed1daf0bf`. Plantilla de export `godot_4.7.2-stable_windows_release_x86_64.exe` presente en `oficina/mediciones/_bin/`. |
| 2 / c | Configuración como archivo | `oficina/godot/project.godot`. Godot 4.7.2 lo abre en modo headless y devuelve `low_processor_mode=true`, `max_fps=30`, `vsync_mode=1`, `rendering_method=gl_compatibility` (salida en `pruebas/evidencia/oficina-motor-050/verificacion.json`). |
| 3 / d | Puerto y transporte | Transporte v1 por archivos. El proceso de Godot con el proyecto: 0 conexiones (psutil `net_connections`). El WebSocket 127.0.0.1:8765 no se abre en la v1. |
| 4 | Respaldo | Camino Pygame-ce 2.5.8 / Python 3.12 / PyInstaller onefile escrito, con el prototipo del spec 5 como base y el disparador (C1/C2 rotos con la escena real, a medir en el spec 17). |
| 5 / e | Sin escenas | `oficina/godot/` solo tiene `project.godot`: 0 `.tscn`, 0 sprites. |
| 6 / f | DECISION-MOTOR.md | Con veredicto, versión, cifras, configuración, respaldo y fecha. |

## FALTA
- `INVESTIGACION-0.5.0-oficina.md` (§6.3, §6.4, §10) no está en este PC. La regla C1–C3 se tomó del texto del spec, que la cita.
- No hay icono ni preset de export (`export_presets.cfg`). Se crean cuando haya algo que exportar (spec 18, ciclo de vida); la plantilla ya está.

## COMO PROBARLO
```
oficina\mediciones\_bin\Godot_v4.7.2-stable_win64_console.exe --version
python pruebas\oficina_motor_050\motor_verif.py     # ajustes leídos por Godot + conexiones + escenas
```

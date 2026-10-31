# DECISION-MOTOR — motor de la oficina 0.5.0

**Fecha:** 30 oct 2026. **Spec:** t-oficina-motor-050 (6 de 18). **Fuente de las cifras:** `ESTADO-OFICINA-MEDICIONES-050.md` (corrida `20261029-162952`, medida en este PC: Ryzen 7 4800H, RTX 3060 Laptop 6 GB, driver 596.49, 16 GB de RAM).

## Veredicto: **Godot 4.7.2-stable (official), renderer Compatibility (OpenGL 3.3), GDScript**

## Regla C1–C3 con las cifras medidas
| Condición | Tope | Godot 4.7.2 medido | ¿Pasa? |
|---|---|---|---|
| C1: VRAM de la oficina | ≤ ~100 MB (§8: ≤128) | 26,3 MiB | Sí |
| C1: VRAM total con Hermes 3 8B cargado | ≤ ~5,9 GB | 5697 MiB (5673 sin oficina; vuelve a 5673 al cerrarla) | Sí (297 MiB libres) |
| C2: RAM de la oficina | ≤ ~300 MB (§8: ≤350) | 152,8 MiB RSS máx. | Sí |
| C3: sin render por software | GPU real | `3.3.0 NVIDIA 596.49`, `gl_compatibility` | Sí |
| C3: sin tirones con llama-server generando | 0 | 0 fotogramas > 50 ms; peor 33,3 ms; 30/30 FPS | Sí |

Sin ambigüedad en el informe: las tres pasan con margen.

## Versión y configuración fijadas
- Editor: `Godot_v4.7.2-stable_win64.exe` (y `_console.exe`). `--version` = `4.7.2.stable.official.ed1daf0bf`.
- Export: plantilla oficial `godot_4.7.2-stable_windows_release_x86_64.exe` de la misma versión.
- Binarios: `oficina/mediciones/_bin/` (no se versionan; los baja `oficina/mediciones/descargar.py`).
- Proyecto: `oficina/godot/project.godot`:
  - `rendering/renderer/rendering_method="gl_compatibility"` (también para móvil)
  - `application/run/low_processor_mode=true` (33 ms de espera)
  - `application/run/max_fps=30`
  - `display/window/vsync/vsync_mode=1` (activado)
  - `physics/common/physics_ticks_per_second=30`
  - filtro de texturas «nearest» (pixel art)
  - estiramiento por enteros

  Verificado: Godot 4.7.2 abre el proyecto y devuelve esos valores con `ProjectSettings.get_setting`.
- Nada de «la última»: cambiar de versión exige re-medir C1–C3 (`oficina/mediciones/medir.py`) y actualizar este archivo.

## Transporte y puerto
- **Transporte v1: archivos** (decisión 7 de §13), el mismo protocolo del prototipo (spec 5):
  - lee: `runner-live.json`, `cola-live.json`, `runner-status.json`, `engines.json`, `skills\`
  - latido: `share\outbox\bridge-latido.json` `{pid, t, cerrar}` cada 5 s, autocierre a los 15 s
  - única escritura: encolar por `oficina/encolar/encolar.py`
- **Ningún puerto en la v1.** Medido: el proceso de Godot con este proyecto tiene 0 conexiones de red.
- El WebSocket en `127.0.0.1:8765` queda como optimización posterior, solo si el polling se queda corto. Si se abre algún día, será solo loopback.

## Respaldo: Pygame-ce 2.5.8
- Si la escena real rompe C1 o C2 (más de 100 MB de VRAM o de 300 MB de RAM, medidos con la escena completa en el spec 17), la oficina pasa a **Pygame-ce 2.5.8** (SDL 2.32.10) sobre **Python 3.12** del Bridge. Para empaquetar: PyInstaller onefile.
- El prototipo existe y está verificado: `oficina/protocolo/oficina_proto.py` (spec 5). Medidas:
  - 0 VRAM, 35 MiB de RAM en la escena de 16 sprites
  - 60 MiB con el protocolo completo
  - 29–30 FPS
- Cambiar de motor no rediseña nada: mismo protocolo, mismos códigos de salida (0 usuario, 2 Bridge no disponible, 3 ya abierta, 4 la app pidió cerrar, 5 falta el motor) y el mismo parche de la app (`oficina_abrir`/`oficina_cerrar`). Solo cambia el ejecutable que lanza `_oficina_script()`.
- Para portar el protocolo a Godot:
  - `leer_json` con 3 reintentos de 100 ms
  - `Latido.comprobar`, con el pid vivo vía `OS.is_process_running`
  - instancia única: archivo de bloqueo o puerto, porque Godot no tiene mutex con nombre
  - lectura en `Thread` / `WorkerThreadPool`

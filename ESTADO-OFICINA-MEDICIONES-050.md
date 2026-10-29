# ESTADO — Mediciones C1-C3 de la oficina 0.5.0 (t-oficina-mediciones-050, spec 1 de 18)

Rama `Claude`, 29-oct-2026, en el PC de Leandro: AMD Ryzen 7 4800H, RTX 3060 Laptop 6 GB con driver 596.49, Windows
11. Todas las cifras de este informe se midieron aquí; ninguna sale de la investigación ni de terceros.

## VEREDICTO: **Godot 4.7.2-stable, renderer Compatibility (OpenGL 3.3)**
C1, C2 y C3 pasan con margen:
- La oficina en Godot usa **26 MiB de VRAM** (tope ~100).
- Con Hermes 3 8B cargado, la VRAM total llega a **5697 MiB** (tope ~5900).
- Usa **152 MiB de RAM** (tope ~300).
- Sin caída a software y **0 tirones** con llama-server generando.

Versión fijada por escrito: **Godot `4.7.2-stable (official)`**, export con la plantilla oficial
`windows_release_x86_64.exe` de esa versión.

Pygame-ce 2.5.8 queda medido como respaldo, y también cumple todo con holgura: 0 VRAM y 35 MiB de RAM.

## Tabla de cifras medidas
Corrida `20261029-162952`. Escena: **16 sprites** de 32×48 (14 personajes + Runa + vigilante; Leandro es el avatar
del jugador y queda fuera) a 30 FPS, 4 fotogramas a 8 FPS. Fases: 20 s quietos, luego animados, y entre los 50 y los
75 s animados **con llama-server generando** (8 peticiones, 2048 tokens, 0 errores).

| Medida | Godot 4.7.2 Compatibility (export) | Pygame-ce 2.5.8 (SDL 2.32.10) | Tope | Fuente |
|---|---|---|---|---|
| VRAM propia en la NVIDIA (máx.) | **26,3 MiB** | **0**: el proceso no tiene ninguna instancia de memoria de GPU | ≤ ~100 MB (§8: ≤128) | contadores `GPU Process Memory(pid_*)\Dedicated Usage` (los del Administrador de tareas) |
| VRAM total antes / durante (máx.) / después | 5673 / **5697** / 5673 MiB | 5673 / 5673 / 5673 MiB | total ≤ ~5,9 GB | `nvidia-smi` cada segundo |
| Memoria GPU compartida (máx.) | 18,8 MiB | — | — | `Shared Usage` |
| RAM en reposo (RSS / USS máx.) | **152,8 / 120,7 MiB** | **34,5 / 17,0 MiB** | ≤ ~300 MB (§8: ≤350) | psutil |
| RAM animando (RSS máx.) | 151,7 MiB | 34,5 MiB | | psutil |
| RAM animando con llama generando | 151,7 MiB | 34,5 MiB | | psutil |
| CPU en reposo (% de un núcleo / % del equipo, 16 hilos) | 6,7 % / ~0,4 % | 1,0 % / ~0,06 % | ≤ 2 % en reposo | psutil |
| CPU animando con llama | 8,4 % / ~0,5 % | 1,3 % / ~0,08 % | | psutil |
| FPS medio / mínimo, animando | 30,0 / 30 | 29,8 / 29,6 | 30 | la propia escena, cada segundo |
| FPS medio / mínimo, **con llama generando** | **30,0 / 30** | **29,8 / 29,5** | | escena |
| Peor fotograma con llama generando | 33,3 ms | 35,0 ms | | escena |
| Fotogramas > 50 ms con llama generando | **0** | **0** | | escena |
| Uso de la GPU mientras llama genera (`nvidia-smi`) | 64,7 % de media | 79,5 % de media | | `nvidia-smi` |
| Adaptador y API | NVIDIA GeForce RTX 3060 Laptop GPU, `3.3.0 NVIDIA 596.49`, `gl_compatibility` | render por CPU, driver de vídeo SDL `windows` | no software | `RenderingServer` en la escena |
| Temperatura de la GPU (máx.) | 62 °C | 63 °C | | `nvidia-smi` |

**Lo que fija los topes:**

| Medida | Valor | Cómo se midió |
|---|---|---|
| RAM total del PC | **16 GB**: 16.558.178.304 bytes, 15,42 GiB utilizables | `Win32_ComputerSystem.TotalPhysicalMemory` y psutil |
| GPU dedicada | RTX 3060 Laptop, 6144 MiB, driver 596.49 | `nvidia-smi` |
| VRAM con Hermes 3 8B cargado (`-c 8192 -ngl 99 -np 1`) | **5673 MiB usados, 322 MiB libres** | `nvidia-smi`. Su proceso usa 3819 MiB de RAM |
| GPU integrada | **Sí hay**: AMD Radeon Graphics (512 MB, driver 30.0.13002.19003) | `Win32_VideoController` |
| WebView2 | **Instalado**: 156.0.4314.50 (en HKLM) | registro de EdgeUpdate `{F3017226-…}` |
| Claude Code (máx. visto durante la corrida) | **1245,6 MiB RSS** (1081 USS) en 12 procesos | psutil, con la sesión de Claude Code de esta misma tarea trabajando |
| Bridge (`growi-bridge.py`, máx. visto) | **123 MiB RSS** en 1 proceso | psutil |

## Regla C1 / C2 / C3 aplicada
- **C1 (VRAM): PASA.** La oficina usa 26,3 MiB en la NVIDIA (≤ ~100) y la VRAM total con el modelo cargado llega a
  5697 MiB (≤ ~5,9 GB). Leo «5,9 GB» en la misma escala que el «~5,7 GB» del modelo, que `nvidia-smi` da como
  5673 MiB. Tomado de forma estricta como 5,9 GiB (6042 MiB), también pasa.
  - Quedan 297 MiB libres con la oficina abierta.
  - Al cerrarla, el total vuelve exactamente a 5673 MiB: no deja memoria colgada.
- **C2 (RAM): PASA.** 152,8 MiB de RSS como máximo (≤ ~300), estable en reposo, animando y con llama generando. El
  PC tiene **16 GB**, no 8, así que **no hay que apretar** los umbrales de la escalera de degradación (§8.4).
- **C3 (driver): PASA.**
  - Con `gl_compatibility` forzado, Godot usa la NVIDIA por OpenGL 3.3 del driver de NVIDIA. No hay render por
    software: sería «Microsoft Basic Render Driver» o «GDI Generic».
  - Con llama-server generando a la vez (la GPU al 64,7 % de media) da 30 FPS constantes, el peor fotograma es de
    33,3 ms y no hay ningún fotograma por encima de 50 ms.
  - El único tirón de toda la corrida es el **primer segundo del arranque** (21 FPS, un fotograma de 59,5 ms, sin
    llama generando). No es contención.
  - **Throttling térmico**: `nvidia-smi` marca `0x20` (SW Thermal Slowdown) **ya antes de abrir nada**, con la GPU en
    reposo a 43-62 °C. Es una marca del portátil o del driver, no algo que provoque la oficina, y no bajó los FPS.
    También aparece `0x1` (GPU idle). Durante la corrida, la GPU no pasó de 63 °C.

## LISTO (una verificación por subfunción)
- **(a) C1**: `nvidia-smi` cada segundo y los contadores de memoria de GPU por proceso.
  - Son la misma fuente que el Administrador de tareas. En vez de capturas de pantalla, se guardaron sus valores
    (`godot-gpu.csv`) para no abrir ventanas.
  - Están en `pruebas/evidencia/oficina-mediciones/`: `resumen.json`, `godot-gpu.csv`, `godot-muestras.csv` y
    `pygame-muestras.csv`.
  - Se midió el **export real**: la plantilla oficial `windows_release_x86_64.exe` más `oficina.pck`, exportados en
    modo headless. De las plantillas de 1,28 GB solo se bajó esa, leyendo el `.tpz` por rangos HTTP
    (`oficina/mediciones/descargar.py`).
- **(b) C2**: RAM de la escena real en reposo, animando y animando con llama (RSS y USS), y la RAM total del PC, 16 GB.
- **(c) C3**: corrida con llama-server generando de verdad (`/completion`, 256 tokens por petición) durante 25 s,
  sin caída a software ni tirones. El adaptador y la API los informa la propia escena (`godot.jsonl`, primera línea).
- **(d) Pygame-ce**: el prototipo con los mismos 16 sprites corre a 29,8 FPS y deja sus cifras (`pygame.jsonl`).
  - Su VRAM es 0 **comprobada**: en el listado completo de contadores de GPU tomado con el proceso vivo no aparece
    ninguna instancia de ese PID.
  - Se mide el intérprete real: el `pythonw.exe` de un venv es un lanzador, y medirlo a él habría dado una RAM falsa.
- **(e) Topes**: RAM total, GPU integrada (existe), WebView2 (instalado), Claude Code y Bridge, todo con el comando
  que lo prueba (`resumen.json` → `topes`, `vigilados_max`).
- **(f) Informe**: este documento. Veredicto único: Godot 4.7.2-stable Compatibility.

Nada de la app instalada se modificó. De `C:\Users\forte\growi-bridge\` solo se **ejecutó** `llama\llama-server.exe`
con `models\hermes-3-8b-q4_k_m.gguf`, en el puerto 8091 (no el 8080 de la app), con el log en el repo. Se paró al
terminar: la VRAM volvió a 0 MiB. No se tocó `growi-bridge.py`, ni `VERSION`, ni el runner.

## FALTA
- **La ventana de Godot se vio un momento.** Se pide fuera de pantalla (`get_window().position = (-16000, 0)` en
  `_ready`), y así salió en la prueba corta y en la propia escena.
  - Pero en la corrida larga, a los 2 s del arranque, Windows la tenía en (0,0): durante el arranque se vio arriba a
    la izquierda, aunque **sin robar el foco** (`foco_cambio: false` en las dos corridas).
  - La de Pygame-ce sí estuvo siempre fuera de pantalla.
  - Para la oficina real da igual, porque es una ventana visible. Para futuras pruebas automáticas hay que crearla ya
    escondida.
- **Renderizar en la GPU integrada**: la AMD Radeon existe, pero **no se probó** que la oficina renderice en ella.
  - Godot con OpenGL no deja elegir el adaptador (`--gpu-index` solo vale para Vulkan). Forzarlo exige la preferencia
    de gráficos de Windows por aplicación, que es un cambio en el registro del usuario, fuera del repo: no se tocó.
  - Dato curioso que no se interpreta más allá: los contadores atribuyen el 2,8 % de uso 3D de Godot al LUID de la
    iGPU (la copia a pantalla de un portátil híbrido) y la VRAM a la NVIDIA.
  - Si se quisiera dejar la NVIDIA al 100 % para el modelo, es un experimento pendiente.
- **Pico de Claude Code**: 1245,6 MiB es el **máximo visto durante esta corrida**, con la sesión de esta tarea
  activa. No es un pico de carga provocado ni el peor caso posible de Claude Code.
- **Throttling en carga larga**: la contención se midió 25 s por motor. No se midió una sesión de horas con la GPU
  caliente.
- **CPU ≤ 2 % en reposo**: se cumple medido sobre el equipo (~0,4 %), pero no sobre un núcleo (6,7 %). Este informe
  da los dos números; el presupuesto §8 no dice cuál de los dos manda.
- **Solo el renderer Compatibility**: no se midió Forward+/Vulkan, porque el spec no lo pide. Tauri no se midió;
  solo se comprobó que WebView2 está instalado.

## CÓMO PROBARLO
Los binarios y entornos se descargan, no van en git (`oficina/mediciones/_bin/`, `.venv/` y `_corridas/`).
1. `python oficina/mediciones/descargar.py 4.7.2-stable`: baja el editor de Godot y solo la plantilla de Windows.
2. `cd oficina/mediciones/godot_escena && ../_bin/Godot_v4.7.2-stable_win64_console.exe --headless --export-release
   "Windows Desktop"`. Deja `_bin/oficina-godot/oficina.exe` + `.pck`. Hay un `_sc_` en `_bin` (modo autocontenido):
   el editor no escribe en AppData.
3. `python -m venv oficina/mediciones/.venv && oficina/mediciones/.venv/Scripts/python.exe -m pip install pygame-ce`.
4. `python oficina/mediciones/medir.py` (o `--app <carpeta de la app>`).
   - Necesita `llama\llama-server.exe` y `models\hermes-3-8b-q4_k_m.gguf` de la app.
   - Unos 5 min: carga el modelo y mide Godot 80 s y Pygame-ce 80 s.
   - Deja `_corridas/<fecha>/` y el resumen en `pruebas/evidencia/oficina-mediciones/`.
   - No lo corras con la app usando su llama-server, porque dos 8B no caben en 6 GB.

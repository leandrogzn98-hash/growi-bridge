# ESTADO — t-oficina-rendimiento-050 (Oficina 0.5.0, spec 17 de 18)

**Fecha:** 31 oct 2026, 00:30. **Veredicto:** LISTO la escalera, la dormida, el ahorro, el cerrado, los FPS y las métricas. Lo verifiqué con el prototipo real y un Bridge falso: los niveles se forzaron con sensores simulados (bandera de prueba rotulada) y además hubo una cesión **real** por RAM.

Hay **dos presupuestos que el prototipo Pygame-ce no cumple** (RAM minimizada y CPU en reposo) y la cesión por VRAM con un modelo real queda sin demostrar. Las tres cosas están abajo, con sus cifras. La app instalada no se tocó.

## Dónde está
- `oficina/rendimiento/rendimiento.py`: presupuestos como constantes, `nivel_objetivo()`, `Escalera` (con histéresis y `despertar()`), `fps()`, `Sensores` (en un hilo: psutil, nvidia-smi y el contador «GPU Process Memory» del spec 1), `metricas_texto()`.
- Prototipo: `parches/parche_oficina_rendimiento_050.py`. Reproducible: aplicado al commit anterior da el archivo idéntico.
  - Escalera con sensores reales; FPS 30/15/0 según foco y minimizado.
  - Sin vagancia desde el nivel 2; sprites quietos desde el 3; dormida (sin render) en el 4; cerrada (código 6) en el 5.
  - Tecla **A** = modo ahorro; **Z** = dormir.
  - Puntito de color y métricas en vivo.
  - Rotación de sus métricas por encima de 40 MB.
- Pruebas: `pruebas/oficina_rendimiento_050/prueba_rendimiento.py` y `ceder_vram.py`.

## LISTO (evidencia en `pruebas/evidencia/oficina-rendimiento-050/`)
| # | Subfunción | Resultado |
|---|---|---|
| 1 | Topes en código | VRAM ≤128 (pico ≤256), RAM 350/450/150/50, tope duro 500, CPU 2/5/10, assets ≤100 MB, sprite ≤512 px. Superar el tope duro sube a «solo estados» y lo registra. Los topes de Tauri no aplican (anotado: el spec 6 eligió Godot). |
| 2 / b | Escalera de 6 niveles | Lógica: cada nivel con su disparador (RAM 77/81/86/91/95 %, VRAM libre 450/350/250/150; dormida por los 5 disparadores). **Real en el prototipo:** 0→1 (VRAM 450 < 500) → 2 (350 < 400) → 3 (250 < 300) → 4 (150 < 200), y con los recursos en verde 4→3 **a los 40 s** (30 s de histéresis más el ritmo del sensor). Cada cambio, con hora y motivo, en el registro. Puntito: verde 0, amarillo 1–2, naranja 3, gris 4–5. |
| 3 / c | La oficina cede | **Real, por RAM:** al cargar Hermes en Ollama (se lo llevó a RAM porque la GPU del portátil estaba inactiva), la RAM del sistema pasó del 93 % y la oficina **se cerró sola en ese instante** (nivel 5). El modelo respondió sin error (sin OOM). **Por VRAM:** verificado con sensores forzados (corrida A). La carga real no bajó la VRAM libre de 1979 MB, así que no hubo cruce que medir. La oficina no usa VRAM: 0,0 MiB en el contador del Administrador de tareas, en todos los modos (Pygame-ce dibuja con la CPU). |
| 4 / d | Modo dormida | Entra con Z (y por lógica con RAM > 90 %, VRAM < 200, 5 min sin mirar y de noche). Sin render: atiende los eventos 4 veces por segundo. **Despertar medido: 9,5 / 8,9 / 5,5 ms** (objetivo < 1 s). RAM dormida 61,9 MB (tope 150). **Corregido en la prueba:** despertar esperaba los 30 s de histéresis. Ahora un clic del usuario baja al instante, si los recursos lo permiten. |
| 5 / e | Modo ahorro | Con la tecla A, nivel efectivo 2 (15 FPS, sin vagancia, sprites…). En 100 s de verde **sigue en 2** (persistente) y vuelve a 0 solo al quitarlo. |
| 6 / f | Modo cerrado | Con RAM al 95 %, el proceso termina con código 6 y **no queda vivo**. Al reabrir, reconstruye los estados desde los archivos (no guarda nada propio). Nunca se reabre solo. |
| 7 / g | FPS y métricas | 30 con foco, 15 sin foco, 0 minimizada (sin pintar). Medido: 15 FPS (ventana sin foco en las pruebas, que no roban el foco), 4–15 alrededor de la dormida. Las métricas en vivo (FPS, RAM, VRAM propia, VRAM libre, CPU, nivel) salen de psutil, nvidia-smi y el contador de Windows: las mismas fuentes que el Administrador de tareas. |
| 8 / h | Qué no hacer | Búsqueda en el código de la oficina. 3 coincidencias revisadas, ninguna es un uso real: `encolar.py:98` abre cola.db con una URI `mode=ro` (solo lectura); un mensaje que sugiere `pip install` (no descarga nada); `PrintWindow` en un **script de prueba** del spec 4 (no en la oficina). Sin red externa, sin telemetría, sin auto-actualización, sin 3D ni vídeo, sin sprites mayores de 512 px. |

## Presupuestos medidos (prototipo Pygame-ce, 16 sprites, 15 FPS)
| Modo | RAM | CPU (% de un núcleo) | VRAM propia | Tope | ¿Cumple? |
|---|---|---|---|---|---|
| Trabajando (nivel 0) | 62,1 MB | 6,6 % (0,4 % del equipo de 16 hilos) | 0,0 | RAM ≤450, CPU ≤5 % del total | Sí |
| Solo estados (nivel 3) | 62,9 MB | 3,6 % | 0,0 | — | Sí |
| Dormida (nivel 4) | 61,9 MB | 0,5–3,1 % | 0,0 | RAM ≤150, CPU ~0 | RAM sí; CPU casi |
| Minimizada | 61,9 MB | 1,1 % | 0,0 | **RAM ≤50** | **No (+12 MB)** |
| Reposo (sin tarea) | ~62 MB | ~6 % a 15 FPS | 0,0 | **CPU ≤2 % de un núcleo** | **No** (redibuja cada fotograma) |
| Assets en disco | 0,09 MB | | | ≤100 MB | Sí |

## FALTA
1. **CPU en reposo > 2 % de un núcleo** (unos 6 % a 15 FPS): el prototipo repinta todo en cada fotograma. Hay dos caminos: repintar solo lo que cambia (rectángulos sucios) o Godot con `low_processor_mode` (ya fijado en `project.godot`), que no redibuja una escena quieta.
2. **RAM minimizada > 50 MB** (61,9 MB): es lo que pesan Python + pygame + fuentes. Bajar a ≤50 exige cerrar el proceso al minimizar (que es lo que pide el modo cerrado) o el motor final.
3. **Cesión por VRAM con un modelo real:** no se pudo provocar (la GPU no tomó la carga). Repetirlo con llama-server cargando el GGUF con `-ngl 99` mientras la oficina corre.
4. Instalador (≤50 MB) y total instalado: todavía no hay instalador (spec 18, ciclo de vida).
5. «Horario nocturno», con cierre de noche opcional (`cerrar_noche`): por defecto la oficina duerme de 23:00 a 07:00. Las pruebas usan `--sin-noche` porque corrieron pasada la medianoche.

## COMO PROBARLO
```
python pruebas\oficina_rendimiento_050\prueba_rendimiento.py   # lógica + 4 corridas reales (~3 min)
python pruebas\oficina_rendimiento_050\ceder_vram.py           # carga Hermes en Ollama ($0) y mide la cesión
```
En la oficina: **A** = modo ahorro, **Z** = dormir; cualquier clic la despierta. El puntito de arriba dice el nivel.

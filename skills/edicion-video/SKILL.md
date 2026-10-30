---
name: edicion-video
description: "Editar vídeo con IA en el PC: reel vertical talking-head desde un crudo (Whisper local, cortes de pausas y muletillas, mejor toma, subtítulos palabra por palabra, Remotion 1080x1920), con QC automático del render, lotes nocturnos sin supervisión, costo estimado antes de renderizar, memoria de marca que aprende de las correcciones y repurposing de un vídeo largo a clips verticales y posts."
version: 0.6.0
requires:
  env: []
  bins:
    - ffmpeg
    - ffprobe
    - node
---

# Edición de vídeo con IA (Growi Bridge)

Convierte un crudo vertical de talking-head en un reel listo para publicar, y un vídeo largo en clips más posts.
Corre entero en el PC: Whisper local, ffmpeg y Remotion cuestan $0. Solo se paga si se elige el director
`claude` (suscripción de Claude Code) o los ojos `gemini` (API de Google), y en ese caso el costo se estima
**antes** de renderizar.

## Instalación (una vez por PC)

```
powershell -ExecutionPolicy Bypass -File skills\edicion-video\instalar.ps1
```

Crea `%LOCALAPPDATA%\growi-video\` con el venv (faster-whisper), la copia de trabajo de Remotion (node_modules)
y, en el primer uso, el modelo `small` de Whisper (~460 MB) y Chrome Headless Shell. Los scripts se pueden llamar
con cualquier `python`: si les falta el venv, se relanzan con él.

## Pipeline

| Paso | Quién | Qué hace |
|---|---|---|
| 1. Transcribir | Whisper local (faster-whisper `small`, CPU int8) | Tiempos por palabra → `palabras.json` |
| 2. Pausas | ffmpeg `silencedetect` | Silencios > umbral del estilo (0,4 s por defecto) |
| 3. Ojos (opcional) | Gemini | Ve el vídeo (versión ligera de 360 px) y anota encuadre, mirada y las tomas que se ven peor. Solo con `--ojos gemini` y `GEMINI_API_KEY` |
| 4. Director | `reglas` ($0) o `claude` | Mejor toma (de dos tomas casi iguales se queda la última), falsas salidas, muletillas, pausas. Escribe 3 ganchos de menos de 8 palabras. Deja `cortes.md`, la lista de cortes para aprobar |
| 5. Costo | `costo.py` | Tokens y USD estimados por paso, **antes** del render → `costo.json` |
| 6. Corte | ffmpeg | Une los segmentos, encuadra a 1080x1920 a 30 fps y nivela el audio a −14 LUFS |
| 7. Render | Remotion | Subtítulos palabra por palabra (máx. 3 en pantalla, palabra activa resaltada), gancho y punch-in |
| 8. QC | `qc.py` | Mira el MP4 final de verdad y lo rechaza con diagnóstico (ver abajo) |

Claude no ve el vídeo: lee el transcript con tiempos. Lo que el texto no dice (la cara, el encuadre) lo dice
Gemini si se activa; si no, queda para quien revisa `cortes.md`.

## Uso

```
python skills\edicion-video\scripts\editar.py --crudo C:\crudos\toma.mp4 --salida C:\videos\toma ^
       --estilo reel-ganchos [--marca summit] [--director reglas|claude] [--ojos no|gemini]
```

- **Revisar los cortes antes de renderizar** (el paso que no hay que saltarse a mano): `--solo-cortes` se para
  tras escribir `cortes.md` y `director.json` (sale con código 2). Si hace falta, se edita `director.json`
  (`segmentos`) y se retoma con `--cortes <carpeta>\director.json`. En lotes y en el runner la lista se aprueba
  sola y queda en el reporte para revisarla después.
- Salida en la carpeta: `final.mp4` (o `final.RECHAZADO.mp4`), `reporte.md` y `reporte.json`, `cortes.md`,
  `costo.json`, `qc.json`, `palabras.json`, `editado.mp4` (sin subtítulos) y `props.json`.
- Código de salida: 0 = listo y pasó el QC; 1 = rechazado o error; 2 = esperando aprobación.

## Estilos (`estilos.json`)

| Estilo | Para qué | Parámetros clave |
|---|---|---|
| `talking-head-limpio` | Cara a cámara sobrio | pausa 0,4 s, 3 palabras, caja oscura, sin gancho ni zoom |
| `reel-ganchos` | Reel para crecer | gancho titulado los primeros 3 s, punch-in ×1,08, palabra activa amarilla sobre rosa |
| `clip-rapido` | Clips de repurposing | pausa 0,25 s, 2 palabras, gancho de 2 s, zoom ×1,12 |

Comunes: 1080x1920 a 30 fps, zona segura (arriba 220 px, abajo 380, derecha 140), −14 LUFS, muletillas. Añadir
un estilo es añadir una entrada al JSON.

## Las 5 cosas que hace además de editar

1. **QC automático** (`qc.py <carpeta>`). Compara el fotograma final con el editado sin subtítulos: la caja del
   subtítulo tiene que verse y caer entera dentro de la zona segura. También comprueba la envolvente del audio
   final contra la del editado (desfase de 1 frame como máximo), la duración esperada (±2 frames) y el formato.
   Si algo falla, renombra a `final.RECHAZADO.mp4` y deja el diagnóstico en `qc.json` y en el reporte.
2. **Lotes nocturnos**: `scripts\lote.py --entrada C:\crudos\ --salida C:\lote --estilo talking-head-limpio
   [--a-las 02:00]`. Edita todo sin supervisión; un vídeo que falla no para el lote. Deja `reporte.md` por vídeo y
   `lote.md` con el resumen.
3. **Costos transparentes**: cada vídeo escribe `costo.json` antes del render (el reporte lo muestra en orden:
   «costo estimado (antes de renderizar)» y después «render: inicio»). Whisper y Remotion son $0; el director
   `claude` y los ojos `gemini` se estiman en tokens. Los USD solo aparecen si el precio está puesto en
   `estilos.json → costos.precio_usd_millon`; si no, el reporte dice qué precio falta y no inventa la cifra. El
   costo real del director (`total_cost_usd` de `claude -p`) queda en `reporte.json → costo_real`.
4. **Memoria de marca**: `scripts\marca.py corregir --marca summit "el resalte en #00E5A0 y quita la muletilla
   «tipo»"`. Se guarda en `%LOCALAPPDATA%\growi-video\marcas\summit.json` con su historial, y cada `editar.py
   --marca summit` posterior la aplica (el reporte dice qué aplicó). Entiende colores (resalte, fondo, texto),
   fuente, más arriba/abajo, más grande/pequeño, mayúsculas, «máximo N palabras» y muletillas. Lo que no
   entiende lo guarda como nota y lo avisa; para eso está `--clave subtitulo.fondo --valor "#101010"`.
   **Cuando el usuario corrija un vídeo, guarda la corrección con `marca.py` antes de re-editar**: así no hay que
   repetirla en el siguiente.
5. **Repurposing**: `scripts\repurposing.py --largo C:\podcast.mp4 --salida C:\rp --clips 2`. Elige ventanas de
   10 a 40 s que empiezan con fuerza de gancho (pregunta, número, «segundo tema»…) y no se pisan. Cada una pasa
   por el pipeline completo (9:16, subtítulos, QC). Además escribe `post.md` con frases reales del vídeo
   (titular, 3 a 5 puntos y cierre); con `--director claude`, el post lo escribe Claude.

## Modo Bridge (tarea del runner, motor `claude`)

Tarea en `share\inbox\runner-tasks\` (o desde la app). El agente lee esta skill y corre los scripts:

```json
{
  "id": "t-reel-violet-01",
  "motor": "claude",
  "modelo": "sonnet",
  "cwd": "C:\\Users\\forte\\videos",
  "timeout_min": 30,
  "prompt": "Usa la skill edicion-video. crudo: C:\\crudos\\violet-01.mp4; estilo: reel-ganchos; marca: summit; director: reglas; salida: C:\\videos\\violet-01. Devuelve la ruta del final, el resumen del QC y el costo estimado."
}
```

Entradas: `crudo` (ruta), `estilo`, `marca`, `director` (`reglas` por defecto), `ojos` (`no` por defecto),
`salida`; para lote, `entrada` (carpeta) y `a-las`; para repurposing, `largo` y `clips`.

El resultado que el agente devuelve (y queda en `<salida>\reporte.json`):

```json
{"estado": "listo | rechazado por QC | error | esperando aprobación",
 "final": "C:\\videos\\violet-01\\final.mp4",
 "duracion_final_s": 23.4,
 "costo_estimado": {"resumen": "0 tokens: todo local, $0", "lineas": ["…"]},
 "costo_real": {"director": null, "ojos": null},
 "qc": {"ok": true, "diagnostico": "OK", "checks": ["…"]},
 "marca_aplicada": ["subtitulo.color_activo = #00E5A0"]}
```

## Límites honestos

- No juzga expresión facial, B-roll ni encuadre si Gemini no está activo; el gusto final es de quien revisa.
- Whisper se equivoca con palabras raras o en inglés («reels» puede salir «rills»): revisa los subtítulos en
  `props.json` antes de publicar algo importante.
- El director `reglas` decide «mejor toma = la última de dos casi iguales». Es lo habitual, pero no siempre es
  la mejor; para decidirlo de verdad, usa `--director claude` o revisa `cortes.md`.
- Sin cut-out (quitar el fondo) ni sonido (hits o música): quedan para una versión siguiente.

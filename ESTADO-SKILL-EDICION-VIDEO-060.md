# ESTADO — Skill de edición de vídeo con IA (0.6.0, t-skill-edicion-video-060)

Rama `Claude`, 29-oct-2026. La skill está en `skills/edicion-video/` (SKILL.md, `estilos.json`, `scripts/`,
plantilla Remotion e `instalar.ps1`). Pasa `python growi-bridge.py --validar-skills` con «frontmatter válido,
sin secretos». No se tocó `VERSION`.

## Con qué se probó (léelo primero)

En el PC **no hay ninguna toma de cámara cruda vertical**. Revisé con ffprobe los vídeos de Descargas, Vídeos,
Escritorio, Imágenes, OneDrive, workspace y Documentos. Los verticales que hay son reels ya editados de terceros,
con subtítulos quemados, y no sirven como crudo. Por eso la verificación usa **crudos sintéticos generados en este
PC** con `pruebas/video/generar_crudos.py`, que en pantalla dicen «CRUDO SINTETICO DE PRUEBA»:

- La voz es la de Windows (SAPI es-ES: Helena, Laura y Pablo), con lo que tiene una toma real: pausas de 0,6 a
  1,4 s, muletillas («eh», «o sea», «este») y frases repetidas (una falsa salida y luego la toma buena).
- La imagen es un fondo vertical con una «boca» (la forma de onda) que se mueve con la voz.
- Hay tres crudos verticales (39,5 s, 21,1 s y 21,3 s) y uno largo horizontal de 91,8 s para el repurposing.

El pipeline completo corrió de verdad sobre esos archivos. **Con una toma de cámara real no está probado**: ver FALTA.

## LISTO (verificado en este PC)

`python pruebas/video/prueba_edicion_video.py`. La evidencia está en `pruebas/evidencia/edicion-video/` (JSON
por punto, reportes, listas de cortes, post y fotogramas).

- **(a) Edición completa de un reel.** El crudo 1 de 39,5 s, con el estilo `reel-ganchos` y el director
  `claude` (`claude -p --model haiku`), quedó en 20,7 s.
  - Pasos: Whisper `small` local (88 palabras en 13 s de CPU), silencedetect (17 pausas), costo estimado,
    director, corte con audio a −14 LUFS, Remotion 1080x1920 a 30 fps y QC OK.
  - Subtítulos: 25 grupos, nunca más de 3 palabras en pantalla, con la palabra activa resaltada.
  - Mejor toma: el director quitó la falsa salida del principio («Hoy te cuento los tres errores que cometí, ¿eh?
    grabando…») y se quedó con la toma completa. Quitó también «el primero, o sea, el primero» y «el segundo,
    este, el segundo».
  - Escribió 3 ganchos: «Lo que más me costó grabando…», «La ventana te oscurece, no te ilumina» y «Tres errores
    que más me costaron».
  - Evidencia: `a-cortes.md`, `a-reporte.md` y `a-fotogramas.png`.
  - Con el director `reglas` ($0) el mismo crudo da 23,4 s. Las decisiones de toma son las mismas, pero los
    ganchos son peores: son frases del propio texto recortadas.
- **(b) El QC rechaza renders saboteados y deja pasar el bueno.**
  - Subtítulos por debajo del borde (`y_pct` 1,12): RECHAZADO, «no hay subtítulo visible en t=3,96 s (0 px
    cambiados)…». Evidencia: `b-saboteado-subtitulos.png`.
  - Audio retrasado 250 ms con silencio real: RECHAZADO, «desfase de la señal 0,25 s».
  - Audio desplazado 250 ms solo en el contenedor (`-itsoffset`): RECHAZADO, «del contenedor 0,207 s», y también
    por duración.
  - El render bueno: OK.
  - Ojo: la primera versión del QC **no** detectaba el desfase de contenedor. Lo destapó esta prueba y se arregló
    comparando el `start_time` del audio con el del vídeo.
- **(c) Lote de 3 vídeos sin intervención**: 3 de 3 listos en 233 s con `talking-head-limpio` (39,5 → 20,7 s,
  21,1 → 10,7 s y 21,3 → 10,8 s), cada uno con su `reporte.md` y el resumen en `c-lote.md`. `lote.py --a-las HH:MM`
  espera hasta esa hora; esa espera no la probé de noche.
- **(d) Costo antes del render**: en los 7 vídeos editados en la prueba, el evento «costo estimado (antes de
  renderizar)» va antes de «render: inicio» (`d.json`).
  - Con el director `claude`: **estimado 53 242 tokens y $0,0086; real 50 795 tokens y $0,0073**, según
    `total_cost_usd` de `claude -p`.
  - El USD estimado sale de la media de las corridas reales guardadas en
    `%LOCALAPPDATA%\growi-video\costos-historial.jsonl`, porque no hay precios puestos en `estilos.json`, y no se
    inventan. La sobrecarga de ~52 000 tokens que mete `claude -p` (el contexto de sistema de Claude Code) se
    midió en la primera corrida; mi primera estimación (1 242 tokens) la ignoraba y se corrigió.
  - Con el director `reglas`: «0 tokens: todo local, $0».
- **(e) Una corrección de marca se aplica en el siguiente vídeo.**
  - Corrección: `marca.py corregir --marca prueba-060 "El resalte en #00E5A0, el fondo de la caja en #101820 y
    quita la muletilla «justo»"`. Entendió y guardó los tres cambios.
  - En el siguiente `editar.py --marca prueba-060` el reporte dice qué aplicó, el render sale con la palabra activa
    en #00E5A0 sobre caja #101820, y «justo» ya no aparece (antes sí). Comparación: `e-sin-marca.png` frente a
    `e-con-marca.png`.
  - La prueba usó una carpeta de marcas temporal; la memoria real no se tocó.
- **(f) Repurposing**: del largo de 91,8 s salieron 2 clips verticales, cada uno de una sola idea:
  - 29,1–41,0 s → 8,5 s, gancho «Por qué la gente deja de mirar…», QC OK;
  - 66,7–78,3 s → 6,1 s, gancho «Mira la retención a los tres segundos…», QC OK.
  - Además salió `post.md`, con un titular, 5 puntos y el cierre, todo con frases reales del vídeo (`f-post.md`,
    `f-clip1.png` y `f-clip2.png`).
- **Estilos**: `talking-head-limpio`, `reel-ganchos` y `clip-rapido`, con sus parámetros en `estilos.json`. Los tres
  se usaron en las pruebas.
- **Modo Bridge**: el formato de la tarea (motor `claude`) y el del resultado están en SKILL.md, «Modo Bridge».

## Qué se instaló en el PC

- `%LOCALAPPDATA%\growi-video\venv`: faster-whisper 1.2.1 y numpy, aparte del Python global. El audio lo
  decodifica ffmpeg, porque faster-whisper 1.2.1 choca con PyAV 19 (`metadata_errors`).
- `%LOCALAPPDATA%\growi-video\modelos`: el Whisper `small`, descargado de Hugging Face a través del proxy.
- `%LOCALAPPDATA%\growi-video\remotion`: Remotion 4.0.539, React 19.1 y Chrome Headless Shell.
  - Los `node_modules` no van en `skills\`, porque la guía limita a 6 niveles de carpetas. La plantilla
    (`remotion/src`) sí vive en la skill y se sincroniza en cada render.
  - Un render de 20 s tarda unos 2 min en este portátil.

Nada de esto costó dinero. Lo único pagado fueron las 2 llamadas a `claude -p` con haiku de la verificación (a), la primera y la repetida: $0,0086 + $0,0073 ≈ $0,016.

## FALTA

- **Probar con una toma de cámara real** (Violet o una propia). Los sintéticos tienen voz limpia de TTS: con una
  voz real, el ruido de sala y las muletillas reales, Whisper y el umbral de pausas (−35 dB) pueden comportarse
  distinto.
- **Gemini como ojos: escrito, no probado.** `ojos.py` solo llama con `--ojos gemini` y `GEMINI_API_KEY` en el
  entorno. En este PC no había ninguna clave a la vista y no busqué en el almacén de credenciales. Por eso no hay
  verificación ni costo real de Gemini. El modelo por defecto (`gemini-2.5-flash`) y los 263 tokens/s son de la
  documentación de Gemini 1.5/2.x y hay que revisarlos.
- **Precios por millón de tokens** en `estilos.json`: siguen en null a propósito. El USD se estima por historial
  medido; para el de Gemini no hay historial.
- **Lote «nocturno» real**: `--a-las` no se dejó corriendo una noche. El lote corrió de seguido.
- **Prueba como tarea del runner**: el formato está documentado, pero no mandé una tarea real a la cola del
  runner (estaba ocupado con tareas de Leandro). Lo probado es la ejecución directa de los mismos scripts.
- Errores de Whisper que pasan a los subtítulos («reels» → «rills», «guion» → «huyan») y que se cuelan en los
  ganchos. Falta un diccionario de marca para corregir palabras.
- No hay cut-out (quitar el fondo) ni sonido (hits o música) del kit 5-Pass.
- Los clips del repurposing salen cortos (6 a 8 s) con `clip-rapido`, que corta pausas desde 0,25 s.
  Con más contenido por tema saldrían más largos; la ventana mínima está en 10 s.

## CÓMO PROBARLO

```
powershell -ExecutionPolicy Bypass -File skills\edicion-video\instalar.ps1     (una vez)
python pruebas\video\generar_crudos.py                                          (crudos de prueba)
python pruebas\video\prueba_edicion_video.py                                    (a-f; ~13 min; 1 llamada a haiku)
python pruebas\video\prueba_edicion_video.py b c d e f --sin-claude             ($0)
```

Con un crudo propio:

```
python skills\edicion-video\scripts\editar.py --crudo C:\crudos\toma.mp4 --salida C:\videos\toma --estilo reel-ganchos --solo-cortes
  (revisar C:\videos\toma\cortes.md)
python skills\edicion-video\scripts\editar.py --crudo C:\crudos\toma.mp4 --salida C:\videos\toma --cortes C:\videos\toma\director.json
python skills\edicion-video\scripts\qc.py C:\videos\toma
python skills\edicion-video\scripts\marca.py corregir --marca summit "subtítulos más arriba y el resalte en #FFD400"
python skills\edicion-video\scripts\lote.py --entrada C:\crudos --salida C:\lote --a-las 02:00
python skills\edicion-video\scripts\repurposing.py --largo C:\podcast.mp4 --salida C:\rp --clips 3
```

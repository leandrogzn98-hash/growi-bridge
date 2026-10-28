# ESTADO — Herramienta «transcribe» con faster-whisper (t-transcribe-whisper)

Rama `Claude`. Prueba: `pruebas/prueba_transcribe.py`. Usa una copia aislada y el runner real. Es real lo
medido en este PC y la tarea por el runner. El progreso, la cancelación y lo parcial se prueban con un
trabajador **falso, marcado «simulado»**, sobre un audio real de 60 s hecho con ffmpeg. Evidencia:
`pruebas/evidencia/transcribe/evidencia.json`.

## LISTO
1. **Herramienta `transcribe` en el runner** (no es un motor). Entra un audio, video o nota de voz (mp4, mov,
   mkv, webm, avi, mp3, wav, m4a, ogg, opus, flac, aac, wma) y sale `<archivo>.transcripcion.txt` **junto al
   archivo**, con marcas de tiempo `[hh:mm:ss - hh:mm:ss]` y una cabecera (idioma, modelo, «$0, local,
   offline»).
   - Se invoca desde una tarea (`"Transcribe <ruta>"` o `"herramienta": {"id": "transcribe", ...}`), desde
     la paleta («Transcribir un audio o video») y desde Ajustes → Motores → «Transcribir…».
   - Usa la **receta de la VM**: ffmpeg → f32le 16 kHz mono, con `decode_audio` parcheado (faster-whisper
     1.2.1 choca con av>=19).
   - Corre en un proceso aparte (`herramientas\transcribe_worker.py`). La única dependencia nueva es
     faster-whisper, justificada por el spec.
2. **Modelo local**: `Systran/faster-whisper-small` **ya está en este PC**, en la caché de Hugging Face
   (`model.bin` de **461,1 MB** = 483 546 902 bytes, bajado el 22-oct). Se usa con `local_files_only=True`,
   así que no hace falta red.
3. **Español por defecto** (`idioma: "es"`), o `"auto"` para que lo detecte. El idioma detectado y su
   probabilidad quedan en la cabecera, en el resultado (`idioma_detectado`) y en el registro.
4. **Progreso real y cancelación**: el trabajador avisa el segundo de audio por el que va → «Transcribiendo
   X: 30 s de 60 s (50 %)». Cancelar mata el proceso y deja lo hecho en `<archivo>.transcripcion.PARCIAL.txt`
   con «PARCIAL: cancelada a los 40 s de 60 s. NO está completa.». No quedan `.tmp` ni un `.transcripcion.txt`
   a medias.
5. **«$0, local, offline»** en la ficha (Ajustes), en la cabecera y en el resultado (`cost_usd: 0`). Nada de
   Descript ni de nube.

## Evidencia
| Criterio | Resultado |
|---|---|
| ficha real | ffmpeg `…\WinGet\Links\ffmpeg.EXE`; modelo small **461,1 MB** en el PC; **faster-whisper: no instalado** → `disponible: false` con el motivo exacto |
| tarea real | «Transcribe …\clip-prueba.mp3» por el runner → error definitivo «falta instalar faster-whisper en …python.exe (pip install faster-whisper==1.2.1…)». No inventa nada |
| (d) progreso (simulado) | 10 s, 20 s… 60 s de 60 s (17 %… 100 %) en `state.paso` y en el Registro |
| (d) cancelación (simulada) | a los 40 s: `PARCIAL.txt` con la marca; `queda_tmp: false`, `queda_completa: false` |
| (c) idioma | cabecera «idioma: es (pedido: es; el modelo detectó es con 0.99)»; el 0.99 es del trabajador simulado |
| paleta | crea la tarea `t-transcribir-…` con `herramienta.archivo` e `idioma: es` |
| Tracebacks | 0 |

## FALTA
- **(a) Transcribir de verdad un video en español y comprobar 3 frases**: **no se pudo**. faster-whisper no
  está instalado en este PC y la instalación (`pip install faster-whisper==1.2.1`, aunque fuera en un venv de
  `%TEMP%`) **no fue autorizada** en esta sesión, como pasó con OpenCode. No se intentó saltarlo.
- **(b) Segunda transcripción sin internet**: depende de lo anterior. El modelo ya está en disco
  (`local_files_only=True`), así que no hace falta bajar nada.
- Para cerrarlo:
  1. `pip install faster-whisper==1.2.1` en el Python de la app, o en otro y ponerlo en `settings.json` →
     `transcribe_python`;
  2. Ctrl+K → «Transcribir un audio o video» con un video de Violet;
  3. comparar 3 frases;
  4. repetir con el proxy apagado.

## COMO PROBARLO
`python pruebas/prueba_transcribe.py` → `pruebas/evidencia/transcribe/`. En la app: Ctrl+K → «Transcribir».

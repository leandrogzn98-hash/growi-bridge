"""Paso 1 y 2 del pipeline: Whisper local (palabra por palabra) y ffmpeg silencedetect. $0, sin red salvo la
primera descarga del modelo de Whisper."""

import re
import time
from pathlib import Path

from comun import DATOS, OCULTO, escribir_json, leer_json, run


def transcribir(video, carpeta, modelo="small", idioma="es"):
    """-> {"palabras": [{texto, inicio, fin, prob}], "idioma", "modelo", "segundos"} (en carpeta/palabras.json).
    Si ya existe para ese mismo crudo, se reutiliza (re-editar no vuelve a transcribir)."""
    carpeta = Path(carpeta)
    dst = carpeta / "palabras.json"
    firma = f"{Path(video).resolve()}|{Path(video).stat().st_size}|{modelo}"
    previo = leer_json(dst)
    if previo and previo.get("firma") == firma:
        return previo
    import subprocess
    import numpy as np
    from faster_whisper import WhisperModel
    # El audio lo decodifica ffmpeg (no PyAV: faster-whisper 1.2.1 choca con PyAV 19).
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le",
                        "-"], capture_output=True, timeout=900, creationflags=OCULTO)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg no pudo leer el audio: {p.stderr[-400:]!r}")
    audio = np.frombuffer(p.stdout, dtype=np.float32)
    t0 = time.time()
    m = WhisperModel(modelo, device="cpu", compute_type="int8", download_root=str(DATOS / "modelos"))
    segs, info = m.transcribe(audio, language=idioma, word_timestamps=True, vad_filter=False, beam_size=5,
                              condition_on_previous_text=False)
    palabras = []
    for s in segs:
        for w in s.words or []:
            txt = w.word.strip()
            if txt:
                palabras.append({"texto": txt, "inicio": round(w.start, 3), "fin": round(w.end, 3),
                                 "prob": round(w.probability, 3)})
    out = {"firma": firma, "modelo": modelo, "idioma": info.language, "segundos": round(time.time() - t0, 1),
           "palabras": palabras}
    escribir_json(dst, out)
    return out


def silencios(video, umbral_s=0.4, ruido_db=-35):
    """ffmpeg silencedetect: [(inicio, fin)] de las pausas de al menos umbral_s."""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-af",
             f"silencedetect=noise={ruido_db}dB:d={umbral_s}", "-f", "null", "-"], timeout=900)
    ini, out = None, []
    for ln in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", ln)
        if m:
            ini = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", ln)
        if m and ini is not None:
            out.append((round(ini, 3), round(float(m.group(1)), 3)))
            ini = None
    return out

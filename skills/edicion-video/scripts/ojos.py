"""Paso opcional: Gemini como «ojos». Ve el vídeo de verdad (Claude solo lee el transcript) y devuelve notas de lo
que el texto no dice: encuadre, mirada a cámara, gestos, la toma que se ve mejor. Solo corre con --ojos gemini Y
la variable GEMINI_API_KEY en el entorno; si no, se salta y el reporte lo dice. Manda una versión ligera del
vídeo (360 px, 1 fps de imagen útil) en línea; nunca el crudo entero."""

import base64
import json
import os
import urllib.request
from pathlib import Path

from comun import ffmpeg

PROMPT = ("Eres los ojos de un editor de reels. Mira el vídeo y responde SOLO JSON: "
          '{"notas": ["<observación con segundo aproximado>"], "tomas_que_se_ven_peor": [{"desde": s, "hasta": s, '
          '"por_que": "..."}], "encuadre_ok": true|false}. Nada de inventar: si no se ve, no lo digas.')


def mirar(video, carpeta, estilo):
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        return {"usado": False, "motivo": "sin GEMINI_API_KEY en el entorno: paso saltado ($0)"}
    ligero = Path(carpeta) / "ojos-360p.mp4"
    ffmpeg("-i", video, "-vf", "scale=-2:360,fps=4", "-c:v", "libx264", "-crf", "32", "-preset", "veryfast",
           "-c:a", "aac", "-b:a", "48k", "-ac", "1", ligero)
    if ligero.stat().st_size > estilo["gemini"]["max_mb_en_linea"] * 2 ** 20:
        return {"usado": False, "motivo": "vídeo ligero demasiado grande para mandarlo en línea"}
    cuerpo = {"contents": [{"parts": [
        {"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(ligero.read_bytes()).decode()}},
        {"text": PROMPT}]}], "generationConfig": {"responseMimeType": "application/json"}}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{estilo['gemini']['modelo']}:generateContent")
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": clave})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode("utf-8"))
    txt = d["candidates"][0]["content"]["parts"][0]["text"]
    uso = d.get("usageMetadata") or {}
    return {"usado": True, "modelo": estilo["gemini"]["modelo"], "vision": json.loads(txt),
            "tokens_entrada": uso.get("promptTokenCount"), "tokens_salida": uso.get("candidatesTokenCount")}

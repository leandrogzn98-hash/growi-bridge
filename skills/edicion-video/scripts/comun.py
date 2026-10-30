"""Lo que comparten los scripts de la skill edicion-video: rutas, ffmpeg/ffprobe, estilos + marca, JSON."""

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REMOTION = SKILL / "remotion"  # la plantilla (fuentes); sus node_modules NO viven en la skill
DATOS = Path(os.environ.get("GROWI_VIDEO_DATOS") or Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "growi-video")
REMOTION_RUN = DATOS / "remotion"  # copia de trabajo con node_modules (la deja instalar.ps1)
VENV_PY = DATOS / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MARCAS = Path(os.environ.get("GROWI_VIDEO_MARCAS") or DATOS / "marcas")
OCULTO = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def asegurar_venv():
    """Si faltan faster-whisper o numpy y existe el venv de la skill, se vuelve a lanzar con su Python (así el
    runner puede llamar a `python editar.py ...` sin saber dónde está el venv)."""
    try:
        import faster_whisper  # noqa: F401
        import numpy  # noqa: F401
        return
    except ImportError:
        pass
    if VENV_PY.is_file() and Path(sys.executable).resolve() != VENV_PY.resolve():
        r = subprocess.run([str(VENV_PY)] + sys.argv)
        sys.exit(r.returncode)
    sys.exit(f"Falta el entorno de la skill: corre  powershell -File {SKILL / 'instalar.ps1'}")


def leer_json(p, defecto=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def escribir_json(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def ahora():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def run(args, timeout=1800, cwd=None):
    """Proceso oculto y sin shell. -> CompletedProcess (texto en UTF-8)."""
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=cwd, creationflags=OCULTO)


def ffmpeg(*args, timeout=1800):
    r = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *args], timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falló ({r.returncode}): {r.stderr[-800:]}")
    return r


def probe(p):
    """-> {duracion, ancho, alto, fps, audio}"""
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,width,height,r_frame_rate:stream_side_data=rotation:format=duration",
             "-of", "json", p], timeout=60)
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    num, _, den = str(v.get("r_frame_rate") or "30/1").partition("/")
    rot = 0
    for sd in v.get("side_data_list") or []:
        rot = int(sd.get("rotation") or 0)
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    if abs(rot) in (90, 270):
        w, h = h, w
    return {"duracion": float((d.get("format") or {}).get("duration") or 0), "ancho": w, "alto": h,
            "fps": round(float(num) / float(den or 1), 3) if num else 30.0,
            "audio": any(s.get("codec_type") == "audio" for s in d.get("streams", []))}


def norm(t):
    """minúsculas, sin acentos ni puntuación: para comparar palabras y frases."""
    t = unicodedata.normalize("NFD", str(t).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ ]+", " ", t).split()


def slug(t):
    return "-".join(norm(t))[:60] or "sin-nombre"


def cargar_estilo(nombre, marca=None):
    """Estilo del catálogo + lo común + lo que la memoria de marca corrigió. -> (estilo, cambios_de_marca)"""
    cat = leer_json(SKILL / "estilos.json")
    if nombre not in cat["estilos"]:
        raise SystemExit(f"estilo «{nombre}» no existe; hay: {', '.join(cat['estilos'])}")
    e = dict(cat["comun"])
    e.update({k: v for k, v in cat["estilos"][nombre].items() if k != "subtitulo"})
    e["subtitulo"] = dict(cat["estilos"][nombre]["subtitulo"])
    e["nombre"], e["costos"], e["gemini"] = nombre, cat["costos"], cat["gemini"]
    aplicados = []
    if marca:
        m = leer_json(MARCAS / f"{slug(marca)}.json", {}) or {}
        for k, v in (m.get("subtitulo") or {}).items():
            e["subtitulo"][k] = v
            aplicados.append(f"subtitulo.{k} = {v}")
        for k in ("umbral_pausa_s", "max_palabras", "zoom_gancho", "loudnorm_lufs"):
            if k in (m.get("edicion") or {}):
                e[k] = m["edicion"][k]
                aplicados.append(f"{k} = {e[k]}")
        extra = [x for x in m.get("muletillas_extra") or [] if x not in e["muletillas_siempre"]]
        if extra:
            e["muletillas_siempre"] = list(e["muletillas_siempre"]) + extra
            aplicados.append(f"muletillas que se quitan siempre: {', '.join(extra)}")
    return e, aplicados

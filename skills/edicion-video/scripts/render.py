"""Paso 4 y 5: aplicar la lista de cortes con ffmpeg (corte, unión, 1080x1920 a 30 fps, audio a -14 LUFS) y
renderizar con Remotion (subtítulos palabra por palabra, máximo 3 en pantalla, gancho y punch-in)."""

import re
import shutil
from pathlib import Path

from comun import REMOTION, REMOTION_RUN, escribir_json, ffmpeg, run

PUNTUACION_FIN = re.compile(r"[,.;:…]+$")


def cortar(crudo, segmentos, estilo, salida):
    w, h, fps = estilo["ancho"], estilo["alto"], estilo["fps"]
    partes, vs = [], []
    for n, (a, b) in enumerate(segmentos):
        d = b - a
        f = min(0.012, d / 4)
        partes.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{n}];"
                      f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d={f},afade=t=out:st={d - f:.3f}:d={f}[a{n}];")
        vs.append(f"[v{n}][a{n}]")
    fc = ("".join(partes) + "".join(vs) + f"concat=n={len(segmentos)}:v=1:a=1[vc][ac];"
          f"[vc]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1[v];"
          f"[ac]loudnorm=I={estilo['loudnorm_lufs']}:TP=-1.5:LRA=11,aresample=48000[a]")
    ffmpeg("-i", crudo, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", salida)
    return sum(b - a for a, b in segmentos)


def a_editado(segmentos):
    """función t_crudo -> t_editado (None si cae en un corte)."""
    acum, tabla = 0.0, []
    for a, b in segmentos:
        tabla.append((a, b, acum))
        acum += b - a

    def f(t):
        for a, b, off in tabla:
            if a - 1e-3 <= t <= b + 1e-3:
                return round(off + min(max(t, a), b) - a, 3)
        return None
    return f


def subtitulos(pal, quitadas, segmentos, estilo, duracion):
    """Grupos de hasta max_palabras (nunca más de 3) en el tiempo del vídeo editado."""
    f = a_editado(segmentos)
    maxp = min(3, int(estilo["max_palabras"]))
    vivas = []
    for i, w in enumerate(pal):
        if str(i) in quitadas:
            continue
        a, b = f(w["inicio"]), f(w["fin"])
        if a is None or b is None:
            continue
        txt = PUNTUACION_FIN.sub("", w["texto"]).strip()
        if txt:
            vivas.append({"texto": txt, "inicio": a, "fin": max(b, a + 0.05),
                          "resalte": bool(re.search(r"\d", txt)), "_corte": bool(PUNTUACION_FIN.search(w["texto"]))})
    grupos, act = [], []
    for w in vivas:
        if act and (len(act) >= maxp or w["inicio"] - act[-1]["fin"] > 0.3 or act[-1]["_corte"]):
            grupos.append(act)
            act = []
        act.append(w)
    if act:
        grupos.append(act)
    out = []
    for n, g in enumerate(grupos):
        ini = g[0]["inicio"]
        fin = grupos[n + 1][0]["inicio"] if n + 1 < len(grupos) else min(duracion, g[-1]["fin"] + 0.4)
        fin = min(fin, g[-1]["fin"] + 0.6)
        out.append({"inicio": round(ini, 3), "fin": round(max(fin, ini + 0.2), 3),
                    "palabras": [{k: v for k, v in w.items() if k != "_corte"} for w in g]})
    return out


def remotion(carpeta, props, salida):
    """Render 1080x1920 con la plantilla de remotion/ (el vídeo editado va en --public-dir = carpeta)."""
    cli = REMOTION_RUN / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not cli.is_file():
        raise RuntimeError(f"falta Remotion: corre instalar.ps1 (no existe {cli})")
    # La plantilla de la skill manda: se copia a la carpeta de trabajo si cambió.
    for f in [REMOTION / "package.json"] + sorted((REMOTION / "src").glob("*")):
        dst = REMOTION_RUN / f.relative_to(REMOTION)
        if not dst.is_file() or dst.read_bytes() != f.read_bytes():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    pj = Path(carpeta) / "props.json"
    escribir_json(pj, props)
    r = run([shutil.which("node") or "node", cli, "render", "src/index.ts", "Reel", salida, f"--props={pj}",
             f"--public-dir={carpeta}", "--log=error", "--concurrency=50%"], timeout=3600, cwd=REMOTION_RUN)
    if r.returncode != 0 or not Path(salida).is_file():
        raise RuntimeError(f"Remotion falló ({r.returncode}): {(r.stderr or r.stdout)[-1200:]}")

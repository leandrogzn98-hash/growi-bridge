"""Repurposing: de 1 vídeo largo (horizontal o vertical) saca N clips verticales editados + 1 post de texto.

  python repurposing.py --largo C:\\podcast.mp4 --salida C:\\repurposing [--clips 2] [--estilo clip-rapido]
                        [--marca summit] [--director reglas|claude]

1. Whisper sobre el largo. 2. Frases -> ventanas de 12-40 s que empiezan en una frase con fuerza de gancho
(pregunta, número, «primero/segundo/tercer tema»…); se eligen las N mejores que no se pisan. 3. Cada ventana se
recorta y pasa por editar.py (pausas, muletillas, 9:16, subtítulos, QC). 4. post.md con el gancho, los puntos
clave (frases reales del vídeo, sin inventar) y el cierre. Con --director claude, el post lo escribe Claude
sobre el transcript.
"""

import argparse
import re
import sys
from pathlib import Path

from comun import ahora, asegurar_venv, cargar_estilo, escribir_json, ffmpeg, norm, probe

MARCAS_TEMA = ("primero", "segundo", "tercer", "tercero", "cuarto", "cerrar", "tema", "por que", "porque")


def _fuerza(texto):
    import director as d
    n = " ".join(norm(texto))
    return d._puntaje_gancho(texto) + (2 if any(m in n for m in MARCAS_TEMA) else 0)


def ventanas(frases, n, min_s=10.0, max_s=40.0):
    cands = []
    for i, f in enumerate(frases):
        j, fin = i, f["fin"]
        while j + 1 < len(frases) and frases[j + 1]["fin"] - f["inicio"] <= max_s:
            j += 1
            fin = frases[j]["fin"]
            # corta antes de otro inicio de tema: un clip = una idea
            if j + 1 < len(frases) and _fuerza(frases[j + 1]["texto"]) >= 2 and fin - f["inicio"] >= min_s:
                break
        dur = fin - f["inicio"]
        if dur < min_s:
            continue
        resto = [_fuerza(x["texto"]) for x in frases[i + 1:j + 1]] or [0]
        puntos = 3 * _fuerza(f["texto"]) + sum(resto) / len(resto) - abs(dur - 25) / 25
        cands.append({"desde": i, "hasta": j, "inicio": f["inicio"], "fin": fin, "puntos": round(puntos, 2),
                      "texto": " ".join(x["texto"] for x in frases[i:j + 1])})
    elegidas = []
    for c in sorted(cands, key=lambda c: -c["puntos"]):
        if all(c["fin"] <= e["inicio"] or c["inicio"] >= e["fin"] for e in elegidas):
            elegidas.append(c)
        if len(elegidas) == n:
            break
    return sorted(elegidas, key=lambda c: c["inicio"])


def _limpio(t):
    """Sin muletillas ni repeticiones en el texto escrito («y eso, eh, eso los deja» -> «y eso los deja»)."""
    t = re.sub(r",?\s*\b(?:eh|em|ehm|mmm)\b(?=[,.\s])", "", t, flags=re.I)
    t = re.sub(r"\b(\w+),?\s+\1\b", r"\1", t, flags=re.I)
    t = re.sub(r"\s+,", ",", t).strip().lstrip(",.; ")
    return t[:1].upper() + t[1:]


def post_reglas(frases, clips):
    """Post con frases reales del vídeo: titular = la frase con más fuerza de gancho; puntos = lo que se dice en
    cada tema (una etiqueta corta tipo «Segundo tema, los ganchos» se cambia por la frase que la sigue)."""
    def etiqueta(t):
        return len(norm(t)) <= 6 and any(m in " ".join(norm(t)) for m in MARCAS_TEMA)
    titular = max(frases, key=lambda f: (_fuerza(f["texto"]), -f["inicio"]))["texto"]
    puntos = []
    for k, f in enumerate(frases):
        if _fuerza(f["texto"]) < 2 or f["texto"] == titular:
            continue
        t = frases[k + 1]["texto"] if etiqueta(f["texto"]) and k + 1 < len(frases) else f["texto"]
        if t not in puntos and t != titular:
            puntos.append(t)
    cierre = next((f["texto"] for f in reversed(frases) if re.search(r"cerrar|gracias|guarda|s[ií]gueme|comenta",
                                                                      f["texto"], re.I)), None)
    puntos = [_limpio(p) for p in puntos if p != cierre][:5]
    out = [f"**{titular.strip()}**", ""] + [f"→ {p}" for p in puntos]
    if cierre:
        out += ["", cierre]
    return "\n".join(out) + "\n"


def post_claude(frases, modelo):
    import json
    import shutil
    from comun import run
    txt = "\n".join(f["texto"] for f in frases)
    prompt = ("Escribe un post de texto para LinkedIn/Instagram a partir de este transcript. Usa solo ideas que "
              "estén en el transcript (sin inventar cifras ni testimonios). Formato: gancho de una línea, 3-5 puntos, "
              "cierre con pregunta. Devuelve solo el post en markdown.\n\nTranscript:\n" + txt)
    r = run([shutil.which("claude") or "claude", "-p", prompt, "--model", modelo, "--output-format", "json"],
            timeout=600)
    env = json.loads(r.stdout)
    return env.get("result") or "", env.get("total_cost_usd")


def repurposing(largo, salida, n=2, estilo="clip-rapido", marca=None, director="reglas", modelo="haiku"):
    import director as dirmod
    from editar import editar
    from transcribir import transcribir
    salida = Path(salida)
    (salida / "largo").mkdir(parents=True, exist_ok=True)
    e, _ = cargar_estilo(estilo, marca)
    info = probe(largo)
    tr = transcribir(largo, salida / "largo", e["whisper_modelo"])
    frases = dirmod._frases(tr["palabras"], 0.6)
    vs = ventanas(frases, n)
    rep = {"largo": str(largo), "largo_info": info, "inicio": ahora(), "clips": []}
    for k, v in enumerate(vs, 1):
        crudo = salida / f"clip{k}-crudo.mp4"
        a, b = max(0.0, v["inicio"] - 0.15), min(info["duracion"], v["fin"] + 0.3)
        ffmpeg("-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", largo, "-c:v", "libx264", "-preset", "veryfast", "-crf",
               "18", "-c:a", "aac", "-b:a", "192k", crudo)
        r = editar(crudo, salida / f"clip{k}", estilo, marca, director, modelo)
        g = (r.get("eventos") and next((x.get("gancho") for x in r["eventos"] if x.get("gancho")), None))
        rep["clips"].append({"n": k, "desde_s": round(a, 2), "hasta_s": round(b, 2), "texto": v["texto"],
                             "puntos": v["puntos"], "estado": r["estado"], "final": r.get("final"),
                             "duracion_final_s": r.get("duracion_final_s"), "gancho": g,
                             "qc": (r.get("qc") or {}).get("diagnostico")})
        escribir_json(salida / "repurposing.json", rep)
    if director == "claude":
        post, costo = post_claude(frases, modelo)
        rep["post_costo_usd"] = costo
    else:
        post = post_reglas(frases, rep["clips"])
    (salida / "post.md").write_text(post, encoding="utf-8")
    rep["post"] = str(salida / "post.md")
    rep["fin"] = ahora()
    escribir_json(salida / "repurposing.json", rep)
    return rep


if __name__ == "__main__":
    asegurar_venv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--largo", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--clips", type=int, default=2)
    ap.add_argument("--estilo", default="clip-rapido")
    ap.add_argument("--marca")
    ap.add_argument("--director", choices=("reglas", "claude"), default="reglas")
    ap.add_argument("--modelo", default="haiku")
    a = ap.parse_args()
    r = repurposing(a.largo, a.salida, a.clips, a.estilo, a.marca, a.director, a.modelo)
    for c in r["clips"]:
        print(f"clip {c['n']}: {c['desde_s']}-{c['hasta_s']} s -> {c['estado']} {c['final']}")
    print("post:", r["post"])
    print(Path(r["post"]).read_text(encoding="utf-8"))
    sys.exit(0 if r["clips"] and all(c["estado"] == "listo" for c in r["clips"]) else 1)

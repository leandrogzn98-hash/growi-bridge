"""Lotes nocturnos: encola N crudos y los edita uno tras otro sin supervisión. Un vídeo que falla no para el lote.
Deja reporte.md por vídeo y lote.md con el resumen (estado, duración, costo estimado, QC).

  python lote.py --entrada C:\\crudos\\ --salida C:\\lote-hoy [--estilo talking-head-limpio] [--marca summit]
                 [--director reglas|claude] [--a-las 02:00]

--entrada acepta una carpeta (todos sus .mp4/.mov) o varias rutas. --a-las espera hasta esa hora antes de empezar
(para dejarlo programado por la noche; también se puede mandar como tarea del runner a esa hora).
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

from comun import ahora, asegurar_venv, escribir_json, slug

EXT = (".mp4", ".mov", ".m4v", ".mkv")


def crudos(entradas):
    out = []
    for e in entradas:
        p = Path(e)
        if p.is_dir():
            out += sorted(f for f in p.iterdir() if f.suffix.lower() in EXT)
        elif p.is_file():
            out.append(p)
    return out


def esperar_hasta(hhmm):
    h, m = (int(x) for x in hhmm.split(":"))
    ya = datetime.datetime.now()
    obj = ya.replace(hour=h, minute=m, second=0, microsecond=0)
    if obj <= ya:
        obj += datetime.timedelta(days=1)
    print(f"lote: espero hasta {obj:%Y-%m-%d %H:%M}", flush=True)
    time.sleep((obj - ya).total_seconds())


def lote(entradas, salida, estilo, marca=None, director="reglas", modelo="haiku"):
    from editar import editar
    salida = Path(salida)
    lista = crudos(entradas)
    res = {"inicio": ahora(), "estilo": estilo, "marca": marca, "director": director, "videos": []}
    for n, c in enumerate(lista, 1):
        print(f"lote: {n}/{len(lista)} {c.name}", flush=True)
        r = editar(c, salida / f"{n:02d}-{slug(c.stem)}", estilo, marca, director, modelo)
        res["videos"].append({"crudo": str(c), "estado": r["estado"], "carpeta": str(salida / f"{n:02d}-{slug(c.stem)}"),
                              "final": r.get("final"), "duracion_final_s": r.get("duracion_final_s"),
                              "crudo_s": (r.get("crudo_info") or {}).get("duracion"), "segundos": r.get("segundos"),
                              "costo_estimado": (r.get("costo_estimado") or {}).get("resumen"),
                              "qc": (r.get("qc") or {}).get("diagnostico"), "error": r.get("error")})
        escribir_json(salida / "lote.json", res)
    res["fin"] = ahora()
    res["listos"] = sum(v["estado"] == "listo" for v in res["videos"])
    escribir_json(salida / "lote.json", res)
    md = [f"# Lote {res['inicio']} — {res['listos']}/{len(lista)} listos", "",
          f"Estilo {estilo}; marca {marca or '—'}; director {director}. Sin supervisión.", "",
          "| # | Crudo | Estado | Crudo → final | Costo estimado | QC | Reporte |", "|---|---|---|---|---|---|---|"]
    for n, v in enumerate(res["videos"], 1):
        md.append(f"| {n} | {Path(v['crudo']).name} | {v['estado']} | {v['crudo_s'] or 0:.1f} s → "
                  f"{v['duracion_final_s'] or 0:.1f} s | {v['costo_estimado'] or '—'} | {v['qc'] or v['error'] or '—'} | "
                  f"`{Path(v['carpeta']) / 'reporte.md'}` |")
    (salida / "lote.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return res


if __name__ == "__main__":
    asegurar_venv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", nargs="+", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--estilo", default="talking-head-limpio")
    ap.add_argument("--marca")
    ap.add_argument("--director", choices=("reglas", "claude"), default="reglas")
    ap.add_argument("--modelo", default="haiku")
    ap.add_argument("--a-las")
    a = ap.parse_args()
    if a.a_las:
        esperar_hasta(a.a_las)
    r = lote(a.entrada, a.salida, a.estilo, a.marca, a.director, a.modelo)
    print((Path(a.salida) / "lote.md").read_text(encoding="utf-8"))
    sys.exit(0 if r["listos"] == len(r["videos"]) else 1)

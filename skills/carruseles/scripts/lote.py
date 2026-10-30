"""Lote de carruseles sin supervisión: una lista de briefs -> un carrusel por brief + reporte por carrusel + lote.md.

  python lote.py --briefs C:\\briefs\\            (todos los *.json de la carpeta, en orden de nombre)
  python lote.py --briefs C:\\briefs\\cola.json   (un JSON con una lista de briefs)
                 --salida C:\\carruseles\\lote-29oct [--marca summit-maker]

Un carrusel que falla no para el lote. Código de salida: 0 = todos listos, 1 = alguno rechazado, con error o bloqueado.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from carrusel import generar
from comun import ahora, escribir_json, slug


def cargar_briefs(ruta):
    p = Path(ruta)
    if p.is_dir():
        return [(f.stem, json.loads(f.read_text(encoding="utf-8"))) for f in sorted(p.glob("*.json"))]
    datos = json.loads(p.read_text(encoding="utf-8"))
    datos = datos if isinstance(datos, list) else datos.get("briefs") or []
    return [(b.get("id") or f"carrusel-{i:02d}", b) for i, b in enumerate(datos, 1)]


def main():
    ap = argparse.ArgumentParser(description="Lote de carruseles")
    ap.add_argument("--briefs", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--marca")
    a = ap.parse_args()
    t0, inicio = time.time(), ahora()
    filas = []
    briefs = cargar_briefs(a.briefs)
    for i, (nombre, b) in enumerate(briefs, 1):
        print(f"[{i}/{len(briefs)}] {nombre} ...", flush=True)
        r = generar(b, Path(a.salida) / slug(b.get("id") or nombre), a.marca)
        q = r.get("qc") or {}
        filas.append({"id": r["id"], "estado": r["estado"], "laminas_ok": q.get("laminas_ok", 0),
                      "total": q.get("total", len(b.get("laminas") or [])), "avisos": len(r.get("avisos") or []),
                      "segundos": r["segundos"], "error": r.get("error"), "carpeta": r["salida"]})
        print(f"      {r['estado']} · {filas[-1]['laminas_ok']}/{filas[-1]['total']} láminas OK · "
              f"{filas[-1]['avisos']} avisos · {r['segundos']} s", flush=True)
    listos = sum(1 for f in filas if f["estado"] == "listo")
    md = [f"# Lote de carruseles: {listos}/{len(filas)} listos", "",
          f"Inicio {inicio}, fin {ahora()}, {round(time.time() - t0, 1)} s en total, sin intervención.", "",
          "| Carrusel | Estado | Láminas OK | Advertencias | Tiempo | Detalle |", "|---|---|---|---|---|---|"]
    for f in filas:
        md.append(f"| {f['id']} | {f['estado']} | {f['laminas_ok']}/{f['total']} | {f['avisos']} | {f['segundos']} s | "
                  f"{(f['error'] or 'reporte.md en ' + f['carpeta'])} |")
    Path(a.salida).mkdir(parents=True, exist_ok=True)
    (Path(a.salida) / "lote.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    escribir_json(Path(a.salida) / "lote.json", {"inicio": inicio, "fin": ahora(), "carruseles": filas})
    print("\n".join(md))
    sys.exit(0 if listos == len(filas) else 1)


if __name__ == "__main__":
    main()

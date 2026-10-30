"""Render de una lámina HTML con Chrome headless: medidas del DOM (--dump-dom), PNG normal y PNG sin texto.

  python render.py <lamina.html> [<lamina2.html> ...]     -> deja lamina.png, lamina.sin-texto.png, lamina.medidas.json
"""

import html as htmlmod
import json
import re
import sys
from pathlib import Path

from comun import chrome_headless, escribir_json


def medidas(p):
    r = chrome_headless(Path(p).resolve().as_uri(), "--dump-dom")
    m = re.search(r'<html[^>]*\sdata-qc="([^"]*)"', r.stdout or "")
    if not m:
        raise RuntimeError(f"Chrome no dejó medidas para {Path(p).name} (rc={r.returncode}): {(r.stderr or '')[-400:]}")
    return json.loads(htmlmod.unescape(m.group(1)))


def captura(p, png, sin_texto=False):
    url = Path(p).resolve().as_uri() + ("#sin-texto" if sin_texto else "")
    Path(png).unlink(missing_ok=True)
    r = chrome_headless(url, f"--screenshot={Path(png).resolve()}")
    if not Path(png).is_file():
        raise RuntimeError(f"Chrome no hizo la captura de {Path(p).name} (rc={r.returncode}): {(r.stderr or '')[-400:]}")
    return png


def render(p):
    """-> (png, png_sin_texto, medidas)"""
    p = Path(p)
    base = p.with_suffix("")
    m = medidas(p)
    escribir_json(f"{base}.medidas.json", m)
    png = captura(p, f"{base}.png")
    sin = captura(p, f"{base}.sin-texto.png", sin_texto=True)
    return png, sin, m


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(render(a)[0])

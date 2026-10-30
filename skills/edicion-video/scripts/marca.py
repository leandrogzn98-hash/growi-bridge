"""Memoria de marca: guarda las correcciones del usuario y editar.py las aplica en los vídeos siguientes.

Vive fuera del repo, en %LOCALAPPDATA%\\growi-video\\marcas\\<marca>.json (cada PC aprende de su dueño).

  python marca.py corregir --marca summit "el resalte en #00E5A0 y quita la muletilla «tipo»"
  python marca.py corregir --marca summit --clave subtitulo.fuente --valor "Montserrat ExtraBold"
  python marca.py ver --marca summit

Lo que entiende del texto libre (lo demás se guarda como nota y se avisa, nunca se adivina):
  color #hex + resalte/activa | fondo/caja | texto/letra  ·  fuente/tipografía <nombre>  ·  más arriba/abajo
  más grande/pequeño  ·  en mayúsculas / sin mayúsculas  ·  máximo N palabras  ·  quita la muletilla «x»
"""

import argparse
import json
import re
import sys

from comun import MARCAS, ahora, escribir_json, leer_json, slug

CLAVES = {"subtitulo.fuente": str, "subtitulo.tam_px": int, "subtitulo.color": str, "subtitulo.color_activo": str,
          "subtitulo.fondo": str, "subtitulo.y_pct": float, "subtitulo.mayusculas": lambda v: str(v).lower() in
          ("1", "true", "si", "sí"), "edicion.max_palabras": int, "edicion.umbral_pausa_s": float,
          "edicion.zoom_gancho": float, "edicion.loudnorm_lufs": float}


def ruta(marca):
    return MARCAS / f"{slug(marca)}.json"


def cargar(marca):
    return leer_json(ruta(marca), None) or {"marca": marca, "subtitulo": {}, "edicion": {}, "muletillas_extra": [],
                                            "correcciones": []}


def _poner(m, clave, valor):
    grupo, k = clave.split(".", 1)
    m.setdefault(grupo, {})[k] = CLAVES[clave](valor)
    return f"{clave} = {m[grupo][k]}"


def interpretar(texto, m):
    """-> lista de cambios aplicados a m."""
    t = texto.lower()
    cambios = []
    for mm in re.finditer(r"(#[0-9a-f]{6})", t):
        antes = t[max(0, mm.start() - 40):mm.start()]
        if re.search(r"resalt|activ|destac", antes):
            cambios.append(_poner(m, "subtitulo.color_activo", mm.group(1).upper()))
        elif re.search(r"fondo|caja|p[ií]ldora", antes):
            cambios.append(_poner(m, "subtitulo.fondo", mm.group(1).upper()))
        elif re.search(r"texto|letra|subt", antes):
            cambios.append(_poner(m, "subtitulo.color", mm.group(1).upper()))
    f = re.search(r"(?:fuente|tipograf[ií]a)\s+(?:en\s+|a\s+)?[«\"']?([A-Za-zÁÉÍÓÚáéíóú0-9 \-]+?)[»\"']?(?:[,.;]|$| y )",
                  texto, re.I)
    if f:
        cambios.append(_poner(m, "subtitulo.fuente", f.group(1).strip()))
    y = m.setdefault("subtitulo", {}).get("y_pct")
    if "más arriba" in t or "mas arriba" in t:
        cambios.append(_poner(m, "subtitulo.y_pct", round((y or 0.68) - 0.06, 3)))
    elif "más abajo" in t or "mas abajo" in t:
        cambios.append(_poner(m, "subtitulo.y_pct", round((y or 0.68) + 0.04, 3)))
    tam = m["subtitulo"].get("tam_px")
    if re.search(r"m[aá]s grande", t):
        cambios.append(_poner(m, "subtitulo.tam_px", (tam or 76) + 8))
    elif re.search(r"m[aá]s peque", t):
        cambios.append(_poner(m, "subtitulo.tam_px", (tam or 76) - 8))
    if re.search(r"sin may[uú]sculas|en min[uú]sculas", t):
        cambios.append(_poner(m, "subtitulo.mayusculas", "false"))
    elif re.search(r"en may[uú]sculas", t):
        cambios.append(_poner(m, "subtitulo.mayusculas", "true"))
    n = re.search(r"m[aá]ximo\s+(\d)\s+palabras", t)
    if n:
        cambios.append(_poner(m, "edicion.max_palabras", min(3, int(n.group(1)))))
    for q in re.finditer(r"(?:quita|elimina|borra|saca)\w*\s+(?:la\s+|las\s+)?(?:muletillas?\s+)?[«\"']([^»\"']+)[»\"']",
                         texto, re.I):
        w = q.group(1).strip().lower()
        if w not in m.setdefault("muletillas_extra", []):
            m["muletillas_extra"].append(w)
            cambios.append(f"muletilla que se quita siempre: «{w}»")
    return cambios


def corregir(marca, texto=None, clave=None, valor=None):
    m = cargar(marca)
    cambios = []
    if clave:
        if clave not in CLAVES:
            raise SystemExit(f"clave desconocida: {clave}; valen {', '.join(CLAVES)}")
        cambios.append(_poner(m, clave, valor))
    if texto:
        cambios += interpretar(texto, m)
    m.setdefault("correcciones", []).append({"fecha": ahora(), "texto": texto, "clave": clave, "valor": valor,
                                             "cambios": cambios, "entendida": bool(cambios)})
    escribir_json(ruta(marca), m)
    return m, cambios


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=("corregir", "ver"))
    ap.add_argument("--marca", required=True)
    ap.add_argument("texto", nargs="?")
    ap.add_argument("--clave")
    ap.add_argument("--valor")
    a = ap.parse_args()
    if a.accion == "ver":
        print(json.dumps(cargar(a.marca), ensure_ascii=False, indent=1))
    else:
        m, cambios = corregir(a.marca, a.texto, a.clave, a.valor)
        print(f"Guardado en {ruta(a.marca)}")
        print("\n".join(f"  - {c}" for c in cambios) or "  (no entendí nada aplicable: quedó como nota; usa --clave/--valor)")

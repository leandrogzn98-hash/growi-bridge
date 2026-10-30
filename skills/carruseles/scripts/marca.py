"""Memoria de marca de los carruseles: brandbooks + correcciones del usuario que se aplican en los siguientes.

El brandbook semilla vive en la skill (skills\\carruseles\\marcas\\<marca>.json, lo escribe una persona). Las
correcciones viven en el PC, en %LOCALAPPDATA%\\growi-carruseles\\marcas\\<marca>.json, con su historial, y se
superponen al brandbook en cada carrusel (el reporte dice qué aplicó).

  python marca.py corregir --marca summit-maker "máximo 12 palabras por lámina"
  python marca.py corregir --marca summit-maker "menos texto por lámina y siempre el RIF en la última"
  python marca.py corregir --marca summit-maker --clave colores.acento --valor "#FA5102"
  python marca.py ver --marca summit-maker
  python marca.py lista

Lo que entiende del texto libre (lo demás se guarda como nota y se avisa, nunca se adivina):
  máximo N palabras · menos texto · siempre el/la X en la última · entre N y M láminas · #hex + principal/acento/
  fondo · fuente de titulares/cuerpo <nombre> · prohíbe/nunca uses la palabra «x» · el CTA es «...»
"""

import argparse
import json
import re
import sys

from comun import MARCAS, MARCAS_SEMILLA, ahora, cargar_marca, escribir_json, leer_json, ruta_semilla, slug

CLAVES = {"reglas.max_palabras_lamina": int, "colores.principal": str, "colores.acento": str, "colores.fondo": str,
          "colores.texto_sobre_oscuro": str, "colores.texto_sobre_claro": str, "fuentes.titulares": str,
          "fuentes.cuerpo": str, "cta.texto": str, "cta.palabra": str, "firma": str, "datos.rif": str}


def ruta(marca):
    return MARCAS / f"{slug(marca)}.json"


def cargar(marca):
    return leer_json(ruta(marca), None) or {"marca": slug(marca), "ajustes": {}, "correcciones": [], "aplicado": []}


def _poner(m, clave, valor):
    grupos = clave.split(".")
    d = m["ajustes"]
    for g in grupos[:-1]:
        d = d.setdefault(g, {})
    d[grupos[-1]] = valor
    return f"{clave} = {valor}"


def interpretar(texto, m, efectiva):
    """-> (cambios aplicados a m, notas que no entendió)"""
    t = texto.lower()
    cambios, notas = [], []
    reglas = efectiva.get("reglas") or {}
    n = re.search(r"m[aá]ximo\s+(\d+)\s+palabras", t)
    if n:
        cambios.append(_poner(m, "reglas.max_palabras_lamina", int(n.group(1))))
    elif re.search(r"menos texto|m[aá]s corto|menos palabras", t):
        actual = (m["ajustes"].get("reglas") or {}).get("max_palabras_lamina") or reglas.get("max_palabras_lamina") or 40
        cambios.append(_poner(m, "reglas.max_palabras_lamina", max(6, round(actual * 0.75))))
    for x in re.findall(r"siempre (?:el|la|los|las)?\s*([\wÁÉÍÓÚáéíóúñÑ ]{2,30}?) en la [uú]ltima", texto, re.I):
        dato = x.strip().upper() if len(x.strip()) <= 5 else x.strip()
        lista = list((m["ajustes"].get("reglas") or {}).get("incluir_en_ultima") or reglas.get("incluir_en_ultima") or [])
        if dato not in lista:
            lista.append(dato)
        cambios.append(_poner(m, "reglas.incluir_en_ultima", lista))
    r = re.search(r"entre\s+(\d+)\s+y\s+(\d+)\s+l[aá]minas", t)
    if r:
        cambios.append(_poner(m, "reglas.laminas_recomendadas", [int(r.group(1)), int(r.group(2))]))
    for mm in re.finditer(r"(#[0-9a-f]{6})", t):
        antes = t[max(0, mm.start() - 40):mm.start()]
        for clave, rx in (("colores.acento", r"acento|resalt|destac"), ("colores.fondo", r"fondo"),
                          ("colores.principal", r"principal|base")):
            if re.search(rx, antes):
                cambios.append(_poner(m, clave, mm.group(1).upper()))
                break
    for clave, rx in (("fuentes.titulares", r"(?:fuente|tipograf[ií]a) (?:de|para) (?:los )?t[ií]tul\w*\s+(?:en\s+)?[«\"']?([A-Za-z0-9 \-]+?)[»\"']?(?:[,.;]|$| y )"),
                      ("fuentes.cuerpo", r"(?:fuente|tipograf[ií]a) (?:de|para|del) (?:el )?cuerpo\s+(?:en\s+)?[«\"']?([A-Za-z0-9 \-]+?)[»\"']?(?:[,.;]|$| y )")):
        f = re.search(rx, texto, re.I)
        if f:
            cambios.append(_poner(m, clave, f.group(1).strip()))
    for p in re.findall(r"(?:proh[ií]be|nunca uses|no uses)(?: la palabra)?\s+[«\"']([^»\"']+)[»\"']", texto, re.I):
        lista = list((m["ajustes"].get("prohibidas")) or efectiva.get("prohibidas") or [])
        if p.lower() not in lista:
            lista.append(p.lower())
        cambios.append(_poner(m, "prohibidas", lista))
    c = re.search(r"(?:el )?cta (?:es|ser[aá])\s+[«\"']([^»\"']+)[»\"']", texto, re.I)
    if c:
        cambios.append(_poner(m, "cta.texto", c.group(1).strip()))
    if not cambios:
        notas.append(texto)
    return cambios, notas


def corregir(marca, texto=None, clave=None, valor=None):
    semilla = leer_json(ruta_semilla(marca))
    if semilla is None:
        raise RuntimeError(f"No hay brandbook «{marca}» en {MARCAS_SEMILLA}")
    nombre = semilla.get("marca") or slug(marca)
    m = cargar(nombre)
    efectiva = cargar_marca(nombre)
    if clave:
        if clave not in CLAVES:
            raise RuntimeError(f"clave desconocida {clave}; válidas: {', '.join(CLAVES)}")
        cambios, notas = [_poner(m, clave, CLAVES[clave](valor))], []
        texto = texto or f"{clave} = {valor}"
    else:
        cambios, notas = interpretar(texto, m, efectiva)
    m["correcciones"].append({"fecha": ahora(), "texto": texto, "cambios": cambios, "notas": notas})
    m["aplicado"] = [x for x in m.get("aplicado") or [] if x.split(" = ")[0] not in {c.split(" = ")[0] for c in cambios}]
    m["aplicado"] += cambios
    escribir_json(ruta(nombre), m)
    return cambios, notas


def main():
    ap = argparse.ArgumentParser(description="Memoria de marca de los carruseles")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("corregir")
    c.add_argument("--marca", required=True)
    c.add_argument("texto", nargs="?")
    c.add_argument("--clave")
    c.add_argument("--valor")
    v = sub.add_parser("ver")
    v.add_argument("--marca", required=True)
    sub.add_parser("lista")
    a = ap.parse_args()
    if a.cmd == "corregir":
        if not a.texto and not a.clave:
            sys.exit("Falta el texto de la corrección o --clave/--valor")
        cambios, notas = corregir(a.marca, a.texto, a.clave, a.valor)
        for x in cambios:
            print(f"guardado: {x}")
        for x in notas:
            print(f"AVISO: no entendí «{x}»; quedó como nota en el historial. Usa --clave/--valor para fijarlo.")
        print(f"-> {ruta(a.marca)}")
    elif a.cmd == "ver":
        print(json.dumps(cargar_marca(a.marca), ensure_ascii=False, indent=1))
    else:
        for p in sorted(MARCAS_SEMILLA.glob("*.json")):
            d = leer_json(p) or {}
            from comun import pendientes_marca
            falta = pendientes_marca(d)
            print(f"{p.stem}: {d.get('nombre')} ({d.get('version')})" + (f" FALTAN {len(falta)} datos" if falta else ""))


if __name__ == "__main__":
    main()

"""Genera un carrusel 1080x1350 desde un brief: HTML por lámina con el brandbook -> PNG (Chrome headless) -> QC.

  python carrusel.py --brief C:\\briefs\\c1.json --salida C:\\carruseles\\c1 [--marca summit-maker] [--tipo 1|2|3]
                     [--fotos C:\\fotos\\taller] [--motor codex]

Tipos: 1 = HTML puro · 2 = HTML + imágenes generadas (solo motores sin costo extra; si no hay, se bloquea y se
reporta) · 3 = HTML + fotos propias de una carpeta (recorte y escala sin deformar).
Salida: lamina-NN.png (o lamina-NN.RECHAZADA.png), lamina-NN.html, caption.txt, copy.md, reporte.md, reporte.json,
qc.json, carrusel.json. Código de salida: 0 = listo y pasó el QC · 1 = rechazado o error · 3 = bloqueado (sin motor
de imagen gratis o brandbook incompleto).
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

from comun import ahora, cargar_marca, escribir_json, leer_json, palabras, pendientes_marca
from plantilla import ROLES, html_lamina, preparar_fuentes
from qc import copy_lamina, qc_carpeta, resumen

EXT_FOTO = (".jpg", ".jpeg", ".png", ".webp")
CON_FOTO = {"gancho": "foto-gancho", "punto": "foto", "contraste": "foto", "foto": "foto", "foto-gancho": "foto-gancho"}


def normalizar(brief):
    """Roles por defecto: 1.ª = gancho, la que trae 'accion' = cierre, la que trae 'items' = lista; el resto alterna
    punto / contraste para que no salgan todas iguales."""
    ls = [dict(x) for x in brief.get("laminas") or []]
    if not ls:
        raise RuntimeError("el brief no trae láminas")
    alterna = 0
    for i, l in enumerate(ls):
        if not l.get("rol"):
            if i == 0:
                l["rol"] = "gancho"
            elif l.get("accion"):
                l["rol"] = "cierre"
            elif l.get("items"):
                l["rol"] = "lista"
            else:
                l["rol"] = ("punto", "contraste")[alterna % 2]
                alterna += 1
        if l["rol"] not in ROLES:
            raise RuntimeError(f"lámina {i + 1}: rol «{l['rol']}» no existe ({', '.join(ROLES)})")
        if l["rol"] == "lista" and not l.get("items"):
            raise RuntimeError(f"lámina {i + 1}: una lista necesita 'items'")
        if not (l.get("titulo") or l.get("items") or l.get("accion")):
            raise RuntimeError(f"lámina {i + 1}: sin texto")
    return ls


def _poner_foto(l, origen, salida, carpeta="fotos"):
    destino = Path(salida) / carpeta / Path(origen).name
    destino.parent.mkdir(parents=True, exist_ok=True)
    if Path(origen).resolve() != destino.resolve():
        shutil.copyfile(origen, destino)
    l["_foto_rel"] = f"{carpeta}/{destino.name}"
    l["rol"] = CON_FOTO.get(l["rol"], l["rol"])


def fotos_propias(ls, carpeta, salida):
    """Tipo 3: la lámina que nombra 'foto' la usa; las demás (gancho/punto/contraste) toman las siguientes en orden."""
    carpeta = Path(carpeta or "")
    if not carpeta.is_dir():
        raise RuntimeError(f"tipo 3 sin carpeta de fotos válida: «{carpeta}»")
    todas = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXT_FOTO)
    if not todas:
        raise RuntimeError(f"no hay fotos ({', '.join(EXT_FOTO)}) en {carpeta}")
    usadas = set()
    for l in ls:
        if l.get("foto"):
            p = carpeta / l["foto"]
            if not p.is_file():
                raise RuntimeError(f"la foto «{l['foto']}» no está en {carpeta}")
            _poner_foto(l, p, salida)
            usadas.add(p.name)
    libres = [p for p in todas if p.name not in usadas]
    for l in ls:
        if not l.get("_foto_rel") and l["rol"] in ("gancho", "punto", "contraste") and libres:
            _poner_foto(l, libres.pop(0), salida)
    return [l.get("_foto_rel") for l in ls if l.get("_foto_rel")]


def imagenes_generadas(ls, marca, salida, motor_pedido, avisos):
    """Tipo 2. -> (motor, detalle por imagen). Sin motor gratis: RuntimeError con el reporte de motores."""
    import motores
    rep = motores.detectar()
    motor = motores.elegir(rep["motores"], motor_pedido)
    if not motor:
        raise Bloqueado("no hay ningún motor de imagen gratis o de suscripción ya pagada en este PC; las APIs de pago "
                        "solo se reportan (ningún gasto sin el OK de Leandro)", motores.texto(rep))
    if "stock" in (marca.get("fotos") or "").lower():
        avisos.append(f"el brandbook dice «{marca['fotos']}»: una imagen generada puede leerse como stock; "
                      "confírmalo con Leandro antes de publicar")
    detalle = []
    registro = leer_json(Path(salida) / "imagenes" / "imagenes.json", {}) or {}
    for i, l in enumerate(ls, 1):
        if not l.get("imagen"):
            continue
        prompt = l["imagen"]
        clave = hashlib.sha1(f"{motor}|{prompt}".encode()).hexdigest()[:12]
        destino = Path(salida) / "imagenes" / f"lamina-{i:02d}-{clave}.png"
        if destino.is_file():
            d = {"motor": motor, "reusada": True}
        else:
            d = motores.generar(motor, prompt, destino, marca.get("prohibido_en_imagenes") or [])
        d.update({"lamina": i, "prompt": prompt, "archivo": destino.name})
        registro[destino.name] = d
        detalle.append(d)
        _poner_foto(l, destino, salida, carpeta="imagenes")
    escribir_json(Path(salida) / "imagenes" / "imagenes.json", registro)
    return motor, detalle


class Bloqueado(Exception):
    def __init__(self, motivo, detalle=""):
        super().__init__(motivo)
        self.detalle = detalle


def caption(brief, marca, ls):
    if brief.get("caption"):
        return brief["caption"].strip(), "del brief"
    cta = (marca.get("cta") or {}).get("texto") or next((l["accion"] for l in ls if l.get("accion")), "")
    contexto = brief.get("contexto") or "[PENDIENTE: contexto del pie de foto: lo que añade a las láminas, sin repetirlas]"
    return f"{contexto}\n\n{cta}".strip(), "sugerido (contexto del brief + CTA de la marca)"


def generar(brief, salida, marca_nombre=None, tipo=None, fotos=None, motor=None):
    t0 = time.time()
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    for viejo in salida.glob("lamina-*.png"):
        viejo.unlink()
    res = {"id": brief.get("id") or salida.name, "inicio": ahora(), "salida": str(salida), "avisos": []}
    try:
        marca = cargar_marca(marca_nombre or brief.get("marca") or "summit-maker")
        res["marca"] = marca["nombre"]
        res["marca_aplicada"] = marca.get("aplicado") or []
        falta = pendientes_marca(marca)
        if falta:
            raise Bloqueado(f"brandbook de {marca['nombre']} incompleto: faltan {', '.join(falta)}. No se inventan colores "
                            f"ni fuentes: complétalo en {marca['_ruta']} o con marca.py corregir --clave")
        tipo = int(tipo or brief.get("tipo") or 1)
        res["tipo"] = tipo
        ls = normalizar(brief)
        if tipo == 3:
            res["fotos"] = fotos_propias(ls, fotos or brief.get("fotos"), salida)
        elif tipo == 2:
            res["motor_imagen"], res["imagenes"] = imagenes_generadas(ls, marca, salida, motor or brief.get("motor"),
                                                                      res["avisos"])
        datos = marca.get("datos") or {}
        pie = []
        for dato in (marca.get("reglas") or {}).get("incluir_en_ultima") or []:
            v = str(datos.get(dato.lower(), ""))
            if v and "PENDIENTE" not in v:
                pie.append(f"{dato}: {v}")
        if pie:
            ls[-1]["_pie"] = "   ".join(pie)
        fuentes, av = preparar_fuentes(marca, salida)
        res["avisos"] += av
        orden = 0
        for n, l in enumerate(ls, 1):
            if l["rol"] in ("punto", "foto"):
                orden += 1
            (salida / f"lamina-{n:02d}.html").write_text(html_lamina(l, marca, fuentes, n, len(ls), orden),
                                                         encoding="utf-8")
        publico = {k: v for k, v in marca.items() if not k.startswith("_")}
        escribir_json(salida / "carrusel.json", {"brief": brief, "marca": publico, "laminas": ls})
        (salida / "copy.md").write_text("\n\n".join(f"## Lámina {n} ({l['rol']}, {len(palabras(copy_lamina(l)))} "
                                                     f"palabras)\n\n{copy_lamina(l)}" for n, l in enumerate(ls, 1)),
                                        encoding="utf-8")
        cap, origen = caption(brief, marca, ls)
        (salida / "caption.txt").write_text(cap, encoding="utf-8")
        res["caption"] = {"texto": cap, "origen": origen}
        q = qc_carpeta(salida)
        res["qc"] = q
        res["avisos"] += q["carrusel"]["avisos"] + [f"lámina {r['lamina']}: {a}" for r in q["laminas"] for a in r["avisos"]]
        res["laminas"] = [str(salida / r["png"]) for r in q["laminas"]]
        res["estado"] = "listo" if q["ok"] else "rechazado por QC"
    except Bloqueado as e:
        res["estado"] = "bloqueado"
        res["error"] = str(e)
        res["detalle"] = e.detalle
    except Exception as e:  # noqa: BLE001 — un carrusel que falla no tumba un lote; el reporte lo dice
        res["estado"] = "error"
        res["error"] = f"{type(e).__name__}: {e}"
    res["segundos"] = round(time.time() - t0, 1)
    escribir_json(salida / "reporte.json", res)
    (salida / "reporte.md").write_text(reporte_md(res), encoding="utf-8")
    return res


def reporte_md(r):
    q = r.get("qc") or {}
    l = [f"# Carrusel {r['id']}: {r['estado'].upper()}", "",
         f"- Marca: {r.get('marca', '?')} · tipo {r.get('tipo', '?')} · {r['segundos']} s · {r['inicio']}"]
    if q:
        l.append(f"- Láminas OK: {q['laminas_ok']}/{q['total']}")
    if r.get("motor_imagen"):
        l.append(f"- Motor de imagen: {r['motor_imagen']} ({len(r.get('imagenes') or [])} imágenes; "
                 + "; ".join(f"lámina {d['lamina']}: {d.get('segundos', 'reusada')} s, {d.get('costo', '')}"
                             for d in r.get("imagenes") or []) + ")")
    if r.get("marca_aplicada"):
        l.append("- Correcciones de marca aplicadas: " + "; ".join(r["marca_aplicada"]))
    if r.get("error"):
        l += ["", f"**{r['error']}**"]
    if r.get("detalle"):
        l += ["", "```", r["detalle"], "```"]
    if q:
        l += ["", "## QC", "", "```", resumen(q), "```", ""]
        for x in q["laminas"]:
            l.append(f"- Lámina {x['lamina']:02d} ({x['rol']}): {'OK' if x['ok'] else 'RECHAZADA'} · "
                     + ", ".join(x["checks"]) + (" · " + " | ".join(x["rechazos"]) if x["rechazos"] else ""))
        l.append("- Carrusel: " + ", ".join(q["carrusel"]["checks"]))
    if r.get("avisos"):
        l += ["", "## Advertencias", ""] + [f"- {a}" for a in r["avisos"]]
    if r.get("caption"):
        l += ["", f"## Caption ({r['caption']['origen']})", "", r["caption"]["texto"]]
    return "\n".join(l) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Carrusel 1080x1350 desde un brief")
    ap.add_argument("--brief", required=True, help="ruta a un brief .json")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--marca")
    ap.add_argument("--tipo", type=int, choices=(1, 2, 3))
    ap.add_argument("--fotos")
    ap.add_argument("--motor", help="motor de imagen para el tipo 2 (codex, a1111); los de pago no se aceptan")
    a = ap.parse_args()
    brief = json.loads(Path(a.brief).read_text(encoding="utf-8"))
    r = generar(brief, a.salida, a.marca, a.tipo, a.fotos, a.motor)
    print(reporte_md(r))
    sys.exit({"listo": 0, "bloqueado": 3}.get(r["estado"], 1))


if __name__ == "__main__":
    main()

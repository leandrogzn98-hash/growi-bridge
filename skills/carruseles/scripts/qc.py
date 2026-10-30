"""QC automático de un carrusel: mira las láminas renderizadas de verdad y rechaza con diagnóstico.

  python qc.py <carpeta_del_carrusel>        (vuelve a renderizar cada lamina-NN.html y la revisa)

Por lámina: dimensiones exactas 1080x1350, fuentes del brandbook cargadas, texto sin cortes ni desbordes (caja,
contenedor, lienzo y zona segura), contraste texto/fondo medido en píxeles (captura con texto contra captura sin
texto, así vale también sobre fotos), sin gradientes, fotos sin deformar, palabras por lámina y palabras prohibidas.
Por carrusel: una sola acción, lo que la marca pide en la última lámina, y avisos (cifras sin fuente, anti-olor-a-IA,
anatomía). Una lámina rechazada se renombra a lamina-NN.RECHAZADA.png. Código de salida: 0 = todo OK, 1 = rechazos.
"""

import importlib.util
import os
import re
import sys
from pathlib import Path

from PIL import Image

from comun import ALTO, ANCHO, SKILL, contraste, escribir_json, leer_json, lum_rgb, palabras

ZONA_SEGURA = 40  # px mínimos entre cualquier texto y el borde del lienzo
CONTRASTE_MIN, CONTRASTE_MIN_GRANDE, TAM_GRANDE = 4.5, 3.0, 60  # WCAG AA; «grande» = 60 px o más a 1080
TAM_MIN_LEGIBLE = 24

# Pedidos al público (acciones de redes). Contar instrucciones del tema («escribe tu prompt») sería un falso positivo.
ACCIONES = {
    "comentar": r"\bcomenta(?:r|me|nos)?\b", "guardar": r"\bgu[aá]rda(?:lo|la|te)?\s+(?:este|esta|el|la)\b",
    "compartir": r"\bcomp[aá]rte(?:lo|la)?\b", "seguir": r"\bs[ií]gue(?:me|nos)\b|\bsigue a\b",
    "etiquetar": r"\betiqueta a\b", "link en bio": r"\blink en (?:la )?bio\b", "clic": r"\bhaz clic\b",
    "registrarse": r"\breg[ií]strate\b|\binscr[ií]bete\b", "escribir por DM": r"\bescr[ií]be(?:me|nos)\b|\bDM\b",
    "me gusta": r"\bdale (?:like|me gusta)\b", "descargar": r"\bdesc[aá]rga(?:lo|la)?\b",
}


def _rgb_css(s):
    n = [float(x) for x in re.findall(r"[\d.]+", s or "")[:3]]
    return tuple(int(v) for v in n) if len(n) == 3 else (0, 0, 0)


def copy_lamina(l):
    partes = [l.get("titulo"), l.get("texto"), l.get("accion")] + list(l.get("items") or [])
    return " ".join(p for p in partes if p)


def _region(img, cajas):
    pix = []
    for x, y, w, h in cajas:
        x0, y0, x1, y1 = max(0, x), max(0, y), min(img.width, x + w), min(img.height, y + h)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        r = img.crop((x0, y0, x1, y1))
        f = max(1.0, max(r.width, r.height) / 160)
        r = r.resize((max(1, int(r.width / f)), max(1, int(r.height / f))), Image.NEAREST)
        pix.extend(r.getdata())
    return pix


def contraste_elemento(e, img, sin):
    """-> (contraste peor (percentil 2), fracción de píxeles que cambian al pintar el texto)"""
    cajas = e.get("lineas") or [e["caja"]]
    fondo = _region(sin, cajas)
    if not fondo:
        return None, 0.0
    lt = lum_rgb(*_rgb_css(e["color"]))
    cs = sorted(contraste(lt, lum_rgb(*p[:3])) for p in fondo)
    peor = cs[int(len(cs) * 0.02)]
    con, sinp = _region(img, cajas), fondo
    cambian = sum(1 for a, b in zip(con, sinp) if max(abs(a[i] - b[i]) for i in range(3)) > 30)
    return round(peor, 2), cambian / max(1, len(sinp))


def revisar_lamina(n, l, png, sin_png, med, marca):
    rech, avisos, checks = [], [], []
    img, sin = Image.open(png).convert("RGB"), Image.open(sin_png).convert("RGB")
    if img.size != (ANCHO, ALTO) or (med.get("ancho"), med.get("alto")) != (ANCHO, ALTO):
        rech.append(f"dimensiones {img.size[0]}x{img.size[1]} (viewport {med.get('ancho')}x{med.get('alto')}); "
                    f"tienen que ser {ANCHO}x{ALTO}")
    else:
        checks.append("1080x1350")
    f = med.get("fuentes") or {}
    if not (f.get("titulares") and f.get("cuerpo")):
        rech.append(f"fuente del brandbook sin cargar ({', '.join(f.get('estado') or []) or 'ninguna'}): se vería "
                    "con una sustituta")
    else:
        checks.append("fuentes cargadas")
    peor_c = None
    for e in med.get("elementos") or []:
        txt = e.get("texto") or ""
        if not txt:
            continue
        cita = f"«{txt[:48]}{'…' if len(txt) > 48 else ''}»"
        x, y, w, h = e["caja"]
        if not e.get("visible"):
            rech.append(f"texto invisible: {cita}")
            continue
        es_caja = "caja" in e.get("clase", "") or "accion" in e.get("clase", "")
        if es_caja and e["clientH"] > 0 and e["scrollH"] > e["clientH"] + 1:
            aj = e.get("ajuste") or [0, 0, 0]
            rech.append(f"texto cortado: {cita} necesita {e['scrollH']} px de alto y su caja tiene {e['clientH']} px "
                        f"(letra ya en el mínimo legible, {aj[2]} px): recorta el copy de esta lámina")
        if es_caja and e["clientW"] > 0 and e["scrollW"] > e["clientW"] + 1:
            rech.append(f"texto desbordado a lo ancho: {cita} mide {e['scrollW']} px y su caja {e['clientW']} px "
                        "(una palabra no cabe en la línea)")
        for r in e.get("recortes") or []:
            rech.append(f"texto recortado por su contenedor ({r}): {cita}")
        if x < 0 or y < 0 or x + w > ANCHO or y + h > ALTO:
            rech.append(f"texto fuera de pantalla: {cita} en x={x}..{x + w}, y={y}..{y + h}")
        elif min(x, y, ANCHO - x - w, ALTO - y - h) < ZONA_SEGURA:
            rech.append(f"texto fuera de la zona segura ({ZONA_SEGURA} px del borde): {cita}")
        if e.get("tam", 99) < TAM_MIN_LEGIBLE:
            rech.append(f"letra de {e['tam']:.0f} px (mínimo {TAM_MIN_LEGIBLE}): {cita}")
        c, cambio = contraste_elemento(e, img, sin)
        if c is not None:
            minimo = CONTRASTE_MIN_GRANDE if e.get("tam", 0) >= TAM_GRANDE else CONTRASTE_MIN
            if c < minimo:
                rech.append(f"contraste {c}:1 (mínimo {minimo}:1) en {cita}")
            if cambio < 0.01:
                rech.append(f"el texto no se ve en la captura ({cambio:.1%} de píxeles cambian): {cita}")
            peor_c = c if peor_c is None else min(peor_c, c)
    if peor_c is not None:
        checks.append(f"contraste mínimo {peor_c}:1")
    if not any(r.startswith(("texto cortado", "texto desbordado", "texto recortado", "texto fuera")) for r in rech):
        checks.append("texto dentro de pantalla y sin cortes")
    if med.get("gradientes"):
        rech.append(f"gradiente en {', '.join(med['gradientes'][:3])}: el brandbook y la guía anti-olor-a-IA lo prohíben")
    for im in med.get("imagenes") or []:
        if not im.get("cargada"):
            rech.append(f"la foto no cargó: {im.get('src')}")
            continue
        (nw, nh), (_, _, cw, ch) = im["natural"], im["caja"]
        sx, sy = cw / nw, ch / nh
        if im.get("objectFit") not in ("cover", "contain") and abs(sx - sy) / max(sx, sy) > 0.01:
            rech.append(f"foto deformada: escala {sx:.3f} x {sy:.3f} ({im.get('src')})")
        else:
            checks.append(f"foto sin deformar ({im.get('objectFit')}, escala uniforme {max(sx, sy):.2f})")
        if max(sx, sy) > 1.6:
            avisos.append(f"foto ampliada ×{max(sx, sy):.1f}: puede verse pixelada ({im.get('src')})")
    copy = copy_lamina(l)
    maxp = (marca.get("reglas") or {}).get("max_palabras_lamina")
    n_pal = len(palabras(copy))
    if maxp and n_pal > maxp:
        origen = next((c["texto"] for c in reversed(marca.get("correcciones") or [])
                       if "max_palabras_lamina" in " ".join(c.get("cambios") or [])), "brandbook")
        rech.append(f"{n_pal} palabras en la lámina; máximo {maxp} (regla de marca: {origen})")
    else:
        checks.append(f"{n_pal} palabras" + (f" (máx. {maxp})" if maxp else ""))
    bajo = copy.lower()
    for p in marca.get("prohibidas") or []:
        if re.search(rf"(?<!\w){re.escape(p.lower())}(?!\w)", bajo):
            rech.append(f"palabra prohibida por el brandbook: «{p}»")
    return {"lamina": n, "rol": l.get("rol"), "ok": not rech, "rechazos": rech, "avisos": avisos, "checks": checks,
            "palabras": n_pal}


# ---------------------------------------------------------------- nivel carrusel

def _auditor():
    """Listas de la guía anti-olor-a-IA de Leandro (skill documentos-humanos), si está instalada."""
    for p in [os.environ.get("GROWI_DOC_HUMANOS") or "", SKILL.parent / "documentos-humanos" / "bin" / "auditar.py",
              Path.home() / "growi-bridge" / "skills" / "documentos-humanos" / "bin" / "auditar.py"]:
        if p and Path(p).is_file():
            spec = importlib.util.spec_from_file_location("auditar_dh", p)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                return mod, str(p)
            except Exception:  # noqa: BLE001 — si el auditor no carga, seguimos sin él y se avisa
                return None, str(p)
    return None, None


def revisar_carrusel(laminas, marca, brief, textos_render):
    rech, avisos, checks = [], [], []
    reglas = marca.get("reglas") or {}
    if reglas.get("una_sola_accion", True):
        hallados = {}
        for i, l in enumerate(laminas, 1):
            for nombre, rx in ACCIONES.items():
                if re.search(rx, copy_lamina(l), re.I):
                    hallados.setdefault(nombre, []).append(i)
        n_caja = sum(1 for l in laminas if l.get("accion"))
        if len(hallados) > 1:
            rech.append("más de una acción en la pieza: " + "; ".join(f"{k} (lámina {', '.join(map(str, v))})"
                                                                       for k, v in hallados.items()) +
                        ". Deja solo una (la del brandbook: " + ((marca.get("cta") or {}).get("texto") or "?") + ")")
        elif n_caja != 1:
            rech.append(f"la pieza tiene {n_caja} láminas con acción: tiene que haber exactamente una")
        else:
            checks.append("una sola acción: " + (next(iter(hallados)) if hallados else "la de la lámina de cierre"))
    for dato in reglas.get("incluir_en_ultima") or []:
        valor = str((marca.get("datos") or {}).get(dato.lower(), ""))
        if not valor or "PENDIENTE" in valor:
            rech.append(f"la marca pide «{dato}» en la última lámina y el dato está [PENDIENTE: {dato}]: complétalo en "
                        "el brandbook (no se inventa)")
        elif valor not in (textos_render[-1] if textos_render else ""):
            rech.append(f"la marca pide «{dato}: {valor}» en la última lámina y no aparece")
        else:
            checks.append(f"{dato} en la última lámina")
    rec = reglas.get("laminas_recomendadas")
    if rec and not (min(rec) <= len(laminas) <= max(rec)):
        avisos.append(f"{len(laminas)} láminas; la anatomía de la marca recomienda {min(rec)}-{max(rec)}")
    if reglas.get("ultima_es_checklist") and not any(l.get("rol") == "lista" for l in laminas[-2:]):
        avisos.append("la anatomía de la marca pide cerrar con un checklist guardable (rol «lista») en las últimas láminas")
    fuentes = {str(k) for k in (brief.get("cifras_con_fuente") or {})}
    for i, l in enumerate(laminas, 1):
        for c in re.findall(r"\$\s?\d[\d.,]*|\d[\d.,]*\s?%|\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{3,}\b", copy_lamina(l)):
            if c.strip() not in fuentes:
                avisos.append(f"lámina {i}: cifra «{c.strip()}» sin fuente declarada (cifras_con_fuente del brief): "
                              "confírmala o quítala; no se inventan cifras")
        if re.search(r"[«\"].{12,}[»\"]\s*[—–-]\s*[A-ZÁÉÍÓÚ]", copy_lamina(l)) and not brief.get("testimonios_con_fuente"):
            avisos.append(f"lámina {i}: parece un testimonio citado: solo con fuente real (testimonios_con_fuente)")
    mod, ruta = _auditor()
    todo = "\n".join(copy_lamina(l) for l in laminas).lower()
    if mod:
        for w in getattr(mod, "BANEADAS", []) + getattr(mod, "EXPRESIONES", []):
            if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", todo):
                avisos.append(f"olor a IA (guía documentos-humanos): «{w}»")
        for w, sug in (getattr(mod, "JERGA", {}) or {}).items():
            if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", todo):
                avisos.append(f"jerga (guía documentos-humanos): «{w}» → «{sug}»")
        checks.append("guía anti-olor-a-IA aplicada")
    else:
        avisos.append("no encontré la skill documentos-humanos: el pase anti-olor-a-IA quedó solo con las reglas de la marca")
    return {"ok": not rech, "rechazos": rech, "avisos": avisos, "checks": checks}


def qc_carpeta(carpeta, rerender=True):
    from render import render
    carpeta = Path(carpeta)
    datos = leer_json(carpeta / "carrusel.json")
    if not datos:
        raise RuntimeError(f"{carpeta} no tiene carrusel.json")
    laminas, marca, brief = datos["laminas"], datos["marca"], datos["brief"]
    res, textos = [], []
    for n, l in enumerate(laminas, 1):
        base = carpeta / f"lamina-{n:02d}"
        Path(f"{base}.RECHAZADA.png").unlink(missing_ok=True)
        if rerender or not Path(f"{base}.png").is_file():
            png, sin, med = render(f"{base}.html")
        else:
            png, sin, med = f"{base}.png", f"{base}.sin-texto.png", leer_json(f"{base}.medidas.json")
        r = revisar_lamina(n, l, png, sin, med, marca)
        textos.append(" ".join(e.get("texto") or "" for e in med.get("elementos") or []))
        if not r["ok"]:
            Path(png).replace(f"{base}.RECHAZADA.png")
            r["png"] = f"lamina-{n:02d}.RECHAZADA.png"
        else:
            r["png"] = f"lamina-{n:02d}.png"
        Path(sin).unlink(missing_ok=True)
        res.append(r)
    pieza = revisar_carrusel(laminas, marca, brief, textos)
    qc = {"ok": pieza["ok"] and all(r["ok"] for r in res), "laminas": res, "carrusel": pieza,
          "laminas_ok": sum(1 for r in res if r["ok"]), "total": len(res)}
    escribir_json(carpeta / "qc.json", qc)
    return qc


def resumen(qc):
    lineas = [f"QC: {'OK' if qc['ok'] else 'RECHAZADO'} ({qc['laminas_ok']}/{qc['total']} láminas OK)"]
    for r in qc["laminas"]:
        if not r["ok"]:
            lineas += [f"  lámina {r['lamina']:02d} RECHAZADA:"] + [f"    - {x}" for x in r["rechazos"]]
    for x in qc["carrusel"]["rechazos"]:
        lineas.append(f"  carrusel RECHAZADO: {x}")
    return "\n".join(lineas)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    q = qc_carpeta(sys.argv[1])
    print(resumen(q))
    sys.exit(0 if q["ok"] else 1)

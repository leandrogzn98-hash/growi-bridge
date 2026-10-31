"""Fase A de arte (t-oficina-arte-base-050, spec 9 de 18): paleta, esqueleto comun 32x48 por capas,
Growi (idle, escribir, celebrar, dormir) y la «Z» compartida, con su JSON de metadatos.

AVISO DE LICENCIA (§7.4 y PALETA-Y-SKINS §8): estos pixeles los coloca un script escrito por una IA.
Son un BORRADOR para validar el pipeline (formato, capas, hojas, JSON, render NEAREST), NO arte final:
la regla es «nunca IA sin retoque humano pixel a pixel». Cada JSON lo dice en `estado_arte`.

  python generar_base.py            # escribe en assets/office/
"""
import colorsys
import json
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parent.parent / "assets" / "office"
W, H = 32, 48
ANCLA = (16, 47)

# ---- paleta: solo hex con fuente escrita (spec, PALETA-Y-SKINS §15, mascota). §1 (los 24) NO esta en el PC.
BASES = [
    ("crema", "#E8D8C0", "mascota growi.png (color dominante del peluche, muestreado)"),
    ("crema_palido", "#FFF6DC", "spec 9 §8: blusa de Runa"),
    ("piel", "#F2C9A0", "specs 050"),
    ("negro_sueter", "#232323", "specs 050 (pelo de Runa); el sueter negro del gerente es identidad de marca"),
    ("negro_cautela", "#1A1A1C", "PALETA-Y-SKINS §15 (tinte negro)"),
    ("jeans", "#33598C", "spec 9 §8: jeans de Runa"),
    ("naranja_claude", "#D97757", "spec 9 §1 (marca, de memoria: no verificado, duda 24)"),
    ("verde_codex", "#00A67E", "spec 9 §1 (marca, de memoria: no verificado, duda 24)"),
    ("azul_gemini", "#4285F4", "spec 9 §1 (marca, de memoria: no verificado, duda 24)"),
    ("azul_gemi_corbata", "#2B5CB8", "spec 9 §5: corbata de Gemi"),
    ("ambar", "#F5A623", "spec 9: corbata del gerente y pin de Runa"),
    ("rubor", "#F2A0A8", "spec 9 §5: rubor de 1-2 px"),
    ("azul_noche", "#052048", "specs 050 (PALETA-Y-SKINS §2)"),
    ("gris_ribete", "#9AA0A6", "PALETA-Y-SKINS §15 (ribete)"),
]
FALTAN = ("morado Local", "azul Summit", "rosa frambuesa del depto Diseno (#C2185B solo propuesto)",
          "y el resto hasta 24: la lista de PALETA-Y-SKINS §1 no esta en este PC")


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _tonos(h):
    """oscuro / base / claro: misma tinta, valor -28 % y mezcla 35 % hacia el blanco (sombra dura de 1 tono)."""
    r, g, b = (v / 255 for v in _hex(h))
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    osc = colorsys.hsv_to_rgb(hh, min(1, ss * 1.1), vv * 0.72)
    cla = tuple(c + (1 - c) * 0.35 for c in (r, g, b))
    f = lambda c: "#%02X%02X%02X" % tuple(round(x * 255) for x in c)  # noqa: E731
    return f(osc), h.upper(), f(cla)


PAL = {n: dict(zip(("oscuro", "base", "claro"), _tonos(h)), fuente=src) for n, h, src in BASES}


def col(nombre, tono="base"):
    return _hex(PAL[nombre][tono]) + (255,)


def escribir_paleta():
    SALIDA.mkdir(parents=True, exist_ok=True)
    pal = {"nombre": "Oficina Growi (parcial)", "_estado": "PARCIAL: 14 de 24 colores base con fuente escrita; "
           "PALETA-Y-SKINS.md §1 no esta en este PC. Faltan: " + "; ".join(FALTAN), "colores": PAL}
    (SALIDA / "paleta.json").write_text(json.dumps(pal, ensure_ascii=False, indent=1), encoding="utf-8")
    # GIMP palette (.gpl): Pixelorama la importa (Paletas -> Importar)
    lineas = ["GIMP Palette", "Name: Oficina Growi (parcial)", "Columns: 3", "#"]
    for n, d in PAL.items():
        for t in ("oscuro", "base", "claro"):
            r, g, b = _hex(d[t])
            lineas.append(f"{r:3d} {g:3d} {b:3d}\t{n}_{t}")
    (SALIDA / "paleta.gpl").write_text("\n".join(lineas) + "\n", encoding="utf-8")



# ---- dibujo por capas (cada capa = una imagen RGBA 32x48)
def capa():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def rect(im, x0, y0, x1, y1, c):
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            im.putpixel((x, y), c)


def elipse(im, cx, cy, rx, ry, relleno, borde):
    for y in range(H):
        for x in range(W):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1.0:
                im.putpixel((x, y), relleno)
    for y in range(H):  # contorno de 1 px con el tono oscuro (no negro puro)
        for x in range(W):
            if im.getpixel((x, y)) == relleno:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < W and 0 <= ny < H) or im.getpixel((nx, ny))[3] == 0:
                        im.putpixel((x, y), borde)
                        break


def esqueleto(dy=0, encogido=0, ladeo=0):
    """Esqueleto comun chibi: cabeza ~22 px (y 3-25), cuerpo ~20 px, piernas; ancla abajo al centro.
    Devuelve las capas en blanco/gris neutro: cada personaje las recolorea (paper doll, spec 10)."""
    cuerpo = capa()
    rect(cuerpo, 9, 26 + dy + encogido, 22, 39 + dy, (200, 200, 200, 255))  # torso
    rect(cuerpo, 11, 40 + dy, 14, 45, (170, 170, 170, 255))  # pierna izq
    rect(cuerpo, 17, 40 + dy, 20, 45, (170, 170, 170, 255))  # pierna der
    rect(cuerpo, 10, 46, 14, 47, (120, 120, 120, 255))  # zapatos
    rect(cuerpo, 17, 46, 21, 47, (120, 120, 120, 255))
    cara = capa()
    elipse(cara, 16 + ladeo, 14 + dy + encogido, 10.5, 10.5, (230, 230, 230, 255), (150, 150, 150, 255))
    return {"cuerpo_ropa": cuerpo, "cara": cara, "pelo": capa(), "accesorio": capa(), "efectos": capa()}


def growi(pose, f):
    """Un frame de Growi. pose: idle | escribir | celebrar | dormir; f = numero de frame."""
    dy, encogido, ladeo, brazos = 0, 0, 0, "abajo"
    if pose == "idle":
        dy = 1 if f in (1, 2) else 0
    elif pose == "escribir":
        brazos = "teclear_a" if f % 2 == 0 else "teclear_b"
    elif pose == "celebrar":
        dy = (0, -2, -3, -1)[f]
        brazos = "arriba"
    elif pose == "dormir":
        encogido, ladeo, dy = 3, 2, (1 if f == 1 else 0)
    L = esqueleto(dy, encogido, ladeo)
    # cuerpo: sueter negro de cuello alto (excepcion de marca: contorno negro) + jeans
    cu = capa()
    top = 26 + dy + encogido
    rect(cu, 9, top, 22, 39 + dy, col("negro_sueter"))
    rect(cu, 13, top - 1, 19, top, col("negro_sueter", "claro"))  # cuello alto
    rect(cu, 9, top, 9, 39 + dy, col("negro_sueter", "claro"))  # luz desde arriba-izquierda
    rect(cu, 11, 40 + dy, 14, 45, col("jeans"))
    rect(cu, 17, 40 + dy, 20, 45, col("jeans"))
    rect(cu, 14, 40 + dy, 14, 45, col("jeans", "oscuro"))
    rect(cu, 20, 40 + dy, 20, 45, col("jeans", "oscuro"))
    rect(cu, 10, 46, 14, 47, col("negro_cautela"))
    rect(cu, 17, 46, 21, 47, col("negro_cautela"))
    # brazos (sueter)
    if brazos == "abajo":
        rect(cu, 7, top + 2, 8, top + 10, col("negro_sueter"))
        rect(cu, 23, top + 2, 24, top + 10, col("negro_sueter"))
    elif brazos.startswith("teclear"):
        a = 1 if brazos == "teclear_a" else 0
        rect(cu, 7, top + 2, 8, top + 7 + a, col("negro_sueter"))
        rect(cu, 23, top + 2, 24, top + 8 - a, col("negro_sueter"))
    elif brazos == "arriba":
        rect(cu, 6, top - 6, 7, top + 2, col("negro_sueter"))
        rect(cu, 24, top - 6, 25, top + 2, col("negro_sueter"))
    L["cuerpo_ropa"] = cu
    # cara: peluche crema redondo con capucha difusa (orejitas de la capucha), sin nariz
    ca = capa()
    cx, cy = 16 + ladeo, 14 + dy + encogido
    elipse(ca, cx, cy, 10.5, 10.5, col("crema"), col("crema", "oscuro"))
    for ox in (-7, 6):  # bultos de la capucha
        rect(ca, cx + ox, cy - 11, cx + ox + 1, cy - 9, col("crema", "oscuro"))
    rect(ca, cx - 6, cy - 6, cx - 4, cy - 5, col("crema", "claro"))  # brillo arriba-izquierda
    if pose == "dormir" or (pose == "idle" and f == 3):
        for ex in (cx - 5, cx + 2):  # ojos cerrados: dos rayitas
            rect(ca, ex, cy + 1, ex + 2, cy + 1, col("negro_cautela"))
    else:
        for ex in (cx - 5, cx + 3):  # ojos negros ovalados grandes con 1 px de brillo
            rect(ca, ex, cy - 1, ex + 1, cy + 2, col("negro_cautela"))
            ca.putpixel((ex, cy - 1), col("crema_palido"))
    rect(ca, cx - 8, cy + 4, cx - 7, cy + 4, col("rubor"))  # rubor 2 px
    rect(ca, cx + 7, cy + 4, cx + 8, cy + 4, col("rubor"))
    if pose != "dormir":
        rect(ca, cx - 1, cy + 5, cx + 1, cy + 5, col("crema", "oscuro"))  # sonrisa pequena
        if pose == "celebrar":
            ca.putpixel((cx - 2, cy + 4), col("crema", "oscuro"))
            ca.putpixel((cx + 2, cy + 4), col("crema", "oscuro"))
    L["cara"] = ca
    # accesorio: corbata ambar + telefono en la mano (el telefono es suyo: llamar = orquestador)
    ac = capa()
    rect(ac, 15, top + 1, 16, top + 7, col("ambar"))
    ac.putpixel((16, top + 1), col("ambar", "claro"))
    rect(ac, 15, top + 7, 16, top + 7, col("ambar", "oscuro"))
    if brazos == "abajo":
        rect(ac, 24, top + 8, 26, top + 12, col("negro_cautela", "claro"))
        ac.putpixel((25, top + 9), col("gris_ribete"))
    elif brazos == "arriba":
        rect(ac, 24, top - 9, 26, top - 5, col("negro_cautela", "claro"))
    L["accesorio"] = ac
    return L


def componer(capas):
    out = capa()
    for k in ("cuerpo_ropa", "cara", "pelo", "accesorio", "efectos"):
        out.alpha_composite(capas[k])
    return out


ANIMS = [("idle", 4, 8, True), ("escribir", 4, 8, True), ("celebrar", 4, 8, False), ("dormir", 2, 2, True)]


def hoja_growi():
    hoja = Image.new("RGBA", (W * 4, H * len(ANIMS)), (0, 0, 0, 0))
    capas_hoja = {k: Image.new("RGBA", hoja.size, (0, 0, 0, 0)) for k in ("cuerpo_ropa", "cara", "pelo", "accesorio",
                                                                          "efectos")}
    for fila, (nombre, n, _fps, _b) in enumerate(ANIMS):
        for f in range(n):
            L = growi(nombre, f)
            hoja.alpha_composite(componer(L), (f * W, fila * H))
            for k, im in L.items():
                capas_hoja[k].alpha_composite(im, (f * W, fila * H))
    d = SALIDA / "personajes"
    (d / "capas").mkdir(parents=True, exist_ok=True)
    hoja.save(d / "growi.png")
    for k, im in capas_hoja.items():
        im.save(d / "capas" / f"growi_{k}.png")
    meta = {"personaje": "growi", "formato": "hoja por personaje, filas = animaciones",
            "frame": {"w": W, "h": H}, "ancla": list(ANCLA), "filtro": "nearest",
            "animaciones": [{"nombre": nm, "fila": i, "frames": n, "fps": fps, "bucle": b}
                            for i, (nm, n, fps, b) in enumerate(ANIMS)],
            "capas": ["cuerpo_ropa", "cara", "pelo", "accesorio", "efectos"],
            "capas_png": {k: f"capas/growi_{k}.png" for k in capas_hoja},
            "efecto_compartido_dormir": "../comun/z.png",
            "paleta": "../paleta.json",
            "licencia": "© Leandro / HAYAI (a formalizar). Arte original de Bridge; sin assets de terceros.",
            "estado_arte": "BORRADOR generado por script (IA): valida el pipeline; requiere retoque humano pixel a "
                           "pixel en Pixelorama antes de usarse como arte final (regla §7.4).",
            "descripcion": "Peluche crema redondo, capucha difusa, sueter negro de cuello alto, jeans azules, ojos "
                           "negros ovalados grandes, sonrisa pequena, rubor rosa, sin nariz, corbata ambar, telefono."}
    (d / "growi.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return hoja


def z_compartida():
    """La «Z» flotante: UN sprite 8x8 para todos los dormidos. El motor la mueve hacia arriba y la desvanece."""
    z = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    c, o = col("gris_ribete"), col("gris_ribete", "oscuro")
    for x in range(1, 7):
        z.putpixel((x, 1), c)
        z.putpixel((x, 6), c)
    for i, x in enumerate(range(6, 0, -1)):
        if 1 < i + 1 < 6:
            z.putpixel((x, i + 1), c)
    for x in range(1, 7):
        z.putpixel((x, 7), o)
    d = SALIDA / "comun"
    d.mkdir(parents=True, exist_ok=True)
    z.save(d / "z.png")
    (d / "z.json").write_text(json.dumps({"efecto": "z_dormir", "frame": {"w": 8, "h": 8}, "compartido": True,
                                          "movimiento": "sube 18 px y se desvanece en 3 s; la mueve el motor",
                                          "sonido": None, "estado_arte": "BORRADOR (script)"}, ensure_ascii=False,
                                         indent=1), encoding="utf-8")


def esqueleto_png():
    d = SALIDA / "esqueleto"
    d.mkdir(parents=True, exist_ok=True)
    L = esqueleto()
    for k, im in L.items():
        im.save(d / f"esqueleto_{k}.png")
    componer(L).save(d / "esqueleto.png")
    (d / "esqueleto.json").write_text(json.dumps(
        {"frame": {"w": W, "h": H}, "ancla": list(ANCLA), "cabeza_px": 22, "cuerpo_px": 20, "proporcion": "chibi",
         "capas": list(L), "uso": "base comun de los 14 personajes + Runa: cada skin recolorea capas (spec 10)",
         "estado_arte": "BORRADOR (script)"}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    escribir_paleta()
    esqueleto_png()
    hoja_growi()
    z_compartida()
    print(f"escrito en {SALIDA}")

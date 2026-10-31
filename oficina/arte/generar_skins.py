"""Capas de plantilla del paper doll y las skins de los 4 lideres + Runa (t-oficina-skins-050).

AVISO DE LICENCIA: pixeles colocados por un script escrito por una IA = BORRADOR para validar el
sistema (capas, recoloreado, skin.json, validador). Arte final: retoque humano en Pixelorama.

  python generar_skins.py      # escribe assets/office/characters/ y assets/office/palettes/
"""
import json
from pathlib import Path

from PIL import Image

import paperdoll as PD

AQUI = Path(__file__).resolve().parent
ASSETS = AQUI.parent.parent / "assets" / "office"
CHAR = ASSETS / "characters"
FW, FH = 32, 48
B, O, C = 1, 2, 3  # indices de plantilla: base, oscuro, claro
ANIMS_STD = [("idle", 4, 8), ("escribir", 4, 8), ("caminar", 4, 8), ("cafe", 2, 4), ("telefono", 2, 4),
             ("vagancia", 2, 2), ("celebrar", 4, 8), ("dormir", 2, 2)]
ANIMS_RUNA = [("idle", 4, 8), ("caminar", 4, 8), ("entregar", 2, 4), ("esperar", 2, 2), ("recoger", 2, 4),
              ("celebrar", 4, 8), ("dormir", 2, 2)]
EXPR_DE = {"escribir": "concentrado", "cafe": "feliz", "celebrar": "feliz", "dormir": "cerrados",
           "esperar": "concentrado", "vagancia": "normal"}
NEGRO, BRILLO, RUBOR, BOCA = (35, 35, 35, 255), (255, 246, 220, 255), (242, 160, 168, 255), (150, 90, 80, 255)


def pose(anim, f):
    p = {"dy": 0, "enc": 0, "lad": 0, "bi": "abajo", "bd": "abajo", "paso": 0, "cabeza_baja": 0}
    if anim == "idle":
        p["dy"] = 1 if f in (1, 2) else 0
    elif anim == "escribir":
        p["bi"] = p["bd"] = "teclear_a" if f % 2 == 0 else "teclear_b"
    elif anim == "caminar":
        p["paso"] = (0, 1, 0, -1)[f]
        p["dy"] = 1 if f in (1, 3) else 0
    elif anim == "cafe":
        p["bd"] = "taza_boca" if f == 1 else "taza"
    elif anim == "telefono":
        p["bd"] = "oreja"
        p["dy"] = f % 2
    elif anim == "vagancia":
        p["enc"], p["lad"] = 1, (-1 if f == 0 else 1)
        p["bi"] = p["bd"] = "cadera"
    elif anim == "celebrar":
        p["dy"] = (0, -2, -3, -1)[f]
        p["bi"] = p["bd"] = "arriba"
    elif anim == "dormir":
        p["enc"], p["lad"], p["dy"] = 3, 2, (1 if f == 1 else 0)
    elif anim == "entregar":
        p["bi"], p["bd"] = "tableta", ("entregar" if f == 1 else "abajo")
    elif anim == "esperar":
        p["bi"], p["bd"] = "tableta", ("reloj" if f == 1 else "abajo")
    elif anim == "recoger":
        p["bi"], p["bd"] = "tableta", ("entregar" if f == 0 else "abajo")
        p["dy"] = 1 if f == 0 else 0
    return p


def lienzo_p(w, h):
    im = Image.new("P", (w, h), 0)
    im.putpalette([0, 0, 0, 200, 200, 200, 120, 120, 120, 235, 235, 235] + [0, 0, 0] * 252)
    im.info["transparency"] = 0
    return im


def rect(im, x0, y0, x1, y1, c, ox=0, oy=0):
    for y in range(max(0, y0), min(FH, y1 + 1)):
        for x in range(max(0, x0), min(FW, x1 + 1)):
            im.putpixel((ox + x, oy + y), c)


def disco(im, cx, cy, r, c, borde, ox=0, oy=0):
    pts = {(x, y) for y in range(FH) for x in range(FW) if (x - cx) ** 2 + (y - cy) ** 2 <= r * r}
    for x, y in pts:
        es_borde = any((x + dx, y + dy) not in pts for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        im.putpixel((ox + x, oy + y), borde if es_borde else c)


def cabeza(p):
    return 16 + p["lad"], 14 + p["dy"] + p["enc"] + p["cabeza_baja"]


def torso_top(p):
    return 25 + p["dy"] + p["enc"]


def brazo(im, lado, modo, p, c, ox, oy, mano=None):
    """Dibuja un brazo (ropa) y devuelve donde queda la mano (para la piel y los objetos)."""
    t = torso_top(p)
    x = 7 if lado == "i" else 23
    s = -1 if lado == "i" else 1
    if modo == "abajo":
        rect(im, x, t + 2, x + 1, t + 9, c, ox, oy)
        return (x, t + 10)
    if modo.startswith("teclear"):
        a = 1 if (modo == "teclear_a") == (lado == "i") else 0
        rect(im, x, t + 2, x + 1, t + 6 + a, c, ox, oy)
        return (x, t + 7 + a)
    if modo == "arriba":
        rect(im, x - s, t - 6, x + 1 - s, t + 2, c, ox, oy)
        return (x - s, t - 7)
    if modo in ("taza", "taza_boca", "oreja", "reloj"):
        alto = {"taza": 5, "taza_boca": 0, "oreja": -3, "reloj": 3}[modo]
        rect(im, x, t + 2, x + 1, t + 5, c, ox, oy)
        rect(im, x - 2 * s, t + alto, x - s, t + 5, c, ox, oy)
        return (x - 2 * s, t + alto - 1)
    if modo == "cadera":
        rect(im, x, t + 2, x + 1, t + 5, c, ox, oy)
        rect(im, x - s, t + 5, x - s, t + 7, c, ox, oy)
        return (x - s, t + 7)
    if modo in ("tableta", "entregar"):
        largo = 4 if modo == "entregar" else 0
        rect(im, x, t + 2, x + 1, t + 5, c, ox, oy)
        rect(im, x + s * (0 if modo == "tableta" else 1), t + 5, x + s * largo + 1, t + 6, c, ox, oy)
        return (x + s * (largo + (0 if modo == "tableta" else 1)), t + 6)
    raise ValueError(modo)


def generar_base(anims, sufijo=""):
    """Plantillas comunes para un juego de animaciones: cuerpo (piel), pantalon, ropa, brazos, corbata,
    cara (por expresion por defecto de cada animacion) y los estilos de pelo."""
    n = max(a[1] for a in anims)
    W, H = n * FW, len(anims) * FH
    L = {k: lienzo_p(W, H) for k in ("cuerpo", "ropa", "brazos", "corbata")}
    pant = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cara = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pelos = {e: (lienzo_p(W, H), lienzo_p(W, H)) for e in ("corto_lado", "corto", "recogido", "mono_alto")}
    manos = {}
    for fila, (anim, nf, _fps) in enumerate(anims):
        for f in range(nf):
            ox, oy = f * FW, fila * FH
            p = pose(anim, f)
            cx, cy = cabeza(p)
            t = torso_top(p)
            # piel: cabeza humana chibi (radio 9 -> ~19 px) + manos
            disco(L["cuerpo"], cx, cy, 9, B, O, ox, oy)
            rect(L["cuerpo"], cx - 5, cy - 6, cx - 4, cy - 5, C, ox, oy)  # luz arriba-izquierda
            # ropa (torso) con luz a la izquierda
            rect(L["ropa"], 9, t, 22, 38 + p["dy"], B, ox, oy)
            rect(L["ropa"], 9, t, 9, 38 + p["dy"], C, ox, oy)
            rect(L["ropa"], 22, t, 22, 38 + p["dy"], O, ox, oy)
            rect(L["ropa"], 14, t, 17, t, O, ox, oy)  # cuello
            # pantalon y zapatos (RGBA fijo: jeans #33598C); caminar alterna las piernas
            _t = PD.tonos("#33598C")  # jeans de la paleta: base y su tono oscuro (no un hex suelto)
            jean, jean_o, zap = _t[1] + (255,), _t[0] + (255,), (35, 35, 35, 255)
            pi, pd = p["paso"], -p["paso"]
            for xa, d in ((11, pi), (17, pd)):
                for y in range(39 + p["dy"], 46):
                    for x in range(xa + d, xa + d + 4):
                        pant.putpixel((ox + x, oy + y), jean_o if x == xa + d + 3 else jean)
                for x in range(xa + d - (1 if xa == 11 else 0), xa + d + 4 + (1 if xa == 17 else 0)):
                    for y in (46, 47):
                        pant.putpixel((ox + x, oy + y), zap)
            # brazos (ropa) + manos (piel)
            for lado, modo in (("i", p["bi"]), ("d", p["bd"])):
                mx, my = brazo(L["brazos"], lado, modo, p, B, ox, oy)
                rect(L["cuerpo"], mx, my, mx + 1, my + 1, B, ox, oy)
                manos[(anim, f, lado)] = (mx, my)
            # corbata (plantilla: se recolorea con el color del departamento; solo lideres la usan)
            # con contorno de 1 px en el tono oscuro: se lee aunque la camisa sea del mismo color (Clau)
            rect(L["corbata"], 14, t + 1, 17, t + 2, O, ox, oy)  # nudo
            rect(L["corbata"], 15, t + 1, 16, t + 1, C, ox, oy)
            rect(L["corbata"], 14, t + 3, 14, t + 7, O, ox, oy)
            rect(L["corbata"], 17, t + 3, 17, t + 7, O, ox, oy)
            rect(L["corbata"], 15, t + 3, 16, t + 7, B, ox, oy)
            rect(L["corbata"], 15, t + 8, 16, t + 8, O, ox, oy)
            # cara por defecto de la animacion
            dibujar_cara(cara, EXPR_DE.get(anim, "normal"), cx, cy, ox, oy)
            # pelos
            for estilo, (atras, frente) in pelos.items():
                dibujar_pelo(atras, frente, estilo, cx, cy, ox, oy)
    d = CHAR / "base"
    d.mkdir(parents=True, exist_ok=True)
    for k, im in L.items():
        im.save(d / f"{k}{sufijo}.png", transparency=0)
    pant.save(d / f"pantalon{sufijo}.png")
    cara.save(d / f"cara{sufijo}.png")
    for estilo, (atras, frente) in pelos.items():
        atras.save(d / f"pelo_{estilo}_atras{sufijo}.png", transparency=0)
        frente.save(d / f"pelo_{estilo}_frente{sufijo}.png", transparency=0)
    return manos


def dibujar_cara(im, expr, cx, cy, ox=0, oy=0):
    """Ojos humanos unificados: ovalos negros de 1x3 con 1 px de brillo. Solo ojos y boca cambian."""
    def px(x, y, c):
        if 0 <= x < FW and 0 <= y < FH:
            im.putpixel((ox + x, oy + y), c)
    for ex in (cx - 4, cx + 3):
        if expr == "cerrados":
            px(ex - 1, cy + 1, NEGRO), px(ex, cy + 1, NEGRO), px(ex + 1, cy + 1, NEGRO)
        elif expr == "feliz":
            px(ex - 1, cy + 1, NEGRO), px(ex, cy, NEGRO), px(ex + 1, cy + 1, NEGRO)
        elif expr == "sorprendido":
            for y in range(cy - 1, cy + 3):
                px(ex, y, NEGRO), px(ex + 1, y, NEGRO)
            px(ex, cy - 1, BRILLO)
        elif expr == "concentrado":
            px(ex, cy + 1, NEGRO), px(ex, cy + 2, NEGRO), px(ex - 1, cy - 1, NEGRO), px(ex + 1, cy - 1, NEGRO)
        else:  # normal / triste
            for y in range(cy, cy + 3):
                px(ex, y, NEGRO)
            px(ex, cy, BRILLO)
    px(cx - 7, cy + 4, RUBOR), px(cx + 7, cy + 4, RUBOR)
    if expr == "feliz":
        px(cx - 1, cy + 5, BOCA), px(cx, cy + 6, BOCA), px(cx + 1, cy + 5, BOCA)
    elif expr == "triste":
        px(cx - 1, cy + 6, BOCA), px(cx, cy + 5, BOCA), px(cx + 1, cy + 6, BOCA)
    elif expr == "sorprendido":
        px(cx, cy + 5, BOCA), px(cx, cy + 6, BOCA)
    elif expr != "cerrados":
        px(cx, cy + 5, BOCA), px(cx + 1, cy + 5, BOCA)


def dibujar_pelo(atras, frente, estilo, cx, cy, ox, oy):
    def r(im, x0, y0, x1, y1, c):
        rect(im, x0, y0, x1, y1, c, ox, oy)
    if estilo == "corto_lado":  # castano corto peinado a un lado
        r(frente, cx - 8, cy - 9, cx + 8, cy - 6, B)
        r(frente, cx - 9, cy - 6, cx - 3, cy - 4, B)
        r(frente, cx + 7, cy - 6, cx + 8, cy - 2, O)
        r(frente, cx - 6, cy - 9, cx - 2, cy - 9, C)
    elif estilo == "corto":
        r(frente, cx - 8, cy - 9, cx + 8, cy - 5, B)
        r(frente, cx - 9, cy - 5, cx - 8, cy - 1, O)
        r(frente, cx + 8, cy - 5, cx + 9, cy - 1, O)
        r(frente, cx - 5, cy - 9, cx - 1, cy - 9, C)
    elif estilo == "recogido":  # negro recogido: flequillo + coleta baja detras
        r(frente, cx - 8, cy - 9, cx + 8, cy - 6, B)
        r(frente, cx - 9, cy - 6, cx - 8, cy, B)
        r(atras, cx + 6, cy + 1, cx + 10, cy + 6, B)
        r(atras, cx + 9, cy + 2, cx + 10, cy + 6, O)
    elif estilo == "mono_alto":  # Runa: moño alto que se lee de lejos
        r(frente, cx - 8, cy - 9, cx + 8, cy - 6, B)
        r(frente, cx - 9, cy - 6, cx - 8, cy - 1, B)
        r(frente, cx + 8, cy - 6, cx + 9, cy - 1, B)
        r(atras, cx - 3, cy - 15, cx + 3, cy - 10, B)
        r(atras, cx - 2, cy - 15, cx + 2, cy - 15, C)
        r(atras, cx + 3, cy - 14, cx + 3, cy - 11, O)


def accesorio(skin_id, anims, manos):
    n = max(a[1] for a in anims)
    im = Image.new("RGBA", (n * FW, len(anims) * FH), (0, 0, 0, 0))

    def px(ox, oy, x, y, c):
        if 0 <= x < FW and 0 <= y < FH:
            im.putpixel((ox + x, oy + y), c)
    for fila, (anim, nf, _fps) in enumerate(anims):
        for f in range(nf):
            ox, oy = f * FW, fila * FH
            p = pose(anim, f)
            cx, cy = cabeza(p)
            t = torso_top(p)
            if skin_id == "clau":  # lapiz amarillo de 7 px en la oreja
                for i in range(7):
                    px(ox, oy, cx + 7 + (i // 3), cy - 4 + i, (245, 200, 60, 255) if i < 6 else (60, 60, 60, 255))
            elif skin_id == "cody":  # auriculares negros grandes al cuello
                for x in range(10, 22):
                    px(ox, oy, x, t + 1, (30, 30, 34, 255))
                for x in (9, 10, 21, 22):
                    for y in (t, t + 1, t + 2):
                        px(ox, oy, x, y, (20, 20, 24, 255))
            elif skin_id == "luma":  # taza gigante en UNA mano: la corbata queda a la vista
                mx, my = manos.get((anim, f, "d"), (23, t + 10))
                if anim != "dormir":
                    for y in range(my - 4, my + 2):  # la taza en la mano (no flotando)
                        for x in range(mx - 1, mx + 4):
                            px(ox, oy, x, y, (255, 246, 220, 255) if x < mx + 3 else (154, 160, 166, 255))
                    px(ox, oy, mx + 4, my - 2, (154, 160, 166, 255)), px(ox, oy, mx + 4, my - 1, (154, 160, 166, 255))
            elif skin_id == "gemi":  # casco de obra amarillo
                for y in range(cy - 11, cy - 6):
                    for x in range(cx - 9, cx + 10):
                        if y > cy - 11 or abs(x - cx) < 7:
                            px(ox, oy, x, y, (245, 200, 30, 255) if y < cy - 7 else (200, 160, 20, 255))
            elif skin_id == "runa":
                # tableta con la cola (marco oscuro, pantalla crema con lineas): SU identificador unico
                mx, my = manos.get((anim, f, "i"), (7, t + 10))
                if anim != "dormir":
                    for y in range(my - 6, my + 1):
                        for x in range(mx - 5, mx + 1):
                            borde = y in (my - 6, my) or x in (mx - 5, mx)
                            px(ox, oy, x, y, (40, 40, 44, 255) if borde else (255, 246, 220, 255))
                    for y in (my - 4, my - 2):
                        for x in range(mx - 4, mx - 1):
                            px(ox, oy, x, y, (120, 120, 130, 255))
                # pin ambar con «1»
                for x in range(18, 21):
                    for y in range(t + 2, t + 5):
                        px(ox, oy, x, y, (245, 166, 35, 255))
                px(ox, oy, 19, t + 2, (35, 35, 35, 255)), px(ox, oy, 19, t + 3, (35, 35, 35, 255))
                px(ox, oy, 19, t + 4, (35, 35, 35, 255))
                # smartwatch en la muñeca derecha
                mx2, my2 = manos.get((anim, f, "d"), (23, t + 10))
                px(ox, oy, mx2, my2 - 1, (20, 20, 24, 255)), px(ox, oy, mx2 + 1, my2 - 1, (0, 122, 255, 255))
    return im


SKINS = {
    "clau": {"nombre": "Clau", "departamento": "claude", "plataforma": "Claude Code", "rol": "lider",
             "pelo": "corto_lado", "colores": {"pelo": "#6B4A2E", "ropa": "#D97757", "piel": "#F2C9A0", "corbata": "#D97757"},
             "notas": "Alta (en la final, +1 px). Camisa naranja + corbata naranja; lápiz amarillo de 7 px en la oreja (§7: 6-8 px)."},
    "cody": {"nombre": "Cody", "departamento": "codex", "plataforma": "Codex", "rol": "lider",
             "pelo": "corto", "colores": {"pelo": "#2E2A26", "ropa": "#00805F", "piel": "#E0B48A", "corbata": "#00A67E"},
             "notas": "Sudadera verde oscuro + corbata verde; auriculares negros grandes al cuello (a 32x48 se leen como collar oscuro)."},
    "luma": {"nombre": "Luma", "departamento": "local", "plataforma": "Local (llama-server / Ollama)", "rol": "lider",
             "pelo": "recogido", "colores": {"pelo": "#232323", "ropa": "#8C52C8", "piel": "#F2C9A0", "corbata": "#6A3A9E"},
             "notas": "Camisa morada + corbata morada; taza gigante en UNA mano para que la corbata se vea (§7). Morado PROVISIONAL: el hex de PALETA-Y-SKINS §1 no está en el PC."},
    "gemi": {"nombre": "Gemi", "departamento": "gemini", "plataforma": "Gemini (agy, en obras)", "rol": "lider",
             "pelo": "corto", "colores": {"pelo": "#4A3324", "ropa": "#4285F4", "piel": "#D9A47A", "corbata": "#2B5CB8"},
             "notas": "Camisa azul + corbata azul oscuro #2B5CB8 (§7); casco de obra amarillo. El cartel «EN OBRAS» va en su mesa (plano.json), no en el sprite."},
    "runa": {"nombre": "Runa", "departamento": "despacho", "plataforma": "—", "rol": "subgerente",
             "pelo": "mono_alto", "colores": {"pelo": "#232323", "ropa": "#232323", "piel": "#F2C9A0"},
             "notas": "Fuera del personal. Blazer negro, blusa #FFF6DC (cuello), jeans #33598C, pin ámbar «1», smartwatch; la ÚNICA con tableta. Sin corbata. Duerme apoyada en la mesa de despacho. Tinte de pensamiento azul (§15) pendiente de decidir sobre el blazer negro de §10."},
}


def escribir_skins(manos_std, manos_runa):
    for sid, s in SKINS.items():
        runa = sid == "runa"
        anims = ANIMS_RUNA if runa else ANIMS_STD
        suf = "_runa" if runa else ""
        d = CHAR / "skins" / sid
        d.mkdir(parents=True, exist_ok=True)
        accesorio(sid, anims, manos_runa if runa else manos_std).save(d / "accesorio.png")
        capas = {"cuerpo": f"base:cuerpo{suf}", "pantalon": f"base:pantalon{suf}", "ropa": f"base:ropa{suf}",
                 "brazos": f"base:brazos{suf}", "cara": f"base:cara{suf}",
                 "pelo_atras": f"base:pelo_{s['pelo']}_atras{suf}", "pelo_frente": f"base:pelo_{s['pelo']}_frente{suf}",
                 "accesorio": "accesorio"}
        if s["rol"] == "lider":
            capas["corbata"] = f"base:corbata{suf}"
        sj = {"id": sid, "nombre": s["nombre"], "departamento": s["departamento"], "plataforma": s["plataforma"],
              "rol": s["rol"], "paleta": f"../../../palettes/{s['departamento']}.json", "capas": capas,
              "colores": s["colores"], "frame": {"w": FW, "h": FH}, "ancla": [16, 47],
              "animaciones": [{"nombre": a, "frames": n, "fps": fps, "bucle": a not in ("celebrar", "entregar", "recoger")}
                              for a, n, fps in anims],
              "efectos_compartidos": {"dormir": "base:efectos/z", "duda": "base:efectos/duda", "aviso": "base:efectos/aviso"},
              "notas": s["notas"],
              "estado_arte": "BORRADOR generado por script (IA): valida el sistema de skins; retoque humano pendiente."}
        (d / "skin.json").write_text(json.dumps(sj, ensure_ascii=False, indent=1), encoding="utf-8")


def efectos():
    d = CHAR / "base" / "efectos"
    d.mkdir(parents=True, exist_ok=True)
    src = ASSETS / "comun" / "z.png"
    if src.exists():
        Image.open(src).save(d / "z.png")
    for nombre, glifo, c in (("duda", "?", (154, 160, 166, 255)), ("aviso", "!", (245, 166, 35, 255))):
        im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        if glifo == "!":
            for y in range(1, 5):
                im.putpixel((3, y), c), im.putpixel((4, y), c)
            im.putpixel((3, 6), c), im.putpixel((4, 6), c)
        else:
            for x in (2, 3, 4, 5):
                im.putpixel((x, 1), c)
            for (x, y) in ((5, 2), (5, 3), (4, 4), (3, 4), (3, 6)):
                im.putpixel((x, y), c)
        im.save(d / f"{nombre}.png")


def paletas():
    d = ASSETS / "palettes"
    d.mkdir(parents=True, exist_ok=True)
    glob = json.loads((ASSETS / "paleta.json").read_text(encoding="utf-8"))
    (d / "global.json").write_text(json.dumps(glob, ensure_ascii=False, indent=1), encoding="utf-8")
    for depto in ("claude", "codex", "local", "gemini", "despacho"):
        extra = {sid: s["colores"] for sid, s in SKINS.items() if s["departamento"] == depto}
        (d / f"{depto}.json").write_text(json.dumps({"departamento": depto, "base": "global.json", "skins": extra},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    m_std = generar_base(ANIMS_STD)
    m_runa = generar_base(ANIMS_RUNA, "_runa")
    efectos()
    escribir_skins(m_std, m_runa)
    paletas()
    print(f"escrito en {CHAR}")

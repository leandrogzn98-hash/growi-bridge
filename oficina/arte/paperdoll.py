"""Compositor paper doll de la oficina (t-oficina-skins-050, spec 10 de 18).

Un personaje no es una imagen: es una pila de capas que se componen al cargar su skin.json.
Orden (de atras hacia adelante): pelo_atras, cuerpo, ropa, brazos, cara, pelo_frente, accesorio, efectos.
- Capas que se recolorean (cuerpo=piel, ropa, pelo, corbata): PNG modo P con indices de plantilla
  (1 base, 2 oscuro, 3 claro). El recoloreado cambia la paleta del PNG (putpalette) UNA vez al cargar.
- Capas con detalle (cara, accesorios): RGBA tal cual.
- Cada hoja: filas = animaciones del skin, columnas = frames (32x48 cada uno).
- La «Z» de dormir y los «?», «!» son efectos compartidos (characters/base/efectos/), no frames por personaje.
Leandro cambia un personaje editando su skin.json (colores, capas, accesorio) y recargando: sin tocar Python.
"""
import colorsys
import json
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
ASSETS = AQUI.parent.parent / "assets" / "office"
CHAR = ASSETS / "characters"
ORDEN = ("pelo_atras", "cuerpo", "pantalon", "ropa", "brazos", "cara", "pelo_frente", "corbata", "accesorio", "efectos")
RECOLOR = ("cuerpo", "ropa", "brazos", "pelo_atras", "pelo_frente", "corbata")
COLOR_DE_CAPA = {"cuerpo": "piel", "ropa": "ropa", "brazos": "ropa", "pelo_atras": "pelo", "pelo_frente": "pelo",
                 "corbata": "corbata"}
FW, FH = 32, 48


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def tonos(h):
    """(oscuro, base, claro) de un hex: los indices 2, 1, 3 de una capa de plantilla."""
    r, g, b = (v / 255 for v in _hex(h))
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    osc = colorsys.hsv_to_rgb(hh, min(1, ss * 1.1), vv * 0.72)
    cla = tuple(c + (1 - c) * 0.35 for c in (r, g, b))
    return (tuple(round(x * 255) for x in osc), _hex(h), tuple(round(x * 255) for x in cla))


def ruta_capa(skin_dir, ref):
    """«base:ropa_camisa» = characters/base/ropa_camisa.png; «lapiz» = la carpeta del skin."""
    if ref.startswith("base:"):
        return CHAR / "base" / (ref[5:] + ".png")
    return skin_dir / (ref + ".png")


def recolorear(im, hexcolor):
    """PNG modo P de plantilla -> RGBA con los 3 tonos del color (indice 0 = transparente)."""
    if im.mode != "P":
        raise ValueError("una capa que se recolorea tiene que ser PNG modo P (indices de plantilla)")
    osc, base, cla = tonos(hexcolor)
    pal = [0, 0, 0] + list(base) + list(osc) + list(cla) + [0, 0, 0] * 252
    im = im.copy()
    im.putpalette(pal)
    im.info["transparency"] = 0
    return im.convert("RGBA")


class Skin:
    """Un personaje compuesto desde su skin.json. frames[(animacion, i)] = Image RGBA 32x48 (cacheado)."""

    _cache = {}

    def __init__(self, skin_json):
        self.path = Path(skin_json)
        self.d = json.loads(self.path.read_text(encoding="utf-8"))
        self.dir = self.path.parent
        clave = (str(self.path), self.path.stat().st_mtime)
        if clave in Skin._cache:
            self.frames = Skin._cache[clave]
            return
        anims = self.d["animaciones"]
        filas = {a["nombre"]: i for i, a in enumerate(anims)}
        capas = []
        for nombre in ORDEN:
            ref = self.d["capas"].get(nombre)
            if not ref:
                continue
            im = Image.open(ruta_capa(self.dir, ref))
            if nombre in RECOLOR:
                im = recolorear(im, self.d["colores"][COLOR_DE_CAPA[nombre]])
            else:
                im = im.convert("RGBA")
            capas.append((nombre, im))
        self.frames = {}
        for a in anims:
            for f in range(a["frames"]):
                out = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
                for _n, im in capas:
                    caja = (f * FW, filas[a["nombre"]] * FH, (f + 1) * FW, (filas[a["nombre"]] + 1) * FH)
                    out.alpha_composite(im.crop(caja))
                self.frames[(a["nombre"], f)] = out
        Skin._cache[clave] = self.frames

    def hoja(self):
        anims = self.d["animaciones"]
        n = max(a["frames"] for a in anims)
        out = Image.new("RGBA", (n * FW, len(anims) * FH), (0, 0, 0, 0))
        for i, a in enumerate(anims):
            for f in range(a["frames"]):
                out.alpha_composite(self.frames[(a["nombre"], f)], (f * FW, i * FH))
        return out


def skins_disponibles():
    return sorted((CHAR / "skins").glob("*/skin.json"))

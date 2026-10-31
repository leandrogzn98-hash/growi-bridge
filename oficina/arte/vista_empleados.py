"""Evidencia visual de t-oficina-empleados-050 (solo Pillow):
- hoja de los 14 a 32x48 NEAREST x4, con la deteccion real aplicada (silla vacia con cartel si no esta);
- prueba del entrecerrar los ojos: cada silueta reducida y desenfocada se compara con las demas
  (distancia minima entre pares; Hermes Directo / Ollama se parecen A PROPOSITO);
- Gemini: 2 sillas vacias con su cartel; Runa en la mesa de despacho con tableta y pin.

  python vista_empleados.py <carpeta de evidencia> [--app <carpeta de la app>]
"""
import json
import sys
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "personal"))
import deteccion as DET  # noqa: E402
import paperdoll as PD  # noqa: E402

EV = Path(sys.argv[1])
EV.mkdir(parents=True, exist_ok=True)
APP = Path(sys.argv[sys.argv.index("--app") + 1]) if "--app" in sys.argv else Path.home() / "growi-bridge"
K = 4
ORDEN14 = ["growi", "clau", "sonny", "opus", "haiku", "cody", "dex", "luma", "hermes_directo", "hermes_ollama",
           "gemi", "mensajero", "blender", "tripo"]
det = DET.detectar(APP)["personal"]


def frame(pid):
    if pid == "growi":
        hoja = Image.open(PD.ASSETS / "personajes" / "growi.png").convert("RGBA")
        return hoja.crop((0, 0, 32, 48))
    return PD.Skin(PD.CHAR / "skins" / pid / "skin.json").frames[("idle", 0)]


celda = 32 * K + 20
hoja = Image.new("RGBA", (7 * celda + 20, 2 * (48 * K + 56) + 10), (245, 245, 247, 255))
g = ImageDraw.Draw(hoja)
siluetas = {}
for i, pid in enumerate(ORDEN14):
    x, y = 20 + (i % 7) * celda, 10 + (i // 7) * (48 * K + 56)
    fr = frame(pid)
    siluetas[pid] = fr
    if det[pid]["detectado"]:
        hoja.alpha_composite(fr.resize((32 * K, 48 * K), Image.NEAREST), (x, y))
    else:  # silla vacia con cartel: no se inventa al empleado
        g.rectangle([x + 20, y + 100, x + 32 * K - 20, y + 48 * K - 10], outline=(174, 174, 178, 255), width=3)
        g.text((x + 6, y + 60), "sin instalar", fill=(110, 110, 115, 255))
    g.text((x, y + 48 * K + 6), pid, fill=(29, 29, 31, 255))
    g.text((x, y + 48 * K + 22), det[pid]["silla"], fill=(110, 110, 115, 255))
hoja.save(EV / "hoja-14-x4.png")

# prueba del entrecerrar los ojos: fondo comun, 50 % de tamano y desenfoque de 1 px; distancia media por pixel
def borrosa(im):
    fondo = Image.new("RGBA", im.size, (245, 245, 247, 255))
    fondo.alpha_composite(im)
    return fondo.convert("RGB").resize((16, 24), Image.BOX).filter(ImageFilter.GaussianBlur(1))


B = {p: borrosa(im) for p, im in siluetas.items()}
dist = {}
for a, b in combinations(ORDEN14, 2):
    pa, pb = B[a].load(), B[b].load()
    d = sum(abs(pa[x, y][c] - pb[x, y][c]) for x in range(16) for y in range(24) for c in range(3)) / (16 * 24 * 3)
    dist[f"{a}~{b}"] = round(d, 2)
orden = sorted(dist.items(), key=lambda kv: kv[1])
borrosas = Image.new("RGB", (14 * 16 * 4, 24 * 4), (245, 245, 247))
for i, p in enumerate(ORDEN14):
    borrosas.paste(B[p].resize((64, 96), Image.NEAREST), (i * 64, 0))
borrosas.save(EV / "entrecerrar-ojos.png")

# Gemini: local en obras con 2 sillas vacias y su cartel; Runa en su mesa de despacho
plano = json.loads((AQUI.parent / "plano" / "plano.json").read_text(encoding="utf-8"))
esc = 3 * 8  # 8 px por baldosa x3


def zona_png(nombre, zona, extra):
    zx, zy, zw, zh = zona["x"], zona["y"], zona["w"], zona["h"]
    im = Image.new("RGBA", (zw * esc, zh * esc), (240, 238, 232, 255))
    d = ImageDraw.Draw(im)
    for m in plano["mesas"] + [plano["despacho"]["mesa"]]:
        r = m["rect"]
        if zx <= r["x"] < zx + zw and zy <= r["y"] < zy + zh:
            d.rectangle([(r["x"] - zx) * esc, (r["y"] - zy) * esc, (r["x"] - zx + r["w"]) * esc - 1,
                         (r["y"] - zy + r["h"]) * esc - 1], fill=(190, 160, 120, 255), outline=(120, 90, 60, 255))
    for s in plano["sillas"]:
        sx, sy = s["punto"]
        if zx <= sx < zx + zw and zy <= sy < zy + zh:
            d.ellipse([(sx - zx) * esc + 4, (sy - zy) * esc + 4, (sx - zx + 1) * esc - 4, (sy - zy + 1) * esc - 4],
                      outline=(90, 90, 95, 255), width=2)
            if s.get("cartel"):
                d.text(((sx - zx) * esc - 30, (sy - zy + 1) * esc), s["cartel"], fill=(29, 29, 31, 255))
    extra(im, d, zx, zy)
    im.save(EV / nombre)


def gem_extra(im, d, zx, zy):
    z = next(x for x in plano["departamentos"] if x["id"] == "gemini")
    d.text((6, 4), z["cartel"], fill=(200, 120, 20, 255))
    for k in range(40):  # polvo
        d.point(((k * 37) % im.width, (k * 53) % im.height), fill=(200, 196, 186, 255))
    gx, gy = next(s["punto"] for s in plano["sillas"] if s["empleado"] == "gemi")
    im.alpha_composite(frame("gemi").resize((48, 72), Image.NEAREST), ((gx - zx) * esc - 12, (gy - zy) * esc - 60))


def runa_extra(im, d, zx, zy):
    r = plano["despacho"]["mesa"]["rect"]
    runa = PD.Skin(PD.CHAR / "skins" / "runa" / "skin.json").frames[("idle", 0)].resize((64, 96), Image.NEAREST)
    im.alpha_composite(runa, ((r["x"] - zx) * esc + 40, (r["y"] - zy + r["h"]) * esc + 2))
    d.text(((r["x"] - zx) * esc + 4, (r["y"] - zy) * esc + 4), "tablero de la cola", fill=(29, 29, 31, 255))


zona_png("gemini-sillas-vacias.png", next(x for x in plano["departamentos"] if x["id"] == "gemini")["zona"], gem_extra)
zona_png("runa-mesa-despacho.png", next(x for x in plano["departamentos"] if x["id"] == "despacho")["zona"], runa_extra)
res = {"deteccion": {p: det[p]["silla"] for p in ORDEN14},
       "entrecerrar": {"pares_mas_parecidos": orden[:5], "par_mas_distinto": orden[-1],
                       "minimo_sin_hermes": min(v for k, v in dist.items() if k != "hermes_directo~hermes_ollama")}}
(EV / "vista-empleados.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))

"""Capturas de las skins a tamano de juego (NEAREST x4) y prueba «editar el JSON y recargar»
(t-oficina-skins-050). Solo Pillow.

  python vista_skins.py <carpeta de evidencia>
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paperdoll as PD  # noqa: E402

EV = Path(sys.argv[1])
EV.mkdir(parents=True, exist_ok=True)
K = 4
res = {}

# (a, d) cada skin compuesta: hoja completa x4
for sj in PD.skins_disponibles():
    s = PD.Skin(sj)
    hoja = s.hoja()
    hoja.resize((hoja.width * K, hoja.height * K), Image.NEAREST).save(EV / f"hoja-{s.d['id']}-x4.png")
    res[s.d["id"]] = {"animaciones": [a["nombre"] for a in s.d["animaciones"]], "frames": len(s.frames)}

# (e) los 4 lideres + Runa en idle, uno al lado del otro, a 32x48 x4: la corbata de lider se ve
fila = Image.new("RGBA", (5 * (32 * K + 16) + 16, 48 * K + 40), (245, 245, 247, 255))
g = ImageDraw.Draw(fila)
for i, sid in enumerate(("clau", "cody", "luma", "gemi", "runa")):
    s = PD.Skin(PD.CHAR / "skins" / sid / "skin.json")
    fr = s.frames[("idle", 0)].resize((32 * K, 48 * K), Image.NEAREST)
    fila.alpha_composite(fr, (16 + i * (32 * K + 16), 8))
    g.text((16 + i * (32 * K + 16), 48 * K + 14), f"{s.d['nombre']} ({s.d['rol']})", fill=(29, 29, 31, 255))
fila.save(EV / "lideres-y-runa-idle-x4.png")

# corbata visible: pixeles del color de corbata del departamento en el torso de cada lider (idle 0)
for sid in ("clau", "cody", "luma", "gemi"):
    s = PD.Skin(PD.CHAR / "skins" / sid / "skin.json")
    tonos = set(PD.tonos(s.d["colores"]["corbata"]))
    fr = s.frames[("idle", 0)]
    n = sum(1 for y in range(24, 34) for x in range(14, 18) if fr.getpixel((x, y))[:3] in tonos)
    res[sid]["px_corbata_visibles"] = n

# (f) editar el JSON (color de ropa + quitar el accesorio) y recargar: cambia sin tocar codigo
src = PD.CHAR / "skins" / "clau"
tmp = PD.CHAR / "skins" / "_prueba_editar_json"
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(src, tmp)
antes = PD.Skin(tmp / "skin.json").frames[("idle", 0)]
d = json.loads((tmp / "skin.json").read_text(encoding="utf-8"))
d["colores"]["ropa"] = "#007AFF"
d["capas"].pop("accesorio")
(tmp / "skin.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
despues = PD.Skin(tmp / "skin.json").frames[("idle", 0)]
distintos = sum(1 for y in range(48) for x in range(32) if antes.getpixel((x, y)) != despues.getpixel((x, y)))
azul = PD.tonos("#007AFF")[1]
comp = Image.new("RGBA", (2 * 32 * K + 24, 48 * K + 16), (245, 245, 247, 255))
comp.alpha_composite(antes.resize((32 * K, 48 * K), Image.NEAREST), (8, 8))
comp.alpha_composite(despues.resize((32 * K, 48 * K), Image.NEAREST), (16 + 32 * K, 8))
comp.save(EV / "editar-json-antes-despues-x4.png")
res["editar_json"] = {"pixeles_distintos": distintos, "ropa_azul_presente": any(
    despues.getpixel((x, y))[:3] == azul for y in range(48) for x in range(32)),
    "lapiz_quitado": not any(despues.getpixel((x, y))[:3] == (245, 200, 60) for y in range(48) for x in range(32))}
shutil.rmtree(tmp, ignore_errors=True)

# expresiones sobre la misma cara base (solo ojos y boca)
import generar_skins as GS  # noqa: E402
ex = Image.new("RGBA", (5 * 32, 48), (0, 0, 0, 0))
base = PD.Skin(PD.CHAR / "skins" / "luma" / "skin.json")
cuerpo_sin_cara = None
for i, e in enumerate(("normal", "feliz", "triste", "sorprendido", "concentrado")):
    lienzo = Image.new("RGBA", (32, 48), (0, 0, 0, 0))
    GS.dibujar_cara(lienzo, e, 16, 14)
    fr = base.frames[("idle", 0)].copy()
    # tapar la cara por defecto con la piel y pintar la expresion
    piel = PD.tonos(base.d["colores"]["piel"])[1] + (255,)
    for y in range(13, 21):
        for x in range(9, 24):
            if fr.getpixel((x, y))[:3] in GS.__dict__.get("_x", set()) or fr.getpixel((x, y))[:3] in (
                    (35, 35, 35), (255, 246, 220), (242, 160, 168), (150, 90, 80)):
                fr.putpixel((x, y), piel)
    fr.alpha_composite(lienzo)
    ex.alpha_composite(fr, (i * 32, 0))
ex.resize((ex.width * K, ex.height * K), Image.NEAREST).save(EV / "expresiones-x4.png")
(EV / "vista-skins.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))

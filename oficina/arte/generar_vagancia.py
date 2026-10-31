"""Frames de vagancia (t-oficina-vagancia-050) sobre el paper doll: caminar con taza, servirse cafe, beber,
estirarse, bostezar, mirar la ventana, gesticular, celular, pelota y fundido del bano. BORRADOR de script (IA):
valida el formato (una hoja por personaje, filas = animaciones) y cuantos frames hacen falta; retoque humano.

  python generar_vagancia.py [skin]      # por defecto sonny
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paperdoll as PD  # noqa: E402

SKIN = sys.argv[1] if len(sys.argv) > 1 else "sonny"
TAZA, CAFE, PANT, PEL = (255, 246, 220, 255), (120, 80, 50, 255), (35, 35, 35, 255), (217, 119, 87, 255)
ANIMS = [("caminar_taza", 4), ("servir_cafe", 5), ("beber", 3), ("estirarse", 4), ("bostezar", 3), ("ventana", 2),
         ("gesticular", 3), ("celular", 2), ("pelota", 2), ("bano_fundido", 2)]


def px(im, x, y, c):
    if 0 <= x < 32 and 0 <= y < 48:
        im.putpixel((x, y), c)


def rect(im, x0, y0, x1, y1, c):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px(im, x, y, c)


def frame(sk, anim, f):
    base = {"caminar_taza": ("caminar", f % 4), "estirarse": ("celebrar", min(f, 3)), "gesticular": ("telefono", f % 2),
            "bostezar": ("dormir", 0) if f == 1 else ("idle", 0)}.get(anim, ("idle", f % 4))
    im = sk.frames[base].copy()
    if anim in ("caminar_taza", "beber", "servir_cafe"):
        y = (34, 22, 30)[f] if anim == "beber" else 34  # beber: la taza sube a la boca y baja
        rect(im, 23, y, 26, y + 4, TAZA)
        if anim == "servir_cafe":
            for k in range(f):
                px(im, 24, y - 1 - k, CAFE)  # el chorro sube con los frames
    elif anim == "bostezar" and f != 1:
        rect(im, 15, 19 + f, 17, 21 + f, PANT)  # boca abierta
    elif anim == "ventana":
        im = im.transpose(Image.FLIP_LEFT_RIGHT) if f else im  # gira la cabeza
    elif anim == "celular":
        rect(im, 21, 26, 23, 30, PANT)
        px(im, 22, 27 + f, (0, 122, 255, 255))
    elif anim == "pelota":
        rect(im, 14, 2 - 2 * f + 2, 17, 5 - 2 * f + 2, PEL)
    elif anim == "bano_fundido":
        a = im.split()[3].point(lambda v: int(v * (0.6 if f == 0 else 0.25)))
        im.putalpha(a)
    return im


sk = PD.Skin(PD.CHAR / "skins" / SKIN / "skin.json")
n = max(k for _a, k in ANIMS)
hoja = Image.new("RGBA", (n * 32, len(ANIMS) * 48), (0, 0, 0, 0))
for fila, (anim, k) in enumerate(ANIMS):
    for f in range(k):
        hoja.alpha_composite(frame(sk, anim, f), (f * 32, fila * 48))
d = PD.CHAR / "skins" / SKIN
hoja.save(d / "vagancia.png")
meta = {"skin": SKIN, "frame": {"w": 32, "h": 48}, "animaciones": [{"nombre": a, "frames": k, "fps": 4} for a, k in ANIMS],
        "total_frames": sum(k for _a, k in ANIMS), "pasear": "reutiliza «caminar» del skin",
        "estado_arte": "BORRADOR (script); retoque humano pendiente"}
(d / "vagancia.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
hoja.resize((hoja.width * 4, hoja.height * 4), Image.NEAREST).save(
    Path(__file__).resolve().parents[2] / "pruebas" / "evidencia" / "oficina-vagancia-050" / f"frames-vagancia-{SKIN}-x4.png")
print(json.dumps({"total_frames": meta["total_frames"]}))

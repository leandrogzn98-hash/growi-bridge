"""Validador de skins (t-oficina-skins-050). Para cada characters/skins/<id>/skin.json comprueba:
campos obligatorios; que cada capa existe; que todas las hojas miden lo mismo (frames x 32, animaciones x 48);
que cada animacion tiene los mismos frames con contenido en todas las capas que dibujan; que las capas que se
recolorean son PNG modo P y solo usan los indices de plantilla (0 transparente, 1 base, 2 oscuro, 3 claro);
que los colores de las capas RGBA (cara, accesorio, pantalon) estan en la paleta (global + los del skin);
que existen los efectos compartidos. Falla rapido, con mensaje claro.

  python validate_skins.py [skins...] [--json] [--autoprueba]
"""
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paperdoll as PD  # noqa: E402

CAMPOS = ("id", "nombre", "departamento", "plataforma", "rol", "paleta", "capas", "colores", "animaciones", "notas")
COLORES = ("pelo", "ropa", "piel")
ANIMS_LIDER = ("idle", "escribir", "caminar", "cafe", "telefono", "vagancia", "celebrar", "dormir")
def _px(im):
    return im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()


RGBA_LIBRES = {(35, 35, 35), (255, 246, 220), (242, 160, 168), (150, 90, 80)}  # ojos, brillo, rubor, boca


def colores_paleta(d, skin_dir):
    cols = set(RGBA_LIBRES)
    try:
        glob = json.loads((PD.ASSETS / "palettes" / "global.json").read_text(encoding="utf-8"))
        for c in glob["colores"].values():
            cols |= {PD._hex(c[t]) for t in ("oscuro", "base", "claro")}
    except (OSError, ValueError, KeyError):
        pass
    for h in d.get("colores", {}).values():
        cols |= set(PD.tonos(h))
    for extra in d.get("colores_accesorio", []):
        cols.add(PD._hex(extra))
    return cols


def validar_skin(path, accesorio_libre=True):
    F = []
    path = Path(path)
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{path}: no se puede leer como JSON ({type(e).__name__}: {e})"]
    sid = d.get("id", path.parent.name)
    for k in CAMPOS:
        if k not in d:
            F.append(f"{sid}: falta el campo «{k}»")
    for k in COLORES:
        if k not in d.get("colores", {}):
            F.append(f"{sid}: falta colores.{k}")
    if d.get("rol") == "lider" and "corbata" not in d.get("capas", {}):
        F.append(f"{sid}: un líder lleva corbata (capas.corbata) del color de su departamento")
    if d.get("rol") != "lider" and "corbata" in d.get("capas", {}):
        F.append(f"{sid}: solo los líderes llevan corbata (rol {d.get('rol')})")
    if F:
        return F
    anims = d["animaciones"]
    nmax = max(a["frames"] for a in anims)
    W, H = nmax * PD.FW, len(anims) * PD.FH
    if d.get("rol") == "lider":
        faltan = [a for a in ANIMS_LIDER if a not in {x["nombre"] for x in anims}]
        if faltan:
            F.append(f"{sid}: le faltan animaciones de líder: {', '.join(faltan)}")
    pal = colores_paleta(d, path.parent)
    for nombre, ref in d["capas"].items():
        rp = PD.ruta_capa(path.parent, ref)
        if not rp.is_file():
            F.append(f"{sid}: la capa «{nombre}» apunta a {rp}, que no existe")
            continue
        im = Image.open(rp)
        if im.size != (W, H):
            F.append(f"{sid}: la capa «{nombre}» mide {im.size[0]}x{im.size[1]} y la hoja debe medir {W}x{H} "
                     f"({nmax} frames x {len(anims)} animaciones)")
            continue
        if nombre in PD.RECOLOR:
            if im.mode != "P":
                F.append(f"{sid}: «{nombre}» se recolorea y tiene que ser PNG modo P (es {im.mode})")
                continue
            usados = set(_px(im))
            raros = sorted(usados - {0, 1, 2, 3})
            if raros:
                F.append(f"{sid}: «{nombre}» usa índices fuera de la plantilla (0-3): {raros[:6]}")
        else:
            rgba = im.convert("RGBA")
            usados = {px[:3] for px in _px(rgba) if px[3] > 0}
            fuera = usados - pal
            if fuera and not (nombre == "accesorio" and accesorio_libre):
                F.append(f"{sid}: «{nombre}» usa {len(fuera)} colores que no están en su paleta, p. ej. "
                         + ", ".join("#%02X%02X%02X" % c for c in sorted(fuera)[:4]))
        # frames con contenido: cada animacion igual de larga en las capas que dibujan en todos los frames
        if nombre in ("cuerpo", "ropa", "cara"):
            alpha = im.convert("RGBA").split()[3]
            for i, a in enumerate(anims):
                llenos = [f for f in range(nmax)
                          if alpha.crop((f * PD.FW, i * PD.FH, (f + 1) * PD.FW, (i + 1) * PD.FH)).getbbox()]
                if llenos != list(range(a["frames"])):
                    F.append(f"{sid}: en «{nombre}», la animación «{a['nombre']}» tiene contenido en los frames "
                             f"{llenos} y el skin dice {a['frames']}")
    for k, ref in (d.get("efectos_compartidos") or {}).items():
        if not PD.ruta_capa(path.parent, ref).is_file():
            F.append(f"{sid}: falta el efecto compartido «{k}» ({ref})")
    return F


def autoprueba():
    """Rompe copias de un skin bueno y comprueba que el validador lo dice."""
    casos = []
    src = PD.CHAR / "skins" / "clau"
    tmp = Path(tempfile.mkdtemp(prefix="skins-rotos-"))
    try:
        def caso(nombre, romper, espera):
            d = tmp / nombre.replace(" ", "_")
            shutil.copytree(src, d)
            sj = json.loads((d / "skin.json").read_text(encoding="utf-8"))
            if romper(d, sj) != "ya_escrito":
                (d / "skin.json").write_text(json.dumps(sj, ensure_ascii=False), encoding="utf-8")
            # las referencias base: siguen apuntando a characters/base (ruta_capa); las propias, a la copia
            f = validar_skin(d / "skin.json")
            casos.append({"caso": nombre, "falla": bool(f), "mensaje": f[:1], "ok": any(espera in m for m in f)})

        caso("archivo que falta", lambda d, sj: (d / "accesorio.png").unlink(), "no existe")
        caso("dimensiones distintas", lambda d, sj: Image.open(d / "accesorio.png").crop((0, 0, 96, 384)).save(
            d / "accesorio.png"), "mide")
        caso("frames desiguales", lambda d, sj: sj["animaciones"][0].update(frames=3), "contenido en los frames")
        caso("campo que falta", lambda d, sj: sj.pop("plataforma"), "plataforma")
        caso("líder sin corbata", lambda d, sj: sj["capas"].pop("corbata"), "corbata")
        caso("JSON roto", lambda d, sj: (d / "skin.json").write_text("{roto", encoding="utf-8") and "ya_escrito",
             "no se puede leer como JSON")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return casos


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skins = [Path(a) for a in args] or PD.skins_disponibles()
    res = {str(s): validar_skin(s) for s in skins}
    salida = {"skins": {Path(k).parent.name: (v or "OK") for k, v in res.items()},
              "pasa": all(not v for v in res.values())}
    if "--autoprueba" in sys.argv:
        salida["autoprueba"] = autoprueba()
    if "--json" in sys.argv:
        print(json.dumps(salida, ensure_ascii=False, indent=1))
    else:
        for k, v in salida["skins"].items():
            print(f"{k}: {'OK' if v == 'OK' else 'FALLA'}")
            for m in ([] if v == "OK" else v):
                print(f"  - {m}")
        for c in salida.get("autoprueba", []):
            print(f"autoprueba {c['caso']}: {'detectado' if c['ok'] else 'NO DETECTADO'} {c['mensaje']}")
    ok = salida["pasa"] and all(c["ok"] for c in salida.get("autoprueba", []))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

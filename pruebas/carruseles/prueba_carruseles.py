"""Verificación de la skill carruseles en este PC: (a) tipo 1 de 5 láminas con Summit Maker, (b) el QC rechaza
láminas saboteadas, (c) lote de 3 sin intervención, (d) tipo 3 con 3 fotos sin deformar, (e) una corrección guardada
se aplica en el siguiente carrusel, (f) reporte de motores de imagen sin gastar nada. (g, opcional) tipo 2 de verdad
con el motor gratis que haya (codex gasta cuota de ChatGPT Plus, no dinero): solo con --con-imagen.

  python pruebas\\carruseles\\prueba_carruseles.py [a b c d e f] [--con-imagen]

La memoria de marca de la prueba vive en una carpeta temporal (GROWI_CARRUSELES_DATOS): la real no se toca.
Evidencia: pruebas\\evidencia\\carruseles\\ (JSON por punto, PNG, reportes y resumen.md).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "skills" / "carruseles" / "scripts"
BRIEFS = Path(__file__).resolve().parent / "briefs"
EVID = RAIZ / "pruebas" / "evidencia" / "carruseles"
TRABAJO = Path(tempfile.gettempdir()) / "prueba-carruseles"
os.environ["GROWI_CARRUSELES_DATOS"] = str(TRABAJO / "datos")
sys.path.insert(0, str(SCRIPTS))

from PIL import Image, ImageDraw  # noqa: E402

import carrusel  # noqa: E402
import motores  # noqa: E402
from comun import escribir_json  # noqa: E402
from qc import qc_carpeta, resumen  # noqa: E402

RESULTADOS = {}


def py(*args, timeout=900):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, env=os.environ.copy())
    return r.returncode, r.stdout + r.stderr


def tira(carpeta, destino, ancho=360):
    ps = sorted(Path(carpeta).glob("lamina-*.png"))
    ps = [p for p in ps if ".sin-texto" not in p.name]
    alto = int(ancho * 1350 / 1080)
    h = Image.new("RGB", ((ancho + 10) * len(ps), alto), "white")
    for i, p in enumerate(ps):
        h.paste(Image.open(p).convert("RGB").resize((ancho, alto)), (i * (ancho + 10), 0))
    h.save(destino)


def anotar(clave, ok, **datos):
    RESULTADOS[clave] = {"ok": ok, **datos}
    escribir_json(EVID / f"{clave}.json", RESULTADOS[clave])
    print(f"({clave}) {'OK' if ok else 'FALLA'}  {datos.get('resumen', '')}", flush=True)


def prueba_a():
    sal = TRABAJO / "a"
    r = carrusel.generar(json.loads((BRIEFS / "a-summit-5.json").read_text(encoding="utf-8")), sal)
    pngs = sorted(sal.glob("lamina-*.png"))
    tam = {p.name: Image.open(p).size for p in pngs}
    fuera = [e for x in r["qc"]["laminas"] for e in x["rechazos"]]
    ok = r["estado"] == "listo" and len(pngs) == 5 and all(s == (1080, 1350) for s in tam.values()) and not fuera
    for p in pngs:
        shutil.copyfile(p, EVID / f"a-{p.name}")
    shutil.copyfile(sal / "reporte.md", EVID / "a-reporte.md")
    tira(sal, EVID / "a-tira.png")
    anotar("a", ok, resumen=f"{r['estado']}, {len(pngs)} PNG {set(tam.values())}, {r['segundos']} s",
           tamanos=tam, checks=[x["checks"] for x in r["qc"]["laminas"]], avisos=r["avisos"])


def prueba_b():
    """Sabotajes sobre una copia del carrusel (a): texto cortado (lámina 3), texto fuera de pantalla (lámina 2)."""
    origen, sal = TRABAJO / "a", TRABAJO / "b-saboteado"
    shutil.rmtree(sal, ignore_errors=True)
    shutil.copytree(origen, sal)
    for n, css in ((3, ".cue{height:40px!important}"), (2, ".tit{left:700px!important}")):
        h = sal / f"lamina-{n:02d}.html"
        h.write_text(h.read_text(encoding="utf-8").replace("</style>", css + "</style>"), encoding="utf-8")
    q = qc_carpeta(sal)
    por = {x["lamina"]: x for x in q["laminas"]}
    cortada = any(r.startswith("texto cortado") for r in por[3]["rechazos"])
    fuera = any("fuera de pantalla" in r or "recortado" in r for r in por[2]["rechazos"])
    sanas = all(por[n]["ok"] for n in (1, 4, 5))
    ok = not q["ok"] and cortada and fuera and sanas and (sal / "lamina-03.RECHAZADA.png").is_file()
    shutil.copyfile(sal / "lamina-03.RECHAZADA.png", EVID / "b-lamina-03.RECHAZADA.png")
    shutil.copyfile(sal / "lamina-02.RECHAZADA.png", EVID / "b-lamina-02.RECHAZADA.png")
    control = qc_carpeta(origen)
    anotar("b", ok and control["ok"], resumen=f"saboteado: {q['laminas_ok']}/5 OK (2 y 3 rechazadas); "
           f"control sin sabotaje: {'OK' if control['ok'] else 'FALLA'}", diagnostico=resumen(q),
           rechazos_2=por[2]["rechazos"], rechazos_3=por[3]["rechazos"])


def prueba_c():
    sal = TRABAJO / "c-lote"
    shutil.rmtree(sal, ignore_errors=True)
    t = time.time()
    rc, out = py(SCRIPTS / "lote.py", "--briefs", BRIEFS / "lote", "--salida", sal)
    lote = json.loads((sal / "lote.json").read_text(encoding="utf-8"))
    ok = rc == 0 and len(lote["carruseles"]) == 3 and all(c["estado"] == "listo" for c in lote["carruseles"])
    shutil.copyfile(sal / "lote.md", EVID / "c-lote.md")
    for c in lote["carruseles"]:
        tira(c["carpeta"], EVID / f"c-{c['id']}.png", ancho=240)
    anotar("c", ok, resumen=f"rc={rc}, {sum(c['estado'] == 'listo' for c in lote['carruseles'])}/3 listos en "
           f"{round(time.time() - t, 1)} s", carruseles=lote["carruseles"])


VERDE = (0, 200, 83)


def fotos_sinteticas(carpeta):
    """3 fotos de prueba con proporciones distintas y un círculo verde: si la composición deforma, el círculo sale óvalo."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, (w, h) in (("1-vertical.png", (3000, 4000)), ("2-horizontal.png", (4000, 2250)),
                           ("3-cuadrada.png", (2000, 2000))):
        im = Image.new("RGB", (w, h), (214, 205, 190))
        d = ImageDraw.Draw(im)
        for x in range(0, w, max(w, h) // 20):
            d.line([(x, 0), (x, h)], fill=(190, 180, 165), width=6)
        r = int(min(w, h) * 0.15)
        cx, cy = w // 2, int(h * 0.3)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=VERDE)
        d.text((40, h - 80), "FOTO DE PRUEBA SINTETICA", fill=(60, 60, 60))
        im.save(carpeta / nombre)


def aspecto_circulo(png):
    im = Image.open(png).convert("RGB")
    xs, ys = [], []
    px = im.load()
    for y in range(0, im.height, 2):
        for x in range(0, im.width, 2):
            r, g, b = px[x, y]
            if abs(r - VERDE[0]) < 25 and abs(g - VERDE[1]) < 25 and abs(b - VERDE[2]) < 25:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return round((max(xs) - min(xs) + 2) / (max(ys) - min(ys) + 2), 3)


def prueba_d():
    fotos, sal = TRABAJO / "fotos", TRABAJO / "d-fotos"
    fotos_sinteticas(fotos)
    r = carrusel.generar(json.loads((BRIEFS / "d-fotos.json").read_text(encoding="utf-8")), sal, fotos=str(fotos))
    aspectos = {n: aspecto_circulo(sal / f"lamina-{n:02d}.png") for n in (1, 2, 3)
                if (sal / f"lamina-{n:02d}.png").is_file()}
    checks = [c for x in r["qc"]["laminas"] for c in x["checks"] if c.startswith("foto")]
    ok_fotos = len(aspectos) == 3 and all(a is not None and abs(a - 1) <= 0.03 for a in aspectos.values())
    # control: forzar object-fit:fill en la lámina 2 tiene que dar «foto deformada»
    sab = TRABAJO / "d-saboteado"
    shutil.rmtree(sab, ignore_errors=True)
    shutil.copytree(sal, sab)
    h = sab / "lamina-02.html"
    h.write_text(h.read_text(encoding="utf-8").replace("</style>", ".foto{object-fit:fill!important}</style>"),
                 encoding="utf-8")
    q = qc_carpeta(sab)
    deformada = [x for x in q["laminas"][1]["rechazos"] if x.startswith("foto deformada")]
    for n in (1, 2, 3):
        shutil.copyfile(sal / f"lamina-{n:02d}.png", EVID / f"d-lamina-{n:02d}.png")
    tira(sal, EVID / "d-tira.png")
    shutil.copyfile(sal / "reporte.md", EVID / "d-reporte.md")
    anotar("d", r["estado"] == "listo" and ok_fotos and bool(deformada),
           resumen=f"{r['estado']}; círculo ancho/alto por lámina {aspectos} (1,00 = sin deformar); "
           f"sabotaje object-fit:fill -> {deformada[:1]}", checks=checks, avisos=r["avisos"])


def prueba_e():
    datos_e = TRABAJO / "datos-e"
    shutil.rmtree(datos_e, ignore_errors=True)
    os.environ["GROWI_CARRUSELES_DATOS"] = str(datos_e)  # para marca.py (subproceso)
    import comun
    marcas_antes = comun.MARCAS
    comun.MARCAS = datos_e / "marcas"  # para cargar_marca (en este proceso)
    try:
        largo = json.loads((BRIEFS / "e-largo.json").read_text(encoding="utf-8"))
        antes = carrusel.generar(largo, TRABAJO / "e-1-antes")
        rc, out = py(SCRIPTS / "marca.py", "corregir", "--marca", "summit-maker", "máximo 12 palabras por lámina")
        despues = carrusel.generar(largo, TRABAJO / "e-2-despues")
        corto = carrusel.generar(json.loads((BRIEFS / "e-corto.json").read_text(encoding="utf-8")), TRABAJO / "e-3-corto")
        rc2, out2 = py(SCRIPTS / "marca.py", "corregir", "--marca", "summit-maker", "siempre el RIF en la última")
        rif = carrusel.generar(json.loads((BRIEFS / "e-corto.json").read_text(encoding="utf-8")), TRABAJO / "e-4-rif")
    finally:
        os.environ["GROWI_CARRUSELES_DATOS"] = str(TRABAJO / "datos")
        comun.MARCAS = marcas_antes
    rech_despues = [x for l in despues["qc"]["laminas"] for x in l["rechazos"]]
    rif_rech = rif.get("qc", {}).get("carrusel", {}).get("rechazos", [])
    ok = (antes["estado"] == "listo" and rc == 0 and despues["estado"] == "rechazado por QC"
          and any("máximo 12" in x for x in rech_despues) and corto["estado"] == "listo"
          and any("max_palabras_lamina = 12" in x for x in corto["marca_aplicada"])
          and any("RIF" in x and "PENDIENTE" in x for x in rif_rech))
    for nombre, r in (("1-antes", antes), ("2-despues", despues), ("3-corto", corto), ("4-rif", rif)):
        shutil.copyfile(TRABAJO / f"e-{nombre}" / "reporte.md", EVID / f"e-{nombre}-reporte.md")
    anotar("e", ok, resumen=f"antes: {antes['estado']}; corrección guardada (rc={rc}); mismo brief: {despues['estado']} "
           f"({rech_despues[:1]}); reescrito: {corto['estado']} con {corto['marca_aplicada']}; «siempre el RIF»: "
           f"{rif['estado']} ({rif_rech[:1]})", salida_marca=out.strip(), salida_marca_rif=out2.strip())


def prueba_f():
    t = time.time()
    rep = motores.detectar()
    txt = motores.texto(rep)
    (EVID / "f-motores.txt").write_text(txt, encoding="utf-8")
    pago_activado = [m["id"] for m in rep["motores"] if m["tipo"] == "pago" and m["disponible"]]
    elegido = rep["elegido"]
    tipo_elegido = next((m["tipo"] for m in rep["motores"] if m["id"] == elegido), None)
    # el tipo 2 con un motor que no está tiene que bloquearse y reportar, no buscar uno de pago
    b = json.loads((BRIEFS / "g-generada.json").read_text(encoding="utf-8"))
    b["motor"] = "a1111"
    bloq = carrusel.generar(b, TRABAJO / "f-bloqueado")
    try:
        motores.elegir(rep["motores"], "api-gemini_api_key")
        rechaza_pago = False
    except RuntimeError:
        rechaza_pago = True
    shutil.copyfile(TRABAJO / "f-bloqueado" / "reporte.md", EVID / "f-bloqueado-reporte.md")
    ok = not pago_activado and tipo_elegido in (None, "local", "suscripción") and bloq["estado"] == "bloqueado" \
        and rechaza_pago
    anotar("f", ok, resumen=f"elegido: {elegido} ({tipo_elegido}); motores de pago activos: {pago_activado or 'ninguno'}; "
           f"tipo 2 sin motor -> {bloq['estado']}; pedir uno de pago -> rechazado={rechaza_pago}; "
           f"{round(time.time() - t, 1)} s, $0", reporte=txt)


def prueba_g():
    r = carrusel.generar(json.loads((BRIEFS / "g-generada.json").read_text(encoding="utf-8")), TRABAJO / "g-generada")
    if (TRABAJO / "g-generada" / "lamina-01.png").is_file():
        shutil.copyfile(TRABAJO / "g-generada" / "lamina-01.png", EVID / "g-lamina-01.png")
    tira(TRABAJO / "g-generada", EVID / "g-tira.png")
    shutil.copyfile(TRABAJO / "g-generada" / "reporte.md", EVID / "g-reporte.md")
    anotar("g", r["estado"] == "listo", resumen=f"{r['estado']}; motor {r.get('motor_imagen')}; "
           f"{r.get('imagenes')}", avisos=r.get("avisos"))


def main():
    pedidas = [a for a in sys.argv[1:] if not a.startswith("--")] or list("abcdef")
    if "--con-imagen" in sys.argv and "g" not in pedidas:
        pedidas.append("g")
    EVID.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    if any(p in pedidas for p in "b") and not (TRABAJO / "a" / "carrusel.json").is_file() and "a" not in pedidas:
        pedidas.insert(0, "a")
    for p in pedidas:
        try:
            globals()[f"prueba_{p}"]()
        except Exception as e:  # noqa: BLE001
            anotar(p, False, resumen=f"{type(e).__name__}: {e}")
    lineas = ["# Verificación skill carruseles", "", f"{time.strftime('%Y-%m-%d %H:%M')}, en este PC.", ""]
    lineas += [f"- ({k}) {'OK' if v['ok'] else 'FALLA'}: {v.get('resumen', '')}" for k, v in RESULTADOS.items()]
    (EVID / f"resumen-{''.join(pedidas)}.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    sys.exit(0 if all(v["ok"] for v in RESULTADOS.values()) else 1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

"""Verificación de la skill edicion-video (t-skill-edicion-video-060) en este PC, con los crudos de
generar_crudos.py (sintéticos: voz SAPI con pausas, muletillas y tomas repetidas). Evidencia en
pruebas/evidencia/edicion-video/.

  (a) edición completa de un reel (crudo1, estilo reel-ganchos, director claude = 1 llamada a haiku)
  (b) el QC rechaza un render saboteado: subtítulos fuera de pantalla y audio desfasado 250 ms
  (c) lote de 3 vídeos sin intervención (talking-head-limpio, director reglas)
  (d) costo estimado antes del render en cada vídeo
  (e) una corrección de marca se guarda y se aplica en el siguiente vídeo
  (f) repurposing: 2 clips + 1 post desde el vídeo largo

  python pruebas/video/prueba_edicion_video.py [a b c d e f] [--sin-claude]
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SK = REPO / "skills" / "edicion-video" / "scripts"
CRUDOS = REPO / "pruebas" / "video" / "crudos"
OUT = REPO / "pruebas" / "evidencia" / "edicion-video"
TMP = Path(os.environ.get("GV_PRUEBA_DIR") or Path(tempfile.gettempdir()) / "gv-prueba-060")
OCULTO = getattr(subprocess, "CREATE_NO_WINDOW", 0)
sys.path.insert(0, str(SK))
os.environ.setdefault("GROWI_VIDEO_MARCAS", str(TMP / "marcas"))  # la memoria de marca real no se toca

from comun import asegurar_venv  # noqa: E402

asegurar_venv()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
OUT.mkdir(parents=True, exist_ok=True)


def guardar(nombre, d):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{nombre}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def fotos(video, tiempos, dst):
    """Tira de fotogramas (evidencia visual pequeña, 270 px de ancho)."""
    tmp = []
    for i, t in enumerate(tiempos):
        f = OUT / f"_f{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf",
                        "scale=270:-1", str(f)], creationflags=OCULTO, check=True)
        tmp.append(f)
    if len(tmp) == 1:
        shutil.move(str(tmp[0]), str(OUT / dst))
        return
    args = []
    for f in tmp:
        args += ["-i", str(f)]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", f"hstack={len(tmp)}", str(OUT / dst)],
                   creationflags=OCULTO, check=True)
    for f in tmp:
        f.unlink()


def copiar_md(carpeta, nombre):
    for f in ("reporte.md", "cortes.md"):
        if (Path(carpeta) / f).is_file():
            shutil.copy2(Path(carpeta) / f, OUT / f"{nombre}-{f}")


def orden_costo(rep):
    q = [e["que"] for e in rep["eventos"]]
    i = next((k for k, x in enumerate(q) if x.startswith("costo estimado")), None)
    j = next((k for k, x in enumerate(q) if x == "render: inicio"), None)
    return i is not None and j is not None and i < j


def a(con_claude=True):
    from editar import editar
    d = TMP / "a-reel"
    shutil.rmtree(d, ignore_errors=True)
    r = editar(CRUDOS / "crudo1-errores.mp4", d, "reel-ganchos", None, "claude" if con_claude else "reglas")
    copiar_md(d, "a")
    props = json.loads((d / "props.json").read_text(encoding="utf-8")) if (d / "props.json").is_file() else {}
    subs = props.get("subtitulos") or []
    if r.get("final") and Path(r["final"]).is_file():
        fotos(r["final"], [1.0, props["duracion_s"] * 0.45, props["duracion_s"] * 0.8], "a-fotogramas.png")
    ev = {"estado": r["estado"], "director": r["director"], "crudo_s": r["crudo_info"]["duracion"],
          "final_s": r.get("duracion_final_s"), "qc": r.get("qc"), "costo_estimado": r.get("costo_estimado"),
          "costo_real": r.get("costo_real"), "max_palabras_en_pantalla": max((len(g["palabras"]) for g in subs), default=0),
          "grupos_subtitulo": len(subs), "error": r.get("error"),
          "pasos": [e["que"] for e in r["eventos"]]}
    ev["ok"] = r["estado"] == "listo" and ev["max_palabras_en_pantalla"] <= 3 and ev["final_s"] < ev["crudo_s"]
    guardar("a", ev)
    return ev


def b():
    import render
    from qc import qc
    base = TMP / "a-reel"
    if not (base / "final.mp4").is_file():
        return {"ok": False, "error": "falta el reel de (a)"}
    d = TMP / "b-sabotaje"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for f in ("editado.mp4", "props.json"):
        shutil.copy2(base / f, d / f)
    props = json.loads((d / "props.json").read_text(encoding="utf-8"))
    props["estilo"]["y_pct"] = 1.12  # sabotaje 1: subtítulos por debajo del borde
    render.remotion(d, props, d / "final.mp4")
    q1 = qc(d)
    fotos(d / "final.mp4", [props["duracion_s"] * 0.45], "b-saboteado-subtitulos.png")
    props["estilo"]["y_pct"] = json.loads((base / "props.json").read_text(encoding="utf-8"))["estilo"]["y_pct"]
    (d / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    # sabotaje 2: el reel bueno con el audio retrasado 250 ms de verdad (silencio al principio)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base / "final.mp4"), "-af", "adelay=250:all=1",
                    "-c:v", "copy", "-c:a", "aac", "-t", str(props["duracion_s"]), str(d / "final-audio-corrido.mp4")],
                   creationflags=OCULTO, check=True)
    q2 = qc(d, d / "final-audio-corrido.mp4")
    # sabotaje 3: mismo audio, pero el contenedor dice que empieza 250 ms tarde (-itsoffset)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base / "final.mp4"), "-itsoffset", "0.25", "-i",
                    str(base / "final.mp4"), "-map", "0:v", "-map", "1:a", "-c", "copy",
                    str(d / "final-contenedor-corrido.mp4")], creationflags=OCULTO, check=True)
    q4 = qc(d, d / "final-contenedor-corrido.mp4")
    q3 = qc(base)  # el bueno sigue pasando
    ev = {"subtitulos_fuera": q1, "audio_corrido": q2, "contenedor_corrido": q4, "control_bueno": q3}
    sub = next(c for c in q1["checks"] if c["nombre"] == "subtítulos en pantalla")
    aud = next(c for c in q2["checks"] if c["nombre"] == "audio sincronizado")
    aud4 = next(c for c in q4["checks"] if c["nombre"] == "audio sincronizado")
    ev["ok"] = (not q1["ok"] and not sub["ok"] and not q2["ok"] and not aud["ok"] and not q4["ok"]
                and not aud4["ok"] and q3["ok"])
    guardar("b", ev)
    return ev


def c():
    from lote import lote
    d = TMP / "c-lote"
    shutil.rmtree(d, ignore_errors=True)
    t0 = time.time()
    r = lote([CRUDOS / "crudo1-errores.mp4", CRUDOS / "crudo2-luz.mp4", CRUDOS / "crudo3-ganchos.mp4"], d,
             "talking-head-limpio")
    shutil.copy2(d / "lote.md", OUT / "c-lote.md")
    reportes = sorted(str(p) for p in d.glob("*/reporte.md"))
    ev = {"listos": r["listos"], "videos": r["videos"], "reportes_por_video": reportes,
          "segundos": round(time.time() - t0, 1)}
    ev["ok"] = r["listos"] == 3 and len(reportes) == 3
    guardar("c", ev)
    return ev


def d_costo():
    filas = []
    for rep in sorted(TMP.glob("**/reporte.json")):
        r = json.loads(rep.read_text(encoding="utf-8"))
        if r.get("estado") in ("listo", "rechazado por QC"):
            filas.append({"video": str(rep.parent), "costo_estimado": (r.get("costo_estimado") or {}).get("resumen"),
                          "antes_del_render": orden_costo(r), "costo_real": r.get("costo_real")})
    ev = {"videos": filas, "ok": bool(filas) and all(f["antes_del_render"] and f["costo_estimado"] for f in filas)}
    guardar("d", ev)
    return ev


def e():
    import marca as mk
    from editar import editar
    nombre = "prueba-060"
    (TMP / "marcas").mkdir(parents=True, exist_ok=True)
    (Path(os.environ["GROWI_VIDEO_MARCAS"]) / f"{nombre}.json").unlink(missing_ok=True)
    antes = TMP / "c-lote" / "02-crudo2-luz"
    texto = "El resalte en #00E5A0, el fondo de la caja en #101820 y quita la muletilla «justo»"
    m, cambios = mk.corregir(nombre, texto)
    d = TMP / "e-marca"
    shutil.rmtree(d, ignore_errors=True)
    r = editar(CRUDOS / "crudo2-luz.mp4", d, "talking-head-limpio", nombre)
    copiar_md(d, "e")
    props = json.loads((d / "props.json").read_text(encoding="utf-8"))
    pal_d = [w["texto"].lower() for g in props["subtitulos"] for w in g["palabras"]]
    pal_a = [w["texto"].lower() for g in json.loads((antes / "props.json").read_text(encoding="utf-8"))["subtitulos"]
             for w in g["palabras"]] if (antes / "props.json").is_file() else []
    if r.get("final") and Path(r["final"]).is_file():
        fotos(r["final"], [props["duracion_s"] * 0.3], "e-con-marca.png")
    if (antes / "final.mp4").is_file():
        fotos(antes / "final.mp4", [props["duracion_s"] * 0.3], "e-sin-marca.png")
    ev = {"correccion": texto, "cambios_entendidos": cambios, "marca_guardada": m,
          "marca_aplicada_en_el_reporte": r.get("marca_aplicada"), "estado": r["estado"],
          "estilo_render": props["estilo"], "justo_antes": "justo" in pal_a, "justo_despues": "justo" in pal_d}
    ev["ok"] = (r["estado"] == "listo" and props["estilo"]["color_activo"] == "#00E5A0"
                and props["estilo"]["fondo"] == "#101820" and not ev["justo_despues"] and ev["justo_antes"])
    guardar("e", ev)
    return ev


def f():
    from repurposing import repurposing
    d = TMP / "f-repurposing"
    shutil.rmtree(d, ignore_errors=True)
    r = repurposing(CRUDOS / "largo-podcast.mp4", d, 2)
    shutil.copy2(d / "post.md", OUT / "f-post.md")
    for c in r["clips"]:
        if c.get("final") and Path(c["final"]).is_file():
            fotos(c["final"], [0.8, 4.0], f"f-clip{c['n']}.png")
    ev = {"clips": r["clips"], "post": (d / "post.md").read_text(encoding="utf-8")}
    ev["ok"] = len([c for c in r["clips"] if c["estado"] == "listo"]) >= 2 and len(ev["post"].strip()) > 40
    guardar("f", ev)
    return ev


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    pasos = args or ["a", "b", "c", "d", "e", "f"]
    res = {}
    for p in pasos:
        t0 = time.time()
        fn = {"a": lambda: a("--sin-claude" not in sys.argv), "b": b, "c": c, "d": d_costo, "e": e, "f": f}[p]
        try:
            ev = fn()
        except Exception as ex:  # noqa: BLE001
            import traceback
            ev = {"ok": False, "error": traceback.format_exc()}
            guardar(p, ev)
        res[p] = {"ok": ev.get("ok"), "segundos": round(time.time() - t0, 1)}
        print(p, json.dumps(res[p]), flush=True)
    print("RESULTADO", json.dumps(res))
    sys.exit(0 if all(v["ok"] for v in res.values()) else 1)

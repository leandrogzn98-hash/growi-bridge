"""Prueba de Blender como herramienta del runner (ESTADO-BLENDER-HERRAMIENTA.md).

Copia aislada de growi-bridge.py en %TEMP% (share y cola propios). Las
plantillas se COPIAN (lectura) de la app instalada a skills\\blender\\ de la
copia, y el modelo de prueba (un .glb real) a una carpeta de proyecto
temporal. Dos tareas reales por el runner (_process_one_impl):
«tornamesa de <glb>» y «QC de <glb>». Blender corre de verdad.

  python pruebas/prueba_blender.py [ruta.glb]
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALADA = Path.home() / "growi-bridge"


def main():
    glb = Path(sys.argv[1]) if len(sys.argv) > 1 else INSTALADA / "share" / "outbox" / "volante.glb"
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-blender-"))
    app, proy = tmp / "app", tmp / "proyecto"
    (app / "skills" / "blender").mkdir(parents=True)
    proy.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    for f in ("template_turntable.py", "template_qc_views.py"):
        shutil.copy2(INSTALADA / "skills" / "blender" / f, app / "skills" / "blender" / f)
    shutil.copy2(glb, proy / glb.name)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(proy)]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"))
    spec = importlib.util.spec_from_file_location("gb_blender", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    gb._approval_needed = lambda task: None
    ev = {"copia": str(tmp), "modelo": glb.name}
    ev["a_ficha"] = gb.herramienta_ficha(fresca=True)
    ev["a_no_es_motor"] = {"motores_en_engines_json": gb.engine_ids(), "blender_en_selector": "blender" in gb.engine_ids()}
    casos = [("b-tornamesa", f"Haz una tornamesa de {glb.name} para revisarla", {"frames": 8}),
             ("c-qc", f"QC de {glb.name}: vistas de control para revisar los flancos", None)]
    for tid, prompt, extra in casos:
        task = {"id": tid, "prompt": prompt, "motor": "claude", "cwd": str(proy), "timeout_min": 20,
                "revisar": False}
        if extra:
            task["herramienta"] = {"operacion": "turntable", "modelo": glb.name, **extra}
        tf = gb.TASKS / f"{tid}.task.json"
        tf.write_text(json.dumps(task), encoding="utf-8")
        gb._process_one_impl(tf)
        res = json.loads((gb.RESULTS / f"{tid}.result.json").read_text(encoding="utf-8"))
        ev[tid] = {k: res.get(k) for k in ("status", "motor", "error", "exit_code", "cost_usd", "duration_s",
                                           "herramienta", "result")} | {
            "imagenes": [Path(p).name for p in res.get("archivos") or []],
            "carpeta_salida": str(Path((res.get("archivos") or [""])[0]).parent) if res.get("archivos") else None}
    # (d) sin Blender: la ficha dice «no disponible» con el motivo, y la tarea falla diciendo por qué
    gb._blender_buscar = lambda: None
    ev["d_ficha_sin_blender"] = gb.herramienta_ficha(fresca=True)
    task = {"id": "d-sin-blender", "prompt": f"tornamesa de {glb.name}", "motor": "claude", "cwd": str(proy),
            "timeout_min": 5, "revisar": False}
    (gb.TASKS / "d-sin-blender.task.json").write_text(json.dumps(task), encoding="utf-8")
    gb._process_one_impl(gb.TASKS / "d-sin-blender.task.json")
    ev["d_tarea_sin_blender"] = {k: json.loads((gb.RESULTS / "d-sin-blender.result.json").read_text(
        encoding="utf-8")).get(k) for k in ("status", "error")}
    ev["log"] = [x for x in gb.LOG_FILE.read_text(encoding="utf-8").splitlines() if "herramienta" in x.lower()][-8:]
    out = REPO / "pruebas" / "evidencia" / "blender"
    out.mkdir(parents=True, exist_ok=True)
    for tid in ("b-tornamesa", "c-qc"):  # 2 imagenes de muestra de cada una
        for p in ([Path(ev[tid]["carpeta_salida"]) / n for n in ev[tid]["imagenes"]] if ev[tid]["carpeta_salida"] else [])[:5]:
            if tid == "c-qc" or p.name.endswith(("0001.png", "0003.png")):
                shutil.copy2(p, out / f"{tid}-{p.name}")
    (out / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1), flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()

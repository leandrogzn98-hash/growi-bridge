"""Prueba del pronostico de gasto (ESTADO-GASTO-PRONOSTICO.md).

Copia aislada. Los 7 dias de historia son .result.json de PRUEBA (con su
.task.json archivado: carpeta = proyecto) escritos con fechas de los dias
anteriores; una tarea mas pasa por el runner real (motor falso con costo).
La tarjeta Gasto se dibuja de verdad (Tk) y se leen sus textos.

  python pruebas/prueba_gasto_pronostico.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def falso():
    c = float(os.environ.get("FAKE_COSTO", "0.4"))
    for ev in ({"type": "system", "subtype": "init", "session_id": "f", "model": "falso"},
               {"type": "result", "subtype": "success", "is_error": False, "result": "hecho",
                "total_cost_usd": c, "num_turns": 1, "session_id": "f"}):
        print(json.dumps(ev), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-pron-"))
    app = tmp / "app"
    app.mkdir()
    proys = {n: tmp / "proyectos" / n for n in ("Aqualine", "Summit Maker", "HAYAI")}
    for p in proys.values():
        p.mkdir(parents=True)
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(tmp / "proyectos")]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"))
    spec = importlib.util.spec_from_file_location("gb_pron", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX, gb.DONE):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    gb._claude_plan = lambda: "max"
    toasts = []
    gb.toast = lambda t, c=None: toasts.append(t)
    gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [sys.executable, str(Path(__file__).resolve()),
                                                                       "--falso"]
    gb._swap_args = lambda c, old, new: list(c)
    gb._approval_needed = lambda task: None
    ahora = datetime.now().astimezone()
    # historia de prueba: 6 dias anteriores, 2 proyectos con claude (equiv) y uno local
    n = 0
    for dias_atras in range(1, 7):
        for proy, costo, motor in (("Aqualine", 0.20, "claude"), ("Summit Maker", 0.10, "claude"),
                                   ("Summit Maker", None, "llama")):
            n += 1
            tid = f"hist-{n}"
            ts = (ahora - timedelta(days=dias_atras)).replace(hour=12).timestamp()
            (gb.DONE / f"{tid}.task.json").write_text(json.dumps({"id": tid, "cwd": str(proys[proy])}),
                                                      encoding="utf-8")
            rf = gb.RESULTS / f"{tid}.result.json"
            rf.write_text(json.dumps({"id": tid, "motor": motor, "modelo": "sonnet" if motor == "claude" else "hermes",
                                      "cost_usd": costo, "status": "ok",
                                      "finished_at": datetime.fromtimestamp(ts).astimezone().isoformat()}),
                          encoding="utf-8")
            os.utime(rf, (ts, ts))
    ev = {"copia": str(tmp)}
    # una tarea real por el runner, en la carpeta HAYAI, con un freno dicho en el encargo
    os.environ["FAKE_COSTO"] = "0.90"
    task = {"id": "hoy-hayai", "prompt": "Prepara el resumen de HAYAI. No gastes más de $0.50 en esto.",
            "motor": "claude", "cwd": str(proys["HAYAI"]), "timeout_min": 5, "revisar": False}
    t_val, _ = gb.validate_task(task)
    ev["freno_leido_del_encargo"] = t_val["presupuesto_max_usd"]
    (gb.TASKS / "hoy-hayai.task.json").write_text(json.dumps(task), encoding="utf-8")
    gb._process_one_impl(gb.TASKS / "hoy-hayai.task.json")
    res = json.loads((gb.RESULTS / "hoy-hayai.result.json").read_text(encoding="utf-8"))
    fam = gb.load_family("hoy-hayai") or {}
    ev["tarea_real"] = {"proyecto_en_el_resultado": res.get("proyecto"), "costo": res.get("cost_usd"),
                        "estado": fam.get("estado"), "reporte": fam.get("reporte")}
    filas = gb.gasto_7dias()
    ev["b_por_proyecto_7d"] = {k: {kk: (sorted(v) if isinstance(v, set) else round(v, 2) if isinstance(v, float)
                                        else v) for kk, v in x.items()}
                               for k, x in gb.gasto_por_proyecto_7d(filas).items()}
    ev["a_pronostico_sin_limite"] = gb.pronostico_semana(filas=filas)
    for lim in (50.0, 2.0):
        s = gb.load_settings()
        s["aviso_cuota_semanal_usd"] = lim
        gb.save_settings(s)
        ev[f"a_pronostico_limite_{lim:g}"] = gb.pronostico_semana(filas=filas)["texto"]
    ev["c_pico"] = gb._pronostico_avisar()
    gb._pronostico_avisar()  # segunda vez el mismo dia: no repite el aviso
    ev["c_avisos"] = toasts
    # la tarjeta Gasto de verdad
    root = tk.Tk()
    root.withdraw()
    gb._root = root
    marco = tk.Frame(root)
    gb._build_spend_card(marco)
    gb._SP.update(data=gb.spend_summary(), at=time.time())
    gb._render_spend()
    ev["d_tarjeta"] = {k: gb._widgets[k].cget("text") for k in ("sp_pron", "sp_pico", "sp_7d", "sp_real", "sp_equiv",
                                                                "sp_local")}
    out = REPO / "pruebas" / "evidencia" / "gasto-pronostico"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str), flush=True)
    os._exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--falso":
        falso()
    else:
        main()

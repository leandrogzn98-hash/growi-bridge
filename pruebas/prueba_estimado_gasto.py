"""Prueba del estimado de gasto (ESTADO-ESTIMADO-GASTO.md).

Copia aislada de growi-bridge.py; tareas por el runner real
(_process_one_impl y el bucle runner_loop). El motor es un claude falso que
contesta «hecho» y declara un costo (FAKE_COSTO); si FAKE_FALLA=1, falla con
un error de red (transitorio).

  python pruebas/prueba_estimado_gasto.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def falso():
    if os.environ.get("FAKE_FALLA") == "1":
        print("connection reset by peer: network error", file=sys.stderr)
        sys.exit(1)
    c = float(os.environ.get("FAKE_COSTO", "0.08"))
    for ev in ({"type": "system", "subtype": "init", "session_id": "f", "model": "falso"},
               {"type": "result", "subtype": "success", "is_error": False, "result": "hecho",
                "total_cost_usd": c, "num_turns": 1, "session_id": "f"}):
        print(json.dumps(ev), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-gasto-"))
    app, work = tmp / "app", tmp / "trabajo"
    app.mkdir()
    work.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "delicado", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work)]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"))
    spec = importlib.util.spec_from_file_location("gb_gasto", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX, gb.WAITING, gb.DONE):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    orig_cmd = gb._build_cli_cmd
    gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [sys.executable, str(Path(__file__).resolve()),
                                                                       "--falso"]
    gb._swap_args = lambda c, old, new: list(c)
    gb._ui_call = lambda fn: None
    ev = {"copia": str(tmp)}

    def tarea(tid, prompt, **extra):
        t = {"id": tid, "prompt": prompt, "motor": "claude", "cwd": str(work), "timeout_min": 5, "revisar": False}
        t.update(extra)
        (gb.TASKS / f"{tid}.task.json").write_text(json.dumps(t), encoding="utf-8")
        return gb.TASKS / f"{tid}.task.json"

    # (a)+(e) estimado sin historico: tarea corta con sonnet
    t_corta, _ = gb.validate_task({"id": "a-corta", "prompt": "Resume en 3 líneas qué es Growi Bridge.", "motor": "claude",
                                   "modelo": "sonnet", "cwd": str(work)})
    est = gb.estimar_gasto(t_corta)
    ev["a_estimado_corta"] = {k: est[k] for k in ("tokens_entrada", "como_se_conto", "tipo", "reserva_salida",
                                                  "una_ronda", "revision", "peor_caso", "dinero", "calibrado",
                                                  "rango", "texto")}
    # (b) umbral: con «solo lo delicado», la corta corre sin preguntar; una enorme con opus pide aprobación
    gb._process_one_impl(tarea("b-corta", "Resume en 3 líneas qué es Growi Bridge.", modelo="sonnet"))
    fam = gb.load_family("b-corta") or {}
    ev["b_corta"] = {"estado": fam.get("estado"), "estimado_guardado_antes": fam.get("estimado"),
                     "esperando": (gb.WAITING / "b-corta.task.json").exists()}
    grande = "Escribe un documento largo con el análisis completo de este material.\n" + ("dato " * 18000)
    gb._process_one_impl(tarea("b-grande", grande, modelo="opus"))
    t_g, err_g = gb.validate_task({"id": "b-grande-x", "prompt": grande, "motor": "claude", "modelo": "opus",
                                   "cwd": str(work)})
    need = gb._approval_needed(t_g) if t_g else {"motivo": f"validate_task: {err_g}"}
    ev["b_grande"] = {"aparcada_esperando_aprobacion": (gb.WAITING / "b-grande.task.json").exists(),
                      "accion": [a for a in (need or {}).get("acciones", []) if a["tipo"] == "gasto_estimado"],
                      "motivo_en_la_tarjeta": (need or {}).get("motivo", "")[:700]}
    # (c) tope por tarea: presupuesto $0.05, el motor declara $0.08
    os.environ["FAKE_COSTO"] = "0.08"
    gb._process_one_impl(tarea("c-tope", "Haz algo pequeño.", modelo="sonnet", presupuesto_max_usd=0.05))
    fam = gb.load_family("c-tope") or {}
    ev["c_tope"] = {"estado": fam.get("estado"), "reporte": fam.get("reporte"), "costo_familia": fam.get("costo_usd")}
    t_c, _ = gb.validate_task({"id": "c-cmd", "prompt": "x", "motor": "claude", "cwd": str(work),
                               "presupuesto_max_usd": 0.5})
    ev["c_comando_claude"] = orig_cmd(t_c, "claude", gb.get_engine("claude"), "hola")
    # (c) circuit breaker con el bucle real del runner
    os.environ["FAKE_FALLA"] = "1"
    for i in range(3):
        gb.breaker_apuntar({"status": "error", "error": "connection reset by peer"}, True)
    ev["c_breaker_tras_3_fallos"] = dict(gb._BREAKER)
    os.environ["FAKE_FALLA"] = "0"
    tarea("c-en-pausa", "Esta no debe correr mientras la cola está en pausa.", modelo="sonnet")
    stop = threading.Event()
    th = threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True)
    th.start()
    time.sleep(12)
    ev["c_en_pausa_no_corrio"] = not (gb.RESULTS / "c-en-pausa.result.json").exists()
    ev["c_reset_antes_de_10_min"] = gb.breaker_reset()
    ev["c_reset"] = gb.breaker_reset("prueba")
    for _ in range(60):
        if (gb.RESULTS / "c-en-pausa.result.json").exists():
            break
        time.sleep(1)
    stop.set()
    ev["c_tras_reset_corrio"] = (gb.RESULTS / "c-en-pausa.result.json").exists()
    # (d) costo por tarea completada: una fallida suma su costo pero no cuenta como completada
    os.environ["FAKE_FALLA"] = "0"
    gb._family_update("d-fallida", motor="claude", estado="fallida", sumar_costo=0.30)
    ev["d_costo_por_tarea_completada"] = gb.costo_por_tarea_completada()
    # (e) calibrado: 6 resultados historicos de claude (datos de prueba) -> rango real
    for i, c in enumerate((0.21, 0.28, 0.33, 0.36, 0.40, 0.52)):
        (gb.RESULTS / f"hist-{i}.result.json").write_text(json.dumps({"id": f"hist-{i}", "motor": "claude",
                                                                      "cost_usd": c}), encoding="utf-8")
    est2 = gb.estimar_gasto(t_corta)
    ev["e_calibrado"] = {k: est2[k] for k in ("calibrado", "historico", "rango", "texto")}
    ev["log"] = [x for x in gb.LOG_FILE.read_text(encoding="utf-8").splitlines()
                 if "Estimado" in x or "tope" in x or "circuit" in x][-8:]
    out = REPO / "pruebas" / "evidencia" / "estimado-gasto"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str), flush=True)
    os._exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--falso":
        falso()
    else:
        main()

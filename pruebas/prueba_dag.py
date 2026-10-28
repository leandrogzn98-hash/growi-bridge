"""Prueba de los planes con grafo de fases (ESTADO-DAG-FASES.md).

Copia aislada de growi-bridge.py (share y cola.db propios). Los planes pasan
por el runner real (_process_one_impl -> dag_ingestar -> cola -> motor ->
_after_run -> dag_fase_terminada). El motor es un claude falso: contesta
«hecho» y apunta cada fase que corre en un archivo (para contar repeticiones);
si el encargo dice FALLA, sale con error. Revisar: false (lo que se prueba es
el grafo, no el juez).

  python pruebas/prueba_dag.py            todas las pruebas
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def falso():
    prompt = sys.stdin.read() if not sys.stdin.isatty() else ""
    prompt = prompt or " ".join(sys.argv[2:])
    with open(os.environ["DAG_CORRIDAS"], "a", encoding="utf-8") as fh:
        linea = next((x for x in prompt.splitlines() if x.strip().lower().startswith("fase")), prompt[:60])
        fh.write(linea.strip()[:60] + "\n")  # la linea del encargo (la app antepone sus reglas)
    if "FALLA" in prompt:
        print(json.dumps({"type": "result", "subtype": "error", "is_error": True, "result": "falló a propósito"}))
        sys.exit(1)
    for ev in ({"type": "system", "subtype": "init", "session_id": "f", "model": "falso"},
               {"type": "result", "subtype": "success", "is_error": False, "result": "hecho",
                "total_cost_usd": 0, "num_turns": 1, "session_id": "f"}):
        print(json.dumps(ev), flush=True)


def cargar(tmp):
    app = tmp / "app"
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      DAG_CORRIDAS=str(tmp / "corridas.txt"))
    spec = importlib.util.spec_from_file_location("gb_dag", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [
        sys.executable, str(Path(__file__).resolve()), "--falso", prompt]
    gb._swap_args = lambda c, old, new: list(c)
    gb._approval_needed = lambda task: None
    return gb


def preparar():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-dag-"))
    app, work = tmp / "app", tmp / "trabajo"
    app.mkdir()
    work.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work)]}), encoding="utf-8")
    (work / "a.txt").write_text("listo A\n", encoding="utf-8")
    (work / "b.txt").write_text("listo B\n", encoding="utf-8")
    return tmp, work


def plan(gb, pid, fases, work):
    (gb.TASKS / f"{pid}.task.json").write_text(json.dumps({"id": pid, "cwd": str(work), "motor": "claude",
                                                          "revisar": False, "fases": fases}), encoding="utf-8")


def correr_cola(gb, max_n=20):
    orden = []
    for _ in range(max_n):
        fs = sorted(gb.TASKS.glob("*.task.json"), key=lambda p: p.stat().st_mtime)
        if not fs:
            break
        orden.append(fs[0].stem)
        gb._process_one_impl(fs[0])
    return orden


def fases_de(gb, pid):
    return {f["fase_id"]: f["estado"] for f in gb._dag_fases(pid)}


def corridas(tmp):
    p = tmp / "corridas.txt"
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def matar_a_mitad(tmp_s, work_s):
    """Proceso aparte: registra el plan, corre SOLO la primera fase y muere (os._exit)."""
    tmp, work = Path(tmp_s), Path(work_s)
    gb = cargar(tmp)
    gb.cola_init()
    plan(gb, "p-corte", [{"id": "A", "prompt": "fase A del corte"},
                         {"id": "B", "prompt": "fase B del corte", "depende_de": ["A"]},
                         {"id": "C", "prompt": "fase C del corte", "depende_de": ["B"]}], work)
    correr_cola(gb, max_n=2)  # el plan y la fase A
    os._exit(1)  # se mata la app: B queda en cola, C sin arrancar


def main():
    tmp, work = preparar()
    gb = cargar(tmp)
    gb.cola_init()
    ev = {"copia": str(tmp)}
    tip = lambda f, t: {"tipo": "contiene", "archivo": f, "texto": t}  # noqa: E731
    # (a) 3 fases: C depende de A y B (fan-in con validacion tipada)
    plan(gb, "p-orden", [{"id": "A", "prompt": "fase A", "criterios": [tip("a.txt", "listo A")]},
                         {"id": "B", "prompt": "fase B", "criterios": [tip("b.txt", "listo B")]},
                         {"id": "C", "prompt": "fase C (une A y B)", "depende_de": ["A", "B"]}], work)
    gb.dag_ingestar(gb.TASKS / "p-orden.task.json", json.loads((gb.TASKS / "p-orden.task.json").read_text()))
    ev["a_tras_registrar"] = {"fases": fases_de(gb, "p-orden"), "texto": gb.dag_txt("p-orden"),
                              "en_cola": sorted(p.stem for p in gb.TASKS.glob("*.task.json"))}
    ev["a_orden_ejecutado"] = correr_cola(gb)
    ev["a_final"] = {"fases": fases_de(gb, "p-orden"), "plan": gb._dag_plan("p-orden")["estado"],
                     "texto": gb.dag_txt("p-orden")}
    # (b) al_fallar=pedir_decision
    plan(gb, "p-decision", [{"id": "A", "prompt": "fase A ok"},
                            {"id": "B", "prompt": "fase B FALLA", "depende_de": ["A"], "al_fallar": "pedir_decision"},
                            {"id": "C", "prompt": "fase C tras B", "depende_de": ["B"]}], work)
    correr_cola(gb)
    ev["b_pedir_decision"] = {"fases": fases_de(gb, "p-decision"), "plan": gb._dag_plan("p-decision")["estado"],
                              "texto": gb.dag_txt("p-decision")}
    # (c) fan-in con una dependencia fallida
    plan(gb, "p-fanin", [{"id": "A", "prompt": "fase A bien"},
                         {"id": "B", "prompt": "fase B FALLA", "al_fallar": "pedir_decision"},
                         {"id": "C", "prompt": "fase C no debe correr", "depende_de": ["A", "B"]}], work)
    correr_cola(gb)
    ev["c_fanin_dep_fallida"] = {"fases": fases_de(gb, "p-fanin"), "texto": gb.dag_txt("p-fanin"),
                                 "C_corrio": any("no debe correr" in x for x in corridas(tmp))}
    # (c2) fan-in: deps en ok pero su criterio tipado ya no se cumple -> C no arranca
    (work / "b2.txt").write_text("dato\n", encoding="utf-8")
    plan(gb, "p-validacion", [{"id": "A", "prompt": "fase A borra el dato de b2"},
                              {"id": "B", "prompt": "fase B del dato", "criterios": [tip("b2.txt", "dato")]},
                              {"id": "C", "prompt": "fase C valida", "depende_de": ["A", "B"],
                               "al_fallar": "abortar_plan"}], work)
    gb.dag_ingestar(gb.TASKS / "p-validacion.task.json",
                    json.loads((gb.TASKS / "p-validacion.task.json").read_text()))
    correr_cola(gb, max_n=1)  # A
    (work / "b2.txt").write_text("cambiado\n", encoding="utf-8")  # el hecho que B garantizaba ya no se cumple
    correr_cola(gb)
    ev["c2_fanin_validacion"] = {"fases": fases_de(gb, "p-validacion"), "plan": gb._dag_plan("p-validacion")["estado"],
                                 "texto": gb.dag_txt("p-validacion")}
    # (e) ciclo y dependencia rota: rechazados antes de ejecutar
    n_antes = len(corridas(tmp))
    plan(gb, "p-ciclo", [{"id": "A", "prompt": "a", "depende_de": ["B"]},
                         {"id": "B", "prompt": "b", "depende_de": ["A"]}], work)
    plan(gb, "p-rota", [{"id": "A", "prompt": "a", "depende_de": ["Z"]}], work)
    correr_cola(gb)
    ev["e_ciclo"] = json.loads((gb.RESULTS / "p-ciclo.result.json").read_text(encoding="utf-8")).get("reporte")
    ev["e_rota"] = json.loads((gb.RESULTS / "p-rota.result.json").read_text(encoding="utf-8")).get("reporte")
    ev["e_no_se_ejecuto_nada"] = len(corridas(tmp)) == n_antes and gb._dag_plan("p-ciclo") is None
    # (d) matar la app a mitad de un plan y rearrancar
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "--matar", str(tmp), str(work)])
    ev["d_tras_matar"] = {"corridas_del_plan": [x for x in corridas(tmp) if "corte" in x],
                          "en_cola": sorted(p.stem for p in gb.TASKS.glob("p-corte*.task.json"))}
    (gb.TASKS / "p-corte-B.task.json").unlink()  # peor caso: la fase B se perdio de la carpeta
    gb2 = cargar(tmp)  # «rearranque»: modulo nuevo, misma cola.db
    gb2.cola_init()
    gb2.supervisor_arranque()
    ev["d_supervisor"] = gb2.dag_supervisor()
    correr_cola(gb2)
    ev["d_final"] = {"fases": fases_de(gb2, "p-corte"), "plan": gb2._dag_plan("p-corte")["estado"],
                     "corridas_del_plan": [x for x in corridas(tmp) if "corte" in x]}
    # (f) lo que se ve en Tareas: la fila del plan
    ev["f_fila_tareas"] = {pid: (gb2.load_family(pid) or {}).get("reporte") for pid in ("p-orden", "p-decision")}
    ev["log"] = [x for x in gb2.LOG_FILE.read_text(encoding="utf-8").splitlines() if "plan [" in x or
                 "supervisor: plan" in x][-25:]
    out = REPO / "pruebas" / "evidencia" / "dag"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1), flush=True)
    os._exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--falso":
        falso()
    elif len(sys.argv) > 1 and sys.argv[1] == "--matar":
        matar_a_mitad(sys.argv[2], sys.argv[3])
    else:
        main()

"""Prueba de «revisar»: «solo_checks» (ESTADO-REVISION-SOLO-CHECKS.md).

Carga una COPIA de growi-bridge.py del repo en una carpeta temporal (share,
cola y carpetas propias; no toca la app instalada) y pasa tareas reales por
el camino de siempre (_process_one_impl: validacion del task, cola, motor,
_after_run, review_task, <id>.revision.json). El motor y el juez son un
claude falso (este mismo archivo con --falso): el motor contesta «hecho» y el
juez contesta un veredicto JSON valido que aprueba. Se cuentan las llamadas a
_llm_review y _llamar_juez para ver si hubo juez.

  python pruebas/prueba_solo_checks.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def falso(rol):
    """claude -p falso, stream-json. rol=juez: un veredicto que aprueba."""
    if rol == "juez":
        txt = json.dumps({"puntuacion": {"completitud": 5, "correccion": 5, "no_regresion": 5, "evidencia": 5},
                          "aprobado": "si", "que_falta": [], "evidencia": ["hola.txt"]})
    else:
        txt = "hecho: hola.txt ya dice hola"
    for ev in ({"type": "system", "subtype": "init", "session_id": f"falso-{rol}", "model": "falso"},
               {"type": "assistant", "message": {"id": "m1", "model": "falso",
                                                 "content": [{"type": "text", "text": txt}]}},
               {"type": "result", "subtype": "success", "is_error": False, "result": txt,
                "total_cost_usd": 0, "num_turns": 1, "session_id": f"falso-{rol}"}):
        print(json.dumps(ev), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-solo-checks-"))
    app, work = tmp / "app", tmp / "trabajo"
    app.mkdir()
    work.mkdir()
    (work / "hola.txt").write_text("hola mundo\n", encoding="utf-8")
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    if os.environ.get("PRUEBA_GB_ORIGEN"):  # otra version (p. ej. la de antes del cambio) para comparar
        shutil.copy2(os.environ["PRUEBA_GB_ORIGEN"], app / "growi-bridge.py")
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work)]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"))
    spec = importlib.util.spec_from_file_location("gb_solo_checks", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()

    def cmd(task, motor_id, eng, prompt, abilities=True):
        rol = "juez" if "Eres un juez estricto" in (prompt or "") else "motor"
        return [sys.executable, str(Path(__file__).resolve()), "--falso", rol]
    gb._build_cli_cmd = cmd
    gb._swap_args = lambda c, old, new: list(c)
    gb._approval_needed = lambda task: None  # la aprobacion humana no es lo que se prueba
    llamadas = {"_llm_review": 0, "_llamar_juez": 0}
    for nombre in llamadas:
        orig = getattr(gb, nombre)

        def envuelta(*a, _o=orig, _n=nombre, **k):
            llamadas[_n] += 1
            return _o(*a, **k)
        setattr(gb, nombre, envuelta)

    tip_ok = [{"tipo": "existe", "archivo": "hola.txt"}, {"tipo": "contiene", "archivo": "hola.txt", "texto": "hola"}]
    tip_mal = tip_ok + [{"tipo": "contiene", "archivo": "hola.txt", "texto": "adios"}]
    casos = [
        ("a-solo-checks-verde", {"revisar": "solo_checks", "criterios": tip_ok}),
        ("b-solo-checks-rojo", {"revisar": "solo_checks", "criterios": tip_mal}),
        ("c-solo-checks-solo-frases", {"revisar": "solo_checks",
                                       "criterios": ["hola.txt saluda al mundo de forma amable"]}),
        ("d1-revisar-true", {"revisar": True, "criterios": tip_ok}),
        ("d2-revisar-false", {"revisar": False, "criterios": tip_ok}),
        ("d3-revisar-true-R1", {"revisar": True, "criterios": tip_ok}),
    ]
    nivel_orig = gb._nivel_de_tarea
    gb._nivel_de_tarea = lambda t: "R1" if t["id"].endswith("-R1") else nivel_orig(t)  # que el juez de pago entre
    out = {"carpeta": str(tmp), "casos": {}}
    for tid, extra in casos:
        antes = dict(llamadas)
        tf = gb.TASKS / f"{tid}.task.json"
        tf.write_text(json.dumps(dict({"id": tid, "prompt": "prueba de revisión: comprueba hola.txt",
                                       "motor": "claude", "cwd": str(work), "timeout_min": 5}, **extra)),
                      encoding="utf-8")
        t0 = time.time()
        gb._process_one_impl(tf)
        revf = gb.RESULTS / f"{tid}.revision.json"
        rev = json.loads(revf.read_text(encoding="utf-8")) if revf.exists() else None
        res = json.loads((gb.RESULTS / f"{tid}.result.json").read_text(encoding="utf-8"))
        fam = gb.load_family(tid) or {}
        out["casos"][tid] = {
            "task_revisar_enviado": extra.get("revisar"),
            "segundos": round(time.time() - t0, 1),
            "estado_final_familia": fam.get("estado"),
            "llamadas_juez_en_este_caso": {k: llamadas[k] - antes[k] for k in llamadas},
            "revision_json": None if rev is None else {k: rev.get(k) for k in (
                "modo_revision", "decision", "aprobado", "necesita_decision", "motivo_decision", "motor_revision",
                "cost_usd", "que_falta", "jueces_intentados", "segundo_juez")} | {
                "checks": [(c["criterio"], c["resultado"], c.get("tipado")) for c in rev.get("checks_deterministas")
                           or []],
                "veredictos": [(v.get("motor"), v.get("estado"), v.get("aprobado")) for v in rev.get("veredictos")
                               or []]},
            "revision_json_existe": rev is not None,
            "resultado_status": res.get("status"),
            "log": [x for x in gb.LOG_FILE.read_text(encoding="utf-8").splitlines() if tid in x][-4:],
        }
    dest = REPO / "pruebas" / "evidencia" / (os.environ.get("PRUEBA_SALIDA") or "solo-checks.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1), flush=True)
    os._exit(0)  # hilos de fondo del modulo


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--falso":
        falso(sys.argv[2])
    else:
        main()

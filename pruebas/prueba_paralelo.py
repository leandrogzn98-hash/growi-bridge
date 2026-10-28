"""Prueba del paralelo seguro (ESTADO-PARALELO-SEGURO.md).

Copia aislada de growi-bridge.py (share, cola.db, mutex y memoria propios). La
1.ª tarea corre por el runner real en este proceso; el vigía del 2.º hueco
(slot_vigia) lanza la 2.ª en un PROCESO APARTE de verdad (--slot2). Los motores
son falsos en los dos procesos (un «hook» que solo se acepta en una instancia
aislada): duermen lo que diga el encargo y escriben lo que pida. El repo git del
caso del worktree se crea aquí, con una suite pytest real.

  python pruebas/prueba_paralelo.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "paralelo"

HOOK = r'''
import re, time
from pathlib import Path


def falso(task):
    r = gb._base_result(task, task["motor"])
    t0 = time.time()
    m = re.search(r"DUERME (\d+)", task["prompt"])
    time.sleep(int(m.group(1)) if m else 1)
    for nombre, txt in re.findall(r"ESCRIBE (\S+) CON (.+?)(?:\.|$)", task["prompt"]):
        p = Path(task["cwd"]) / nombre
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt.replace("\\n", "\n") + "\n", encoding="utf-8")
    r.update(status="ok", result=f"hecho por {task['motor']} [simulado] en {task['cwd']}", cost_usd=0.0,
             finished_at=gb._now_iso(), duration_s=round(time.time() - t0, 1))
    return r


gb._run_task_motor = falso
'''


def git(*a, cwd):
    return subprocess.run(["git"] + list(a), cwd=cwd, capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-paralelo-"))
    app = tmp / "app"
    app.mkdir()
    for d in ("libre1", "libre2", "libre3", "repo/subA", "repo/subB", "repo/tests"):
        (tmp / d).mkdir(parents=True, exist_ok=True)
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True,
                                                   "paralelo_max": 2}), encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(tmp)]}), encoding="utf-8")
    repo = tmp / "repo"
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "subA" / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "subB" / "b.txt").write_text("b\n", encoding="utf-8")
    git("init", "-q", "-b", "main", cwd=repo)
    git("-c", "user.name=prueba", "-c", "user.email=p@p", "add", ".", cwd=repo)
    git("-c", "user.name=prueba", "-c", "user.email=p@p", "commit", "-q", "-m", "base", cwd=repo)
    (tmp / "hook.py").write_text(HOOK, encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"), GROWI_BRIDGE_MUTEX="Local\\GrowiPruebaParalelo",
                      GROWI_BRIDGE_PRUEBA_HOOK=str(tmp / "hook.py"),
                      GIT_AUTHOR_NAME="prueba", GIT_AUTHOR_EMAIL="p@p", GIT_COMMITTER_NAME="prueba",
                      GIT_COMMITTER_EMAIL="p@p")
    spec = importlib.util.spec_from_file_location("gb_par", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX, gb.PROCESSING, gb.DONE):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    exec(HOOK, {"gb": gb})  # los mismos motores falsos en este proceso
    stop = threading.Event()
    threading.Thread(target=gb.slot_vigia, args=(stop,), daemon=True).start()
    ev = {"copia": str(tmp)}

    def tarea(tid, motor, cwd, prompt, **extra):
        d = {"id": tid, "motor": motor, "cwd": str(cwd), "prompt": prompt, "revisar": False}
        if motor == "ollama":
            d["model"] = "ollama:prueba"
        d.update(extra)
        f = gb.TASKS / f"{tid}.task.json"
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.utime(f, (time.time() - 5, time.time() - 5))
        return f

    def resultado(tid):
        p = gb.RESULTS / f"{tid}.result.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def principal(f):
        th = threading.Thread(target=lambda: gb.process_one(f))
        th.start()
        return th

    def esperar(cond, seg):
        fin = time.time() + seg
        while time.time() < fin and not cond():
            time.sleep(0.5)
        return cond()

    # (a) sin solapamiento: Claude (libre1) y un local (libre2) a la vez
    fm = tarea("t-par-a1", "claude", tmp / "libre1", "DUERME 14")
    tarea("t-par-a2", "ollama", tmp / "libre2", "DUERME 3 y ESCRIBE hecho.txt CON listo.")
    th = principal(fm)
    esperar(lambda: bool(resultado("t-par-a2")), 40)
    th.join()
    r1, r2 = resultado("t-par-a1"), resultado("t-par-a2")
    ev["a_paralelo"] = {"a1": [r1.get("started_at"), r1.get("finished_at"), r1.get("status")],
                        "a2": [r2.get("started_at"), r2.get("finished_at"), r2.get("status")],
                        "a2_dentro_de_a1": bool(r1 and r2 and r1["started_at"] <= r2["started_at"]
                                                and r2["finished_at"] <= r1["finished_at"])}
    esperar(lambda: gb._SLOT["proc"] is None, 15)
    # (b) dos Claudes, y un local que se solapa: los dos en serie (no se lanzan en el 2.º hueco)
    fm = tarea("t-par-b1", "claude", tmp / "libre1", "DUERME 10")
    tarea("t-par-b2", "claude", tmp / "libre2", "DUERME 1")
    tarea("t-par-b3", "ollama", tmp / "libre1" / "dentro", "DUERME 1") if (tmp / "libre1" / "dentro").mkdir() is None else None
    th = principal(fm)
    th.join()
    ev["b_serie"] = {"b2_sigue_en_cola": (gb.TASKS / "t-par-b2.task.json").exists(),
                     "b3_sigue_en_cola": (gb.TASKS / "t-par-b3.task.json").exists(),
                     "decisiones": [gb.paralelo_decidir({"motor": "claude", "cwd": str(tmp / "libre1")},
                                                        {"motor": "claude", "cwd": str(tmp / "libre2")}),
                                    gb.paralelo_decidir({"motor": "claude", "cwd": str(tmp / "libre1")},
                                                        {"motor": "ollama", "model": "ollama:x",
                                                         "cwd": str(tmp / "libre1" / "dentro")})]}
    for n in ("t-par-b2", "t-par-b3"):
        (gb.TASKS / f"{n}.task.json").unlink(missing_ok=True)
    # (c) mismo repo, sin solaparse: la 2.ª en su worktree agent/<id>; nada se fusiona solo
    fm = tarea("t-par-c1", "claude", repo / "subA", "DUERME 14")
    tarea("t-par-c2", "ollama", repo / "subB", "DUERME 2 y ESCRIBE nuevo.txt CON cambio en la rama del agente.")
    th = principal(fm)
    esperar(lambda: bool(resultado("t-par-c2")), 50)
    th.join()
    esperar(lambda: gb._SLOT["proc"] is None, 30)
    w = gb._wt_reg().get("t-par-c2") or {}
    rama_log = git("log", "--oneline", "-3", w.get("rama") or "HEAD", cwd=repo).stdout
    nota = gb.RESULTS / "t-par-c2.merge.md"
    ev["c_worktree"] = {"registro": {k: w.get(k) for k in ("ruta", "rama", "base", "estado", "cwd")},
                        "cwd_de_la_tarea": resultado("t-par-c2").get("result"),
                        "en_main_no_esta_aun": not (repo / "subB" / "nuevo.txt").exists(),
                        "nota_merge": nota.read_text(encoding="utf-8")[:700] if nota.exists() else None}
    # el agente deja su cambio hecho en la rama (lo haría el motor; aquí, el commit lo hace la prueba)
    if w.get("ruta"):
        git("add", ".", cwd=w["ruta"])
        git("commit", "-q", "-m", "cambio del agente", cwd=w["ruta"])
    ev["c_fusionar"] = gb.paralelo_fusionar("t-par-c2")
    ev["c_tras_fusionar"] = {"en_main": (repo / "subB" / "nuevo.txt").exists(),
                             "worktree_quitado": not Path(w.get("ruta", "x")).exists(),
                             "log_main": git("log", "--oneline", "-3", cwd=repo).stdout.strip()}
    # (d) el agente rompe un test en su worktree: no se fusiona y recibe el fallo
    fm = tarea("t-par-d1", "claude", repo / "subA", "DUERME 14")
    tarea("t-par-d2", "ollama", repo / "subB",
          "DUERME 2 y ESCRIBE ../tests/test_rompe.py CON def test_rompe():\\n    assert False")
    th = principal(fm)
    esperar(lambda: bool(resultado("t-par-d2")), 50)
    th.join()
    esperar(lambda: gb._SLOT["proc"] is None, 40)
    wd = gb._wt_reg().get("t-par-d2") or {}
    reintento = sorted(p.name for p in gb.TASKS.glob("t-par-d2-test*.task.json"))
    ev["d_test_rojo"] = {"estado_wt": wd.get("estado"), "tests": [(t["comando"], t["exit"]) for t in wd.get("tests", [])],
                         "reintento_del_agente": reintento,
                         "prompt_reintento": json.loads((gb.TASKS / reintento[0]).read_text(encoding="utf-8"))["prompt"][:300]
                         if reintento else None,
                         "fusionar": gb.paralelo_fusionar("t-par-d2")}
    # que (d) no siga en el 2.º hueco durante (e): su rama queda descartada para la prueba
    reg = gb._wt_reg()
    reg["t-par-d2"]["estado"] = "descartado (prueba)"
    gb._wt_guardar(reg)
    for _ in range(3):
        esperar(lambda: gb._SLOT["proc"] is None, 40)
        for p in gb.TASKS.glob("t-par-d2-test*.task.json"):
            p.unlink()
    # (e) con el paralelo activo, una tarea que espera aprobación libera el hueco
    s = gb.load_settings()
    s["guardrail"] = "delicado"
    gb.save_settings(s)
    (tmp / "libre2" / "viejo.txt").write_text("x", encoding="utf-8")
    fm = tarea("t-par-e1", "claude", tmp / "libre1", "DUERME 20")
    tarea("t-par-e2", "ollama", tmp / "libre2", f"Borra el archivo {tmp / 'libre2' / 'viejo.txt'}.")
    time.sleep(1)
    tarea("t-par-e3", "ollama", tmp / "libre3", "DUERME 2 y ESCRIBE e3.txt CON hecho.")
    th = principal(fm)
    esperar(lambda: bool(resultado("t-par-e3")), 60)
    e1_corriendo = gb.state.get("current") == "t-par-e1"
    th.join()
    fam2 = gb.load_family("t-par-e2") or {}
    ev["e_espera_libera"] = {"e2": fam2.get("estado"), "e3": resultado("t-par-e3").get("status"),
                             "e3_termino_con_e1_corriendo": e1_corriendo}
    stop.set()
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "paralelo:" in x][-30:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()

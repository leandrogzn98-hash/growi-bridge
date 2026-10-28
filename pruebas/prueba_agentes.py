"""Prueba de los agentes en paralelo (ESTADO-AGENTES-PARALELOS.md).

Copia aislada de growi-bridge.py (share, cola.db, mutex y memoria propios). El
agente 1 corre por el runner real en este proceso; el vigía lanza el agente 2
en un PROCESO APARTE de verdad (--slot2). Motores falsos en los dos procesos
(hook que solo se acepta en una instancia aislada): duermen, escriben y, si el
encargo dice MUERE, el proceso del agente se mata una vez (os._exit) a mitad.

  python pruebas/prueba_agentes.py
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
OUT = REPO / "pruebas" / "evidencia" / "agentes"

HOOK = r'''
import os, re, time
from pathlib import Path


def falso(task):
    r = gb._base_result(task, task["motor"])
    t0 = time.time()
    marca = Path(os.environ["AGENTES_MARCA"])
    if "MUERE" in task["prompt"] and not marca.exists():
        marca.write_text("murió una vez", encoding="utf-8")
        time.sleep(2)
        os._exit(3)  # el proceso del agente muere a mitad de su tarea
    m = re.search(r"DUERME (\d+)", task["prompt"])
    time.sleep(int(m.group(1)) if m else 1)
    for nombre, txt in re.findall(r"ESCRIBE (\S+) CON (.+?)(?:\.|$)", task["prompt"]):
        (Path(task["cwd"]) / nombre).write_text(txt + "\n", encoding="utf-8")
    r.update(status="ok", result=f"hecho por {task['motor']} [simulado] en {task['cwd']}", cost_usd=0.004,
             finished_at=gb._now_iso(), duration_s=round(time.time() - t0, 1))
    return r


gb._run_task_motor = falso
'''


def git(*a, cwd):
    return subprocess.run(["git"] + list(a), cwd=cwd, capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-agentes-"))
    app = tmp / "app"
    app.mkdir()
    for d in ("libre1", "libre2", "repo/subA", "repo/subB"):
        (tmp / d).mkdir(parents=True, exist_ok=True)
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True,
                                                   "paralelo_max": 2}), encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(tmp)]}), encoding="utf-8")
    repo = tmp / "repo"
    (repo / "subA" / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "subB" / "b.txt").write_text("b\n", encoding="utf-8")
    git("init", "-q", "-b", "main", cwd=repo)
    git("-c", "user.name=prueba", "-c", "user.email=p@p", "add", ".", cwd=repo)
    git("-c", "user.name=prueba", "-c", "user.email=p@p", "commit", "-q", "-m", "base", cwd=repo)
    (tmp / "hook.py").write_text(HOOK, encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"), GROWI_BRIDGE_MUTEX="Local\\GrowiPruebaAgentes",
                      GROWI_BRIDGE_PRUEBA_HOOK=str(tmp / "hook.py"), AGENTES_MARCA=str(tmp / "murio.txt"))
    spec = importlib.util.spec_from_file_location("gb_ag", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX, gb.PROCESSING, gb.DONE):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    exec(HOOK, {"gb": gb})
    stop = threading.Event()
    threading.Thread(target=gb.slot_vigia, args=(stop,), daemon=True).start()
    ev = {"copia": str(tmp)}

    def tarea(tid, motor, cwd, prompt, archivo=None, **extra):
        d = {"id": tid, "motor": motor, "cwd": str(cwd), "prompt": prompt, "revisar": False}
        if motor == "ollama":
            d["model"] = "ollama:prueba"
        d.update(extra)
        f = gb.TASKS / (archivo or f"{tid}.task.json")
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.utime(f, (time.time() - 5, time.time() - 5))
        return f

    def resultado(tid):
        p = gb.RESULTS / f"{tid}.result.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def esperar(cond, seg):
        fin = time.time() + seg
        while time.time() < fin and not cond():
            time.sleep(0.5)
        return cond()

    # (a) Claude (agente 1) + Hermes local (agente 2) a la vez, cada uno con su tarea; el 2 en su worktree
    fm = tarea("t-ag-1", "claude", repo / "subA", "DUERME 25")
    tarea("t-ag-2", "ollama", repo / "subB", "DUERME 8 y ESCRIBE hecho.txt CON del agente 2.")
    # (b) un 3.er agente posible (codex): no cabe, espera en la cola con el motivo a la vista
    tarea("t-ag-3", "codex", tmp / "libre1", "DUERME 1")
    # (c) un duplicado con el MISMO task_id que el agente 1
    dup = tarea("t-ag-1", "ollama", tmp / "libre2", "DUERME 1", archivo="t-ag-1-duplicado.task.json")
    os.utime(dup, (time.time() - 60, time.time() - 60))  # el más viejo: el vigía lo mira el primero
    th = threading.Thread(target=lambda: gb.process_one(fm))
    th.start()
    esperar(lambda: gb._SLOT.get("proc") is not None, 20)
    time.sleep(5)
    filas, cola = gb.agentes_vista()
    ev["e_vista_con_dos"] = {"agentes": filas, "en_cola": cola}
    ev["a_dos_a_la_vez"] = [(f["hueco"], f["tarea"], f["motor"], f.get("worktree")) for f in filas]
    esperar(lambda: bool(resultado("t-ag-2")), 40)
    ev["b_tercero"] = {"sigue_en_cola": (gb.TASKS / "t-ag-3.task.json").exists(),
                       "motivo_visible": (gb.cola_get("t-ag-3") or {}).get("motivo")}
    ev["c_duplicado"] = {"no_se_lanzo": (gb.TASKS / "t-ag-1-duplicado.task.json").exists()}
    th.join()
    r1, r2 = resultado("t-ag-1"), resultado("t-ag-2")
    ev["a_resultados"] = {"agente1": [r1.get("motor"), r1.get("started_at"), r1.get("finished_at"), r1.get("status")],
                          "agente2": [r2.get("motor"), r2.get("started_at"), r2.get("finished_at"), r2.get("status"),
                                      r2.get("result")],
                          "contexto_agente2": r2.get("contexto_recibido"),
                          "contexto_agente1": r1.get("contexto_recibido")}
    esperar(lambda: gb._SLOT["proc"] is None, 20)
    for n in ("t-ag-3.task.json", "t-ag-1-duplicado.task.json"):
        (gb.TASKS / n).unlink(missing_ok=True)
    # (d) el agente 2 muere a mitad: vuelve a la cola y sigue desde su checkpoint; el 1 ni se entera
    fm = tarea("t-ag-4", "claude", tmp / "libre1", "DUERME 30")
    tarea("t-ag-5", "ollama", tmp / "libre2", "MUERE (una vez) y luego DUERME 2 y ESCRIBE d.txt CON recuperado.")
    th = threading.Thread(target=lambda: gb.process_one(fm))
    th.start()
    esperar(lambda: (gb.cola_get("t-ag-5") or {}).get("cortes"), 40)
    ev["d_tras_morir"] = {k: (gb.cola_get("t-ag-5") or {}).get(k) for k in ("estado", "cortes", "motivo")}
    esperar(lambda: bool(resultado("t-ag-5")), 60)
    agente1_corriendo = gb.state.get("current") == "t-ag-4"
    th.join()
    r5 = resultado("t-ag-5")
    ev["d_reasignado"] = {"estado": r5.get("status"), "recuperada_tras_corte": r5.get("recuperada_tras_corte"),
                          "cortes": r5.get("cortes"), "avisos": r5.get("avisos"),
                          "termino_mientras_el_1_seguia": agente1_corriendo,
                          "agente1": resultado("t-ag-4").get("status")}
    stop.set()
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "paralelo:" in x or "agentes:" in x][-24:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()

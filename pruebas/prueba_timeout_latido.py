"""Prueba del timeout de inactividad y del latido (t-timeout-latido).

Corre el runner (runner/runner.py) y el gateway (growi-bridge.py) de ESTE
repo contra un claude falso (pruebas/fake_claude.py), en una carpeta
temporal propia: no toca share/, cola.db ni ningun carril instalado.

  python pruebas/prueba_timeout_latido.py runner-colgado
  python pruebas/prueba_timeout_latido.py runner-lento [segundos]
  python pruebas/prueba_timeout_latido.py gateway-colgado

El umbral sale de GROWI_NO_PROGRESS_S (sin ella, 300 s reales). Escribe la
evidencia en JSON en stdout y en pruebas/evidencia/<modo>-<umbral>s.json.
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
FAKE = REPO / "pruebas" / "fake_claude.py"
MARCAS = ("fake_claude.py", "growi-fake-hijo")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_procs():
    """Procesos vivos del claude falso o de su hijo (huerfanos si quedan)."""
    import psutil
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
        except Exception:
            continue
        if any(m in cl for m in MARCAS) and p.pid != os.getpid():
            out.append({"pid": p.pid, "name": p.info["name"], "cmdline": cl[-120:]})
    return out


def _tasklist(image):
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.startswith('"')]


def _watch(status_file, live_file, samples, stop):
    """Apunta cada cambio de runner-status.json (y del vivo, si hay)."""
    last = None
    vistos = set()
    while not stop.is_set():
        try:
            st = json.loads(status_file.read_text(encoding="utf-8"))
            key = (st.get("last_poll"), json.dumps(st.get("current"), sort_keys=True))
            if key != last:
                last = key
                samples.append({"t": round(time.time() - T0, 1), "archivo": status_file.name,
                                "last_poll": st.get("last_poll"), "current": st.get("current")})
        except (OSError, ValueError):
            pass
        if live_file is not None:
            try:
                lv = json.loads(live_file.read_text(encoding="utf-8"))
                k = (lv.get("actualizado"), lv.get("idle_s"))
                if k not in vistos and "idle_s" in lv:
                    vistos.add(k)
                    samples.append({"t": round(time.time() - T0, 1), "archivo": live_file.name,
                                    "estado": lv.get("estado"), "ultima_actividad": lv.get("ultima_actividad"),
                                    "idle_s": lv.get("idle_s")})
            except (OSError, ValueError):
                pass
        for p in _fake_procs():
            VISTOS[p["pid"]] = p
        time.sleep(1)


def prueba_runner(modo, seg):
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-"))
    rdir = tmp / "share" / "inbox" / "runner"
    rdir.mkdir(parents=True)
    shutil.copy2(REPO / "runner" / "runner.py", rdir / "runner.py")
    rn = _load(rdir / "runner.py", "runner_prueba")
    fake_mode = ["colgado"] if modo == "runner-colgado" else ["lento", str(seg)]
    rn._build_cmd = lambda task, fmt: [sys.executable, str(FAKE)] + fake_mode
    for d in (rn.TASKS, rn.PROCESSING, rn.DONE, rn.RESULTS):
        d.mkdir(parents=True, exist_ok=True)
    tid = f"prueba-{modo}"
    (rn.TASKS / f"{tid}.task.json").write_text(json.dumps(
        {"id": tid, "prompt": "prueba de inactividad", "timeout_min": 30}), encoding="utf-8")
    claude_antes = _tasklist("claude.exe")
    samples, stop = [], threading.Event()
    threading.Thread(target=_watch, args=(rn.STATUS_FILE, None, samples, stop), daemon=True).start()
    threading.Thread(target=rn.main, daemon=True).start()  # el bucle real del runner
    res_file = rn.RESULTS / f"{tid}.result.json"
    while not res_file.exists():
        time.sleep(1)
    time.sleep(8)  # el bucle escribe el latido con current=null al terminar
    stop.set()
    time.sleep(1.5)
    res = json.loads(res_file.read_text(encoding="utf-8"))
    log = [l for l in rn.LOG.read_text(encoding="utf-8").splitlines() if tid in l]
    return {"modo": modo, "umbral_s": rn.no_progress_s(), "carpeta": str(tmp),
            "resultado": res, "log": log, "latidos": samples,
            "status_final": json.loads(rn.STATUS_FILE.read_text(encoding="utf-8")),
            "task_archivado_en_done": (rn.DONE / f"{tid}.task.json").exists(),
            "procesos_falsos_vistos_durante": list(VISTOS.values()),
            "procesos_falsos_vivos_despues": _fake_procs(),
            "claude_exe_antes": len(claude_antes), "claude_exe_despues": len(_tasklist("claude.exe"))}


def prueba_gateway():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-gw-"))
    app = tmp / "app"
    app.mkdir()
    shutil.copy2(REPO / "growi-bridge.py", app / "growi-bridge.py")
    shutil.copy2(REPO / "engines.json", app / "engines.json")
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca",
                                                   "onboarding_done": True}), encoding="utf-8")
    os.environ["GROWI_BRIDGE_SHARE"] = str(tmp / "share")
    os.environ["GROWI_BRIDGE_COLA"] = str(tmp / "cola.db")
    os.environ["GROWI_BRIDGE_LANE_A_DIR"] = str(tmp / "no-existe")
    gb = _load(app / "growi-bridge.py", "growi_bridge_prueba")
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    # El motor claude de engines.json, pero el binario es el claude falso colgado.
    fake = [sys.executable, str(FAKE), "colgado"]
    gb._build_cli_cmd = lambda *a, **k: list(fake)
    gb._swap_args = lambda cmd, old, new: list(fake)
    # La aprobacion humana no es lo que se prueba aqui (sin riesgos.json todo
    # seria R3 y la tarea quedaria aparcada esperando).
    gb._approval_needed = lambda task: None
    tid = "prueba-gw-colgado"
    tf = gb.TASKS / f"{tid}.task.json"
    tf.write_text(json.dumps({"id": tid, "prompt": "prueba de inactividad", "motor": "claude",
                              "timeout_min": 30, "revisar": False}), encoding="utf-8")
    samples, stop = [], threading.Event()
    threading.Thread(target=_watch, args=(gb.OUTBOX / "runner-status.json", gb.LIVE_FILE, samples, stop),
                     daemon=True).start()
    pulse_stop = threading.Event()
    threading.Thread(target=gb._runner_pulse_loop, args=(pulse_stop,), daemon=True).start()
    t0 = time.time()
    gb._process_one_impl(tf)  # el camino real: cola, checkpoint, motor, resultado
    dur = round(time.time() - t0, 1)
    gb.runner_heartbeat()  # el bucle lo escribe al quedar libre
    time.sleep(2)
    stop.set()
    pulse_stop.set()
    res = json.loads((gb.RESULTS / f"{tid}.result.json").read_text(encoding="utf-8"))
    ck = gb.ck_ultimo(tid)
    cola = gb.cola_get(tid) if hasattr(gb, "cola_get") else None
    log = [l for l in gb.LOG_FILE.read_text(encoding="utf-8").splitlines() if tid in l]
    return {"modo": "gateway-colgado", "umbral_s": gb.no_progress_s(), "carpeta": str(tmp),
            "duracion_s": dur,
            "resultado": {k: res.get(k) for k in ("status", "error", "error_tipo", "duration_s",
                                                  "cost_usd", "exit_code", "estado", "reintentos")},
            "checkpoint": {k: (ck or {}).get(k) for k in ("estado", "paso", "siguiente_paso", "historial")},
            "cola": {k: (cola or {}).get(k) for k in ("estado", "motivo", "reintentos")} if cola else None,
            "es_transitorio": gb._es_transitorio(res),
            "log": log, "latidos_y_vivo": samples,
            "status_final_current": json.loads((gb.OUTBOX / "runner-status.json").read_text(
                encoding="utf-8")).get("current", "falta"),
            "procesos_falsos_vistos_durante": list(VISTOS.values()),
            "procesos_falsos_vivos_despues": _fake_procs()}


def prueba_http():
    """_http_local_stream contra un servidor local que acepta y no manda nada."""
    import socket
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-http-"))
    shutil.copy2(REPO / "growi-bridge.py", tmp / "growi-bridge.py")
    os.environ["GROWI_BRIDGE_SHARE"] = str(tmp / "share")
    os.environ["GROWI_BRIDGE_COLA"] = str(tmp / "cola.db")
    gb = _load(tmp / "growi-bridge.py", "growi_bridge_http")
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    held = []
    threading.Thread(target=lambda: held.append(srv.accept()), daemon=True).start()
    t0 = time.time()
    try:
        gb._http_local_stream(f"http://127.0.0.1:{port}/completion", {"prompt": "x"}, 1800,
                              {"formato": "sse"}, lambda n: None, idle=gb.no_progress_s())
        err = None
    except gb.LocalCallError as e:
        err = str(e)
    return {"modo": "gateway-http-colgado", "umbral_s": gb.no_progress_s(), "timeout_total_s": 1800,
            "error": err, "error_exacto": err == "lanzamiento sin progreso en 5 min",
            "esperado_s": round(time.time() - t0, 1)}


T0 = time.time()
VISTOS = {}

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "runner-colgado"
    if modo == "gateway-http-colgado":
        ev = prueba_http()
    elif modo == "gateway-colgado":
        ev = prueba_gateway()
    else:
        ev = prueba_runner(modo, float(sys.argv[2]) if len(sys.argv) > 2 else 45)
    out = REPO / "pruebas" / "evidencia"
    out.mkdir(exist_ok=True)
    name = f"{modo}-{ev['umbral_s']}s.json"
    (out / name).write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=2), flush=True)
    os._exit(0)  # los hilos del runner/gateway son bucles infinitos

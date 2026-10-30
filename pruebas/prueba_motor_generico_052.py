"""Prueba de t-motor-generico-052 (multimotor) en una instancia AISLADA.

C:\\Users\\forte\\growi-bridge\\_prueba-motor-generico-052\\app\\ = el
growi-bridge.py y el engines.json del REPO + la config de la app instalada
(solo se lee), con su propia share, cola.db, log y settings.json. No abre
ventana ni el puente; el runner_loop real corre en este proceso y lanza los
motores ocultos (CREATE_NO_WINDOW). La app instalada no se toca.

  a) motor: codex  -> lo corre Codex de verdad (session_id = thread_id, uso)
  b) el task real rechazado el 28 oct (model "motor:codex") -> entra como codex
  c) motor: gemini -> lo corre agy (sesion de Google)
  d) motor y model contradictorios -> rechazado con el motivo
  e) cubos: la tarea de codex cuenta en chatgpt-plus y no mueve claude-max
  f) runner.py suelto: motor codex -> rechazado con «lo corre el runner de la app»
  g) via api: motor gemini + via api -> motor api, api:gemini:default

Uso: python prueba_motor_generico_052.py [--sin-motores]   (sin-motores: solo b, d, f, g)
Evidencia: pruebas\\evidencia\\motor-generico-052\\resultado.json
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REAL = Path(r"C:\Users\forte\growi-bridge")
BASE = REAL / "_prueba-motor-generico-052"
APP = BASE / "app"
EVID = REPO / "pruebas" / "evidencia" / "motor-generico-052"
SIN_MOTORES = "--sin-motores" in sys.argv
OUT = {"inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "casos": {}}


def caso(k, ok, **datos):
    OUT["casos"][k] = dict(ok=bool(ok), **datos)
    print(f"[{'OK' if ok else 'FALLA'}] {k}: {json.dumps(datos, ensure_ascii=False)[:400]}", flush=True)


def preparar():
    if APP.exists():
        shutil.rmtree(APP)  # solo la carpeta de prueba propia
    APP.mkdir(parents=True)
    for f in ("growi-bridge.py", "engines.json", "riesgos.json", "models-catalog.json", "VERSION",
              "growi.png", "growi.ico", "growi-header.png", "growi-tray.png", "growi-tray-b.png"):
        if (REPO / f).is_file():
            shutil.copy2(REPO / f, APP / f)
    for f in ("rules.json", "availability.json", "pc-specs.json", "proxy.json", "motores-salud.json"):
        if (REAL / f).is_file():
            shutil.copy2(REAL / f, APP / f)
    for d in ("asistentes", "temas", "mascot", "skills", "comandos"):
        if (REPO / d).is_dir():
            shutil.copytree(REPO / d, APP / d, ignore=shutil.ignore_patterns("__pycache__"))
    s = json.loads((REAL / "settings.json").read_text(encoding="utf-8"))
    s.update(guardrail="nunca", onboarding_done=True, motores_off=[],
             limites_cubo={"chatgpt-plus": {"5h": {"tareas": 1}}})
    for k in ("motor_principal",):
        s.pop(k, None)
    (APP / "settings.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    inbox = APP / "share" / "inbox"
    for d in ("runner-tasks", "trabajo"):
        (inbox / d).mkdir(parents=True, exist_ok=True)
    (APP / "share" / "outbox" / "runner-results").mkdir(parents=True, exist_ok=True)
    (APP / "folders.json").write_text(json.dumps({"allowed_roots": [str(inbox)]}), encoding="utf-8")


def cargar():
    for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
        os.environ.pop(k, None)
    src = APP / "growi-bridge.py"
    ld = importlib.machinery.SourceFileLoader("growi_bridge", str(src))
    spec = importlib.util.spec_from_file_location("growi_bridge", src, loader=ld)
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    assert gb.APP_DIR == APP, gb.APP_DIR
    return gb


def casos_sin_motores(gb):
    trabajo = str(APP / "share" / "inbox" / "trabajo")
    # b) el task real que se rechazo el 28 oct, con cwd de la instancia aislada
    viejo = REAL / "share" / "inbox" / "runner-tasks" / "done" / "t-lote-estados-030-r2.task.json"
    d = json.loads(viejo.read_text(encoding="utf-8"))
    d["cwd"] = trabajo
    t, err = gb.validate_task(d)
    caso("b_task_28oct_motor_codex", t is not None and t["motor"] == "codex" and t["modelo"] is None,
         model_original=d.get("model"), motor=t and t["motor"], error=err)
    # d) contradicciones
    malos = [({"motor": "codex", "model": "sonnet"}, "es de 'claude'"),
             ({"motor": "gemini", "model": "motor:codex"}, "es de 'codex'"),
             ({"motor": "claude", "model": "ollama:qwen3"}, "es de 'ollama'"),
             ({"motor": "noexiste"}, "no existe en engines.json"),
             ({"motor": "gemini", "via": "fax"}, "via debe ser")]
    filas = []
    for extra, espera in malos:
        t, err = gb.validate_task(dict({"id": "t-d", "prompt": "x", "cwd": trabajo}, **extra))
        filas.append({"task": extra, "error": err, "ok": t is None and espera in (err or "")})
    caso("d_contradicciones_rechazadas", all(f["ok"] for f in filas), filas=filas)
    # sigue valiendo lo de antes
    buenos = [({"motor": "codex"}, ("codex", None)), ({"model": "motor:gemini"}, ("gemini", None)),
              ({"model": "sonnet"}, ("claude", "sonnet")), ({"model": "ollama:default"}, ("ollama", None)),
              ({"motor": "claude", "model": "opus"}, ("claude", "opus")),
              ({"model": "codex:gpt-6.1-sol"}, ("codex", "gpt-6.1-sol"))]
    filas = []
    for extra, (m, mod) in buenos:
        t, err = gb.validate_task(dict({"id": "t-v", "prompt": "x", "cwd": trabajo}, **extra))
        filas.append({"task": extra, "motor": t and t["motor"], "modelo": t and t["modelo"], "error": err,
                      "ok": t is not None and t["motor"] == m and t["modelo"] == mod})
    caso("formas_validas", all(f["ok"] for f in filas), filas=filas)
    # g) via api
    t, err = gb.validate_task({"id": "t-g", "prompt": "x", "cwd": trabajo, "motor": "gemini", "via": "api"})
    caso("g_via_api", t is not None and t["motor"] == "api" and t["model"] == f"api:gemini:{gb.api_model_for('gemini')}",
         motor=t and t["motor"], model=t and t["model"], error=err)
    # f) runner.py suelto
    src = REPO / "runner" / "runner.py"
    ld = importlib.machinery.SourceFileLoader("runner_suelto", str(src))
    sp = importlib.util.spec_from_file_location("runner_suelto", src, loader=ld)
    rs = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(rs)
    rs.INBOX = APP / "share" / "inbox"  # su INBOX sale de donde esta el archivo; aqui, el aislado
    filas = []
    for extra in ({"motor": "codex"}, {"model": "motor:gemini"}):
        t, err = rs.validate_task(dict({"id": "t-f", "prompt": "x", "cwd": str(rs.INBOX)}, **extra))
        filas.append({"task": extra, "error": err, "ok": t is None and "runner de la app" in (err or "")})
    t, err = rs.validate_task({"id": "t-f", "prompt": "x", "cwd": str(rs.INBOX), "motor": "claude"})
    filas.append({"task": {"motor": "claude"}, "error": err, "ok": t is not None})
    caso("f_runner_suelto", all(f["ok"] for f in filas), filas=filas)


def esperar_resultado(gb, tid, limite=600):
    p = gb.RESULTS / f"{tid}.result.json"
    t0 = time.time()
    while time.time() - t0 < limite:
        if p.exists():
            time.sleep(2)
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                pass
        time.sleep(2)
    return None


def casos_con_motores(gb):
    trabajo = APP / "share" / "inbox" / "trabajo"
    gb.POLL_SECONDS = 1
    gb.state["runner"] = "corriendo"
    stop = threading.Event()
    threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
    antes = gb.cubos_cuota()
    tareas = {
        "a": ("t-052-codex", "codex", "codex-052.txt"),
        "c": ("t-052-gemini", "gemini", "gemini-052.txt"),
    }
    try:
        for k, (tid, motor, archivo) in tareas.items():
            task = {"id": tid, "motor": motor, "cwd": str(trabajo), "timeout_min": 10,
                    "permission_mode": "acceptEdits", "revisar": False, "memoria": False,
                    "prompt": f"Crea en esta carpeta el archivo {archivo} con una sola línea: listo {motor}. "
                              "No hagas nada más y responde LISTO."}
            tmp = gb.TASKS / f"{tid}.tmp"
            tmp.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, gb.TASKS / f"{tid}.task.json")
            r = esperar_resultado(gb, tid)
            f = trabajo / archivo
            contenido = f.read_text(encoding="utf-8", errors="replace").strip() if f.exists() else None
            caso(f"{k}_motor_{motor}", bool(r) and r.get("status") == "ok" and r.get("motor") == motor
                 and contenido is not None and motor in contenido,
                 status=r and r.get("status"), motor_result=r and r.get("motor"), error=r and r.get("error"),
                 session_id=r and r.get("session_id"), duracion_s=r and r.get("duration_s"),
                 uso=r and r.get("uso"), acceso=r and r.get("acceso"), archivo=contenido,
                 respuesta=r and str(r.get("result"))[:200])
    finally:
        stop.set()
        time.sleep(2)
    despues = gb.cubos_cuota()

    def n(c, cubo):
        return (c.get(cubo) or {}).get("5h", {}).get("tareas", 0)
    caso("e_cubos_separados",
         n(despues, "chatgpt-plus") == n(antes, "chatgpt-plus") + 1
         and n(despues, "google-agy") == n(antes, "google-agy") + 1
         and n(despues, "claude-max") == n(antes, "claude-max"),
         antes={k: v["5h"] for k, v in antes.items()}, despues={k: v["5h"] for k, v in despues.items()},
         pct_chatgpt_plus=despues.get("chatgpt-plus", {}).get("pct"),
         motivo_codex=gb.cubo_motivo("codex"), motivo_claude=gb.cubo_motivo("claude"),
         motivo_gemini=gb.cubo_motivo("gemini"))
    OUT["cola"] = [dict(zip(("id", "estado", "motor"), r)) for r in
                   __import__("sqlite3").connect(str(gb.COLA_DB)).execute(
                       "select id, estado, motor from tareas order by creado_en")]


def main():
    preparar()
    gb = cargar()
    OUT["motores"] = {m: list(gb.engine_status(m)) for m in ("claude", "codex", "gemini")}
    print("motores:", OUT["motores"], flush=True)
    casos_sin_motores(gb)
    if not SIN_MOTORES:
        casos_con_motores(gb)
    OUT["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT["todo_ok"] = all(c["ok"] for c in OUT["casos"].values())
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=2), encoding="utf-8")
    log = APP / "growi-bridge.log"
    if log.exists():
        shutil.copy2(log, EVID / "growi-bridge-aislada.log")
    print("TODO OK" if OUT["todo_ok"] else "HAY FALLOS", flush=True)


if __name__ == "__main__":
    main()

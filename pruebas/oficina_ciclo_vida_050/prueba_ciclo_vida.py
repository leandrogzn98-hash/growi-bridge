"""t-oficina-ciclo-vida-050 (spec 18): cada camino del ciclo de vida, POR SEPARADO, en una copia aislada
(%USERPROFILE%\\growi-bridge\\_prueba-ciclo-vida\\). No toca ni reinicia la app instalada.

  python prueba_ciclo_vida.py            -> evidencia\\ciclo-vida-salida.json (+ log de cada oficina)

(a) abrir/cerrar 3 veces · (b) 2.a apertura con una abierta · (c) importar/arrancar no la abre ·
(d1) app muerta (taskkill) -> la oficina muere con ella (Job Object) · (d2) app colgada (suspendida)
-> «Bridge no disponible» y autocierre por latido · (d3) sin Job Object, app muerta -> autocierre por pid
· (e) salir de la app (quit_app) · (f) DEMO desde la app: rotulado y sin encolar · (r) cierre por falta
de recursos (codigo 6): no se reabre sola · (s) huerfana de una app anterior: se limpia al arrancar.
"""
import ctypes
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = Path.home() / "growi-bridge" / "_prueba-ciclo-vida"
APP = BASE / "app"
EVI = BASE / "evidencia"
HOST = Path(__file__).with_name("host_app.py")
PYGAME = Path(r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Lib\site-packages")
R = {}


def preparar():
    shutil.rmtree(APP, ignore_errors=True)
    APP.mkdir(parents=True)
    EVI.mkdir(parents=True, exist_ok=True)
    for f in ("growi-bridge.py", "engines.json", "riesgos.json", "models-catalog.json", "VERSION"):
        shutil.copy2(REPO / f, APP / f)
    for d in ("asistentes", "skills"):
        shutil.copytree(REPO / d, APP / d, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "oficina", APP / "share" / "inbox" / "oficina",
                    ignore=shutil.ignore_patterns("__pycache__", "mediciones", "arte", "godot", "datos", "*.bak"))
    (APP / "share" / "outbox").mkdir(parents=True, exist_ok=True)
    s = json.loads((Path.home() / "growi-bridge" / "settings.json").read_text(encoding="utf-8"))
    s.update(onboarding_done=True, oficina_pygame_dir=str(PYGAME))
    s.pop("oficina_python", None)
    (APP / "settings.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def procesos():
    """Procesos python cuya linea de comandos es la oficina de ESTA copia (pid, ppid)."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                        "ForEach-Object { \"$($_.ProcessId)|$($_.ParentProcessId)|$($_.CommandLine)\" }"],
                       capture_output=True, text=True, errors="replace")
    out = []
    for l in r.stdout.splitlines():
        pid, _, rest = l.partition("|")
        ppid, _, cmd = rest.partition("|")
        if "oficina_proto.py" in cmd and str(APP) in cmd:
            out.append((int(pid), int(ppid)))
    return out


def esperar(cond, tope, paso=0.25):
    t = time.time()
    while time.time() - t < tope:
        if cond():
            return round(time.time() - t, 2)
        time.sleep(paso)
    return None


def host(modo, *extra, env=None):
    return subprocess.Popen([sys.executable, str(HOST), str(APP), modo, *extra], cwd=str(APP),
                            env=dict(os.environ, **(env or {})), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def log_oficina():
    p = APP / "share" / "inbox" / "oficina" / "protocolo" / "datos" / "oficina-protocolo.log"
    return p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []


def log_app():
    p = APP / "growi-bridge.log"
    return [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if "oficina" in l] if p.exists() else []


def importar():
    for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
        os.environ.pop(k, None)
    ld = importlib.machinery.SourceFileLoader("gbo", str(APP / "growi-bridge.py"))
    sp = importlib.util.spec_from_file_location("gbo", APP / "growi-bridge.py", loader=ld)
    gb = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(gb)
    assert gb.APP_DIR == APP
    return gb


def huella(carpeta):
    h = hashlib.sha256()
    for f in sorted(Path(carpeta).rglob("*")):
        if f.is_file() and "oficina" not in f.parts and f.suffix not in (".log",) and "outbox" not in f.parts:
            h.update(str(f).encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


preparar()
gb = importar()

# (c) importar la app y correr lo que hace al arrancar: no abre la oficina
gb._oficina_huerfana_limpiar()
time.sleep(4)
R["c_no_se_abre_sola"] = {"procesos": len(procesos()), "abierta": gb.oficina_abierta(),
                          "ok": not procesos() and not gb.oficina_abierta()}

# (a) abrir y cerrar 3 veces desde la app
ciclos = []
for i in range(3):
    ab = gb.oficina_abrir()
    pid = gb._OFICINA["pid"]
    job = gb._OFICINA["job"] is not None
    viva = esperar(lambda: len(procesos()) >= 1, 15)
    time.sleep(4)
    gb._oficina_tick()
    pidf = json.loads(gb.OFICINA_PID_FILE.read_text(encoding="utf-8")) if gb.OFICINA_PID_FILE.exists() else {}
    n_abierta = len(procesos())
    t = time.time()
    ce = gb.oficina_cerrar("prueba (a)")
    cerrar_s = round(time.time() - t, 2)
    restos = esperar(lambda: not procesos(), 5)
    ciclos.append({"abrir": ab, "pid": pid, "pid_guardado": pidf.get("pid") == pid, "job": job,
                   "procesos_abierta": n_abierta, "cerrar": ce, "cerrar_s": cerrar_s,
                   "codigo": gb._OFICINA["ultimo_codigo"], "restos_tras_cerrar": len(procesos()),
                   "pid_file_tras_cerrar": gb.OFICINA_PID_FILE.exists()})
R["a_abrir_cerrar_3"] = {"ciclos": ciclos, "ok": all(c["abrir"] and c["pid_guardado"] and c["cerrar"] and c["codigo"] == 4
                                                    and c["restos_tras_cerrar"] == 0 and not c["pid_file_tras_cerrar"]
                                                    for c in ciclos)}

# (b) con una abierta (de otra «app» viva), abrir otra vez: no hay segunda
h1 = host("vivir")
esperar(lambda: len(procesos()) >= 1, 15)
time.sleep(3)
antes = procesos()
h2 = host("abrir")
h2.wait(60)
time.sleep(3)
r2 = json.loads(next(BASE.glob(f"host-abrir-{h2.pid}.json")).read_text(encoding="utf-8"))
despues = procesos()
R["b_segunda_instancia"] = {"procesos_antes": antes, "segunda_abrir": r2.get("abrir"), "procesos_despues": despues,
                            "ok": r2.get("abrir") is False and sorted(antes) == sorted(despues)}

# (d1) matar la app de golpe: la oficina muere con ella (Job Object), sin huerfanos
t = time.time()
subprocess.run(["taskkill", "/F", "/PID", str(h1.pid)], capture_output=True)
s_d1 = esperar(lambda: not procesos(), 20)
R["d1_app_muerta_job"] = {"oficina_cerrada_en_s": s_d1, "restos": procesos(), "ok": s_d1 is not None and not procesos()}
gb.OFICINA_PID_FILE.unlink(missing_ok=True)

# (d2) app colgada (suspendida: no late, pero su proceso existe) -> «Bridge no disponible» y autocierre
h3 = host("vivir")
esperar(lambda: len(procesos()) >= 1, 15)
time.sleep(6)
k32 = ctypes.windll.kernel32
hp = k32.OpenProcess(0x0800, False, h3.pid)  # PROCESS_SUSPEND_RESUME
ctypes.windll.ntdll.NtSuspendProcess(ctypes.c_void_p(hp))
t_susp = time.time()
s_d2 = esperar(lambda: not procesos(), 30)
lin = [l for l in log_oficina()[-30:] if "Bridge no disponible" in l]
ctypes.windll.ntdll.NtResumeProcess(ctypes.c_void_p(hp))
k32.CloseHandle(hp)
subprocess.run(["taskkill", "/F", "/PID", str(h3.pid)], capture_output=True)
R["d2_app_colgada_latido"] = {"oficina_cerrada_en_s": s_d2, "aviso": lin[-1] if lin else None, "restos": procesos(),
                              "ok": s_d2 is not None and s_d2 <= 15 + 3 + 6 and bool(lin) and not procesos()}
gb.OFICINA_PID_FILE.unlink(missing_ok=True)

# (d3) sin Job Object: matar la app -> la oficina ve el pid muerto, «Bridge no disponible», se cierra sola
h4 = host("vivir", env={"GROWI_OFICINA_SIN_JOB": "1"})
esperar(lambda: len(procesos()) >= 1, 15)
time.sleep(6)
subprocess.run(["taskkill", "/F", "/PID", str(h4.pid)], capture_output=True)
s_d3 = esperar(lambda: not procesos(), 30)
lin = [l for l in log_oficina()[-30:] if "Bridge no disponible" in l]
R["d3_sin_job_latido"] = {"oficina_cerrada_en_s": s_d3, "aviso": lin[-1] if lin else None, "restos": procesos(),
                          "ok": s_d3 is not None and s_d3 <= 15 and bool(lin) and not procesos()}
gb.OFICINA_PID_FILE.unlink(missing_ok=True)

# (e) salir de la app con la oficina abierta (quit_app)
h5 = host("salir")
esperar(lambda: len(procesos()) >= 1, 15)
h5.wait(90)
s_e = esperar(lambda: not procesos(), 10)
r5 = json.loads(next(BASE.glob(f"host-salir-{h5.pid}.json")).read_text(encoding="utf-8"))
R["e_salir_app"] = {"host": r5, "restos": procesos(), "en_s": s_e,
                    "ok": r5.get("salio") and not r5.get("abierta_tras_salir") and not procesos()}

# (f) DEMO desde la app: rotulo en CADA linea del log de esa oficina, y nada encolado
def cola_real():
    """Filas de cola.db (solo lectura) + encargos en runner-tasks: lo que cambiaria si algo se encolara."""
    import sqlite3
    n = None
    db = APP / "cola.db"
    if db.exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            n = con.execute("SELECT COUNT(*) FROM tareas").fetchone()[0]
        except sqlite3.Error:
            n = "sin tabla"
        con.close()
    tareas = sorted(str(q.relative_to(APP)) for q in (APP / "share" / "inbox" / "runner-tasks").rglob("*.json")) \
        if (APP / "share" / "inbox" / "runner-tasks").exists() else []
    return {"filas_cola_db": n, "encargos": tareas}


h6 = host("vivir", "demo")
esperar(lambda: len(procesos()) >= 1, 15)
time.sleep(3)
cola_antes = cola_real()  # despues de que la «app» arranque (ella crea cola.db); antes de lo que haga la oficina
time.sleep(12)
pid_demo = json.loads(next(BASE.glob(f"host-vivir-{h6.pid}.json")).read_text(encoding="utf-8"))["oficina_pid"]
subprocess.run(["taskkill", "/F", "/PID", str(h6.pid)], capture_output=True)
esperar(lambda: not procesos(), 20)
cola_despues = cola_real()
# la oficina corre en el hijo del lanzador del venv: sus lineas son las de la sesion que dice «abierta en DEMO»
lineas = log_oficina()
k = max(i_ for i_, l in enumerate(lineas) if "abierta: share=" in l)
sesion = [l for l in lineas[k:] if "[oficina pid" in l]
pid_of = sesion[0].split("[oficina pid ")[1].split("]")[0]
sesion = [l for l in sesion if l.split("[oficina pid ")[1].split("]")[0] == pid_of]
R["f_demo"] = {"lanzador_pid": pid_demo, "oficina_pid": pid_of, "lineas": len(sesion), "muestra": sesion[:2],
               "todas_rotuladas": all("DEMO" in l for l in sesion),
               "encolar_cargado": any("encolado listo" in l for l in sesion),
               "cola_antes": cola_antes, "cola_despues": cola_despues,
               "ok": bool(sesion) and all("DEMO" in l for l in sesion) and not any("encolado listo" in l for l in sesion)
               and cola_antes == cola_despues}
gb.OFICINA_PID_FILE.unlink(missing_ok=True)


# (r) cierre por falta de recursos (codigo 6): la app NO la reabre (sin configurar)
class _P:
    pid = 999999

    def poll(self):
        return 6


gb._OFICINA.update(proc=_P(), pid=999999)
gb._oficina_tick()
time.sleep(3)
R["r_falta_recursos"] = {"abierta": gb.oficina_abierta(), "procesos": len(procesos()),
                         "reabrir_programado": gb._OFICINA["reabrir_after"] is not None,
                         "ok": not gb.oficina_abierta() and not procesos() and gb._OFICINA["reabrir_after"] is None}

# (s) huerfana de una app anterior (su Bridge murio y el pid file quedo): se limpia al arrancar
falso_bridge = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
cmd = [str(Path(PYGAME).parents[1] / "Scripts" / "python.exe"), str(APP / "share" / "inbox" / "oficina" / "protocolo" / "oficina_proto.py"),
       "--share", str(APP / "share"), "--app", str(APP), "--bridge-pid", str(falso_bridge.pid),
       "--latido", str(APP / "share" / "outbox" / "huerfana-latido.json")]
huer = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
esperar(lambda: len(procesos()) >= 1, 15)
gb.OFICINA_PID_FILE.write_text(json.dumps({"pid": huer.pid, "bridge_pid": falso_bridge.pid}), encoding="utf-8")
falso_bridge.kill()
falso_bridge.wait()
t = time.time()
res = gb._oficina_huerfana_limpiar("al arrancar (prueba)")
s_s = esperar(lambda: not procesos(), 10)
R["s_huerfana_al_arrancar"] = {"resultado": res, "en_s": s_s, "restos": procesos(),
                               "ok": res == "limpiada" and not procesos()}

R["registro_app"] = log_app()[-30:]
R["ok"] = all(v.get("ok") for k, v in R.items() if isinstance(v, dict))
(EVI / "ciclo-vida-salida.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v.get("ok") if isinstance(v, dict) else None for k, v in R.items()}, indent=1), flush=True)
os._exit(0)

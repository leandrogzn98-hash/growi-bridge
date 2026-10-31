"""Subfuncion 5 de t-oficina-protocolo-050 con el growi-bridge.py del REPO parcheado, en una carpeta
aislada: importar no abre la oficina; abrir lanza el subproceso y guarda su PID; una segunda apertura
no lanza otra; si la oficina muere la app sigue; cerrar la mata limpio y borra el PID."""
import importlib.machinery, importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path(r"C:\Users\forte\source\growi-bridge")
APP = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\ciclo\app")
EVID = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\evidencia")
PARCHE = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\scripts\parche_oficina.py")
shutil.rmtree(APP.parent, ignore_errors=True)
APP.mkdir(parents=True)
for f in ("growi-bridge.py", "engines.json", "riesgos.json", "models-catalog.json", "VERSION"):
    shutil.copy2(REPO / f, APP / f)
for d in ("asistentes", "skills"):
    shutil.copytree(REPO / d, APP / d, ignore=shutil.ignore_patterns("__pycache__"))
s = json.loads((Path.home() / "growi-bridge" / "settings.json").read_text(encoding="utf-8"))
s.update(onboarding_done=True,
         oficina_pygame_dir=str(REPO / "oficina" / "mediciones" / ".venv" / "Lib" / "site-packages"))
(APP / "settings.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
(APP / "share" / "inbox").mkdir(parents=True)
(APP / "share" / "outbox").mkdir(parents=True)
assert subprocess.run([sys.executable, str(PARCHE), str(APP / "growi-bridge.py")]).returncode == 0
for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
    os.environ.pop(k, None)
ld = importlib.machinery.SourceFileLoader("gbo", str(APP / "growi-bridge.py"))
sp = importlib.util.spec_from_file_location("gbo", APP / "growi-bridge.py", loader=ld)
gb = importlib.util.module_from_spec(sp)
sp.loader.exec_module(gb)
assert gb.APP_DIR == APP, gb.APP_DIR


def procesos_oficina():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ForEach-Object { $_.CommandLine }"],
                       capture_output=True, text=True, errors="replace")
    return [l.strip() for l in r.stdout.splitlines() if "oficina_proto.py" in l and str(APP) in l]


OUT = {"script": str(gb._oficina_script()), "python": gb._oficina_python()[2]}
OUT["al_importar_sin_oficina"] = not procesos_oficina() and not gb.oficina_abierta()
OUT["abrir"] = gb.oficina_abrir()
time.sleep(6)
gb._oficina_tick()  # sin ventana: el latido a mano (en la app lo hace root.after cada 5 s)
pidf = json.loads(gb.OFICINA_PID_FILE.read_text(encoding="utf-8")) if gb.OFICINA_PID_FILE.exists() else None
OUT["pid_guardado"] = pidf and pidf["pid"] == gb._OFICINA["pid"]
OUT["viva_tras_6s"] = gb.oficina_abierta() and len(procesos_oficina()) == 1
OUT["segunda_apertura"] = gb.oficina_abrir()  # debe ser False
OUT["procesos_tras_segunda"] = len(procesos_oficina())
t = time.time()
OUT["cerrar"] = gb.oficina_cerrar("prueba")
OUT["cerrar_s"] = round(time.time() - t, 2)
time.sleep(1)
OUT["tras_cerrar"] = {"procesos": len(procesos_oficina()), "pid_file": gb.OFICINA_PID_FILE.exists()}
# la oficina muere sola: la app sigue
gb.oficina_abrir()
time.sleep(5)
pid = gb._OFICINA["pid"]
subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
time.sleep(1)
gb._oficina_tick()
OUT["oficina_muerta_app_sigue"] = {"abierta": gb.oficina_abierta(), "pid_file": gb.OFICINA_PID_FILE.exists(),
                                   "app_viva": True}
lineas = [l for l in (APP / "growi-bridge.log").read_text(encoding="utf-8", errors="replace").splitlines()
          if "oficina:" in l]
OUT["registro"] = lineas[-8:]
OUT["ok"] = bool(OUT["al_importar_sin_oficina"] and OUT["abrir"] and OUT["pid_guardado"] and OUT["viva_tras_6s"]
                 and OUT["segunda_apertura"] is False and OUT["procesos_tras_segunda"] == 1 and OUT["cerrar"]
                 and OUT["tras_cerrar"] == {"procesos": 0, "pid_file": False}
                 and not OUT["oficina_muerta_app_sigue"]["abierta"])
(EVID / "e2-ciclo-app-salida.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(OUT, ensure_ascii=False, indent=1))
os._exit(0)

"""Verificacion visual (f, h) de t-oficina-estados-050 en el prototipo: un «Bridge falso» escribe
runner-status / runner-live / cola-live / latido coherentes en una carpeta share de prueba y la
oficina los deriva con estados.py. Fases:
  0-14 s : Sonny trabajando, Dex en cola, Opus esperando aprobacion, Hermes Ollama terminado; el resto
           sin tarea y, con --sueno-min 0.1 (DEMO rotulado), dormidos a los 6 s.
  14 s   : clic (PostMessage a la ventana, sin mover el raton) sobre Luma dormida -> T24.
  18 s   : Sonny termina y el runner toma una tarea de Hermes Directo, que dormia -> T23.
Capturas en pruebas/evidencia/oficina-estados-050/ y transiciones en el jsonl de metricas."""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

R = Path(__file__).resolve().parents[2]
PROTO = R / "oficina" / "protocolo" / "oficina_proto.py"
BASE = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "growi-bridge" / "_prueba-estados-050" / "demo"
EVID = R / "pruebas" / "evidencia" / "oficina-estados-050"
PYG = R / "oficina" / "mediciones" / ".venv" / "Lib" / "site-packages"
APP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "growi-bridge" / "_prueba-oficina-protocolo" / "app"
shutil.rmtree(BASE, ignore_errors=True)
OUT = BASE / "share" / "outbox"
(OUT / "runner-results").mkdir(parents=True)
EVID.mkdir(parents=True, exist_ok=True)


def iso(t):
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def escribir(nombre, d):
    tmp = OUT / (nombre + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    for i in range(6):  # como cola_live_write: un lector puede tenerlo abierto justo ahora
        try:
            os.replace(tmp, OUT / nombre)
            return
        except PermissionError:
            time.sleep(0.05 * (i + 1))


def tarea(tid, estado, motor, modelo, creado, fin=None):
    return {"id": tid, "estado": estado, "motor": motor, "modelo": modelo, "raiz": tid, "creado_en": iso(creado),
            "actualizado_en": iso(fin or time.time())}


def mundo(fase, t_ini):
    ahora = time.time()
    tareas = [tarea("t-dex", "en_cola", "codex", None, t_ini - 50),
              tarea("t-opus", "esperando_aprobacion", "claude", "opus", t_ini - 80),
              tarea("t-ollama", "terminada", "ollama", "hermes", t_ini - 120, fin=t_ini - 2)]
    if fase == 0:
        tareas.append(tarea("t-sonny", "en_curso", "claude", "sonnet", t_ini - 30))
        live = {"task_id": "t-sonny", "estado": "en curso", "motor": "claude", "modelo": "sonnet", "actualizado": iso(ahora)}
        cur = {"id": "t-sonny"}
    else:
        tareas.append(tarea("t-sonny", "terminada", "claude", "sonnet", t_ini - 30, fin=t_ini + 18))
        tareas.append(tarea("t-hermes", "en_curso", "llama", "hermes-3", t_ini + 17))
        live = {"task_id": "t-hermes", "estado": "en curso", "motor": "llama", "modelo": "hermes-3", "actualizado": iso(ahora)}
        cur = {"id": "t-hermes"}
    escribir("cola-live.json", {"actualizado": iso(ahora), "guardrail": "siempre", "cola_pendiente": 2, "tareas": tareas})
    escribir("runner-live.json", live)
    escribir("runner-status.json", {"alive": True, "last_poll": iso(ahora), "current": cur, "pid": os.getpid()})
    escribir("bridge-latido.json", {"pid": os.getpid(), "t": ahora, "cerrar": False})


def clic(titulo, x, y):
    u32 = ctypes.windll.user32
    hwnd = u32.FindWindowW(None, titulo)
    if not hwnd:
        return False
    lp = (y << 16) | (x & 0xFFFF)
    u32.PostMessageW(hwnd, 0x0200, 0, lp)  # WM_MOUSEMOVE: SDL da el foco del raton a la ventana con esto
    time.sleep(0.1)
    u32.PostMessageW(hwnd, 0x0201, 1, lp)  # WM_LBUTTONDOWN
    u32.PostMessageW(hwnd, 0x0202, 0, lp)  # WM_LBUTTONUP
    return True


t_ini = time.time()
mundo(0, t_ini)
datos = BASE / "datos"
env = dict(os.environ, PYTHONPATH=str(PYG), PYTHONIOENCODING="utf-8")
of = subprocess.Popen([sys.executable, str(PROTO), "--share", str(BASE / "share"), "--app", str(APP), "--bridge-pid",
                       str(os.getpid()), "--datos", str(datos), "--mutex", "Local\\GrowiDemoEstados", "--sueno-min", "0.1",
                       "--captura", str(EVID / "f-sin-tarea-3s.png") + "@3",
                       "--captura", str(EVID / "h-dormidos-11s.png") + "@11",
                       "--captura", str(EVID / "h-clic-despierta-16s.png") + "@16",
                       "--captura", str(EVID / "h-tarea-despierta-23s.png") + "@23", "--salir-a", "25"],
                      env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
t_of = None
clicado = False
while of.poll() is None:
    t = time.time() - t_ini
    mundo(0 if t < 18 else 1, t_ini)
    if t_of is None and (datos / "oficina-protocolo.log").exists():
        t_of = time.time()
    if not clicado and t_of and time.time() - t_of > 13.5:
        # Luma: zona «local» (x=220,y=300) -> primer miembro en (244, 334); centro del sprite
        clicado = clic("Oficina Growi — prototipo de protocolo (Pygame-ce)", 244 + 16, 334 + 24)
    time.sleep(0.5)
trans = []
for f in datos.glob("metricas-*.jsonl"):
    for linea in f.read_text(encoding="utf-8").splitlines():
        d = json.loads(linea)
        if d.get("evento") in ("transicion", "despertar", "fuera_de_tabla"):
            trans.append({k: d.get(k) for k in ("evento", "agente", "desde", "hacia", "T", "por", "motivo")})
res = {"clic_enviado": clicado, "codigo": of.returncode, "transiciones": trans,
       "T22": sorted({x["agente"] for x in trans if x.get("T") == "T22"}),
       "T23": [x["agente"] for x in trans if x.get("T") == "T23"],
       "T24": [x["agente"] for x in trans if x.get("evento") == "despertar"],
       "fuera_de_tabla": [x for x in trans if x["evento"] == "fuera_de_tabla"],
       "vigilante_o_leandro_dormidos": [x for x in trans if x.get("hacia") == "dormir" and x["agente"] in ("vigilante", "leandro")]}
res["ok"] = bool(res["T22"] and "hermes_directo" in res["T23"] and "luma" in res["T24"] and not res["fuera_de_tabla"]
                 and not res["vigilante_o_leandro_dormidos"])
(EVID / "demo-estados.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: res[k] for k in ("ok", "clic_enviado", "T22", "T23", "T24", "fuera_de_tabla")}, ensure_ascii=False))

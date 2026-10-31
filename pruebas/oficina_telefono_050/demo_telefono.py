"""Verificacion visual (a, b) del telefono en el prototipo: runner real aislado (motor ollama, $0) + latido,
y teclas por PostMessage a la ventana (T, el texto con WM_CHAR, Enter) sin tocar el teclado ni el raton."""
import ctypes
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
src = R / "pruebas" / "prueba_motor_generico_052.py"
ld = importlib.machinery.SourceFileLoader("p052", str(src))
sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp)
ld.exec_module(p052)
p052.BASE = p052.REAL / "_prueba-telefono-050-demo"
p052.APP = p052.BASE / "app"
p052.preparar()
gb = p052.cargar()
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
time.sleep(1)
gb.runner_heartbeat()  # runner-status.json desde el primer segundo (la app lo hace en su bucle)
LAT = gb.OUTBOX / "bridge-latido.json"


def latir():
    while not stop.is_set():
        tmp = LAT.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pid": os.getpid(), "t": time.time(), "cerrar": False}), encoding="utf-8")
        for i in range(6):
            try:
                os.replace(tmp, LAT)
                break
            except PermissionError:
                time.sleep(0.05)
        time.sleep(2)


threading.Thread(target=latir, daemon=True).start()
EV = R / "pruebas" / "evidencia" / "oficina-telefono-050"
PYG = Path(r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Lib\site-packages")
env = dict(os.environ, PYTHONPATH=str(PYG), PYTHONIOENCODING="utf-8", GROWI_BRIDGE_APP_DIR=str(p052.APP))
datos = p052.BASE / "datos"
import shutil  # noqa: E402
shutil.rmtree(datos, ignore_errors=True)  # sin metricas de corridas anteriores
of = subprocess.Popen([sys.executable, str(R / "oficina" / "protocolo" / "oficina_proto.py"), "--share",
                       str(p052.APP / "share"), "--app", str(p052.APP), "--bridge-pid", str(os.getpid()),
                       "--datos", str(datos), "--mutex", "Local\\GrowiDemoTelefono",
                       "--captura", str(EV / "a-telefono-cerrado.png") + "@4",
                       "--captura", str(EV / "a-telefono-abierto-escribiendo.png") + "@9",
                       "--captura", str(EV / "b-growi-leyendo.png") + "@11",
                       "--captura", str(EV / "b-respuesta-con-id.png") + "@17", "--salir-a", "19"],
                      env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
u32 = ctypes.windll.user32
TIT = "Oficina Growi — prototipo de protocolo (Pygame-ce)"
t0 = time.time()
while not (datos / "oficina-protocolo.log").exists() and time.time() - t0 < 30:
    time.sleep(0.2)
time.sleep(5)
hwnd = u32.FindWindowW(None, TIT)
enviado = False
if hwnd:
    u32.PostMessageW(hwnd, 0x0100, 0x54, 1 | (0x14 << 16))  # WM_KEYDOWN «T» (SDL lee el scancode del lParam)
    u32.PostMessageW(hwnd, 0x0101, 0x54, 1 | (0x14 << 16) | (3 << 30))
    time.sleep(0.4)
    for ch in "Pídele a ollama: responde solo con la palabra hola":
        u32.PostMessageW(hwnd, 0x0102, ord(ch), 0)  # WM_CHAR
        time.sleep(0.03)
    time.sleep(2.0)
    u32.PostMessageW(hwnd, 0x0100, 0x0D, 1 | (0x1C << 16))  # Enter
    u32.PostMessageW(hwnd, 0x0101, 0x0D, 1 | (0x1C << 16) | (3 << 30))
    enviado = True
of.wait(timeout=60)
stop.set()
lineas = (datos / "oficina-protocolo.log").read_text(encoding="utf-8").splitlines()
tel = [x for x in lineas if "telefono" in x]
mets = []
for f in datos.glob("metricas-*.jsonl"):
    mets += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if '"telefono"' in x]
res = {"ventana": bool(hwnd), "teclas_enviadas": enviado, "log": tel, "confirmaciones": mets,
       "ok": bool(mets) and len(mets) == 1 and "t-" in mets[0].get("respuesta", "")}
(EV / "demo-telefono.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
sys.stdout.flush()
os._exit(0)

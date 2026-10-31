"""(a) el boton «Oficina · Abrir/Cerrar» de la barra lateral: construye la ventana de la copia aislada
(build_gui, sin main(): no toca puertos ni la app instalada), pulsa el boton y captura la ventana.

  python prueba_boton.py   (despues de prueba_ciclo_vida.py, que prepara la copia)
"""
import importlib.machinery
import importlib.util
import json
import os
import time
from pathlib import Path

from PIL import ImageGrab

BASE = Path.home() / "growi-bridge" / "_prueba-ciclo-vida"
APP = BASE / "app"
EVI = BASE / "evidencia"
for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
    os.environ.pop(k, None)
ld = importlib.machinery.SourceFileLoader("gbo", str(APP / "growi-bridge.py"))
sp = importlib.util.spec_from_file_location("gbo", APP / "growi-bridge.py", loader=ld)
gb = importlib.util.module_from_spec(sp)
sp.loader.exec_module(gb)
gb._theme_init()
root = gb.build_gui()
root.deiconify()
root.geometry("1200x800+40+40")
root.lift()
root.attributes("-topmost", True)
R = {}


def esperar(seg):
    t = time.time()
    while time.time() - t < seg:
        root.update()
        time.sleep(0.05)


def captura(nombre):
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height())).save(EVI / nombre)


esperar(2)
b = gb._widgets["sb_oficina_btn"]
R["texto_inicial"] = b.cget("text")
captura("a-boton-abrir.png")
b.invoke()
esperar(6)
R["tras_pulsar"] = {"texto": b.cget("text"), "abierta": gb.oficina_abierta(), "pid": gb._OFICINA["pid"]}
captura("a-boton-cerrar.png")
b.invoke()
esperar(2)
R["tras_pulsar_otra_vez"] = {"texto": b.cget("text"), "abierta": gb.oficina_abierta()}
R["ok"] = (R["texto_inicial"] == "Abrir" and R["tras_pulsar"]["texto"] == "Cerrar" and R["tras_pulsar"]["abierta"]
           and R["tras_pulsar_otra_vez"] == {"texto": "Abrir", "abierta": False})
(EVI / "a-boton-salida.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(R, ensure_ascii=False), flush=True)
os._exit(0)

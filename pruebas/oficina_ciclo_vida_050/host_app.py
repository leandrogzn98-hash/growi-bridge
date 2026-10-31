"""Hace de «app» en las pruebas del ciclo de vida (t-oficina-ciclo-vida-050): importa el growi-bridge.py
de una copia AISLADA y usa sus funciones reales (oficina_abrir / oficina_cerrar / _oficina_tick /
quit_app). Sin ventana: el latido que en la app da root.after cada 5 s aqui lo da un bucle.

  python host_app.py <carpeta app> vivir [demo]   abre la oficina y late hasta que lo maten
  python host_app.py <carpeta app> abrir          intenta abrir (para la 2.a instancia) y sale
  python host_app.py <carpeta app> salir          abre, espera 8 s y sale por quit_app()
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

APP = Path(sys.argv[1])
MODO = sys.argv[2]
for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
    os.environ.pop(k, None)
ld = importlib.machinery.SourceFileLoader("gbo", str(APP / "growi-bridge.py"))
sp = importlib.util.spec_from_file_location("gbo", APP / "growi-bridge.py", loader=ld)
gb = importlib.util.module_from_spec(sp)
sp.loader.exec_module(gb)
assert gb.APP_DIR == APP, gb.APP_DIR
OUT = APP.parent / f"host-{MODO}-{os.getpid()}.json"


def guardar(**kw):
    OUT.write_text(json.dumps(dict(pid=os.getpid(), **kw), ensure_ascii=False), encoding="utf-8")


if MODO == "abrir":
    r = gb.oficina_abrir()
    guardar(abrir=r, oficina_pid=gb._OFICINA["pid"])
    os._exit(0)
ok = gb.oficina_abrir(demo=len(sys.argv) > 3 and sys.argv[3] == "demo")
guardar(abrir=ok, oficina_pid=gb._OFICINA["pid"], job=gb._OFICINA["job"] is not None)
t0 = time.time()
while True:
    time.sleep(5)
    gb._oficina_tick()
    if MODO == "salir" and time.time() - t0 >= 8:
        gb.quit_app()
        guardar(abrir=ok, salio=True, abierta_tras_salir=gb.oficina_abierta())
        os._exit(0)

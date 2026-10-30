"""Runner AISLADO para t-oficina-encolar-externa-050: el runner_loop real de
growi-bridge.py, pero desde la copia en _prueba-encolar-externa\\app (su share,
su cola.db, su log y su settings.json). Sin ventana, sin puente (no abre 8787).
Se para al aparecer app\\STOP o a los N segundos; al salir para el llama-server
que haya lanzado (srv_al_salir, como la app al salir).
Uso: python encolar_runner_aislado.py [segundos]"""
import importlib.machinery
import importlib.util
import os
import sys
import threading
import time
from pathlib import Path

APP = Path(r"C:\Users\forte\growi-bridge\_prueba-encolar-externa\app")
for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
    os.environ.pop(k, None)
src = APP / "growi-bridge.py"
ld = importlib.machinery.SourceFileLoader("growi_bridge", str(src))
spec = importlib.util.spec_from_file_location("growi_bridge", src, loader=ld)
gb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gb)
assert gb.APP_DIR == APP, gb.APP_DIR
gb.POLL_SECONDS = 1
gb.state["runner"] = "corriendo"
print(f"runner aislado pid={os.getpid()} TASKS={gb.TASKS} COLA_DB={gb.COLA_DB} "
      f"guardrail={gb.guardrail_level()}", flush=True)
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
threading.Thread(target=gb.model_lane_loop, args=(stop,), daemon=True).start()
limite = float(sys.argv[1]) if len(sys.argv) > 1 else 1800
t0 = time.time()
(APP / "STOP").unlink(missing_ok=True)
while time.time() - t0 < limite and not (APP / "STOP").exists():
    time.sleep(1)
stop.set()
time.sleep(3)
try:
    gb.srv_al_salir()
except Exception as e:
    print("srv_al_salir:", type(e).__name__, e)
print("runner aislado: parado", flush=True)

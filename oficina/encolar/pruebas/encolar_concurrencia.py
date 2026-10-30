"""Dos procesos encolan a la vez (mismo segundo): ids distintos, ningun archivo pisado."""
import json, os, sys, time
os.environ["GROWI_BRIDGE_APP_DIR"] = r"C:\Users\forte\growi-bridge\_prueba-encolar-externa\app"
sys.path.insert(0, r"C:\Users\forte\growi-bridge\share\inbox\oficina\encolar")
import encolar
encolar.cargar_app()
t = float(sys.argv[1])
while time.time() < t:
    time.sleep(0.001)
r = encolar.encolar("Borra el archivo concurrencia.txt (prueba de concurrencia)", ["concurrencia.txt ya no existe"], model="haiku")
print(json.dumps({"pid": os.getpid(), "ok": r["ok"], "id": r.get("id")}))

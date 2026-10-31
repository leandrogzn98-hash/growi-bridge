"""lote-live integrado en el repo: el runner del repo publica cola-live.json (y runner-live.json)
en una instancia aislada, con una tarea local de $0 (motor llama u ollama)."""
import importlib.machinery, importlib.util, json, os, sys, threading, time
from pathlib import Path

src = Path(r"C:\Users\forte\source\growi-bridge\pruebas\prueba_motor_generico_052.py")
ld = importlib.machinery.SourceFileLoader("p052", str(src)); sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp); ld.exec_module(p052)
p052.BASE = p052.REAL / "_prueba-lote-live-repo"
p052.APP = p052.BASE / "app"
p052.preparar()
gb = p052.cargar()
EVID = Path(r"C:\Users\forte\source\growi-bridge\pruebas\evidencia\lote-live-repo")
EVID.mkdir(parents=True, exist_ok=True)
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
CL = gb.COLA_LIVE_FILE
t0 = time.time()
while not CL.exists() and time.time() - t0 < 30:
    time.sleep(0.2)
out = {"cola_live_al_arrancar_s": round(time.time() - t0, 1) if CL.exists() else None}
first = json.loads(CL.read_text(encoding="utf-8")) if CL.exists() else None
out["cabecera"] = {k: v for k, v in (first or {}).items() if k != "tareas"}
r = gb.encolar_tarea("Responde solo con la palabra: listo", criterios=["la respuesta contiene listo"],
                     model="motor:ollama", origen="prueba")
tid = r.get("id")
out["encolar"] = {k: r.get(k) for k in ("ok", "id", "error")}
vistos, muestras = [], []
t1 = time.time()
while time.time() - t1 < 300:
    try:
        d = json.loads(CL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        time.sleep(0.3)
        continue
    fila = next((x for x in d.get("tareas", []) if x.get("id") == tid), None)
    est = fila and fila.get("estado")
    if est and (not vistos or vistos[-1] != est):
        vistos.append(est)
        muestras.append({"t": round(time.time() - t1, 1), "fila": fila, "actualizado": d.get("actualizado")})
    if est in ("terminada", "fallida", "necesita_decision"):
        break
    time.sleep(0.5)
# frescura sin cambios: el pulso reescribe cada <= 10 s
a1 = json.loads(CL.read_text(encoding="utf-8"))["actualizado"]
time.sleep(12)
a2 = json.loads(CL.read_text(encoding="utf-8"))["actualizado"]
out.update(estados_vistos=vistos, muestras=muestras, latido=[a1, a2], latido_ok=a1 != a2,
           campos_fuera_de_contrato=sorted({k for m in muestras for k in m["fila"]} - set(gb.CL_CAMPOS_TAREA)),
           runner_live=json.loads(gb.LIVE_FILE.read_text(encoding="utf-8")).get("task_id") if gb.LIVE_FILE.exists() else None)
out["ok"] = bool(out["cola_live_al_arrancar_s"] is not None and "en_cola" in vistos[:1] + vistos
                 and vistos and vistos[-1] == "terminada" and out["latido_ok"] and not out["campos_fuera_de_contrato"])
stop.set()
(EVID / "resultado.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("ok", "estados_vistos", "latido_ok", "cola_live_al_arrancar_s", "runner_live")},
                 ensure_ascii=False))
sys.stdout.flush()
os._exit(0)

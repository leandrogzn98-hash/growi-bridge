"""Duda 13/14 (t-oficina-estados-050): captura en vivo que valor toman .orquestacion.json,
runner-live.json, cola-live.json y cola.db MIENTRAS el runner revisa una tarea. Instancia aislada,
tarea local de $0 (motor ollama, revision con el revisor configurado)."""
import importlib.machinery, importlib.util, json, os, shutil, sqlite3, sys, threading, time
from pathlib import Path

src = Path(r"C:\Users\forte\source\growi-bridge\pruebas\prueba_motor_generico_052.py")
ld = importlib.machinery.SourceFileLoader("p052", str(src)); sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp); ld.exec_module(p052)
p052.BASE = p052.REAL / "_prueba-estados-050"
p052.APP = p052.BASE / "app"
p052.preparar()
gb = p052.cargar()
EVID = Path(r"C:\Users\forte\source\growi-bridge\pruebas\evidencia\oficina-estados-050")
EVID.mkdir(parents=True, exist_ok=True)
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
time.sleep(2)
r = gb.encolar_tarea("Escribe en una sola línea tres colores primarios separados por comas.",
                     criterios=["la respuesta nombra tres colores"], model="motor:ollama", origen="prueba")
tid = r["id"]


def leer(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


filas, ultimo, copia_revisando = [], None, None
t0 = time.time()
while time.time() - t0 < 600:
    fam = leer(gb._family_path(tid)) or {}
    live = leer(gb.LIVE_FILE) or {}
    cl = leer(gb.COLA_LIVE_FILE) or {}
    fila_cl = next((x for x in cl.get("tareas", []) if x.get("id") == tid), {})
    try:
        c = sqlite3.connect(f"file:{gb.COLA_DB}?mode=ro", uri=True)
        db = c.execute("select estado from tareas where id=?", (tid,)).fetchone()
        c.close()
    except sqlite3.Error:
        db = None
    hay_res = (gb.RESULTS / f"{tid}.result.json").exists()
    hay_rev = (gb.RESULTS / f"{tid}.revision.json").exists()
    v = (fam.get("estado"), live.get("estado") if live.get("task_id") == tid else None, fila_cl.get("estado"),
         db and db[0], hay_res, hay_rev)
    if v != ultimo:
        filas.append({"t": round(time.time() - t0, 1), "orquestacion": v[0], "runner_live": v[1], "cola_live": v[2],
                      "cola_db": v[3], "result_json": v[4], "revision_json": v[5]})
        ultimo = v
        if v[0] == "revisando" and copia_revisando is None:
            copia_revisando = fam
            shutil.copy2(gb._family_path(tid), EVID / "orquestacion-durante-revision.json")
    if fam.get("final"):
        break
    time.sleep(0.15)
out = {"tarea": tid, "secuencia": filas, "orquestacion_revisando": copia_revisando}
stop.set()
(EVID / "captura-revisando.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(filas, ensure_ascii=False))
sys.stdout.flush()
os._exit(0)

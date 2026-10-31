"""Prueba de t-skills-unidades-052 (0.5.2, componente 4) en instancia aislada con el runner del repo:
(a) una tarea pide una skill por su nombre y se activa aunque la descripcion no coincida, con sus entradas en el
prompt y sus salidas como criterio «existe» que la revision comprueba; (b) skill que no existe -> no se encola;
(c) entrada obligatoria sin valor -> no se encola; (d) paso de workflow con skill; (e) estadisticas por skill;
(f) /gateway/skills con token 200, sin token 401. Motor local (ollama, $0)."""
import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

R = Path(__file__).resolve().parents[1]
ld = importlib.machinery.SourceFileLoader("p052", str(R / "pruebas" / "prueba_motor_generico_052.py"))
sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp)
ld.exec_module(p052)
p052.BASE = p052.REAL / "_prueba-skills-unidades-052"
p052.APP = p052.BASE / "app"
p052.preparar()
sk_dir = p052.APP / "skills" / "nota-prueba"
sk_dir.mkdir(parents=True, exist_ok=True)
(sk_dir / "SKILL.md").write_text("""---
name: nota-prueba
description: "Escribe una nota corta en un archivo de texto con el contenido que se le pasa como entrada, para probar las skills como unidades."
version: 1.0.0
entradas:
  - "texto | ¿Qué escribo en la nota?"
  - "archivo | ¿Cómo se llama el archivo? | nota.txt"
salidas:
  - nota.txt
---

# Nota de prueba

Crea en la carpeta de la tarea el archivo indicado en la entrada «archivo» con exactamente el contenido de la
entrada «texto», en una sola línea. Responde solo: HECHO.
""", encoding="utf-8")
gb = p052.cargar()
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
EV = R / "pruebas" / "evidencia" / "skills-unidades-052"
EV.mkdir(parents=True, exist_ok=True)
OUT = {}
gb.skills_indexar("prueba")
OUT["indice"] = [(s["name"], s.get("entradas"), s.get("salidas")) for s in gb.skills_indice()["skills"]]

# (b) y (c) al validar: no se encola
cwd = str(p052.APP / "share" / "inbox" / "trabajo")
_t, err_b = gb.validate_task({"id": "t-b", "prompt": "hola", "cwd": cwd, "skill": "no-existe", "model": "motor:ollama"})
_t, err_c = gb.validate_task({"id": "t-c", "prompt": "hola", "cwd": cwd, "skill": "nota-prueba", "model": "motor:ollama"})
OUT["b_no_existe"] = {"error": err_b, "ok": _t is None and "no existe" in (err_b or "")}
OUT["c_entrada_obligatoria"] = {"error": err_c, "ok": "falta la entrada «texto»" in (err_c or "")}

# (a) tarea real que pide la skill por su nombre (el encargo NO se parece a la descripcion)
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
r = gb.encolar_tarea("Haz lo que dice la skill.", criterios=None, model="motor:ollama", skill="nota-prueba",
                     entradas={"texto": "las skills ya son unidades"})
tid = r["id"]
t0 = time.time()
while time.time() - t0 < 300:
    f = gb.cola_get(tid) or {}
    if f.get("estado") in ("terminada", "fallida", "necesita_decision"):
        break
    time.sleep(1)
res = json.loads((gb.RESULTS / f"{tid}.result.json").read_text(encoding="utf-8"))
task = json.loads(next(p for p in (gb.DONE / f"{tid}.task.json", gb.PROCESSING / f"{tid}.task.json") if p.exists())
                  .read_text(encoding="utf-8"))
v, _e = gb.validate_task(dict(task, id=tid + "-v"))
rev = gb.RESULTS / f"{tid}.revision.json"
revj = json.loads(rev.read_text(encoding="utf-8")) if rev.exists() else {}
nota = Path(task["cwd"]) / "nota.txt"
OUT["a_pedida"] = {"estado": f.get("estado"), "skills_activadas": res.get("skills_activadas"),
                   "skills_pedidas": res.get("skills_pedidas"),
                   "registro": {k: res.get("skills", {}).get(k) for k in ("pedidas", "activadas")},
                   "criterios_tipados_derivados": v and v.get("criterios_tipados"), "entradas_en_task": v and v.get("entradas_skill"),
                   "nota_txt": nota.read_text(encoding="utf-8").strip() if nota.exists() else None,
                   "revision": {k: revj.get(k) for k in ("veredicto", "aprobada", "checks", "motivo") if k in revj},
                   "ok": "nota-prueba" in (res.get("skills_activadas") or []) and res.get("skills_pedidas") == ["nota-prueba"]
                   and bool(v and v.get("criterios_tipados")) and (v.get("entradas_skill") or {}).get("archivo") == "nota.txt"}

# (d) paso de workflow con skill: pasa wf_validar y el .task.json de la fase lleva skill y entradas
(gb.WF_DIR).mkdir(parents=True, exist_ok=True)
(gb.WF_DIR / "con-skill.json").write_text(json.dumps({"id": "con-skill", "nombre": "Con skill", "motor": "motor:ollama",
    "pasos": [{"id": "nota", "prompt": "Haz lo de la skill.", "skill": "nota-prueba",
               "entradas": {"texto": "desde un workflow"}, "revisar": False}]}, ensure_ascii=False), encoding="utf-8")
wf = gb.wf_get("con-skill")
rw = gb.encolar_workflow("con-skill", confirmado=True)
t1 = time.time()
fase_task = None
while time.time() - t1 < 120:
    for d in (gb.TASKS, gb.PROCESSING, gb.DONE):
        q = d / f"{rw['id']}-nota.task.json"
        if q.exists():
            fase_task = json.loads(q.read_text(encoding="utf-8"))
    if fase_task:
        break
    time.sleep(1)
OUT["d_workflow"] = {"wf_valido": wf["wf"] is not None, "error": wf.get("error"),
                     "fase_skill": (fase_task or {}).get("skill"), "fase_entradas": (fase_task or {}).get("entradas"),
                     "ok": (fase_task or {}).get("skill") == "nota-prueba"}
time.sleep(30)  # que la fase termine para que cuente en las estadisticas
stop.set()

# (e) estadisticas y (f) gateway
est = gb.skills_estadisticas()
OUT["e_estadisticas"] = {"nota-prueba": est.get("nota-prueba"), "ok": (est.get("nota-prueba") or {}).get("usos", 0) >= 1
                         and (est.get("nota-prueba") or {}).get("pedida", 0) >= 1}
SECRETO = "prueba-skills-052"


class H(gb.BridgeHandler):
    SECRET = SECRETO

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/gateway/skills"
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with op.open(urllib.request.Request(url, headers={"Authorization": f"Bearer {SECRETO}"}), timeout=30) as rr:
    vista, code = json.loads(rr.read().decode("utf-8")), rr.status
try:
    op.open(url, timeout=10)
    sin = None
except urllib.error.HTTPError as e:
    sin = e.code
srv.shutdown()
OUT["f_gateway"] = {"codigo": code, "sin_token": sin, "skills": [(x["nombre"], x["como_pedirla"]) for x in vista["skills"]],
                    "ok": code == 200 and sin == 401 and any(x["nombre"] == "nota-prueba" for x in vista["skills"])}
OUT["todo_ok"] = all(v.get("ok") for v in OUT.values() if isinstance(v, dict) and "ok" in v)
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v.get("ok") for k, v in OUT.items() if isinstance(v, dict) and "ok" in v}, ensure_ascii=False),
      OUT["todo_ok"])
sys.stdout.flush()
os._exit(0)

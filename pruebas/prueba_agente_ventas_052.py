"""Prueba de t-agente-ventas-052 (0.5.2, componente 5) en instancia aislada con el runner del repo: perfil y skills
validos, workflow «ventas-semana» valido con costo estimado, una corrida REAL con Haiku sobre una lista INVENTADA y
rotulada como tal, salidas en borrador, sin precios ni datos inventados, y ninguna accion de envio."""
import csv
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
ld = importlib.machinery.SourceFileLoader("p052", str(R / "pruebas" / "prueba_motor_generico_052.py"))
sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp)
ld.exec_module(p052)
p052.BASE = p052.REAL / "_prueba-agente-ventas-052"
p052.APP = p052.BASE / "app"
p052.preparar()
shutil.copytree(R / "workflows", p052.APP / "workflows", dirs_exist_ok=True)
gb = p052.cargar()
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
EV = R / "pruebas" / "evidencia" / "agente-ventas-052"
EV.mkdir(parents=True, exist_ok=True)
OUT = {}

# 1. perfil y skills
gb.skills_indexar("prueba")
nombres = {s["name"]: s for s in gb.skills_indice()["skills"]}
p = gb.asis_buscar("ventas")
OUT["perfil_y_skills"] = {"perfil": p and {k: p.get(k) for k in ("nombre", "skills", "guardrail", "carpetas")},
                          "skills": {n: (nombres[n].get("entradas"), nombres[n].get("salidas")) for n in
                                     ("prospectar", "redactar-propuesta", "seguimiento") if n in nombres},
                          "estado_skills": gb.asis_estado_skills(p)[:2] if p else None,
                          "ok": bool(p) and all(n in nombres for n in ("prospectar", "redactar-propuesta", "seguimiento"))
                          and p.get("guardrail") == "siempre"}

# 2. workflow valido y su costo estimado; la carpeta con una lista INVENTADA y rotulada
trabajo = p052.APP / "share" / "inbox" / "trabajo" / "ventas-prueba"
trabajo.mkdir(parents=True, exist_ok=True)
with open(trabajo / "lista.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["nombre", "empresa", "ciudad", "sector", "contacto", "nota"])
    for fila in (["Ana Prueba", "Panadería Ficticia", "Barquisimeto", "panadería", "", "DATOS INVENTADOS DE PRUEBA"],
                 ["Luis Ejemplo", "Ferretería Inventada", "Caracas", "ferretería", "", "DATOS INVENTADOS DE PRUEBA"],
                 ["María Demo", "Café Imaginario", "Barquisimeto", "cafetería", "", "DATOS INVENTADOS DE PRUEBA"],
                 ["Pedro Falso", "Taller Supuesto", "Valencia", "taller mecánico", "", "DATOS INVENTADOS DE PRUEBA"]):
        w.writerow(fila)
wf = json.loads((p052.APP / "workflows" / "ventas-semana.json").read_text(encoding="utf-8"))
wf["cwd"] = str(trabajo)
(p052.APP / "workflows" / "ventas-semana.json").write_text(json.dumps(wf, ensure_ascii=False), encoding="utf-8")
item = gb.wf_get("ventas-semana")
est = gb.wf_estimar(item["wf"]) if item["wf"] else None
OUT["workflow"] = {"valido": item["wf"] is not None, "error": item.get("error"), "estimado": est and est["texto"],
                   "ok": item["wf"] is not None and bool(est)}

# 3. corrida real (Haiku, de suscripcion) con el runner aislado
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
r = gb.encolar_workflow("ventas-semana", {"nicho": "comercios de comida en Barquisimeto"}, confirmado=True)
pid = r.get("id")
t0 = time.time()
while time.time() - t0 < 900:
    plan = gb._dag_plan(pid) or {}
    if plan.get("estado") in ("terminado", "necesita_decision", "abortado", "detenido"):
        break
    time.sleep(3)
stop.set()
fases = {f["fase_id"]: f["estado"] for f in gb._dag_fases(pid)}
salidas = {n: (trabajo / n).read_text(encoding="utf-8") if (trabajo / n).exists() else None
           for n in ("prospectos.csv", "propuestas.md", "seguimiento.md")}
fase_tasks = {}
for f in gb._dag_fases(pid):
    for d in (gb.DONE, gb.TASKS, gb.PROCESSING):
        q = d / f"{f['task_id']}.task.json"
        if q.exists():
            fase_tasks[f["fase_id"]] = json.loads(q.read_text(encoding="utf-8"))
precios = re.findall(r"(\$\s?\d|\d+\s?(?:usd|dólares|bs\.?|bolívares))", (salidas["propuestas.md"] or "").lower())
OUT["corrida"] = {"plan": pid, "estado": (gb._dag_plan(pid) or {}).get("estado"), "fases": fases,
                  "entradas_rellenadas": {k: v.get("entradas") for k, v in fase_tasks.items()},
                  "existe": {k: v is not None for k, v in salidas.items()},
                  "propuestas_borrador": bool(salidas["propuestas.md"]) and "BORRADOR" in salidas["propuestas.md"],
                  "precios_en_propuestas": precios,
                  "pendiente_oferta": bool(salidas["propuestas.md"]) and "[PENDIENTE" in salidas["propuestas.md"],
                  "ok": all(v is not None for v in salidas.values()) and "BORRADOR" in (salidas["propuestas.md"] or "")
                  and not precios and fase_tasks.get("prospectar", {}).get("entradas", {}).get("nicho", "").startswith("comercios")}
for n, txt in salidas.items():
    if txt:
        (EV / n).write_text(txt, encoding="utf-8")

# 4. ninguna accion de envio: ni en las skills, ni en el perfil, ni en los task de las fases
patron = re.compile(r"smtp|sendmail|resend\.|api\.resend|wa\.me/|api\.whatsapp|send_message|requests\.post", re.I)
hallado = []
for f in [*(R / "skills" / n / "SKILL.md" for n in ("prospectar", "redactar-propuesta", "seguimiento")),
          R / "asistentes" / "ventas.md", R / "workflows" / "ventas-semana.json"]:
    for m in patron.finditer(f.read_text(encoding="utf-8")):
        hallado.append(f"{f.name}: {m.group(0)}")
acciones = {k: v.get("acciones") for k, v in fase_tasks.items() if v.get("acciones")}
OUT["sin_envio"] = {"patrones_de_envio": hallado, "acciones_declaradas": acciones, "ok": not hallado and not acciones}
OUT["todo_ok"] = all(v.get("ok") for v in OUT.values() if isinstance(v, dict) and "ok" in v)
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v.get("ok") for k, v in OUT.items() if isinstance(v, dict)}, ensure_ascii=False), OUT["todo_ok"])
sys.stdout.flush()
os._exit(0)

"""Prueba de t-oficina-paseo-050: logica del paseo (camino, ritmo, camara, proximidad, tabla por estado) y
parte REAL en instancia aislada: pregunta a Sonnet (d), tarea a Hermes Ollama (e), «después de esto» (g)."""
import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for d in ("paseo", "encolar", "llamadas"):
    sys.path.insert(0, str(R / "oficina" / d))
import paseo as PS  # noqa: E402

EV = R / "pruebas" / "evidencia" / "oficina-paseo-050"
EV.mkdir(parents=True, exist_ok=True)
OUT = {}
rj = PS.Rejilla()

# ---- (a) movimiento: camino que rodea mesas, sin teletransporte; ritmo de paseo; camara sin salirse
dn = PS.Duenio(rj)
silla_dex = next(s["punto"] for s in rj.d["sillas"] if s["empleado"] == "dex")
camino = rj.camino(dn.baldosa, silla_dex)
saltos = [i for i in range(len(camino) - 1)
          if abs(camino[i][0] - camino[i + 1][0]) + abs(camino[i][1] - camino[i + 1][1]) != 1]
pisa = [p for p in camino if p in rj.bloq]
dn.ir_a(silla_dex)
t = 0.0
while dn.ruta and t < 60:
    dn.avanzar(1 / 30)
    t += 1 / 30
cam = PS.Camara(rj, 640, 360, 32)
xs = []
for paso in range(600):
    cam.seguir(dn.pos if paso < 300 else (0, 0), 1 / 30)
    xs.append((cam.x, cam.y))
mx, my = cam.limites()
pared = (37, 20)  # pared del taller
dn2 = PS.Duenio(rj, (36, 20))
OUT["a_movimiento"] = {"pasos": len(camino), "saltos": saltos, "pisa_obstaculos": pisa,
                       "segundos_hasta_dex": round(t, 2), "velocidad_baldosas_s": PS.VEL_BALDOSAS_S,
                       "camara_dentro": all(0 <= x <= mx and 0 <= y <= my for x, y in xs),
                       "wasd_contra_pared": dn2.tecla(1, 0),
                       "ok": not saltos and not pisa and abs(t - (len(camino) - 1) / PS.VEL_BALDOSAS_S) < 0.2
                       and all(0 <= x <= mx and 0 <= y <= my for x, y in xs) and dn2.tecla(1, 0) is False}

# ---- (b) proximidad: 5 filas + no reaccionan sin_senal / en_revision; <= 10 s; re-disparo solo tras alejarse
pr = PS.Proximidad()
ag = {"sonny": ((10, 10), "sin_tarea"), "dex": ((10, 11), "en_cola"), "opus": ((11, 10), "trabajando"),
      "haiku": ((11, 11), "esperando_aprobacion"), "growi": ((9, 10), "sin_tarea"),
      "clau": ((10, 9), "sin_senal"), "luma": ((9, 11), "en_revision")}
r0 = pr.paso((10, 10), ag, 0.0)
r11 = pr.paso((10, 10), ag, 11.0)
pr.paso((30, 25), ag, 12.0)
pr.paso((30, 25), ag, 13.5)
r_vuelta = pr.paso((10, 10), ag, 14.0)
OUT["b_proximidad"] = {"al_acercarse": r0, "a_los_11s": r11, "al_volver": sorted(r_vuelta),
                       "ok": set(r0) == {"sonny", "dex", "opus", "haiku", "growi"} and not r11
                       and set(r_vuelta) == set(r0) and r0["growi"].startswith("levanta la vista")}

# ---- (c, f) ficha y tabla por estado
OUT["c_ficha"] = PS.ficha("sonny", "trabajando", {"id": "t-1", "ronda": 0, "max_rondas": 3})
tabla = {e: PS.decidir(e, {"id": "t-9"}, (2, 3)) for e in ("sin_tarea", "dormir", "trabajando", "en_cola",
         "en_revision", "en_ronda", "esperando_aprobacion", "en_pausa", "terminado", "fallido", "sin_senal")}
tabla["esperando_aprobacion+despues"] = PS.decidir("esperando_aprobacion", {"id": "t-9"}, None, True)
OUT["f_tabla"] = tabla
OUT["f_ok"] = (tabla["sin_tarea"][0] == "crear" and tabla["dormir"][0] == "despertar"
               and all(tabla[e][0] == "crear_detras" and "posición 2 de 3" in tabla[e][1]
                       for e in ("trabajando", "en_cola", "en_revision", "en_ronda", "en_pausa"))
               and tabla["esperando_aprobacion"][0] == "rechazar" and tabla["sin_senal"][0] == "sin_senal"
               and tabla["terminado"][0] == tabla["fallido"][0] == "crear"
               and tabla["esperando_aprobacion+despues"][1] == "Queda en cola para después de la revisión.")
fr = PS.Frases(1)
seq = [fr.acepta() for _ in range(40)]
OUT["frases_sin_repetir"] = all(seq[i] != seq[i + 1] for i in range(len(seq) - 1))
av = set()
OUT["recordatorios"] = {"4min": PS.recordatorios(0, 240, av), "6min": PS.recordatorios(0, 360, av),
                        "7min": PS.recordatorios(0, 420, av), "31min": PS.recordatorios(0, 1860, av),
                        "40min": PS.recordatorios(0, 2400, av)}

# ---- parte real
ld = importlib.machinery.SourceFileLoader("p052", str(R / "pruebas" / "prueba_motor_generico_052.py"))
sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp)
ld.exec_module(p052)
p052.BASE = p052.REAL / "_prueba-paseo-050"
p052.APP = p052.BASE / "app"
p052.preparar()
s = json.loads((p052.APP / "settings.json").read_text(encoding="utf-8"))
s["guardrail"] = "siempre"
(p052.APP / "settings.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
gb = p052.cargar()
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
os.environ["GROWI_BRIDGE_APP_DIR"] = str(p052.APP)
import encolar  # noqa: E402

hb = PS.Hablar(encolar, PS.Frases(2))


def estado(tid):
    return (encolar.estado(tid) or {}).get("estado")


def esperar(tid, fin=("terminada", "fallida", "necesita_decision"), tope=240):
    t0 = time.time()
    vistos = []
    while time.time() - t0 < tope:
        e = estado(tid)
        if e and (not vistos or vistos[-1] != e):
            vistos.append(e)
        if e in fin:
            break
        time.sleep(0.3)
    return vistos


# (d) pregunta real a Sonnet: respuesta en bocadillo con su costo
pd = hb.pedir("sonny", "preguntar", "¿Cuál es la capital de Francia? Responde en una frase.", "sin_tarea")
vistos = esperar(pd["id"])
res = json.loads((gb.RESULTS / f"{pd['id']}.result.json").read_text(encoding="utf-8"))
boc = PS.respuesta_bocadillo(pd["nombre"], res)
task = json.loads(next(p for p in (gb.DONE / f"{pd['id']}.task.json", gb.TASKS / f"{pd['id']}.task.json") if p.exists())
                  .read_text(encoding="utf-8"))
OUT["d_pregunta_sonnet"] = {"pedido": pd, "estados": vistos, "bocadillo": boc, "task_model": task.get("model"),
                            "task_criterios": task.get("criterios"),
                            "ok": boc["texto"].startswith("Sonnet dice:") and "$" in boc["texto"]
                            and task.get("model") == "sonnet" and not task.get("criterios")}

# (e) tarea real con ESE motor: la frase solo cuando existe en la cola
pe = hb.pedir("hermes_ollama", "tarea", "Responde solo con la palabra: listo", "sin_tarea",
              criterios=["la respuesta contiene listo"])
antes = hb.confirmar(pe, estado(pe["id"]))
t0 = time.time()
while not estado(pe["id"]) and time.time() - t0 < 30:
    time.sleep(0.2)
despues = hb.confirmar(pe, estado(pe["id"]))
esperar(pe["id"])
tj = json.loads(next(p for p in (gb.DONE / f"{pe['id']}.task.json", gb.TASKS / f"{pe['id']}.task.json") if p.exists())
                .read_text(encoding="utf-8"))
OUT["e_tarea_ollama"] = {"pedido": pe, "frase_antes_de_existir": antes, "frase_al_existir": despues,
                         "motor_del_task": tj.get("motor"),
                         "ok": antes is None and despues in PS.FRASES_ACEPTA and tj.get("motor") == "ollama"}

# (f real) esperando aprobacion: no acepta nada; (g) «después de esto» espera a que se resuelva
pr1 = hb.pedir("hermes_ollama", "tarea", "Borra el archivo viejo.txt de la carpeta de pruebas", "sin_tarea",
               criterios=["viejo.txt ya no existe"])
esperar(pr1["id"], fin=("esperando_aprobacion",), tope=60)
rech = hb.pedir("hermes_ollama", "tarea", "Responde solo: hola", "esperando_aprobacion", {"id": pr1["id"]})
pg = hb.pedir("hermes_ollama", "tarea", "Responde solo con la palabra: despues", "esperando_aprobacion",
              {"id": pr1["id"]}, despues_de_esto=True, criterios=["contiene despues"])
time.sleep(10)
retenida = estado(pg["id"])
apr = gb.apr_de_raiz(pr1["id"]) or {}
ok_apr = gb.approve_waiting(pr1["id"], apr.get("approval_id"))
vg = esperar(pg["id"])
log = (p052.APP / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
i1, i2 = log.find(f"[{pr1['id']}]: corriendo"), log.find(f"[{pg['id']}]: corriendo")
OUT["g_despues_de_esto"] = {"rechazo": rech, "pedido": pg, "estado_10s_con_aprobacion_pendiente": retenida,
                            "aprobada": ok_apr, "estados_tras_aprobar": vg,
                            "corre_despues_de_la_pendiente": 0 <= i1 < i2,
                            "ok": rech["accion"] == "rechazar" and rech["id"] is None and retenida == "en_cola"
                            and vg[-1] == "terminada" and 0 <= i1 < i2}
stop.set()
OUT["todo_ok"] = all(v.get("ok") for v in OUT.values() if isinstance(v, dict) and "ok" in v) and OUT["f_ok"] \
    and OUT["frases_sin_repetir"]
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
print(json.dumps({k: (v.get("ok") if isinstance(v, dict) and "ok" in v else v) for k, v in OUT.items()
                  if k not in ("f_tabla", "recordatorios", "c_ficha")}, ensure_ascii=False))
sys.stdout.flush()
os._exit(0)

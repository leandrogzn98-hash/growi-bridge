"""Prueba de t-oficina-llamadas-050. Parte REAL (instancia aislada, runner del repo): llamada a Claude Haiku
con su linea de tiempo frente al lanzamiento real (a), motor inexistente (b), Meshy sin clave (c), una
urgente adelanta sin interrumpir (e) y el aviso de 3 en cola con su si/no (e). Parte SIMULADA con el formato
real de cola-live / runner-live: ocupado con posicion (d), no contesta / necesita revision (f), fin (g)."""
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

R = Path(__file__).resolve().parents[2]
ld = importlib.machinery.SourceFileLoader("p052", str(R / "pruebas" / "prueba_motor_generico_052.py"))
sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp)
ld.exec_module(p052)
p052.BASE = p052.REAL / "_prueba-llamadas-050"
p052.APP = p052.BASE / "app"
p052.preparar()
gb = p052.cargar()
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
os.environ["GROWI_BRIDGE_APP_DIR"] = str(p052.APP)
for d in ("encolar", "telefono", "llamadas"):
    sys.path.insert(0, str(R / "oficina" / d))
import encolar  # noqa: E402
import llamadas as LL  # noqa: E402
import telefono as TF  # noqa: E402

EV = R / "pruebas" / "evidencia" / "oficina-llamadas-050"
EV.mkdir(parents=True, exist_ok=True)
OUT = {}
MOT = set((json.loads((p052.APP / "engines.json").read_text(encoding="utf-8")).get("motores") or {}).keys())


def leer(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fila_de(tid):
    c = leer(gb.COLA_LIVE_FILE) or {}
    return next((x for x in c.get("tareas") or [] if x.get("id") == tid), None), c


def edad(iso):
    try:
        return time.time() - datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return None


# ---- (e) urgente: 3 tareas con el runner PARADO (la urgente, la ultima); al arrancar, ¿cual toma primero?
ids = []
for i, (txt, urg) in enumerate((("Responde solo: uno", False), ("Responde solo: dos", False),
                                ("Responde solo: urgente", True))):
    r = encolar.encolar(txt, model="motor:ollama", urgente=urg)
    ids.append(r["id"])
    time.sleep(1.1)  # ids y mtime distintos
time.sleep(2.2)  # el runner solo mira tareas con >= 2 s
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
time.sleep(1)
gb.runner_heartbeat()
t0 = time.time()
while time.time() - t0 < 120:
    fs = [fila_de(i)[0] for i in ids]
    if all(f and f.get("estado") in ("terminada", "fallida") for f in fs):
        break
    time.sleep(0.5)
log = (p052.APP / "growi-bridge.log").read_text(encoding="utf-8", errors="replace").splitlines()
orden = []
for linea in log:
    m = re.search(r"runner \[(t-[\d-]+)\]: corriendo", linea)
    if m and m.group(1) in ids and m.group(1) not in orden:
        orden.append(m.group(1))
OUT["e_urgente"] = {"encoladas_en_orden": ids, "urgente": ids[2], "orden_de_ejecucion": orden,
                    "ok": bool(orden) and orden[0] == ids[2] and orden[1:] == ids[:2]}

# ---- (a) llamada real a Claude Haiku: fases de la oficina cada 0,1 s frente al log del runner
r = encolar.encolar("Responde solo con la palabra: listo", model="haiku")
tid = r["id"]
fases, t0 = [], time.time()
while time.time() - t0 < 180:
    f, cola = fila_de(tid)
    live = leer(gb.LIVE_FILE)
    st = leer(gb.OUTBOX / "runner-status.json")
    if f:
        ll = LL.llamada(f, cola, live, st, MOT, live_edad=edad((live or {}).get("actualizado")))
        if not fases or fases[-1][1] != ll["fase"]:
            fases.append((round(time.time() - t0, 2), ll["fase"], ll["gerente"], ll["jefe_dice"]))
        if f.get("estado") in ("terminada", "fallida", "necesita_decision"):
            break
    time.sleep(0.1)
log = (p052.APP / "growi-bridge.log").read_text(encoding="utf-8", errors="replace").splitlines()
lanz = [x[:25] + " " + x.split("]: ", 1)[-1][:80] for x in log if tid in x and ("corriendo" in x or "lanzado" in x
                                                                               or "terminado" in x)]
OUT["a_llamada_claude"] = {"tarea": tid, "fases": fases, "log_runner": lanz,
                           "ok": [x[1] for x in fases][:1] in (["marcando"], ["ocupado"])
                           and any(x[1] in ("timbre", "en_linea") for x in fases) and fases[-1][1] in ("fin_ok",)}

# ---- (b) motor que no existe en engines.json
r = encolar.encolar("Responde: hola", model="motor:noexiste")
t0 = time.time()
f = None
while time.time() - t0 < 30:
    f, cola = fila_de(r["id"])
    if f and f.get("estado") in ("fallida", "necesita_decision"):
        break
    time.sleep(0.5)
st = leer(gb.OUTBOX / "runner-status.json")
ll = LL.llamada(f or {"id": r["id"], "motor": "noexiste", "estado": "en_cola"}, cola, leer(gb.LIVE_FILE), st, MOT, live_edad=99)
OUT["b_motor_inexistente"] = {"encolar": {k: r.get(k) for k in ("ok", "id", "error")}, "fila": f, "llamada": ll,
                              "ok": ll["fase"] == "suena_en_vacio" and bool(f) and f.get("estado") == "fallida"}

# ---- (c) Meshy sin clave: candado, nadie teclea
gb.runner_heartbeat()
st = leer(gb.OUTBOX / "runner-status.json")
ll = LL.llamada({"id": "t-meshy", "motor": "meshy", "estado": "en_cola"}, {"tareas": []}, None, st, MOT, live_edad=None)
OUT["c_meshy_sin_clave"] = {"runner_status_meshy": (st.get("motores") or {}).get("meshy"), "llamada": ll,
                            "ok": ll["fase"] == "candado"}
ll2 = LL.llamada({"id": "t-meshy2", "motor": "meshy", "estado": "en_curso", "actualizado_en": datetime.now().astimezone().isoformat()},
                 {"tareas": []}, None, {"motores": {"meshy": {"disponible": True, "motivo": "clave en APIs"}}}, MOT, live_edad=None)
OUT["c_meshy_con_clave_simulado"] = {"llamada": ll2, "ok": ll2["fase"] == "buzon"}

# ---- (e) aviso de 3 en cola y su si/no (runner parado: las tareas se quedan en cola)
stop.set()
time.sleep(2)
for i in range(3):
    rr = encolar.encolar(f"Pídele a ollama: tarea de relleno {i}", model="motor:ollama")
    gb._cola_ver(Path(rr["archivo"]))  # lo que hace el runner al verla: la apunta en cola.db (en_cola)
    time.sleep(1.05)
gb.cola_live_write()
tel = TF.Telefono(encolar_mod=encolar, cola=lambda: leer(gb.COLA_LIVE_FILE))
tel.TOPE_S = 4


def hablar(txt):
    tel.enviar(txt)
    t1 = time.time()
    while tel.estado != "colgado" and time.time() - t1 < 15:
        time.sleep(0.1)
    return tel.confirmaciones[-1][1]


r1 = hablar("Pídele a ollama: una más")
r2 = hablar("no")
r3 = hablar("Pídele a ollama: otra más")
r4 = hablar("sí")
OUT["e_tres_en_cola"] = {"pregunta": r1, "respuesta_no": r2, "pregunta_2": r3, "respuesta_si": r4,
                         "ok": "tiene 3 en cola" in r1 and r2 == "Vale, no lo encolo." and "en cola" in r3 and "t-" in r4}

# ---- parte simulada (formato real): ocupado con posicion, no contesta, necesita revision, fin
ahora = time.time()
iso = lambda s: datetime.fromtimestamp(ahora + s).astimezone().isoformat(timespec="seconds")  # noqa: E731
cola = {"tareas": [{"id": "t-a", "estado": "en_curso", "motor": "claude", "creado_en": iso(-90)},
                   {"id": "t-b", "estado": "en_cola", "motor": "codex", "creado_en": iso(-60)},
                   {"id": "t-c", "estado": "en_cola", "motor": "claude", "creado_en": iso(-30)},
                   {"id": "t-u", "estado": "en_cola", "motor": "ollama", "creado_en": iso(-5), "urgente": True}]}
live = {"task_id": "t-a", "estado": "en curso", "started_at": iso(-200), "lanzado_at": iso(-198), "actualizado": iso(-2)}
sim = {}
sim["d_ocupado_t-c"] = LL.llamada(cola["tareas"][2], cola, live, {"current": {"id": "t-a"}}, MOT, ahora, 2)
sim["d_urgente_t-u"] = LL.llamada(cola["tareas"][3], cola, live, {"current": {"id": "t-a"}}, MOT, ahora, 2)
sim["en_linea_ambar_t-a"] = LL.llamada(cola["tareas"][0], cola, live, {}, MOT, ahora, 2)
sim["f_no_contesta"] = LL.llamada({"id": "t-x", "estado": "en_cola", "motor": "codex", "reintentos": 1,
                                   "proximo_intento": iso(+120)}, cola, live, {}, MOT, ahora, 2)
sim["f_necesita_revision"] = LL.llamada({"id": "t-x", "estado": "fallida", "motor": "codex", "reintentos": 3,
                                         "actualizado_en": iso(-5), "motivo": "Codex falló con un error pasajero "
                                         "(timeout) tras 3 reintentos y la tarea queda fallida"}, cola, live, {}, MOT, ahora, 2)
sim["g_fin_ok"] = LL.llamada({"id": "t-a", "estado": "terminada", "motor": "claude", "actualizado_en": iso(-3)},
                             cola, live, {}, MOT, ahora, 2)
sim["g_fin_aprobacion"] = LL.llamada({"id": "t-a", "estado": "esperando_aprobacion", "motor": "claude"}, cola, live,
                                     {}, MOT, ahora, 2)
OUT["simulado"] = sim
OUT["d_ok"] = sim["d_ocupado_t-c"]["posicion"] == (3, 3) and sim["d_urgente_t-u"]["posicion"] == (1, 3) \
    and "n.º 3 de 3" in sim["d_ocupado_t-c"]["gerente"] and sim["d_urgente_t-u"]["gerente"].startswith("!")
OUT["ambar_ok"] = sim["en_linea_ambar_t-a"]["ambar"] and sim["en_linea_ambar_t-a"]["jefe_dice"] == "Sigue en ello..."
OUT["f_ok"] = sim["f_no_contesta"]["fase"] == "no_contesta" and sim["f_necesita_revision"]["fase"] == "necesita_revision"
OUT["g_ok"] = all("resultado" not in json.dumps(sim[k], ensure_ascii=False) for k in ("g_fin_ok", "g_fin_aprobacion")) \
    and sim["g_fin_ok"]["gerente"] == "Listo, Claude se encarga."
OUT["todo_ok"] = all(v.get("ok") for v in OUT.values() if isinstance(v, dict) and "ok" in v) and all(
    OUT[k] for k in ("d_ok", "ambar_ok", "f_ok", "g_ok"))
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
print(json.dumps({k: (v.get("ok") if isinstance(v, dict) and "ok" in v else v) for k, v in OUT.items()
                  if k != "simulado"}, ensure_ascii=False))
sys.stdout.flush()
os._exit(0)

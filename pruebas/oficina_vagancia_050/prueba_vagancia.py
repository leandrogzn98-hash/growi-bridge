"""Prueba de t-oficina-vagancia-050 con reloj simulado (sin esperar de verdad): R1-R5, tick de 5 s con semilla,
sin repeticiones, las 8 actividades, A4 a 0 sin con quien, catalogo, eventos raros, degradacion y dormir."""
import json
import socket
import sys
import tempfile
from collections import Counter
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "oficina" / "vagancia"))
import vagancia as VG  # noqa: E402

EV = R / "pruebas" / "evidencia" / "oficina-vagancia-050"
EV.mkdir(parents=True, exist_ok=True)
plano = json.loads((R / "oficina" / "plano" / "plano.json").read_text(encoding="utf-8"))
POIS = {p["id"]: p["capacidad"] for p in plano["puntos_interes"]}
OUT = {}


def sesion(pois=POIS, agentes=("sonny", "dex", "luma", "cody", "opus"), horas=2.0, hora=11, of=None, paso=1.0):
    of = of or VG.Oficina(pois, fecha="2026-10-30")
    t = 0.0
    while t < horas * 3600:
        for a in agentes:
            of.evento_estado(a, "sin_tarea", t)
        of.tick(t, hora)
        t += paso
    return of


# R3: ni red ni modelos durante 10 min de vagancia (cualquier socket nuevo revienta la prueba)
real_socket = socket.socket
llamadas = []


class Prohibido(socket.socket):
    def __init__(self, *a, **k):
        llamadas.append(a)
        raise RuntimeError("R3: la vagancia abrió un socket")


socket.socket = Prohibido
try:
    of10 = sesion(horas=10 / 60)
finally:
    socket.socket = real_socket
fuente = (R / "oficina" / "vagancia" / "vagancia.py").read_text(encoding="utf-8")
OUT["R3_sin_red_ni_modelos"] = {"sockets": len(llamadas), "imports_red": [m for m in ("urllib", "requests", "http.client",
                                "socket", "sqlite3", "subprocess") if f"import {m}" in fuente],
                                "ok": not llamadas and not any(f"import {m}" in fuente for m in ("urllib", "requests", "socket"))}

# R1: el badge dice el estado real aunque el sprite tome cafe
of = VG.Oficina(POIS)
OUT["R1_badge"] = {"tomando_cafe_y_esperando": VG.badge("esperando_aprobacion"),
                   "ok": VG.badge("esperando_aprobacion") == "esperando aprobacion" and VG.badge("trabajando") == "trabajando"}

# R2: interrupcion a mitad de un cafe al llegar trabajo real (sin terminarlo)
of = VG.Oficina(POIS, fecha="2026-10-30")
t = 0.0
while not (of.actividad_de("sonny") == "cafe"):
    of.evento_estado("sonny", "sin_tarea", t)
    of.evento_estado("dex", "sin_tarea", t)
    of.tick(t, 9)
    t += 1
    if t > 20000:
        break
fin_previsto = of.agentes["sonny"].actividad[2]
of.evento_estado("sonny", "trabajando", t + 1)
OUT["R2_interrupcion"] = {"t_cafe": t, "fin_previsto_del_cafe": fin_previsto, "interrumpido_en": t + 1,
                          "actividad_tras_evento": of.actividad_de("sonny"), "cafe_liberado": "sonny" not in of.uso["cafe"],
                          "ok": of.actividad_de("sonny") is None and "sonny" not in of.uso["cafe"] and fin_previsto > t + 1}

# R4: oficina seria
of = sesion(horas=0.2)
of.vagancia_activa = False
of.tick(10000, 11)
OUT["R4_oficina_seria"] = {"actividades_tras_apagar": {a: of.actividad_de(a) for a in of.agentes},
                           "ok": all(of.actividad_de(a) is None for a in of.agentes)}

# R5: el bano (cap. 1) y el cafe (cap. 2) nunca por encima de su capacidad
of = VG.Oficina(POIS, fecha="2026-10-30")
max_uso = Counter()
t = 0.0
while t < 4 * 3600:
    for a in ("sonny", "dex", "luma", "cody", "opus", "haiku", "gemi"):
        of.evento_estado(a, "sin_tarea", t)
    of.tick(t, 9)
    for p, u in of.uso.items():
        max_uso[p] = max(max_uso[p], len(u))
    t += 1
OUT["R5_capacidad"] = {"maximo_simultaneo": dict(max_uso), "capacidad": POIS,
                       "ok": all(max_uso[p] <= POIS[p] for p in POIS)}

# (b, c, d) tick con semilla reproducible; nunca dos seguidas; las 8 actividades; A4 a 0 sin otro ocioso
a1 = sesion(horas=3).historial
a2 = sesion(horas=3).historial
seq = {}
for _t, a, act in a1:
    seq.setdefault(a, []).append(act)
repes = {a: [i for i in range(len(s) - 1) if s[i] == s[i + 1] and not s[i].startswith("INTERRUMPIDA")]
         for a, s in seq.items()}
vistas = Counter(act for _t, _a, act in a1)
solo = VG.Oficina(POIS, fecha="2026-10-30")
ag = solo.evento_estado("sonny", "sin_tarea", 0)
OUT["b_tick"] = {"tick_s": VG.TICK_S, "reproducible": a1 == a2, "decisiones": len(a1)}
OUT["c_sin_repetir"] = {"repeticiones": repes, "ok": all(not v for v in repes.values())}
OUT["d_actividades"] = {"vistas": dict(vistas), "A4_sin_otro_ocioso": solo.puntuar(ag, "charlar", 100, 11),
                        "aplazadas": VG.APLAZADAS,
                        "ok": set(VG.ACTIVIDADES) <= set(vistas) and solo.puntuar(ag, "charlar", 100, 11) == 0}

# (e) catalogo: prueba de fuego y editable
fr = VG.cargar_frases()
malas = {f: VG.prueba_de_fuego(f) for f in fr["charla"] + fr["sueltas"] if VG.prueba_de_fuego(f)}
trampas = {f: VG.prueba_de_fuego(f) for f in ("ya terminé la tarea", "revisando lo de Codex", "van 3 de 5",
                                              "listo el informe", "¡ya acabé!")}
OUT["e_frases"] = {"charla": len(fr["charla"]), "sueltas": len(fr["sueltas"]), "fallan": malas, "trampas_detectadas": trampas,
                   "ok": len(fr["charla"]) == 24 and len(fr["sueltas"]) == 10 and not malas and all(trampas.values())}

# (f) eventos raros: frecuencia aproximada y log local; el del gerente NO existe
log = Path(tempfile.mkdtemp()) / "raros.jsonl"
of = VG.Oficina(POIS, fecha="2026-10-30", registro_raros=str(log))
sesion(horas=40, of=of, paso=2.0)
raros = Counter(json.loads(l)["evento"] for l in log.read_text(encoding="utf-8").splitlines()) if log.exists() else {}
OUT["f_raros"] = {"en_40_h": dict(raros), "gerente_disimulan_existe": "disimul" in fuente.split("ELIMINADO")[0],
                  "ok": bool(raros) and "disimul" not in json.dumps(VG.EVENTOS_RAROS)}

# (h) degradacion: sin bano ni ventana, sus actividades no existen y nada se rompe
pocos = {k: v for k, v in POIS.items() if k in ("cafe", "pasillo")}
ofp = sesion(pois=pocos, horas=2)
usadas = {act for _t, _a, act in ofp.historial}
OUT["h_degradacion"] = {"pois": pocos, "usadas": sorted(usadas),
                        "ok": not ({"bano", "ventana"} & usadas) and "cafe" in usadas}

# (i) dormir no es vagancia
of = VG.Oficina(POIS, fecha="2026-10-30")
for t in range(0, 600):
    of.evento_estado("sonny", "dormir", t)
    of.evento_estado("dex", "sin_tarea", t)
    of.tick(t, 11)
of.vagancia_activa = False
of.tick(700, 11)
OUT["i_dormir"] = {"en_el_tick": "sonny" in of.agentes, "actividades_de_sonny": [x for x in of.historial if x[1] == "sonny"],
                   "ok": "sonny" not in of.agentes and not [x for x in of.historial if x[1] == "sonny"]}
OUT["todo_ok"] = all(v.get("ok", True) for v in OUT.values() if isinstance(v, dict)) and OUT["b_tick"]["reproducible"]
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v.get("ok", v.get("reproducible")) for k, v in OUT.items() if isinstance(v, dict)}, ensure_ascii=False),
      OUT["todo_ok"])

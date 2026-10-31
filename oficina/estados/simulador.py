"""Simulador de transiciones de la oficina (t-oficina-estados-050). Recorre T1-T24 una por una y
las 6 prohibidas con fuentes de ejemplo (dicts con el formato de runner-status / runner-live /
cola-live / .orquestacion.json) y comprueba que derivar_estado() + Memoria devuelven lo que dice
la tabla. Sale con 0 si todo pasa.

  python simulador.py [--json salida.json]
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estados as E  # noqa: E402

T0 = datetime(2026, 10, 30, 15, 0, 0).astimezone().timestamp()
AG = {"id": "sonny", "rol": "modelo"}
RES = []


def iso(t):
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def fuentes(t, fila=None, live_tid=None, live_estado="en curso", live_edad=3, status_edad=20, cola_edad=4,
            latido_ok=True, current=None, sin=None):
    """Fuentes coherentes en el instante t. sin = nombre de la fuente que falta."""
    live = {"task_id": live_tid, "estado": live_estado if live_tid else "terminado",
            "actualizado": iso(t - live_edad)}
    st = {"last_poll": iso(t - status_edad), "current": {"id": current} if current else None}
    cola = {"actualizado": iso(t - cola_edad), "guardrail": "siempre", "tareas": [fila] if fila else []}
    f = {"status": st, "status_edad": status_edad, "live": live, "live_edad": live_edad, "cola": cola,
         "cola_edad": cola_edad, "latido_ok": latido_ok}
    if sin:
        f[sin] = None
    return f


def fila(tid="t-1", estado="en_cola", motor="claude", modelo="sonnet", ronda=0, fin=None, proximo=None, motivo=None):
    d = {"id": tid, "estado": estado, "motor": motor, "modelo": modelo, "creado_en": iso(T0 - 300),
         "actualizado_en": iso(fin) if fin else iso(T0 - 5)}
    if ronda:
        d["ronda"] = ronda
    if proximo:
        d["proximo_intento"] = iso(proximo)
    if motivo:
        d["motivo"] = motivo
    return d


def tarea(f, t, orq=None, live=None):
    return E.EstadoTarea(f, orq=orq, live=live, ahora=t) if f else None


def paso(mem, t, f, fu, orq=None, aprobada_por=None, ag=AG):
    return mem.paso(ag, tarea(f, t, orq, fu["live"]), fu, t, aprobada_por)


def caso(nombre, esperado_T, esperado_estado, pasos, mem=None):
    """pasos = lista de (t, fila, fuentes, orq, aprobada_por); el ultimo es el que se comprueba."""
    reg = []
    mem = mem or E.Memoria(ahora=T0 - 3600 * 3, registro=reg.append)
    if mem.registro is None:
        mem.registro = reg.append
    salida = None
    for t, f, fu, orq, apr in pasos:
        salida = paso(mem, t, f, fu, orq, apr)
    est, mot, T = salida
    ok = (T == esperado_T or (esperado_T is None)) and est == esperado_estado
    RES.append({"caso": nombre, "esperado": [esperado_T, esperado_estado], "obtenido": [T, est], "motivo": mot,
                "ok": ok, "registro": [r for r in reg if r.get("evento") in ("fuera_de_tabla", "despertar")]})
    return mem


def previo(mem, estado, tid="t-1"):
    mem.previo[AG["id"]] = estado
    mem.tarea_previa[AG["id"]] = tid if estado not in (E.SIN_TAREA, E.DORMIR) else None


def nueva_mem(estado_previo=None, tid="t-1", libre_desde=None, dormido=False):
    reg = []
    m = E.Memoria(ahora=T0 - 600, registro=reg.append)
    if estado_previo:
        previo(m, estado_previo, tid)
    if libre_desde is not None:
        m.libre_desde[AG["id"]] = libre_desde
    if dormido:
        m.dormidos.add(AG["id"])
    return m


t = T0
# ---- T1-T24, cada una por separado
caso("T1 sin_tarea→en_cola", "T1", E.EN_COLA,
     [(t, fila(estado="en_cola"), fuentes(t, current="t-otra", live_tid="t-otra"), None, None)], nueva_mem(E.SIN_TAREA))
caso("T2 sin_tarea→trabajando", "T2", E.TRABAJANDO,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, None)], nueva_mem(E.SIN_TAREA))
caso("T3 sin_tarea→esperando_aprobacion", "T3", E.ESPERANDO_APROBACION,
     [(t, fila(estado="esperando_aprobacion"), fuentes(t), None, None)], nueva_mem(E.SIN_TAREA))
caso("T4 en_cola→trabajando", "T4", E.TRABAJANDO,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, None)], nueva_mem(E.EN_COLA))
caso("T5 en_cola→esperando_aprobacion", "T5", E.ESPERANDO_APROBACION,
     [(t, fila(estado="esperando_aprobacion"), fuentes(t), None, None)], nueva_mem(E.EN_COLA))
caso("T6 trabajando→en_revision", "T6", E.EN_REVISION,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1", live_estado="revisando"), {"estado": "revisando"}, None)],
     nueva_mem(E.TRABAJANDO))
caso("T6b revision solo por .orquestacion (runner-live aun «en curso», medido 2 s)", "T6", E.EN_REVISION,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), {"estado": "revisando"}, None)], nueva_mem(E.TRABAJANDO))
caso("T7 trabajando→terminado", "T7", E.TERMINADO,
     [(t, fila(estado="terminada", fin=t - 2), fuentes(t, live_tid="t-1", live_estado="terminado"), {"estado": "sin_revision"},
       None)], nueva_mem(E.TRABAJANDO))
caso("T8 trabajando→fallido", "T8", E.FALLIDO,
     [(t, fila(estado="fallida", fin=t - 2), fuentes(t), None, None)], nueva_mem(E.TRABAJANDO))
caso("T9 trabajando→en_pausa", "T9", E.EN_PAUSA,
     [(t, fila(estado="en_cola", proximo=t + 120, motivo="límite de uso: reintento"), fuentes(t), None, None)],
     nueva_mem(E.TRABAJANDO))
caso("T10 en_revision→terminado", "T10", E.TERMINADO,
     [(t, fila(estado="terminada", fin=t - 1), fuentes(t, live_tid="t-1", live_estado="terminado"), {"estado": "aprobada"},
       None)], nueva_mem(E.EN_REVISION))
caso("T11 en_revision→en_ronda", "T11", E.EN_RONDA,
     [(t, fila(tid="t-1-r1", estado="en_cola", ronda=1), fuentes(t), {"estado": "en_curso", "ronda": 1}, None)],
     nueva_mem(E.EN_REVISION, tid="t-1-r1"))
caso("T12 en_revision→fallido", "T12", E.FALLIDO,
     [(t, fila(estado="necesita_decision", fin=t - 1), fuentes(t), {"estado": "necesita_decision"}, None)],
     nueva_mem(E.EN_REVISION))
caso("T13 en_ronda→trabajando(ronda)", "=", E.EN_RONDA,
     [(t, fila(tid="t-1-r1", estado="en_curso", ronda=1), fuentes(t, live_tid="t-1-r1"), {"estado": "en_curso"}, None)],
     nueva_mem(E.EN_RONDA, tid="t-1-r1"))
caso("T13 en_ronda→en_revision", "T13", E.EN_REVISION,
     [(t, fila(tid="t-1-r1", estado="en_curso", ronda=1), fuentes(t, live_tid="t-1-r1", live_estado="revisando"),
       {"estado": "revisando"}, None)], nueva_mem(E.EN_RONDA, tid="t-1-r1"))
caso("T14 en_pausa→trabajando", "T14", E.TRABAJANDO,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, None)], nueva_mem(E.EN_PAUSA))
caso("T15 en_pausa→fallido", "T15", E.FALLIDO,
     [(t, fila(estado="fallida", fin=t - 1, motivo="reintentos agotados"), fuentes(t), None, None)], nueva_mem(E.EN_PAUSA))
caso("T16 esperando_aprobacion→trabajando (aprobada en la app)", "T16", E.TRABAJANDO,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, "app")], nueva_mem(E.ESPERANDO_APROBACION))
caso("T16 esperando_aprobacion→en_cola (aprobada por WhatsApp, runner ocupado)", "T16", E.EN_COLA,
     [(t, fila(estado="en_cola"), fuentes(t, live_tid="t-otra"), None, "whatsapp")], nueva_mem(E.ESPERANDO_APROBACION))
caso("T17 esperando_aprobacion→fallido (vencida)", "T17", E.FALLIDO,
     [(t, fila(estado="fallida", fin=t - 1, motivo="aprobación vencida"), fuentes(t), None, None)],
     nueva_mem(E.ESPERANDO_APROBACION))
caso("T18 fallido→en_cola (re-encolada)", "T18", E.EN_COLA,
     [(t, fila(estado="en_cola"), fuentes(t, live_tid="t-otra"), None, None)], nueva_mem(E.FALLIDO))
caso("T19 terminado→sin_tarea (61 s)", "T19", E.SIN_TAREA,
     [(t, fila(estado="terminada", fin=t - 61), fuentes(t), None, None)], nueva_mem(E.TERMINADO))
caso("T20 fallido→sin_tarea (61 s): el empleado no queda «fallido»", "T20", E.SIN_TAREA,
     [(t, fila(estado="fallida", fin=t - 61), fuentes(t), None, None)], nueva_mem(E.FALLIDO))
for falta in ("status", "live", "cola"):
    caso(f"T21 trabajando→sin_senal ({falta} ausente)", "T21", E.SIN_SENAL,
         [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1", sin=falta), None, None)], nueva_mem(E.TRABAJANDO))
caso("T21 latido muerto", "T21", E.SIN_SENAL,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1", latido_ok=False), None, None)], nueva_mem(E.TRABAJANDO))
caso("T22 sin_tarea→dormir (61 min)", "T22", E.DORMIR,
     [(t, None, fuentes(t), None, None)], nueva_mem(E.SIN_TAREA, libre_desde=t - 61 * 60))
caso("T22 no: 59 min sigue sin_tarea", "=", E.SIN_TAREA,
     [(t, None, fuentes(t), None, None)], nueva_mem(E.SIN_TAREA, libre_desde=t - 59 * 60))
caso("T23 dormir→trabajando (el runner toma su tarea)", "T23", E.TRABAJANDO,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, None)],
     nueva_mem(E.DORMIR, libre_desde=t - 90 * 60, dormido=True))
m24 = nueva_mem(E.DORMIR, libre_desde=t - 90 * 60, dormido=True)
m24.despertar("sonny", "clic del jugador", t)
caso("T24 dormir→sin_tarea (clic del jugador)", "T24", E.SIN_TAREA, [(t, None, fuentes(t), None, None)], m24)
m24b = nueva_mem(E.DORMIR, libre_desde=t - 90 * 60, dormido=True)
m24b.despertar("sonny", "vigilante (noche, sin tarea pendiente)", t)
caso("T24 dormir→sin_tarea (vigilante)", "T24", E.SIN_TAREA, [(t, None, fuentes(t), None, None)], m24b)

# ---- prohibidas
caso("PROHIBIDA esperando→trabajando por hablar con el agente (la cola sigue retenida)", "=", E.ESPERANDO_APROBACION,
     [(t, fila(estado="esperando_aprobacion"), fuentes(t, live_tid="t-1"), None, None)], nueva_mem(E.ESPERANDO_APROBACION))
caso("PROHIBIDA esperando→trabajando sin aprobación registrada", "T21", E.SIN_SENAL,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, None)], nueva_mem(E.ESPERANDO_APROBACION))
caso("PROHIBIDA esperando→trabajando por aprobar en el chat", "T21", E.SIN_SENAL,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, "chat")], nueva_mem(E.ESPERANDO_APROBACION))
fu_g = fuentes(t)
fu_g["cola"]["guardrail"] = "nunca"
caso("PROHIBIDA esperando→trabajando por cambiar el guardrail", "=", E.ESPERANDO_APROBACION,
     [(t, fila(estado="esperando_aprobacion"), fu_g, None, None)], nueva_mem(E.ESPERANDO_APROBACION))
caso("PROHIBIDA sin_tarea→trabajando sin tarea en cola (live de una tarea que no está en la cola)", "=", E.SIN_TAREA,
     [(t, None, fuentes(t, live_tid="t-fantasma"), None, None)], nueva_mem(E.SIN_TAREA))
caso("PROHIBIDA fallido→trabajando sin re-encolar (misma tarea)", "T21", E.SIN_SENAL,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1"), None, None)], nueva_mem(E.FALLIDO))
sobran = E.comprobar_serie({"sonny": E.TRABAJANDO, "dex": E.TRABAJANDO, "opus": E.SIN_TAREA})
RES.append({"caso": "PROHIBIDA trabajando→trabajando de dos agentes a la vez (serie)", "esperado": ["sobra 1"],
            "obtenido": sobran, "ok": sobran == ["dex"]})

# ---- umbrales
caso("umbral runner-live 16 s = señal perdida (status viejo)", "T21", E.SIN_SENAL,
     [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1", live_edad=16, status_edad=200), None, None)],
     nueva_mem(E.TRABAJANDO))
caso("umbral runner-status 200 s NO cuenta con runner-live fresco (latido congelado mientras trabaja)", "=",
     E.TRABAJANDO, [(t, fila(estado="en_curso"), fuentes(t, live_tid="t-1", live_edad=4, status_edad=200), None, None)],
     nueva_mem(E.TRABAJANDO))
caso("umbral cola-live 61 s = vieja", "T21", E.SIN_SENAL,
     [(t, fila(estado="en_cola"), fuentes(t, cola_edad=61), None, None)], nueva_mem(E.EN_COLA))
caso("umbral terminado visible 59 s", "=", E.TERMINADO,
     [(t, fila(estado="terminada", fin=t - 59), fuentes(t), None, None)], nueva_mem(E.TERMINADO))

# ---- dormir: no toma tareas dormido; con tarea nunca se duerme; nunca duermen Leandro ni el vigilante
caso("dormido con tarea en cola: sigue dormido (no la toma él)", "=", E.DORMIR,
     [(t, fila(estado="en_cola"), fuentes(t, live_tid="t-otra"), None, None)],
     nueva_mem(E.DORMIR, libre_desde=t - 90 * 60, dormido=True))
caso("con tarea nunca se duerme (en cola 2 h)", "=", E.EN_COLA,
     [(t, fila(estado="en_cola"), fuentes(t, live_tid="t-otra"), None, None)],
     nueva_mem(E.EN_COLA, libre_desde=t - 120 * 60))
for quien in ("vigilante", "leandro"):
    est, mot = E.derivar_estado({"id": quien}, None, fuentes(t), t, t - 300 * 60)
    RES.append({"caso": f"{quien} no duerme (5 h sin tarea)", "esperado": [E.SIN_TAREA], "obtenido": [est],
                "ok": est == E.SIN_TAREA})
est, mot = E.derivar_estado({"id": "growi"}, None, fuentes(t), t, t - 61 * 60)
RES.append({"caso": "Growi (gerente) también duerme", "esperado": [E.DORMIR], "obtenido": [est], "ok": est == E.DORMIR})

# ---- dos niveles: la tarea fallida no mancha al empleado
m = nueva_mem(E.FALLIDO)
e1 = paso(m, t, fila(estado="fallida", fin=t - 61), fuentes(t))[0]
e2 = paso(m, t + 1, fila(tid="t-2", estado="en_curso"), fuentes(t + 1, live_tid="t-2"))[0]
RES.append({"caso": "niveles separados: tras fallar una tarea, el empleado queda libre y toma la siguiente",
            "esperado": [E.SIN_TAREA, E.TRABAJANDO], "obtenido": [e1, e2], "ok": [e1, e2] == [E.SIN_TAREA, E.TRABAJANDO]})

# ---- actividades: nunca teclear sin tarea; gerente
acts = {E.actividad_sin_tarea(a, x / 10.0) for a in ("sonny", "dex", "luma") for x in range(0, 1200)}
RES.append({"caso": "sin tarea nunca teclea", "obtenido": sorted(acts), "ok": "teclear" not in acts
            and acts <= set(E.ACTIVIDADES_SIN_TAREA)})
g = {E.gerente_rutina(x, False, False, ["mesa_clau", "mesa_dex"])[0] for x in range(0, 60)}
RES.append({"caso": "gerente sin trabajo: tablón, ronda y espera; nunca teclea", "obtenido": sorted(g),
            "ok": g == {"mirar_tablon", "revisar_oficina", "esperar_mirando_telefono"}})
RES.append({"caso": "gerente con algo esperando aprobación se queda junto al tablón",
            "obtenido": E.gerente_rutina(30, True, False, [])[0], "ok": E.gerente_rutina(30, True, False, [])[0] == "junto_al_tablon"})
RES.append({"caso": "gerente con el Bridge caído: junto al teléfono, gris", "obtenido": E.gerente_rutina(30, False, True, [])[0],
            "ok": E.gerente_rutina(30, False, True, [])[0] == "junto_al_telefono_gris"})

# ---- cobertura de la tabla
probadas = {r["obtenido"][0] for r in RES if isinstance(r.get("obtenido"), list) and r["obtenido"]
            and isinstance(r["obtenido"][0], str) and r["obtenido"][0].startswith("T")}
probadas |= {"T13"} if any(r["caso"].startswith("T13 en_ronda→trabajando") and r["ok"] for r in RES) else set()
todas = {x[0] for x in E.TRANSICIONES}
RES.append({"caso": "cobertura: las 24 transiciones probadas", "obtenido": sorted(todas - probadas) or "todas",
            "ok": todas <= probadas and len(todas) == 24})

ok = all(r["ok"] for r in RES)
if "--json" in sys.argv:
    Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps({"ok": ok, "casos": RES}, ensure_ascii=False,
                                                                       indent=1), encoding="utf-8")
for r in RES:
    print(("OK   " if r["ok"] else "FALLA") + " " + r["caso"] + ("" if r["ok"] else f"  -> {r.get('obtenido')} {r.get('motivo', '')}"))
print(f"\n{sum(r['ok'] for r in RES)}/{len(RES)} casos OK")
sys.exit(0 if ok else 1)

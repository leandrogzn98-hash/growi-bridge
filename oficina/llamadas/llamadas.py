"""Llamadas gerente -> departamento (t-oficina-llamadas-050, spec 13 de 18).

La llamada es la metafora de invocar a un agente: lo que se ve sale de lo que pasa (cola-live, runner-live,
runner-status, engines.json). Funcion pura `fase_llamada()`; nada se inventa:
- marcando: la tarea paso a processing (en_curso) y el motor aun no arranco (sin runner-live de ella).
- timbre (1,5 s de teatro) y en_linea: runner-live de esa tarea, fresco.
- encendiendo: motor local apagado que el runner arranca solo (llama-server, ~8 s medidos en 0.4.8).
- buzon / candado: motor asincrono (Meshy); con clave, buzon + mensajero; sin clave, candado (no se deja).
- suena_en_vacio: el motor no existe en engines.json (la tarea falla con ese motivo).
- ocupado: en cola mientras el runner esta con otra; posicion N de M calculada como la elige el runner
  (rondas, luego urgentes, luego por antiguedad). cola-live no trae la posicion: se dice «calculada».
- no_contesta: fallo pasajero con reintento programado (la politica es la del runner: 30 s, 2 min, 8 min).
- necesita_revision: fallida tras agotar los reintentos.
- fin_ok / fin_aprobacion / fin_fallo: el resultado NO se entrega aqui; solo el estado.
"""
import time
from datetime import datetime

DEPTO = {"claude": "Claude", "codex": "Codex", "llama": "Local", "ollama": "Local", "gemini": "Gemini",
         "agy": "Gemini", "meshy": "Taller 3D", "tripo": "Taller 3D"}
JEFE = {"Claude": "clau", "Codex": "cody", "Local": "luma", "Gemini": "gemi", "Taller 3D": "mensajero"}
ASINCRONOS = ("meshy", "tripo")
MAX_REINTENTOS_RUNNER = 3  # RETRY_BACKOFF_S = (30, 120, 480) en growi-bridge.py
TIMBRE_S = 1.5
AMBAR_S = 180
FIN_VISIBLE_S = 60


def _ts(iso):
    try:
        return datetime.fromisoformat(str(iso)).timestamp()
    except (TypeError, ValueError):
        return None


def mmss(s):
    s = max(0, int(s or 0))
    return f"{s // 60:02d}:{s % 60:02d}"


def resumen(texto, n=140):
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def posicion(cola, tid):
    """(N, M) en la cola del runner, o None. Orden real del runner: rondas, urgentes, resto por antiguedad
    (growi-bridge.py ordena por mtime del .task.json; creado_en es su equivalente en cola-live)."""
    ts = [x for x in (cola or {}).get("tareas") or [] if x.get("estado") == "en_cola"]
    ts.sort(key=lambda x: (0 if x.get("ronda") else 1 if x.get("urgente") else 2, x.get("creado_en") or ""))
    ids = [x["id"] for x in ts]
    return (ids.index(tid) + 1, len(ids)) if tid in ids else None


def en_cola_de(cola, depto):
    return sum(1 for x in (cola or {}).get("tareas") or []
               if x.get("estado") == "en_cola" and DEPTO.get((x.get("motor") or "").lower()) == depto)


def fase_llamada(fila, live, status, motores_desc, ahora=None, live_edad=None):
    """fila: la tarea en cola-live; live/status: runner-live / runner-status (dicts); motores_desc: ids de
    engines.json. -> dict(fase, depto, jefe, gerente, jefe_dice, duracion, ambar, posicion, urgente, linea)."""
    ahora = time.time() if ahora is None else ahora
    motor = (fila.get("motor") or "").lower()
    if not motor and any(k in (fila.get("modelo") or "").lower() for k in ("haiku", "sonnet", "opus", "claude")):
        motor = "claude"  # cola-live trae solo el modelo hasta que el runner resuelve el motor
    if not motor and isinstance(live, dict) and live.get("task_id") == fila.get("id"):
        motor = (live.get("motor") or "").lower()
    depto = DEPTO.get(motor, motor) if motor else None
    out = {"tarea": fila.get("id"), "depto": depto, "jefe": JEFE.get(depto) if depto else None, "fase": None, "gerente": None,
           "jefe_dice": None, "duracion": None, "ambar": False, "posicion": None, "urgente": bool(fila.get("urgente")),
           "linea": False}
    est = fila.get("estado")
    motivo = fila.get("motivo") or ""
    mst = ((status or {}).get("motores") or {}).get(motor) or {}
    fin = _ts(fila.get("actualizado_en"))
    live_suyo = isinstance(live, dict) and live.get("task_id") == fila.get("id")
    live_fresco = live_suyo and live_edad is not None and live_edad < 15 and live.get("estado") != "terminado"
    if motor and motor not in motores_desc or "no existe en engines.json" in motivo:
        out.update(fase="suena_en_vacio", gerente=f"Suena y suena: «{motor}» no existe en engines.json.",
                   jefe_dice=None)
        return out
    if motor in ASINCRONOS and mst and not mst.get("disponible") and "clave" in (mst.get("motivo") or ""):
        out.update(fase="candado", gerente=f"El buzón de {depto} tiene candado: {mst.get('motivo')}. No lo dejo.")
        return out
    if est == "en_cola" and not (fila.get("proximo_intento") and (_ts(fila.get("proximo_intento")) or 0) > ahora):
        otra = None
        if isinstance(live, dict) and live_edad is not None and live_edad < 15 and live.get("estado") != "terminado":
            otra = live.get("task_id")
        elif isinstance((status or {}).get("current"), dict):
            otra = status["current"].get("id")
        if otra and otra != fila.get("id"):
            out.update(fase="ocupado", jefe_dice="En línea, te llamo en cuanto termine.", ocupado_con=otra)
        else:  # el runner esta libre: la recoge en su siguiente vuelta (<= POLL_SECONDS)
            out.update(fase="marcando", gerente=(f"Llamando a {depto}..." if depto else "Llamando..."), linea=True)
        return out
    if est in ("esperando_aprobacion", "esperando_leandro"):
        out.update(fase="fin_aprobacion", gerente="Listo, te lo dejo por aprobar en la app.",
                   jefe_dice="Esperando tu aprobación.")
        return out
    if est == "terminada":
        if fin and ahora - fin > FIN_VISIBLE_S:
            out["fase"] = None
            return out
        out.update(fase="fin_ok", gerente=(f"Listo, {depto} se encarga." if depto else "Listo, ya se encargan."), jefe_dice="✓")
        return out
    if est in ("fallida", "necesita_decision", "rechazada"):
        if fin and ahora - fin > FIN_VISIBLE_S:
            return out
        if (fila.get("reintentos") or 0) >= MAX_REINTENTOS_RUNNER or "reintentos" in motivo:
            out.update(fase="necesita_revision", gerente=f"{depto} no contestó {MAX_REINTENTOS_RUNNER + 1} veces. "
                                                         "Necesita revisión (queda marcada en la app).",
                       jefe_dice="No contesta.")
        else:
            out.update(fase="fin_fallo", gerente=f"{depto}: {resumen(motivo, 90) or 'falló'}. Queda en la app.",
                       jefe_dice="×")
        return out
    if fila.get("proximo_intento") and (_ts(fila.get("proximo_intento")) or 0) > ahora:
        n = fila.get("reintentos") or 1
        out.update(fase="no_contesta", jefe_dice="No contesta.",
                   gerente=f"{depto} no contesta. Lo reintento a las {str(fila['proximo_intento'])[11:16]} "
                           f"(reintento {n} de {MAX_REINTENTOS_RUNNER}).")
        return out
    if est == "en_curso":
        lanzado = _ts((live or {}).get("lanzado_at")) if live_suyo else None
        if live_suyo and live.get("estado") == "terminado":  # el motor termino; cola aun en_curso: cuelgan
            out.update(fase="colgando", gerente=f"{depto} termina...", jefe_dice="(baja el teléfono)")
            return out
        if live_fresco and lanzado is None and live.get("estado") != "revisando":
            # runner-live se escribe antes del Popen: hasta que el proceso arranca, el gerente sigue marcando
            arranque = _ts(live.get("started_at")) or _ts(fila.get("actualizado_en")) or ahora
            out.update(fase="marcando", gerente=(f"Llamando a {depto}..." if depto else "Llamando..."), linea=True, duracion=mmss(ahora - arranque))
            return out
        inicio = lanzado or (_ts((live or {}).get("started_at")) if live_suyo else None)
        if not live_fresco:
            arranque = _ts(fila.get("actualizado_en")) or ahora
            out["duracion"] = mmss(ahora - arranque)
            if motor == "llama" and "apagado" in (mst.get("motivo") or ""):
                out.update(fase="encendiendo", gerente=(f"Llamando a {depto}..." if depto else "Llamando..."), jefe_dice="(enciende la luz)",
                           linea=True)
            elif motor in ASINCRONOS:
                out.update(fase="buzon", gerente=f"Dejo el encargo en el buzón de {depto}.",
                           jefe_dice="(el mensajero sale)", linea=True)
            else:
                out.update(fase="marcando", gerente=(f"Llamando a {depto}..." if depto else "Llamando..."), linea=True)
            return out
        d = ahora - (inicio or ahora)
        out["duracion"] = mmss(d)
        out["ambar"] = d > AMBAR_S
        out["linea"] = True
        if d < TIMBRE_S:
            out.update(fase="timbre", jefe_dice="¿Sí?", gerente=(f"Llamando a {depto}..." if depto else "Llamando..."))
        elif live.get("estado") == "revisando":
            out.update(fase="en_linea", jefe_dice="En revisión.", gerente="Te lo dejo en revisión.")
        else:
            out.update(fase="en_linea", jefe_dice="Sigue en ello..." if out["ambar"] else "En ello.",
                       gerente=resumen(fila.get("prompt") or f"{depto} trabaja en {fila.get('id')}"))
        return out
    return out


def llamada(fila, cola, live, status, motores_desc, ahora=None, live_edad=None):
    """fase_llamada + la posicion real en la cola y el texto del gerente para «ocupado»."""
    out = fase_llamada(fila, live, status, motores_desc, ahora, live_edad)
    if out["fase"] == "ocupado":
        pos = posicion(cola, fila.get("id"))
        out["posicion"] = pos
        bang = "! " if fila.get("urgente") else ""
        out["gerente"] = (f"{bang}{out['depto']} está ocupado. Tu tarea queda en cola, es la n.º {pos[0]} de {pos[1]} "
                          "(posición calculada como la elige el runner)." if pos else
                          f"{bang}{out['depto']} está ocupado. En cola, sin posición.")
    return out

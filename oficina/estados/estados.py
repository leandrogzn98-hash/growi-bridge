"""Maquina de estados de la oficina 0.5.0 (t-oficina-estados-050, spec 8 de 18).

Dos niveles separados (§3.1):
  - ESTADO DE LA TAREA: lo que dicen cola-live.json / cola.db, .orquestacion.json y .revision.json
    (en_cola, en_curso, esperando_aprobacion, esperando_leandro, terminada, fallida,
    necesita_decision, archivada, esperando_reintento). Vive en `EstadoTarea`.
  - ESTADO DEL AGENTE: lo que se ve (11 estados: los 10 de §3.2 + «dormir» de PALETA-Y-SKINS §14).
    Un agente no tiene mas estado que el de la tarea que tiene entre manos: si su ultima tarea
    fallo, la TAREA fallo; el empleado queda libre (sin_tarea) en cuanto pasan 60 s.

derivar_estado() es una funcion PURA: recibe las fuentes ya leidas y la hora, y devuelve
(estado, motivo). No lee archivos, no duerme, no tiene efectos. La memoria que necesita
(desde cuando esta libre un agente, si esta dormido) se la pasa quien la llama (`Memoria`).
El render (Pygame-ce o Godot) solo pinta lo que sale de aqui.
"""
import time
from datetime import datetime

# ---- estados visibles del agente (11)
SIN_SENAL = "sin_senal"
SIN_TAREA = "sin_tarea"
DORMIR = "dormir"
ESPERANDO_APROBACION = "esperando_aprobacion"
TERMINADO = "terminado"
FALLIDO = "fallido"
EN_PAUSA = "en_pausa"
EN_REVISION = "en_revision"
EN_RONDA = "en_ronda"
TRABAJANDO = "trabajando"
EN_COLA = "en_cola"
ESTADOS_AGENTE = (SIN_SENAL, SIN_TAREA, DORMIR, ESPERANDO_APROBACION, TERMINADO, FALLIDO, EN_PAUSA,
                  EN_REVISION, EN_RONDA, TRABAJANDO, EN_COLA)
ETIQUETA = {SIN_SENAL: "sin señal", SIN_TAREA: "sin tarea", DORMIR: "durmiendo",
            ESPERANDO_APROBACION: "esperando tu aprobación", TERMINADO: "terminó", FALLIDO: "falló",
            EN_PAUSA: "en pausa", EN_REVISION: "en revisión", EN_RONDA: "corrigiendo",
            TRABAJANDO: "trabajando", EN_COLA: "en cola"}

# ---- estados de la TAREA (nivel 1), tal cual los escriben cola.db / cola-live.json
TAREA_ACTIVA = ("en_cola", "en_curso", "esperando_aprobacion", "esperando_leandro", "esperando_reintento")
TAREA_ESPERA_HUMANO = ("esperando_aprobacion", "esperando_leandro")
TAREA_FIN_OK = ("terminada",)
TAREA_FIN_MAL = ("fallida", "necesita_decision", "rechazada", "en_cuarentena")
TAREA_PAUSA = ("esperando_reintento", "pausada", "detenida")

# ---- umbrales (propuesta del spec, validados con el runner real: ver ESTADO-OFICINA-ESTADOS-050.md)
LIVE_FRESCO_S = 15        # runner-live.json se escribe cada ~5 s con tarea en curso: > 15 s = señal perdida
STATUS_MUERTO_S = 120     # runner-status.last_poll: el pulso lo reescribe cada 60 s. SOLO cuenta si no hay
#                           runner-live fresco (en el runner v1.0 el latido se congela mientras el motor trabaja)
COLA_VIEJA_S = 60         # cola-live.json: el runner la reescribe cada <= 10 s; > 60 s = vieja
FIN_VISIBLE_S = 60        # terminado / fallido se ven 60 s; luego el agente queda sin tarea
IDLE_SLEEP_MINUTES = 60   # sin tarea asignada mas de 60 min -> dormir (PALETA-Y-SKINS §14)

# ---- quien duerme y quien no
NUNCA_DUERMEN = ("leandro", "vigilante")


def edad_iso(iso, ahora):
    try:
        return ahora - datetime.fromisoformat(str(iso)).timestamp()
    except (TypeError, ValueError):
        return None


def ts_iso(iso):
    try:
        return datetime.fromisoformat(str(iso)).timestamp()
    except (TypeError, ValueError):
        return None


class EstadoTarea:
    """Nivel 1: el estado de UNA tarea, de sus archivos. No sabe nada de agentes ni de animaciones."""

    def __init__(self, fila, orq=None, live=None, ahora=None, revision_existe=False, aprobada_por=None):
        self.fila = fila or {}
        self.id = self.fila.get("id")
        self.estado = self.fila.get("estado")
        self.orq = orq or {}
        self.live = live if isinstance(live, dict) and live.get("task_id") == self.id else None
        self.ahora = time.time() if ahora is None else ahora
        self.revision_existe = revision_existe
        self.aprobada_por = aprobada_por  # canal de la ultima aprobacion registrada (app | whatsapp | None)

    @property
    def ronda(self):
        try:
            return int(self.fila.get("ronda") or self.orq.get("ronda") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def fin_ts(self):
        return ts_iso(self.fila.get("actualizado_en"))

    def proximo_intento_futuro(self):
        t = ts_iso(self.fila.get("proximo_intento"))
        return t is not None and t > self.ahora

    def revisando(self):
        """Duda 13/14, medido en el PC (captura-revisando.json): durante la revision
        .orquestacion.json dice estado «revisando» y runner-live.json tambien (unos 2 s despues);
        cola.db y cola-live.json siguen en «en_curso» (no tienen estado de revision)."""
        if self.orq.get("estado") == "revisando":
            return True
        return bool(self.live and self.live.get("estado") == "revisando")


def derivar_estado(agente, tarea, fuentes, ahora=None, sin_tarea_desde=None, dormido=False):
    """Estado visible de UN agente. Funcion pura: la primera regla que casa, gana (§3.3).

    agente: {"id", "rol"}; tarea: EstadoTarea o None (la que tiene entre manos, ya asignada);
    fuentes: {"status", "status_edad", "live", "live_edad", "cola", "cola_edad", "latido_ok"}
    (dicts ya parseados o None; edades en s o None); sin_tarea_desde: ts desde que esta libre;
    dormido: si la oficina ya lo tiene dormido (para no despertarlo mientras su tarea espera).
    -> (estado, motivo)"""
    ahora = time.time() if ahora is None else ahora
    st, live, cola = fuentes.get("status"), fuentes.get("live"), fuentes.get("cola")
    e_live, e_st, e_cola = fuentes.get("live_edad"), fuentes.get("status_edad"), fuentes.get("cola_edad")
    live_fresco = live is not None and e_live is not None and e_live < LIVE_FRESCO_S
    # 1. sin señal: faltan status / live / cola, o el latido esta muerto
    if not fuentes.get("latido_ok", True):
        return SIN_SENAL, "el Bridge no da latido"
    if st is None:
        return SIN_SENAL, "runner-status.json ausente o roto"
    if live is None:
        return SIN_SENAL, "runner-live.json ausente o roto"
    if cola is None:
        return SIN_SENAL, "cola-live.json ausente o roto"
    if e_cola is None or e_cola > COLA_VIEJA_S:
        return SIN_SENAL, f"cola-live.json vieja ({'—' if e_cola is None else f'{e_cola:.0f} s'})"
    if not live_fresco and (e_st is None or e_st > STATUS_MUERTO_S):
        return SIN_SENAL, f"latido del runner muerto (runner-status de hace {'—' if e_st is None else f'{e_st:.0f} s'})"
    # 2. sin tarea (y su subestado dormir)
    fin_viejo = (tarea is not None and tarea.estado in TAREA_FIN_OK + TAREA_FIN_MAL
                 and (tarea.fin_ts is None or ahora - tarea.fin_ts > FIN_VISIBLE_S))
    if tarea is None or fin_viejo or tarea.estado == "archivada":
        if agente.get("id") not in NUNCA_DUERMEN and sin_tarea_desde is not None \
                and ahora - sin_tarea_desde > IDLE_SLEEP_MINUTES * 60:
            return DORMIR, f"sin tarea desde hace {(ahora - sin_tarea_desde) / 60:.0f} min"
        return SIN_TAREA, "no tiene ninguna tarea entre manos"
    # dormido con tarea que aun no corre: sigue dormido (no toma tareas); la toma del runner lo despierta (T23)
    if dormido and not (live_fresco and live.get("task_id") == tarea.id and live.get("estado") != "terminado"):
        return DORMIR, f"dormido; su tarea {tarea.id} está {tarea.estado}: lo despierta el runner al tomarla"
    # 3. esperando aprobacion
    if tarea.estado in TAREA_ESPERA_HUMANO:
        return ESPERANDO_APROBACION, f"{tarea.id} retenida ({tarea.estado})"
    # 4. terminado / fallido, 60 s tras el fin
    if tarea.estado in TAREA_FIN_OK:
        return TERMINADO, f"{tarea.id} terminó"
    if tarea.estado in TAREA_FIN_MAL:
        return FALLIDO, f"{tarea.id} {tarea.estado}"
    # 5. en pausa: reintento futuro o el usuario la paro
    if tarea.proximo_intento_futuro() or tarea.estado in TAREA_PAUSA:
        return EN_PAUSA, f"{tarea.id}: {tarea.fila.get('motivo') or 'reintento programado'}"
    # 6. en revision
    if tarea.revisando():
        return EN_REVISION, f"{tarea.id}: .orquestacion.json / runner-live dicen «revisando»"
    # 7. en ronda: ronda > 0 y la revision aun no la aprobo
    if tarea.ronda > 0 and tarea.orq.get("estado") != "aprobada" and not (
            live_fresco and live.get("task_id") == tarea.id and tarea.estado == "en_curso"):
        return EN_RONDA, f"{tarea.id}: ronda {tarea.ronda} de corrección"
    # 8. trabajando: runner-live con ESTE task_id y fresco
    if live_fresco and live.get("task_id") == tarea.id and live.get("estado") != "terminado":
        if tarea.ronda > 0:
            return EN_RONDA, f"{tarea.id}: corriendo la ronda {tarea.ronda}"
        return TRABAJANDO, f"runner-live de hace {e_live:.0f} s"
    # 9. en cola: espera turno (el runner es serie)
    if tarea.estado == "en_cola":
        otra = live.get("task_id") if live_fresco else (st.get("current") or {}).get("id") if isinstance(
            st.get("current"), dict) else None
        return EN_COLA, f"{tarea.id} espera turno" + (f" (el runner está con {otra})" if otra else "")
    return SIN_SENAL, f"{tarea.id} está {tarea.estado} pero runner-live no lo confirma (las fuentes no coinciden)"


# ---- tabla de transiciones (T1-T21 reconstruidas: §3.4 no esta en este PC; T22-T24 del spec)
_ACTIVOS = (EN_COLA, TRABAJANDO, ESPERANDO_APROBACION, EN_REVISION, EN_RONDA, EN_PAUSA, TERMINADO, FALLIDO)
TRANSICIONES = [
    ("T1", SIN_TAREA, (EN_COLA,), "se le asigna una tarea que espera turno"),
    ("T2", SIN_TAREA, (TRABAJANDO,), "se le asigna una tarea y el runner la toma ya (la tarea está en la cola)"),
    ("T3", SIN_TAREA, (ESPERANDO_APROBACION,), "se le asigna una tarea y el guardrail la retiene"),
    ("T4", EN_COLA, (TRABAJANDO,), "el runner toma la tarea"),
    ("T5", EN_COLA, (ESPERANDO_APROBACION,), "el guardrail la retiene al recogerla"),
    ("T6", TRABAJANDO, (EN_REVISION,), "el motor termina y empieza la revisión"),
    ("T7", TRABAJANDO, (TERMINADO,), "termina sin revisión (o sin nada que revisar)"),
    ("T8", TRABAJANDO, (FALLIDO,), "el motor falla de forma definitiva"),
    ("T9", TRABAJANDO, (EN_PAUSA,), "fallo transitorio con reintento programado, o el usuario la para"),
    ("T10", EN_REVISION, (TERMINADO,), "la revisión la aprueba"),
    ("T11", EN_REVISION, (EN_RONDA,), "la revisión pide corrección: ronda nueva"),
    ("T12", EN_REVISION, (FALLIDO,), "necesita decisión o rechazada tras la última ronda"),
    ("T13", EN_RONDA, (TRABAJANDO, EN_REVISION), "corre la ronda / la ronda termina y se revisa otra vez"),
    ("T14", EN_PAUSA, (TRABAJANDO, EN_COLA), "llega la hora del reintento"),
    ("T15", EN_PAUSA, (FALLIDO,), "se agotan los reintentos"),
    ("T16", ESPERANDO_APROBACION, (TRABAJANDO, EN_COLA), "aprobada EN LA APP (Tareas) o por WhatsApp con approval_id"),
    ("T17", ESPERANDO_APROBACION, (FALLIDO,), "rechazada o vencida"),
    ("T18", FALLIDO, (EN_COLA,), "re-encolada"),
    ("T19", TERMINADO, (SIN_TAREA,), "pasan 60 s desde el fin: el agente queda libre"),
    ("T20", FALLIDO, (SIN_TAREA,), "pasan 60 s desde el fallo: la tarea falló, el empleado queda libre"),
    ("T21", "*", (SIN_SENAL,), "se pierde la señal (archivo ausente, viejo o roto, latido muerto)"),
    ("T22", SIN_TAREA, (DORMIR,), f"más de {IDLE_SLEEP_MINUTES} min sin tarea asignada"),
    ("T23", DORMIR, (TRABAJANDO,), "el runner toma su tarea: la asignación lo despierta (sobresalto + estiramiento)"),
    ("T24", DORMIR, (SIN_TAREA,), "el jugador hace clic en él, o el vigilante lo despierta de noche sin tarea"),
]
# Volver de «sin señal» no es una transición de agente: es re-derivar desde cero (la oficina no sabe
# qué pasó mientras no veía). Se registra como «resincronizado», sin pasar por la tabla.
PROHIBIDAS = [
    (ESPERANDO_APROBACION, TRABAJANDO, "hablar con el agente", "solo T16 (aprobar en la app) la suelta"),
    (ESPERANDO_APROBACION, TRABAJANDO, "cambiar el guardrail", "cambiarlo no suelta lo ya retenido (lección del 25 oct)"),
    (ESPERANDO_APROBACION, TRABAJANDO, "aprobar en el chat", "el chat no aprueba: approval_id + hash + vencimiento en la app"),
    (SIN_TAREA, TRABAJANDO, "sin tarea en cola", "no hay trabajo sin tarea"),
    (FALLIDO, TRABAJANDO, "sin re-encolar", "la tarea fallida no vuelve sola: T18 primero"),
    (TRABAJANDO, TRABAJANDO, "dos agentes a la vez", "el runner es serie"),
]
CAUSAS_VALIDAS_T16 = ("app", "whatsapp")


def transicion(desde, hacia):
    """-> id de la transicion de la tabla, «=» si no cambia, None si no esta en la tabla."""
    if desde == hacia:
        return "="
    if hacia == SIN_SENAL:
        return "T21"
    if desde == SIN_SENAL:
        return "resync"
    for tid, d, hs, _c in TRANSICIONES:
        if d == desde and hacia in hs:
            return tid
    return None


class Memoria:
    """Lo que la oficina recuerda entre fotogramas (NO es estado del Bridge): desde cuando esta libre
    cada agente, si duerme, el ultimo estado mostrado y las transiciones fuera de tabla."""

    def __init__(self, ahora=None, registro=None):
        self.arranque = time.time() if ahora is None else ahora
        self.libre_desde = {}
        self.dormidos = set()
        self.previo = {}
        self.tarea_previa = {}
        self.registro = registro or (lambda d: None)
        self.fuera_de_tabla = []

    def despertar(self, agente_id, por, ahora=None):
        """T24 (clic del jugador / vigilante sin tarea): vuelve a sin_tarea y el reloj de sueño empieza de nuevo."""
        ahora = time.time() if ahora is None else ahora
        if agente_id in self.dormidos:
            self.dormidos.discard(agente_id)
            self.libre_desde[agente_id] = ahora
            self.registro({"evento": "despertar", "agente": agente_id, "por": por, "transicion": "T24"})
            return True
        return False

    def paso(self, agente, tarea, fuentes, ahora=None, aprobada_por=None):
        """Deriva, comprueba la transicion contra la tabla y actualiza la memoria. -> (estado, motivo, T)."""
        ahora = time.time() if ahora is None else ahora
        aid = agente["id"]
        prev = self.previo.get(aid)
        tid_prev = self.tarea_previa.get(aid)
        tid = tarea.id if tarea is not None else None
        desde = self.libre_desde.setdefault(aid, self.arranque)
        est, mot = derivar_estado(agente, tarea, fuentes, ahora, desde, aid in self.dormidos)
        t = transicion(prev, est) if prev is not None else "inicio"
        # una tarea NUEVA reinicia al agente: lo anterior termina y la comprobacion es sin_tarea -> nuevo
        if t is None and tid is not None and tid != tid_prev and prev in (TERMINADO, FALLIDO, SIN_TAREA, EN_COLA):
            t = transicion(SIN_TAREA, est)
        if prev == ESPERANDO_APROBACION and est in (TRABAJANDO, EN_COLA):
            # T16 exige una aprobacion registrada en la app o por WhatsApp (approval_id + hash +
            # vencimiento); hablar con el agente, cambiar el guardrail o «aprobar» en el chat no sueltan nada
            t = "T16" if aprobada_por in CAUSAS_VALIDAS_T16 else None
        if t is None:
            motivo = f"transición fuera de tabla: {prev} → {est} ({mot})"
            self.fuera_de_tabla.append({"agente": aid, "desde": prev, "hacia": est, "motivo": mot, "t": ahora})
            self.registro({"evento": "fuera_de_tabla", "agente": aid, "desde": prev, "hacia": est, "motivo": mot})
            est, mot, t = SIN_SENAL, motivo, "T21"
        if est == DORMIR:
            self.dormidos.add(aid)
        elif aid in self.dormidos and est not in (SIN_SENAL,):
            self.dormidos.discard(aid)
        if est in (SIN_TAREA, DORMIR) and prev not in (SIN_TAREA, DORMIR, None, SIN_SENAL):
            self.libre_desde[aid] = (tarea.fin_ts if tarea is not None and tarea.fin_ts else ahora)
        if est not in (SIN_TAREA, DORMIR, SIN_SENAL):
            self.libre_desde[aid] = ahora
        if t not in ("=", "inicio"):
            self.registro({"evento": "transicion", "agente": aid, "desde": prev, "hacia": est, "T": t, "motivo": mot})
        self.previo[aid] = est
        self.tarea_previa[aid] = tid
        return est, mot, t


def comprobar_serie(estados, max_trabajando=1):
    """Prohibida «trabajando → trabajando de otro agente a la vez»: -> lista de agentes que sobran."""
    trab = [a for a, e in estados.items() if e == TRABAJANDO]
    return trab[max_trabajando:]


# ---- asignacion de tareas a agentes (nivel 1 -> nivel 2), sin inventar
def personaje_de(motor, modelo):
    motor = (motor or "").lower()
    modelo = (modelo or "").lower()
    if motor == "claude":
        for m in ("opus", "haiku", "sonnet"):
            if m in modelo:
                return m if m != "sonnet" else "sonny"
        return "sonny"
    return {"codex": "dex", "llama": "hermes_directo", "ollama": "hermes_ollama", "meshy": "mensajero",
            "gemini": "gemi", "agy": "gemi"}.get(motor)


_PRIORIDAD = {"en_curso": 0, "esperando_aprobacion": 1, "esperando_leandro": 1, "esperando_reintento": 2,
              "en_cola": 3, "terminada": 4, "fallida": 4, "necesita_decision": 4}


def asignar(cola, ahora=None):
    """{agente_id: fila de la tarea que tiene entre manos}. Por agente gana la mas viva (en curso >
    retenida > reintento > en cola > recien terminada); a igualdad, la mas antigua en cola o la mas
    reciente terminada. Las terminadas de hace mas de FIN_VISIBLE_S no cuentan."""
    ahora = time.time() if ahora is None else ahora
    por = {}
    for f in (cola or {}).get("tareas") or []:
        if not isinstance(f, dict) or f.get("estado") not in _PRIORIDAD:
            continue
        if f["estado"] in TAREA_FIN_OK + TAREA_FIN_MAL:
            t = ts_iso(f.get("actualizado_en"))
            if t is None or ahora - t > FIN_VISIBLE_S:
                continue
        a = personaje_de(f.get("motor"), f.get("modelo"))
        if a is None:
            continue
        k = (_PRIORIDAD[f["estado"]], f.get("creado_en") or "")
        if a not in por or k < por[a][0]:
            por[a] = (k, f)
    return {a: f for a, (_k, f) in por.items()}


# ---- comportamiento sin tarea (§3.5) y del gerente sin nada que orquestar (§3.6)
ACTIVIDADES_SIN_TAREA = ("respirar", "parpadear", "mirar_tablon", "estirarse")  # nunca «teclear»


def actividad_sin_tarea(agente_id, t, semilla=0):
    """Actividad decorativa de un agente libre: respiro y parpadeo siempre; cada ~20 s mira el tablón
    o se estira unos segundos. Determinista por (agente, t, semilla). Nunca teclea «sin papeles»."""
    h = (sum(map(ord, agente_id)) * 7919 + semilla * 104729) % 997
    ciclo = (t + h) % 24.0
    if ciclo < 3.0:
        return "mirar_tablon"
    if 12.0 <= ciclo < 14.0:
        return "estirarse"
    return "parpadear" if (int(t * 10) + h) % 40 == 0 else "respirar"


def gerente_rutina(t, hay_aprobacion_pendiente, bridge_caido, mesas, semilla=0):
    """Rutina del gerente sin nada que orquestar. -> (actividad, objetivo). Ciclo de ~40 s:
    mira el tablón 4 s (si algo espera aprobación, se queda junto al tablón), revisa la oficina
    (2,5 s por mesa), vuelve a su mesa y espera mirando el teléfono. Si el Bridge cae: junto al
    teléfono, en gris parcial. No teclea, no escribe informes, no inventa tareas."""
    if bridge_caido:
        return "junto_al_telefono_gris", "telefono"
    if hay_aprobacion_pendiente:
        return "junto_al_tablon", "tablon"
    mesas = list(mesas or [])
    ronda = 4.0 + 2.5 * len(mesas)
    c = (t + semilla * 3.1) % (ronda + 20.0)
    if c < 4.0:
        return "mirar_tablon", "tablon"
    if c < ronda:
        return "revisar_oficina", mesas[int((c - 4.0) // 2.5)] if mesas else "pasillo"
    return "esperar_mirando_telefono", "silla_growi"

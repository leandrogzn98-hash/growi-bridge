# -*- coding: utf-8 -*-
"""Supervisión (Fase 4 del plan multi-Muse): el barrido que vigila.

Un barrido periódico (en el latido del tablero, tras el de la Fase 3) que
cruza las fuentes que ya existen — latidos del tablero, runner-status de
cada carril, estados del harness, filas de la cola — y actúa con reglas
estrechas:

- **Fail-open por fuente**: una fuente que falta o no se puede leer nunca
  autoriza un kill ni un cierre. Lo que no se sabe, no se toca.
- **Cuenta caída**: latido del carril viejo (>180 s) y su pid muerto →
  aviso ``cuenta_sin_latido`` (una vez por episodio; la deduplicación de
  avisos hace el resto). Si tenía trabajo en curso, el aviso lo dice.
- **Duración máxima**: una fila ``en_curso`` que supera
  ``DURACION_MAX_MIN`` (120, alineado con el timeout máximo de tarea)
  desde su ``inicio_ts`` real se detiene. El tope de duración ES el tope
  de tenencia de los alquileres de la Fase 3: al morir la ejecución, sus
  alquileres dejan de renovarse y caducan solos.
- **Cuelgue del harness**: estado que no avanza en 600 s con el proceso
  vivo → la misma política de parada.
- **Kill solo en casa y con identidad verificada**: solo se matan árboles
  del carril propio, y solo si el pid del historial sigue siendo el mismo
  proceso (pid + create_time). Si el pid se recicló, se anota y no se
  mata. Las filas del otro carril solo se anotan y se avisa: su duración
  la aplica su propio carril.
- **Encargos**: reconcilia entregas perdidas, recoge los resultados del
  buzón compartido, cierra subtareas cuya dependencia falló, entrega lo
  que ya puede salir, reasigna lo asignado a cuentas caídas y cierra el
  encargo (atómico: solo quien gana el cierre escribe el resumen en el
  carril de origen y emite el aviso).
- **Dual**: con el vigía en servidor confirma lo que ya tiene resultado;
  reconciliando, aplica la gracia de reconciliación y la regla del
  indeterminado (×3 o 30 min → lo decide el dueño, nunca se ejecuta con
  duda).

Todo lo que toca el mundo (leer estados, matar, anotar filas, entregar)
llega inyectado en el contexto: el módulo es testeable sin procesos.
"""

import time
from pathlib import Path

import avisos as _av
import presencia as _pr
import relevo as _rl

DURACION_MAX_MIN = 120
LATIDO_MUERTO_S = 180
CUELGUE_HARNESS_S = 600
GRACIA_RECONCILIACION_S = 120
DUAL_INDETERMINADO_MAX = 3
DUAL_INDETERMINADO_S = 1800
PASADAS_ENTREGA_PERDIDA = 3


def _inicio_de(fila):
    """El inicio real de la ejecución: el ``inicio_ts`` que el runner
    anota en el historial al recoger la tarea (no ``actualizado_ts``,
    que el latido refresca)."""
    inicio = None
    for entrada in fila.get("historial") or []:
        if isinstance(entrada, dict) and isinstance(
                entrada.get("inicio_ts"), (int, float)):
            inicio = entrada["inicio_ts"]
    return inicio


def _pid_de(fila):
    pid = None
    creado = None
    for entrada in fila.get("historial") or []:
        if isinstance(entrada, dict) and entrada.get("pid"):
            pid = entrada["pid"]
            creado = entrada.get("create_time")
    return pid, creado


def _ya_anotado(fila, clave):
    return any(isinstance(e, dict) and e.get("tipo") == clave
               for e in fila.get("historial") or [])


def _resultado_ok(res):
    if not isinstance(res, dict):
        return False
    if res.get("motivo_cierre"):
        return False
    if res.get("estado") in ("fallida", "necesita_decision", "rechazada"):
        return False
    return res.get("status") == "ok"


def _resumen_resultado(res):
    texto = res.get("output") or res.get("result") or res.get("error") or ""
    return str(texto)[:200] or None


# ---------------------------------------------------------------------------
# El barrido
# ---------------------------------------------------------------------------

def barrer(ctx):
    """Ejecuta una pasada de supervisión. ``ctx`` trae las lecturas y los
    efectores inyectados por el monolito. Devuelve un resumen de lo hecho.
    Nunca lanza por una fuente concreta: cada apartado va protegido."""
    base = Path(ctx["base_dir"])
    ahora = ctx.get("ahora") or time.time()
    log = ctx.get("log")
    resumen = {"avisos": [], "paradas": [], "encargos_cerrados": [],
               "entregas": [], "dual": []}

    def _aviso(tipo, texto, **kw):
        av = _av.emitir(base, tipo, texto, log=log, **kw)
        if av:
            resumen["avisos"].append(av["id"])
        return av

    # --- 1. Cuentas sin latido -------------------------------------------
    leer_status = ctx.get("leer_status")
    pid_vivo = ctx.get("pid_vivo")
    filas_de = ctx.get("filas")
    if leer_status and pid_vivo:
        for cuenta in ctx.get("cuentas") or []:
            try:
                if not cuenta.get("habilitada", True):
                    continue
                status = leer_status(cuenta.get("carril"))
                if not status:
                    continue
                ultimo = status.get("last_poll_ts")
                if ultimo is None or ahora - ultimo <= LATIDO_MUERTO_S:
                    continue
                pid = status.get("pid")
                if pid and pid_vivo(pid):
                    continue
                en_curso = [f for f in (filas_de(cuenta.get("carril"))
                                        or [])
                            if f.get("estado") == "en_curso"
                            and f.get("cuenta") == cuenta["id"]]
                if status.get("current"):
                    en_curso = en_curso or [{"id": status["current"]}]
                if en_curso:
                    _aviso("cuenta_sin_latido",
                           f"La cuenta {cuenta['id']} no da señales y "
                           f"tenía trabajo en curso "
                           f"({en_curso[0].get('id')}); su carril "
                           "necesita atención",
                           cuenta=cuenta["id"], nivel="accion")
                else:
                    _aviso("cuenta_sin_latido",
                           f"La cuenta {cuenta['id']} no da señales "
                           "(latido viejo y proceso muerto)",
                           cuenta=cuenta["id"])
            except Exception as e:
                if log:
                    log(f"supervisión: cuenta sin latido: {e}")

    # --- 2. Duración máxima y cuelgues ------------------------------------
    matar = ctx.get("matar")
    anotar = ctx.get("anotar")
    if filas_de:
        for carril in ctx.get("carriles") or []:
            try:
                for fila in filas_de(carril) or []:
                    if fila.get("estado") != "en_curso":
                        continue
                    inicio = _inicio_de(fila)
                    if inicio is None:
                        continue
                    excedida = (ahora - inicio
                                > DURACION_MAX_MIN * 60)
                    cuelgue = False
                    if not excedida and ctx.get("estado_harness"):
                        try:
                            est = ctx["estado_harness"](fila)
                        except Exception:
                            est = None
                        if est and est.get("status") == "working":
                            pasos = est.get("pasos") or []
                            ultimo = (pasos[-1].get("ts")
                                      if pasos and isinstance(
                                          pasos[-1], dict) else None) \
                                or est.get("_mtime_ts")
                            if ultimo and ahora - ultimo > CUELGUE_HARNESS_S:
                                cuelgue = True
                    if not excedida and not cuelgue:
                        continue
                    motivo = ("duración máxima superada "
                              f"({DURACION_MAX_MIN} min)"
                              if excedida else
                              f"harness sin avanzar en "
                              f"{CUELGUE_HARNESS_S} s")
                    pid, creado = _pid_de(fila)
                    if carril != ctx.get("carril_propio"):
                        if anotar and not _ya_anotado(
                                fila, "supervision_ajena"):
                            anotar(fila, {"tipo": "supervision_ajena",
                                          "ts": ahora, "motivo": motivo})
                        continue
                    if pid is None or matar is None:
                        if anotar and not _ya_anotado(
                                fila, "supervision_sin_pid"):
                            anotar(fila, {"tipo": "supervision_sin_pid",
                                          "ts": ahora, "motivo": motivo})
                        continue
                    if pid_vivo and not pid_vivo(pid):
                        continue  # el proceso ya no está; no hay nada que
                        # parar (su process_one ya lo habrá notado)
                    ok, detalle = matar(pid, creado)
                    if anotar:
                        anotar(fila, {"tipo": "supervision_parada",
                                      "ts": ahora, "motivo": motivo,
                                      "pid": pid, "detalle": detalle})
                    resumen["paradas"].append(
                        {"tarea": fila.get("id"), "motivo": motivo,
                         "ok": ok, "detalle": detalle})
            except Exception as e:
                if log:
                    log(f"supervisión: duración/cuelgues carril "
                        f"{carril}: {e}")

    # --- 3. Encargos -------------------------------------------------------
    if ctx.get("encargos", True):
        try:
            _barrer_encargos(ctx, resumen, _aviso)
        except Exception as e:
            if log:
                log(f"supervisión: encargos: {e}")

    # --- 4. Dual ------------------------------------------------------------
    dual = ctx.get("dual")
    if dual:
        try:
            _barrer_dual(ctx, dual, resumen, _aviso)
        except Exception as e:
            if log:
                log(f"supervisión: dual: {e}")

    # --- 5. Marca del barrido ----------------------------------------------
    try:
        _pr.marcar_supervision_ts(base, ahora)
    except Exception:
        pass
    return resumen


# ---------------------------------------------------------------------------
# Encargos
# ---------------------------------------------------------------------------

def _barrer_encargos(ctx, resumen, _aviso):
    base = Path(ctx["base_dir"])
    ahora = ctx.get("ahora") or time.time()
    encargos = _rl.listar(base)
    if _rl.problema(base) and encargos:
        pass  # corrupto ya devolvió vacío en _cargar; nada que reconciliar
    filas_cache = {}

    def _filas(carril):
        if carril not in filas_cache:
            filas_cache[carril] = (ctx["filas"](carril) or []) \
                if ctx.get("filas") else []
        return filas_cache[carril]

    for raiz, ent in encargos.items():
        if ent.get("estado") in _rl.TERMINALES:
            continue
        subs = ent.get("subtareas") or {}

        # Plazo global vencido: se cierra con fallos sin tocar lo que
        # siga en curso (sus resultados tardíos ya no reabren nada).
        if ahora > (ent.get("plazo_ts") or 0) and subs:
            if _rl.cerrar(base, raiz, "terminado_con_fallos"):
                _cerrar_encargo(ctx, raiz, resumen, _aviso)
            continue

        # Reasignación de lo asignado a cuentas caídas y de lo pendiente.
        if ctx.get("vista") is not None and ctx.get("registro") is not None:
            try:
                _rl.reasignar(base, raiz, ctx["vista"], ctx["registro"],
                              ctx.get("activas") or {})
                ent = _rl.obtener(base, raiz) or ent
                subs = ent.get("subtareas") or {}
            except Exception:
                pass

        # Resultados del buzón y entregas perdidas.
        recien_reseteadas = set()
        for sid, sub in list(subs.items()):
            if sub.get("estado") != "entregada":
                continue
            res = _rl.leer_de_buzon(base, raiz, sid)
            if res is not None:
                ok = _resultado_ok(res)
                _rl.marcar_subtarea(
                    base, raiz, sid,
                    estado="terminada" if ok else "fallida",
                    terminada_ts=ahora,
                    resultado={"estado": "terminada" if ok else "fallida",
                               "resumen": _resumen_resultado(res),
                               "motivo_cierre": res.get("motivo_cierre")})
                sub["estado"] = "terminada" if ok else "fallida"
                if not ok:
                    _aviso("subtarea_fallida",
                           f"La subtarea {sid} del encargo {raiz} falló: "
                           f"{_resumen_resultado(res) or 'sin detalle'}",
                           cuenta=sub.get("cuenta"), raiz=raiz, tarea=sid)
                continue
            carril_d = sub.get("carril")
            localizada = any(f.get("id") == sid for f in _filas(carril_d))
            if not localizada and ctx.get("archivo_en_tareas"):
                localizada = bool(ctx["archivo_en_tareas"](carril_d, sid))
            if localizada:
                if sub.get("pasadas_sin_archivo"):
                    _rl.marcar_subtarea(base, raiz, sid,
                                        pasadas_sin_archivo=0)
                    sub["pasadas_sin_archivo"] = 0
            else:
                pasadas = int(sub.get("pasadas_sin_archivo") or 0) + 1
                if pasadas >= PASADAS_ENTREGA_PERDIDA:
                    _rl.marcar_subtarea(
                        base, raiz, sid, estado="pendiente_entrega",
                        entregada_ts=None, pasadas_sin_archivo=0,
                        motivo="entrega perdida: ni archivo ni resultado "
                               "tras 3 pasadas del barrido")
                    sub["estado"] = "pendiente_entrega"
                    sub["entregada_ts"] = None
                    # No se re-entrega en esta misma pasada: queda
                    # pendiente y el siguiente barrido la repone (y la
                    # reasignación puede actuar antes si la cuenta cayó).
                    recien_reseteadas.add(sid)
                else:
                    _rl.marcar_subtarea(base, raiz, sid,
                                        pasadas_sin_archivo=pasadas)
                    sub["pasadas_sin_archivo"] = pasadas

        # Cierre por dependencia fallida (hasta punto fijo: las cadenas
        # se propagan en la misma pasada).
        cambio = True
        vueltas = 0
        while cambio and vueltas <= len(subs):
            cambio = False
            vueltas += 1
            estados = {sid: s.get("estado") for sid, s in subs.items()}
            for sid, sub in subs.items():
                if sub.get("estado") in ("terminada", "fallida"):
                    continue
                deps = (sub.get("spec") or {}).get("depende_de") or []
                fallida = next((d for d in deps
                                if estados.get(d) == "fallida"), None)
                if fallida:
                    _rl.marcar_subtarea(
                        base, raiz, sid, estado="fallida",
                        terminada_ts=ahora,
                        resultado={"estado": "fallida",
                                   "resumen": f"su dependencia {fallida} "
                                              "falló; no se ejecutó"})
                    sub["estado"] = "fallida"
                    cambio = True

        # Entregas: lo asignado (o pendiente con cuenta) cuyas
        # dependencias terminaron bien.
        estados = {sid: s.get("estado") for sid, s in subs.items()}
        for sid, sub in subs.items():
            entregable = sub.get("estado") == "asignada" or (
                sub.get("estado") == "pendiente_entrega"
                and sub.get("cuenta"))
            if not entregable or sid in recien_reseteadas:
                continue
            deps = (sub.get("spec") or {}).get("depende_de") or []
            if any(estados.get(d) != "terminada" for d in deps):
                continue
            if not ctx.get("dir_tareas"):
                continue
            res = _rl.entregar(base, raiz, sid,
                               ctx["dir_tareas"](sub.get("carril")),
                               ctx["base_carril"](sub.get("carril"))
                               if ctx.get("base_carril") else None)
            if res.get("ok"):
                resumen["entregas"].append(sid)
                sub["estado"] = "entregada"
                estados[sid] = "entregada"

        # Cierre del encargo.
        if subs and all(s.get("estado") in ("terminada", "fallida")
                        for s in subs.values()):
            final = "terminado" if all(
                s.get("estado") == "terminada" for s in subs.values()) \
                else "terminado_con_fallos"
            if _rl.cerrar(base, raiz, final):
                _cerrar_encargo(ctx, raiz, resumen, _aviso)


def _cerrar_encargo(ctx, raiz, resumen, _aviso):
    base = Path(ctx["base_dir"])
    resumen["encargos_cerrados"].append(raiz)
    datos = _rl.resumen(base, raiz)
    if datos is None:
        return
    resultado = {
        "id": raiz,
        "raiz": raiz,
        "status": "ok" if datos["estado"] == "terminado" else "error",
        "output": datos["texto"],
        "error": None if datos["estado"] == "terminado" else datos["texto"],
        "encargo": datos,
    }
    if ctx.get("escribir_resumen"):
        try:
            ctx["escribir_resumen"](raiz, resultado)
        except Exception:
            pass
    ent = _rl.obtener(base, raiz) or {}
    _aviso("encargo_terminado", datos["texto"],
           cuenta=ent.get("receptora"), raiz=raiz,
           nivel="info" if datos["estado"] == "terminado" else "accion")


# ---------------------------------------------------------------------------
# Dual
# ---------------------------------------------------------------------------

def _barrer_dual(ctx, dual, resumen, _aviso):
    ahora = ctx.get("ahora") or time.time()
    estado = dual.get("estado")
    for fila in dual.get("filas") or []:
        tarea = fila.get("tarea")
        if not tarea:
            continue
        res = dual["resolver"](tarea)
        if res is True:
            dual["hecha"](tarea)
            resumen["dual"].append({"tarea": tarea, "accion": "hecha"})
            continue
        if estado != "reconciliando":
            continue
        enviada = fila.get("enviada_ts") or ahora
        if res is False:
            if ahora - enviada >= GRACIA_RECONCILIACION_S:
                dual["ejecutar"](tarea)
                resumen["dual"].append({"tarea": tarea,
                                        "accion": "ejecutar_local"})
        elif res is None:
            intentos = dual["indeterminado"](tarea)
            if intentos >= DUAL_INDETERMINADO_MAX or \
                    ahora - enviada > DUAL_INDETERMINADO_S:
                dual["resuelta_dueno"](tarea)
                resumen["dual"].append({"tarea": tarea,
                                        "accion": "resuelta_dueno"})
                _aviso("dual_sin_resolver",
                       f"La tarea {tarea} quedó sin resolver en el modo "
                       "dual: no se sabe si se hizo en el servidor y NO "
                       "se ejecutará aquí sin tu decisión",
                       tarea=tarea, nivel="accion")

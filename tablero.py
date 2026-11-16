# -*- coding: utf-8 -*-
"""Tablero compartido entre cuentas Muse (Growi Bridge, Fase 2).

Un archivo `tablero.json` en la carpeta compartida por usuario del programa (la misma que guarda el token del plano de control: así los dos carriles, que son dos copias del programa, comparten UN tablero) donde cada cuenta publica
su estado: tarea en curso, avance y % de tokens libres declarado. El % nunca
se inventa: lleva su fuente (`declarado`, `estimado`, `declarado_caducado` o
`sin_dato`) y el efectivo se calcula al leer.

Escrituras con el patrón de `cuentas.py` (lock de archivo entre procesos,
read-modify-write bajo el lock, tmp + os.replace) MÁS un mutex en proceso
(revisión Fase 2, I1: la UI y el latido son hilos del mismo proceso y el
lock de archivo no los excluye entre sí). Orden de locks: primero el mutex
en proceso, después el de archivo; NUNCA se llama a la cuota con el lock
del tablero tomado (el estimador se invoca fuera y su resultado entra como
argumento de `recalcular`).

El `estado` de cuarentena lo cambia UNA sola vía (B1): `recalcular()`, bajo
el lock e idempotente, y el recálculo local de `publicar()` cuando entra un
% declarado nuevo. `vista()` no transiciona: muestra lo guardado. La
máquina es `transicion()` (pura): activa -> restringida al bajar del
umbral, salida solo al superar umbral + margen (sin parpadeo), cualquiera
-> cuarentena con el % agotado, y sin dato conserva el estado (sin dato no
se castiga ni se libera a nadie). Para la puerta manda `pct_puerta`: el
mínimo entre el declarado fresco y el estimado cuando hay ambos (I3).
"""
import contextlib
import json
import math
import os
import re
import threading
import time
from pathlib import Path

ARCHIVO = "tablero.json"
VERSION = 1

# Mismo patrón de id que cuentas.py (Fase 1).
_ID_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?")

CONFIG_DEF = {
    "umbral_cuarentena": 10,      # % libre por debajo del cual no hay tareas nuevas
    "margen_salida": 5,           # puntos extra para salir de restringida/cuarentena
    "frescura_declarado_s": 1800,  # cuánto manda un % declarado antes de caducar
}

ESTADOS = ("activa", "restringida", "cuarentena")

SIN_CAMBIO = object()  # centinela: «no tocar este campo» en publicar()

_LOCK_PROCESO = threading.RLock()


class ErrorTablero(Exception):
    """Un dato del tablero es inválido o el archivo está bloqueado."""


def _config_valida(cfg):
    u, m = cfg.get("umbral_cuarentena"), cfg.get("margen_salida")
    return (isinstance(u, (int, float)) and isinstance(m, (int, float))
            and 0 < u and u + m <= 100)


def _config(d):
    cfg = dict(CONFIG_DEF)
    if isinstance(d, dict):
        for k in CONFIG_DEF:
            v = d.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
                cfg[k] = v
    if not _config_valida(cfg):
        # Config imposible (p. ej. umbral + margen > 100: la salida de
        # cuarentena sería inalcanzable). Se vuelve a los valores por
        # defecto y problema() lo reporta: nada de corregir en silencio
        # a otra cosa que el dueño no pidió.
        return dict(CONFIG_DEF)
    return cfg


def tablero_vacio():
    return {"version": VERSION, "revision": 0, "config": dict(CONFIG_DEF), "cuentas": {}}


def cargar(base_dir):
    """Lee tablero.json. Ausente o corrupto -> tablero vacío. Nunca lanza."""
    path = Path(base_dir) / ARCHIVO
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return tablero_vacio()
    if not isinstance(d, dict) or not isinstance(d.get("cuentas"), dict):
        return tablero_vacio()
    t = tablero_vacio()
    rev = d.get("revision", 0)
    t["revision"] = rev if isinstance(rev, int) and not isinstance(rev, bool) else 0
    t["config"] = _config(d.get("config"))
    t["cuentas"] = {k: v for k, v in d["cuentas"].items() if isinstance(v, dict)}
    return t


def problema(base_dir):
    """None si el archivo falta (normal) o es válido; el motivo si existe
    pero no se puede usar. Para que el monolito avise sin gritar en silencio."""
    path = Path(base_dir) / ARCHIVO
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f"tablero.json ilegible: {e}"
    if not isinstance(d, dict) or not isinstance(d.get("cuentas"), dict):
        return "tablero.json sin la estructura esperada"
    cruda = d.get("config")
    if isinstance(cruda, dict):
        cfg = dict(CONFIG_DEF)
        for k in CONFIG_DEF:
            v = cruda.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
                cfg[k] = v
        if not _config_valida(cfg):
            return "la config del tablero es imposible (umbral/margen) y se usan los valores por defecto"
    return None


@contextlib.contextmanager
def _bloqueo(base_dir):
    """Mutex en proceso + lock de archivo entre procesos (cuentas.py)."""
    with _LOCK_PROCESO:
        lock = Path(base_dir) / (ARCHIVO + ".lock")
        fd = None
        for _ in range(150):  # hasta ~3 s de espera
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime > 15:
                        lock.unlink()  # huérfano: se rompe y se reintenta
                        continue
                except OSError:
                    pass
                time.sleep(0.02)
        if fd is None:
            raise ErrorTablero("el tablero está bloqueado por otro proceso")
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


def _guardar(base_dir, t):
    """Escribe el tablero (se llama con el lock tomado)."""
    t["revision"] = int(t.get("revision", 0)) + 1
    path = Path(base_dir) / ARCHIVO
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def _pct_valido(v, nombre):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 <= v <= 100):
        raise ErrorTablero(f"{nombre} debe ser un número entre 0 y 100, no {v!r}")
    return v


def _entero_pct(v):
    """Normaliza un % a entero (I4: sin huecos entre 0 y 1)."""
    if v is None:
        return None
    return int(math.floor(float(v) + 0.5))


# ---------------------------------------------------------------- % y estados

def _pct_detalle(entrada, config, ahora, estimado):
    """Desglose del % de una entrada: declarado/estimado/efectivo/puerta.

    Frescura del declarado: por reloj (<= frescura_declarado_s) o por
    evento — sigue vigente mientras la cuenta tenga el latido fresco y una
    tarea en curso declarada después del % (está a mitad de su trabajo;
    un reloj fijo castigaría justo a la que trabaja)."""
    decl = entrada.get("pct_declarado")
    ts = entrada.get("pct_declarado_ts")
    decl_ok = (isinstance(decl, (int, float)) and not isinstance(decl, bool)
               and isinstance(ts, (int, float)))
    fresco = False
    if decl_ok:
        if 0 <= ahora - ts <= config["frescura_declarado_s"]:
            fresco = True
        else:
            lat = entrada.get("latido_ts")
            if (entrada.get("tarea") and isinstance(lat, (int, float))
                    and 0 <= ahora - lat <= config["frescura_declarado_s"]
                    and ts <= lat):
                fresco = True
    decl_n = _entero_pct(decl) if decl_ok else None
    est_n = _entero_pct(estimado)
    if fresco:
        efectivo, fuente = decl_n, "declarado"
    elif est_n is not None:
        efectivo, fuente = est_n, "estimado"
    elif decl_ok:
        efectivo, fuente = None, "declarado_caducado"
    else:
        efectivo, fuente = None, "sin_dato"
    candidatos = []
    if fresco:
        candidatos.append(decl_n)
    if est_n is not None:
        candidatos.append(est_n)
    puerta = min(candidatos) if candidatos else None
    return {"declarado": decl_n, "estimado": est_n, "efectivo": efectivo,
            "fuente": fuente, "puerta": puerta, "declarado_fresco": fresco}


def pct_efectivo(entrada, config, ahora, estimado):
    """(pct, fuente) de una entrada. Ver _pct_detalle para la precedencia."""
    d = _pct_detalle(entrada, config, ahora, estimado)
    return d["efectivo"], d["fuente"]


def transicion(estado_prev, pct, config):
    """Máquina de estados de cuarentena (pura). pct ya viene normalizada."""
    if estado_prev not in ESTADOS:
        estado_prev = "activa"
    if pct is None:
        return estado_prev
    umbral = config["umbral_cuarentena"]
    salida = umbral + config["margen_salida"]
    if pct <= 0:
        return "cuarentena"
    if estado_prev == "activa":
        return "restringida" if pct < umbral else "activa"
    if estado_prev == "restringida":
        return "activa" if pct >= salida else "restringida"
    # cuarentena
    if pct >= salida:
        return "activa"
    return "restringida" if pct < umbral else "cuarentena"


def _recalcular_entrada(e, cfg, ahora, estimado):
    """Aplica la máquina a una entrada (bajo lock). True si cambió."""
    d = _pct_detalle(e, cfg, ahora, estimado)
    nuevo = transicion(e.get("estado", "activa"), d["puerta"], cfg)
    if nuevo != e.get("estado", "activa") or "estado_ts" not in e:
        e["estado"] = nuevo
        e["estado_ts"] = ahora
        return True
    return False


def recalcular(base_dir, estimaciones=None, reloj=None):
    """La única vía que cambia estados con datos de cuota (B1).

    `estimaciones`: {cuenta: % libre estimado o None}, calculado FUERA del
    lock por el llamador. Idempotente: sin cambios no escribe. Devuelve el
    dict de estados resultante."""
    ahora = (reloj or time.time)()
    estimaciones = estimaciones or {}
    with _bloqueo(base_dir):
        t = cargar(base_dir)
        sucio = False
        for cid, e in t["cuentas"].items():
            if _recalcular_entrada(e, t["config"], ahora, estimaciones.get(cid)):
                sucio = True
        if sucio:
            _guardar(base_dir, t)
        return {cid: e.get("estado", "activa") for cid, e in t["cuentas"].items()}


def publicar(base_dir, cuenta, tarea=SIN_CAMBIO, avance=SIN_CAMBIO,
             pct_declarado=SIN_CAMBIO, motor_principal=SIN_CAMBIO, reloj=None):
    """Actualiza la entrada de una cuenta (solo los campos dados).

    tarea=None limpia la tarea; avance=None la deja sin avance. El latido se
    renueva en cada publicación. Si entra un % declarado nuevo, el estado de
    ESA cuenta se recalcula dentro del mismo lock (B1)."""
    if not _ID_RE.fullmatch(str(cuenta)):
        raise ErrorTablero(f"id de cuenta inválido: {cuenta!r}")
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        t = cargar(base_dir)
        e = dict(t["cuentas"].get(cuenta) or {})
        e.setdefault("estado", "activa")
        e.setdefault("motor_principal", "claude")
        if tarea is not SIN_CAMBIO:
            e["tarea"] = None if tarea is None else str(tarea)
        if avance is not SIN_CAMBIO:
            e["avance"] = None if avance is None else _pct_valido(avance, "avance")
        decl_nuevo = False
        if pct_declarado is not SIN_CAMBIO:
            if pct_declarado is None:
                e["pct_declarado"] = None
                e["pct_declarado_ts"] = None
            else:
                e["pct_declarado"] = _pct_valido(pct_declarado, "pct_declarado")
                e["pct_declarado_ts"] = ahora
                decl_nuevo = True
        if motor_principal is not SIN_CAMBIO:
            e["motor_principal"] = str(motor_principal)
        e["latido_ts"] = ahora
        e["actualizado_ts"] = ahora
        if decl_nuevo:
            _recalcular_entrada(e, t["config"], ahora, None)
        t["cuentas"][cuenta] = e
        _guardar(base_dir, t)
        return e


def declarar_pct(base_dir, cuenta, pct, reloj=None):
    """La cuenta (o el dueño desde la UI) declara su % de tokens libres."""
    return publicar(base_dir, cuenta, pct_declarado=pct, reloj=reloj)


def liberar(base_dir, cuenta, reloj=None):
    """Fuerza el estado a `activa` (botón de la UI; el llamador lo registra).

    Para cuentas atrapadas sin dato (declarado caducado y motor sin límite
    estimado): sin esta salida manual quedarían frenadas para siempre."""
    if cuenta not in cargar(base_dir)["cuentas"]:
        raise ErrorTablero(f"la cuenta «{cuenta}» no está en el tablero")
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        t = cargar(base_dir)
        e = t["cuentas"][cuenta]
        e["estado"] = "activa"
        e["estado_ts"] = ahora
        _guardar(base_dir, t)
        return e


def guardar_config(base_dir, **cambios):
    """Ajusta la config del tablero validando la config RESULTANTE."""
    rangos = {"umbral_cuarentena": (0, 99), "margen_salida": (0, 50),
              "frescura_declarado_s": (60, 86400)}
    for k, v in cambios.items():
        if k not in rangos:
            raise ErrorTablero(f"config del tablero desconocida: {k}")
        lo, hi = rangos[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (lo <= v <= hi):
            raise ErrorTablero(f"{k} debe estar entre {lo} y {hi}, no {v!r}")
    with _bloqueo(base_dir):
        t = cargar(base_dir)
        nueva = dict(t["config"])
        nueva.update(cambios)
        if not _config_valida(nueva):
            raise ErrorTablero(
                "esa config deja la salida de cuarentena inalcanzable "
                f"(umbral {nueva['umbral_cuarentena']} + margen {nueva['margen_salida']} > 100 "
                "o umbral 0)")
        t["config"] = nueva
        _guardar(base_dir, t)
        return t["config"]


# ---------------------------------------------------------------- lectura

def vista(base_dir, estimador=None, ahora=None):
    """Entradas completas por cuenta: lo publicado + el desglose del % y el
    estado GUARDADO (vista no transiciona: eso es de recalcular, B1).

    `estimador(cuenta, motor_principal)` -> % libre estimado o None; se
    llama sin ningún lock tomado."""
    ahora = time.time() if ahora is None else ahora
    t = cargar(base_dir)
    cfg = t["config"]
    out = {}
    for cid, e in t["cuentas"].items():
        estimado = None
        if estimador is not None:
            try:
                estimado = estimador(cid, e.get("motor_principal") or "claude")
            except Exception:
                estimado = None
        d = _pct_detalle(e, cfg, ahora, estimado)
        lat = e.get("latido_ts")
        sin_latido = not (isinstance(lat, (int, float))
                          and 0 <= ahora - lat <= cfg["frescura_declarado_s"])
        out[cid] = dict(e,
                        pct_efectivo=d["efectivo"], pct_fuente=d["fuente"],
                        pct_puerta=d["puerta"], pct_estimado=d["estimado"],
                        pct_declarado=d["declarado"],
                        estado=e.get("estado", "activa"), sin_latido=sin_latido)
    return out


def elegir_cuenta(vista_d, tareas_activas, registro):
    """La cuenta que debe recibir la próxima tarea, o None (determinista).

    Candidatas: habilitadas, con carril y en estado `activa` según la vista.
    Orden: % de puerta conocido antes que sin_dato; mayor % primero; menos
    tareas activas; id ascendente."""
    activas = (tareas_activas or {})
    candidatas = []
    for c in registro.get("cuentas", []):
        if not c.get("habilitada", True) or not c.get("carril"):
            continue
        v = vista_d.get(c["id"]) or {}
        if v.get("estado", "activa") != "activa":
            continue
        pct = v.get("pct_puerta", v.get("pct_efectivo"))
        candidatas.append((c["id"], pct))
    if not candidatas:
        return None

    def clave(item):
        cid, pct = item
        conocido = 0 if pct is not None else 1
        return (conocido, -(pct or 0), activas.get(cid, 0), cid)

    candidatas.sort(key=clave)
    return candidatas[0][0]

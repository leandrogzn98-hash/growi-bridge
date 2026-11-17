#!/usr/bin/env python3
"""sala.py — La sala común de Growi Private MQTT (P3).

La sala es la mesa compartida dentro del programa: ahí caen las
notificaciones, los fallos con su extracto y la conversación del
dueño con todas sus cuentas, y ahí se conversa el reparto de cada
encargo (diseño de equipo §3/§4/§7 bis, en su versión 0.1).

Dos archivos en la carpeta compartida:
- `sala.jsonl`: el registro de mensajes (vista y diario). Un solo
  punto de escritura —esta función `escribir`— con redacción
  obligatoria: ningún secreto entra en la sala.
- `sala-reparto.json`: el estado del reparto en curso por encargo
  (la autoridad del reparto del encargo sigue en `encargos.json`,
  que lleva relevo.py; esto es su cara conversada: quién aceptó,
  quién reclamó qué y con qué peso).

Tipos de mensaje: dueno, cuenta, sistema, propuesta, reclamo,
aceptacion, resolucion. Un mensaje `sistema` puede llevar subtipo
`fallo` con el extracto de diagnóstico.
"""

import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

TIPOS = ("dueno", "cuenta", "sistema", "propuesta", "reclamo",
         "aceptacion", "resolucion")
TOPE_TEXTO = 4000
_LOCK_STALE_S = 15.0

_PATRONES = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_\.]{16,}"),
    re.compile(r"glpat-[A-Za-z0-9\-_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
]


def redactar(texto, valores=()):
    """Redacción de la sala: patrones conocidos de secreto y los
    valores exactos que el llamador pase (claves de las cuentas)."""
    t = str(texto or "")
    for v in valores or ():
        if isinstance(v, str) and len(v) >= 8:
            t = t.replace(v, "•••")
    for patron in _PATRONES:
        t = patron.sub("•••", t)
    return t


@contextmanager
def _bloqueo(base_dir):
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    ruta_lock = base / "sala.lock"
    fd = None
    limite = time.time() + 10
    while True:
        try:
            fd = os.open(ruta_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - ruta_lock.stat().st_mtime > _LOCK_STALE_S:
                    ruta_lock.unlink()
                    continue
            except OSError:
                pass
            if time.time() > limite:
                raise TimeoutError("sala: lock ocupado")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            ruta_lock.unlink()
        except OSError:
            pass


def _ruta_log(base_dir):
    return Path(base_dir) / "sala.jsonl"


def escribir(base_dir, tipo, autor, texto, encargo=None, fase=None,
             subtipo=None, valores=(), reloj=None):
    """Único punto de escritura de la sala. Devuelve el id del
    mensaje. El texto se redacta siempre y se acota a TOPE_TEXTO."""
    if tipo not in TIPOS:
        raise ValueError(f"tipo de mensaje de sala desconocido: {tipo}")
    ahora = (reloj or time.time)()
    msg = {"id": f"{int(ahora * 1000)}-{uuid.uuid4().hex[:8]}",
           "ts": ahora, "tipo": tipo, "autor": autor,
           "texto": redactar(texto, valores)[:TOPE_TEXTO],
           "encargo": encargo, "fase": fase, "subtipo": subtipo}
    with _bloqueo(base_dir):
        with open(_ruta_log(base_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg["id"]


def leer(base_dir, limite=300):
    """Los últimos `limite` mensajes válidos, en orden. Tolera
    líneas corruptas o a medias y deduplica por id."""
    ruta = _ruta_log(base_dir)
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    vistos, out = set(), []
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea)
        except ValueError:
            continue
        if not isinstance(msg, dict) or not msg.get("id"):
            continue
        if msg["id"] in vistos:
            continue
        vistos.add(msg["id"])
        out.append(msg)
    return out[-limite:] if limite else out


# ---------------------------------------------------------------------
# El reparto conversado (cara conversada; la autoridad es encargos.json)
# ---------------------------------------------------------------------

def _ruta_reparto(base_dir):
    return Path(base_dir) / "sala-reparto.json"


def _cargar_repartos(base_dir):
    try:
        datos = json.loads(_ruta_reparto(base_dir).read_text(
            encoding="utf-8"))
        if isinstance(datos, dict) and isinstance(
                datos.get("repartos"), dict):
            return datos
    except (OSError, ValueError):
        pass
    return {"version": 1, "repartos": {}}


def _guardar_repartos(base_dir, datos):
    ruta = _ruta_reparto(base_dir)
    tmp = ruta.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(tmp, ruta)


def reparto_crear(base_dir, raiz, planificadora, fases, reloj=None):
    """fases: [{sid, titulo, cuenta}] con la asignación propuesta."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = _cargar_repartos(base_dir)
        datos["repartos"][raiz] = {
            "raiz": raiz, "planificadora": planificadora,
            "estado": "propuesto", "creado_ts": ahora,
            "fases": {f["sid"]: {"titulo": f.get("titulo") or f["sid"],
                                 "cuenta": f.get("cuenta"),
                                 "aceptada": False, "peso": None}
                      for f in fases}}
        _guardar_repartos(base_dir, datos)
    return datos["repartos"][raiz]


def reparto_obtener(base_dir, raiz=None):
    datos = _cargar_repartos(base_dir)
    if raiz is not None:
        return datos["repartos"].get(raiz)
    abiertos = [r for r in datos["repartos"].values()
                if r.get("estado") in ("propuesto", "resuelto")]
    if not abiertos:
        return None
    return max(abiertos, key=lambda r: r.get("creado_ts") or 0)


def _reparto_mutar(base_dir, raiz, fn):
    with _bloqueo(base_dir):
        datos = _cargar_repartos(base_dir)
        rep = datos["repartos"].get(raiz)
        if rep is None:
            return None
        fn(rep)
        _guardar_repartos(base_dir, datos)
        return rep


def reparto_aceptar(base_dir, raiz, sid, cuenta):
    """La cuenta asignada acepta su fase. False si no era suya."""
    def fn(rep):
        f = rep["fases"].get(sid)
        if f and f.get("cuenta") == cuenta:
            f["aceptada"] = True
    rep = _reparto_mutar(base_dir, raiz, fn)
    if rep is None:
        return False
    f = rep["fases"].get(sid) or {}
    return bool(f.get("aceptada")) and f.get("cuenta") == cuenta


def reparto_reclamar(base_dir, raiz, sid, cuenta, peso=None):
    """Otra cuenta reclama la fase para sí: pasa a ser suya y queda
    aceptada por ella, con su peso anotado."""
    def fn(rep):
        f = rep["fases"].get(sid)
        if f:
            f["cuenta"] = cuenta
            f["aceptada"] = True
            f["peso"] = peso
    rep = _reparto_mutar(base_dir, raiz, fn)
    return rep is not None and sid in rep["fases"]


def reparto_reasignar(base_dir, raiz, sid, cuenta):
    """El dueño reasigna una fase antes de empezar (vuelve a
    pendiente de aceptación)."""
    def fn(rep):
        f = rep["fases"].get(sid)
        if f:
            f["cuenta"] = cuenta
            f["aceptada"] = False
            f["peso"] = None
    rep = _reparto_mutar(base_dir, raiz, fn)
    return rep is not None and sid in rep["fases"]


def reparto_estado(base_dir, raiz, estado):
    """propuesto -> resuelto (todo aceptado o el dueño corta) ->
    arrancado (subtareas entregadas)."""
    if estado not in ("propuesto", "resuelto", "arrancado", "cerrado"):
        raise ValueError(f"estado de reparto no válido: {estado}")
    def fn(rep):
        rep["estado"] = estado
    rep = _reparto_mutar(base_dir, raiz, fn)
    return rep is not None


def reparto_todo_aceptado(rep):
    fases = (rep or {}).get("fases") or {}
    return bool(fases) and all(f.get("aceptada") for f in fases.values())

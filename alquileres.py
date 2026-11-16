# -*- coding: utf-8 -*-
"""Alquileres por proyecto y por archivo (Growi Bridge, Fase 3).

Dos cuentas Muse no editan lo mismo a la vez: antes de trabajar en un
repo, una tarea toma alquiler de sus archivos (o del proyecto entero) y
lo renueva en cada latido. Los alquileres coordinan a los DOS procesos,
así que viven donde vive el tablero — `alquileres.json` en la carpeta
compartida por usuario — y NO en `cola.db`, que es por carril y no
coordina nada entre copias (§4.1 del diseño). Mismo patrón que
`tablero.py`: mutex en proceso + lock de archivo entre procesos con
ruptura de huérfano a los 15 s, `revision`, read-modify-write bajo el
lock y escritura atómica (tmp + `os.replace`).

Reglas (§4.3):
- `tomar` es todo-o-nada: primero purga los caducados, luego comprueba
  conflictos y solo entonces escribe TODOS. Una tarea no se queda con
  media lista.
- El alquiler es por (cuenta, tarea): dos tareas de la misma Muse
  tampoco se pisan.
- `"*"` es el proyecto entero: choca con cualquier archivo de otra
  tarea y viceversa. Las claves `"@…"` (la de mezcla, `@mezcla`) son un
  espacio aparte: solo chocan consigo mismas (corrección B9).
- Tomar una ruta cuyo alquiler estaba caducado es un ROBO por caducidad:
  se devuelve en el resultado para que el monolito lo audite; el
  desposeído se entera en su siguiente `renovar` (devuelve no-ok).
- TTL por defecto 300 s, renovado en cada latido del hilo de pulso
  (corrección I1): el margen real son varios latidos perdidos, no uno.
  Y `renovar` no purga lo propio: un alquiler caducado que nadie robó
  sigue siendo de su dueño al renovar (guarda de salto de reloj).
- Las claves se normalizan a minúsculas si el repo es
  `core.ignorecase=true` (corrección I3; el llamador lo pasa).
"""
import contextlib
import json
import os
import threading
import time
from pathlib import Path

ARCHIVO = "alquileres.json"
VERSION = 1
TTL_DEF_S = 300

_LOCK_PROCESO = threading.RLock()


class ErrorAlquileres(Exception):
    """Un dato de alquileres es inválido o el archivo está bloqueado."""


def _vacio():
    return {"version": VERSION, "revision": 0, "alquileres": {}}


def cargar(base_dir):
    """Lee alquileres.json. Ausente o corrupto -> vacío. Nunca lanza."""
    path = Path(base_dir) / ARCHIVO
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _vacio()
    if not isinstance(d, dict) or not isinstance(d.get("alquileres"), dict):
        return _vacio()
    t = _vacio()
    rev = d.get("revision", 0)
    t["revision"] = rev if isinstance(rev, int) and not isinstance(rev, bool) else 0
    t["alquileres"] = {k: v for k, v in d["alquileres"].items() if isinstance(v, dict)}
    return t


@contextlib.contextmanager
def _bloqueo(base_dir):
    """Mutex en proceso + lock de archivo entre procesos (patrón Fase 2)."""
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
            raise ErrorAlquileres("alquileres.json está bloqueado por otro proceso")
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


def _guardar(base_dir, d):
    d["revision"] = int(d.get("revision", 0)) + 1
    path = Path(base_dir) / ARCHIVO
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- rutas

def normalizar_ruta(ruta, minusculas=False):
    """Ruta relativa al repo, con `/`, sin salir del repo. `"*"` (proyecto
    entero) y `"@…"` (claves especiales) pasan como casos propios."""
    r = str(ruta or "").replace("\\", "/").strip()
    if r == "*":
        return "*"
    if r.startswith("@"):
        return r.lower() if minusculas else r
    if not r:
        raise ErrorAlquileres("ruta de alquiler vacía")
    if r.startswith("/") or (len(r) > 1 and r[1] == ":"):
        raise ErrorAlquileres(f"la ruta de alquiler debe ser relativa al repo: {ruta!r}")
    partes = [p for p in r.split("/") if p not in ("", ".")]
    if any(p == ".." for p in partes):
        raise ErrorAlquileres(f"la ruta de alquiler sale del repo: {ruta!r}")
    if not partes:
        raise ErrorAlquileres(f"ruta de alquiler inválida: {ruta!r}")
    out = "/".join(partes)
    return out.lower() if minusculas else out


def _clave(repo, ruta):
    return f"{repo}|{ruta}"


def _tipo_de(ruta):
    if ruta == "*":
        return "proyecto"
    if ruta.startswith("@"):
        return "clave"
    return "archivo"


def _purgar(d, ahora):
    """Quita los caducados del dict (bajo lock). Devuelve los purgados."""
    fuera = []
    for k in [k for k, e in d["alquileres"].items()
              if not isinstance(e.get("expira_ts"), (int, float))
              or e["expira_ts"] <= ahora]:
        fuera.append(dict(d["alquileres"].pop(k), clave=k))
    return fuera


def _es_de(e, cuenta, tarea):
    return e.get("cuenta") == cuenta and e.get("tarea") == tarea


def _conflictos(d, repo, rutas, cuenta, tarea):
    """Conflictos de `rutas` contra los alquileres VIVOS del dict."""
    conf = []
    vivos = {k: e for k, e in d["alquileres"].items() if e.get("repo") == repo}
    for ruta in rutas:
        for k, e in vivos.items():
            if _es_de(e, cuenta, tarea):
                continue
            otra = e.get("ruta")
            choca = False
            if ruta.startswith("@") or str(otra).startswith("@"):
                choca = ruta == otra  # las claves @ solo chocan consigo mismas (B9)
            elif ruta == "*" or otra == "*":
                choca = True
            elif ruta == otra:
                choca = True
            if choca:
                conf.append({"ruta": ruta, "cuenta": e.get("cuenta"),
                             "tarea": e.get("tarea"), "expira_ts": e.get("expira_ts")})
                break
    return conf


# ---------------------------------------------------------------- API

def tomar(base_dir, repo, rutas, cuenta, tarea, ttl_s=TTL_DEF_S,
          minusculas=False, reloj=None):
    """Toma (o renueva) el alquiler de `rutas` de un repo para una tarea.

    Todo-o-nada (§4.3). Devuelve {"ok": True, "expira_ts", "robados"} o
    {"ok": False, "conflictos": [{ruta, cuenta, tarea, expira_ts}]}."""
    if not cuenta or not tarea:
        raise ErrorAlquileres("el alquiler necesita cuenta y tarea")
    if not rutas:
        raise ErrorAlquileres("el alquiler necesita al menos una ruta")
    rutas_n = []
    for r in rutas:
        n = normalizar_ruta(r, minusculas=minusculas)
        if n not in rutas_n:
            rutas_n.append(n)
    if "*" in rutas_n:
        rutas_n = ["*"]  # el proyecto entero subsume a sus archivos
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        d = cargar(base_dir)
        purgados = _purgar(d, ahora)
        conf = _conflictos(d, repo, rutas_n, cuenta, tarea)
        if conf:
            if purgados:
                _guardar(base_dir, d)  # la purga sí se persiste
            return {"ok": False, "conflictos": conf}
        expira = ahora + ttl_s
        for ruta in rutas_n:
            k = _clave(repo, ruta)
            previo = d["alquileres"].get(k)
            d["alquileres"][k] = {
                "tipo": _tipo_de(ruta), "repo": repo, "ruta": ruta,
                "cuenta": cuenta, "tarea": tarea,
                "desde_ts": previo.get("desde_ts", ahora) if previo and _es_de(previo, cuenta, tarea) else ahora,
                "latido_ts": ahora, "expira_ts": expira,
            }
        _guardar(base_dir, d)
        claves_pedidas = {_clave(repo, r) for r in rutas_n}
        robados = [{"ruta": p.get("ruta"), "cuenta_anterior": p.get("cuenta"),
                    "tarea_anterior": p.get("tarea")}
                   for p in purgados
                   if p.get("clave") in claves_pedidas
                   and not _es_de(p, cuenta, tarea)]
        return {"ok": True, "expira_ts": expira, "robados": robados}


def renovar(base_dir, cuenta, tarea, ttl_s=TTL_DEF_S, reloj=None):
    """Renueva TODOS los alquileres de (cuenta, tarea).

    Devuelve {"ok", "renovados", "perdidos"}: ok=False si la tarea ya no
    tiene ninguno suyo o si otra cuenta se quedó con alguno de los suyos
    (robo por caducidad: el monolito marca la tarea y no la deja subir)."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        d = cargar(base_dir)
        propios, perdidos = [], []
        for k, e in d["alquileres"].items():
            if e.get("tarea") != tarea:
                continue
            if e.get("cuenta") == cuenta:
                propios.append(k)
            else:
                perdidos.append({"ruta": e.get("ruta"), "cuenta": e.get("cuenta")})
        for k in propios:
            d["alquileres"][k]["latido_ts"] = ahora
            d["alquileres"][k]["expira_ts"] = ahora + ttl_s
        if propios:
            _guardar(base_dir, d)
        return {"ok": bool(propios) and not perdidos,
                "renovados": len(propios), "perdidos": perdidos}


def soltar(base_dir, cuenta, tarea):
    """Libera los alquileres de (cuenta, tarea). Lo de otro no se puede
    soltar por la API: cuenta y tarea deben coincidir. Devuelve cuántos."""
    with _bloqueo(base_dir):
        d = cargar(base_dir)
        claves = [k for k, e in d["alquileres"].items() if _es_de(e, cuenta, tarea)]
        for k in claves:
            del d["alquileres"][k]
        if claves:
            _guardar(base_dir, d)
        return len(claves)


def vigentes(base_dir, repo=None, reloj=None):
    """Los alquileres vivos (purga perezosa al leer: los caducados no se
    muestran; se borran en la siguiente escritura)."""
    ahora = (reloj or time.time)()
    d = cargar(base_dir)
    out = []
    for k, e in d["alquileres"].items():
        exp = e.get("expira_ts")
        if not isinstance(exp, (int, float)) or exp <= ahora:
            continue
        if repo is not None and e.get("repo") != repo:
            continue
        out.append(dict(e, clave=k))
    return out


def de_tarea(base_dir, repo, tarea, reloj=None):
    """Los alquileres vivos de una tarea en un repo (de cualquier cuenta)."""
    return [e for e in vigentes(base_dir, repo=repo, reloj=reloj)
            if e.get("tarea") == tarea]


def reasignar(base_dir, repo, tarea, de_cuenta, a_cuenta, reloj=None):
    """Pasa los alquileres de la tarea de una cuenta a otra (el claim del
    traspaso, corrección B5). Se llama con el lock de traspasos tomado:
    el orden de locks es traspasos -> alquileres, siempre el mismo."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        d = cargar(base_dir)
        n = 0
        for e in d["alquileres"].values():
            if (e.get("repo") == repo and e.get("tarea") == tarea
                    and e.get("cuenta") == de_cuenta):
                e["cuenta"] = a_cuenta
                e["latido_ts"] = ahora
                n += 1
        if n:
            _guardar(base_dir, d)
        return n

"""Growi Bridge — Reforma de cuentas: la bóveda compartida.

Los secretos de trabajo (contraseñas y claves que las cuentas Muse
pueden necesitar) se guardan UNA sola vez para todas las cuentas, no
por cuenta. Este módulo es solo el registro de NOMBRES
(`boveda-compartida.json`, en la carpeta compartida entre carriles):
etiqueta, nota y fecha. Los VALORES jamás pasan por aquí: viven en el
almacén de credenciales del sistema, con el nombre
`compartido:<etiqueta>`, y los pone/lee/borra el monolito con
`_sec_set/_sec_get/_sec_del`.

La clave de conexión de cada cuenta NO es un secreto compartido: es lo
que distingue a una Muse de la otra y sigue en `muse:<id>`.

Patrones heredados de `cuentas.py`: lock entre procesos (O_EXCL, con
ruptura si queda huérfano más de 15 s), revisión optimista y escritura
atómica (tmp + os.replace). `cargar` nunca lanza: ante cualquier
problema devuelve el registro vacío y la app sigue.
"""

import contextlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

VERSION_ESQUEMA = 1
ARCHIVO = "boveda-compartida.json"
# Etiqueta: 1-41 caracteres, empieza en letra o dígito minúsculo, sigue
# con minúsculas, dígitos, guiones y guiones bajos.
_RX_ETIQUETA = re.compile(r"[a-z0-9][a-z0-9-_]{0,40}")


class ErrorCompartida(Exception):
    """El registro de la bóveda compartida no valida o la operación no
    se puede hacer (etiqueta inválida o duplicada); el llamante avisa."""


def nombre_valor(etiqueta):
    """Nombre de la credencial en el almacén para un secreto compartido."""
    return f"compartido:{etiqueta}"


def etiqueta_valida(etiqueta):
    return isinstance(etiqueta, str) and bool(_RX_ETIQUETA.fullmatch(etiqueta))


def _registro_vacio():
    return {"version": VERSION_ESQUEMA, "revision": 0, "entradas": []}


def validar(reg):
    """Lista de errores del registro (vacía si es válido)."""
    errores = []
    if not isinstance(reg, dict):
        return ["el registro no es un objeto"]
    if reg.get("version") != VERSION_ESQUEMA:
        errores.append(f"version de esquema no soportada: {reg.get('version')!r}")
    rev = reg.get("revision", 0)
    if not isinstance(rev, int) or isinstance(rev, bool) or rev < 0:
        errores.append(f"revision inválida: {rev!r}")
    entradas = reg.get("entradas")
    if not isinstance(entradas, list):
        return errores + ["entradas debe ser una lista"]
    vistas = set()
    for e in entradas:
        if not isinstance(e, dict):
            errores.append("hay una entrada que no es un objeto")
            continue
        et = e.get("etiqueta")
        if not etiqueta_valida(et):
            errores.append(f"etiqueta inválida: {et!r}")
        elif et in vistas:
            errores.append(f"etiqueta duplicada: {et}")
        vistas.add(et)
        if not isinstance(e.get("nota") or "", str):
            errores.append(f"{et}: nota inválida")
        if e.get("creada") is not None and not isinstance(e.get("creada"), str):
            errores.append(f"{et}: creada inválida")
        if "valor" in e:
            # Defensa en profundidad: un valor en el registro es un
            # error de esquema, no un dato (jamás se escriben valores).
            errores.append(f"{et}: el registro no puede contener valores")
    return errores


def _leer(base_dir):
    """El registro tal cual está en disco (vacío si falta o está roto)."""
    try:
        reg = json.loads((Path(base_dir) / ARCHIVO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _registro_vacio()
    if not isinstance(reg, dict):
        return _registro_vacio()
    reg.setdefault("version", VERSION_ESQUEMA)
    reg.setdefault("revision", 0)
    reg.setdefault("entradas", [])
    return reg


def cargar(base_dir):
    """Lee boveda-compartida.json. Nunca lanza: ante cualquier problema
    devuelve el registro vacío (la pantalla enseña «sin secretos»)."""
    try:
        reg = _leer(base_dir)
    except Exception:
        return _registro_vacio()
    if validar(reg):
        return _registro_vacio()
    return reg


def listar(base_dir):
    """Las entradas del registro: [{etiqueta, nota, creada}] (copias)."""
    return [dict(e) for e in cargar(base_dir).get("entradas", [])]


@contextlib.contextmanager
def _bloqueo(base_dir):
    """Lock de archivo entre procesos (mismo patrón que cuentas.py):
    los dos carriles comparten esta carpeta y no deben pisarse."""
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    lock = base / (ARCHIVO + ".lock")
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
        raise ErrorCompartida(
            "el registro de la bóveda compartida está bloqueado por otro proceso")
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except OSError:
            pass


def _revision_en_disco(base_dir):
    try:
        reg = json.loads((Path(base_dir) / ARCHIVO).read_text(encoding="utf-8"))
        rev = reg.get("revision", 0)
        return rev if isinstance(rev, int) and not isinstance(rev, bool) else 0
    except (OSError, ValueError, AttributeError):
        return 0


def _guardar_bajo_lock(base_dir, reg):
    """guardar() suponiendo que el llamante ya tiene _bloqueo."""
    errores = validar(reg)
    if errores:
        raise ErrorCompartida("; ".join(errores))
    disco = _revision_en_disco(base_dir)
    if reg.get("revision", 0) != disco:
        raise ErrorCompartida(
            f"el registro cambió en disco (revisión {disco}); "
            "recarga antes de guardar")
    reg["revision"] = disco + 1
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / ARCHIVO
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)
    return path


def guardar(base_dir, reg):
    """Valida y guarda con escritura atómica y control optimista de
    revisión (como cuentas.guardar)."""
    with _bloqueo(base_dir):
        return _guardar_bajo_lock(base_dir, reg)


def agregar(base_dir, etiqueta, nota=""):
    """Registra un nombre de secreto compartido (el valor va aparte, al
    almacén de credenciales). Devuelve la entrada creada. Lanza
    ErrorCompartida si la etiqueta es inválida o ya existe."""
    etiqueta = (etiqueta or "").strip() if isinstance(etiqueta, str) else ""
    if not etiqueta_valida(etiqueta):
        raise ErrorCompartida(
            f"etiqueta inválida: {etiqueta!r} (minúsculas, dígitos, "
            "guiones y guiones bajos; empieza en letra o dígito; "
            "máximo 41 caracteres)")
    nota = str(nota or "").strip()
    with _bloqueo(base_dir):
        reg = _leer(base_dir)
        if any(e.get("etiqueta") == etiqueta for e in reg.get("entradas", [])):
            raise ErrorCompartida(
                f"ya hay un secreto compartido con la etiqueta «{etiqueta}»")
        entrada = {"etiqueta": etiqueta, "nota": nota,
                   "creada": datetime.now().astimezone().isoformat(
                       timespec="seconds")}
        reg.setdefault("entradas", []).append(entrada)
        _guardar_bajo_lock(base_dir, reg)
        return entrada


def quitar(base_dir, etiqueta):
    """Quita el nombre del registro (el valor lo borra el llamante del
    almacén). True si estaba; False si no había nada que quitar."""
    with _bloqueo(base_dir):
        reg = _leer(base_dir)
        entradas = reg.get("entradas", [])
        nuevas = [e for e in entradas if e.get("etiqueta") != etiqueta]
        if len(nuevas) == len(entradas):
            return False
        reg["entradas"] = nuevas
        _guardar_bajo_lock(base_dir, reg)
        return True

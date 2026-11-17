"""Growi Bridge — Fase 1 Multi-Muse: registro de cuentas Muse.

Este módulo es la lógica pura del registro de cuentas (`accounts.json`):
cargar, validar, guardar (atómico) y migrar el `secret.txt` histórico a la
bóveda. No conoce el monolito: el almacén de secretos se inyecta como dos
funciones `sec_get(nombre) -> str | None` y `sec_set(nombre, valor)`, que en
la app son `_sec_get/_sec_set` de growi-bridge.py con el nombre
`muse:<id>` por cuenta.

Reglas de oro (PLAN-MULTI-MUSE.md, Fase 1):
- El secreto NUNCA se escribe en accounts.json: solo vive en la bóveda.
- Si accounts.json falta o está corrupto, se devuelve el registro de
  compatibilidad (una cuenta implícita) y la app arranca como siempre.
- La migración de secret.txt es idempotente y reversible: el archivo
  secret.txt no se toca (browser/browser-server.py todavía lo lee).
"""

import contextlib
import json
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

VERSION_ESQUEMA = 1
ARCHIVO = "accounts.json"
CONEXIONES = ("servidor", "local", "ambas", "mqtt")
CARRILES = ("a", "b")
# Id: 2-32 caracteres, empieza y termina en letra o dígito (sin guion en los
# extremos), minúsculas, dígitos y guiones.
_RX_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,30}[a-z0-9]")
# Asistente: nombre simple de perfil, sin rutas (nada de /, \ ni ..).
_RX_ASISTENTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}")
# Clase de acción de la capa de permisos (los permisos por cuenta solo
# restan clases conocidas; el formato se valida aquí y la pertenencia la
# impone el clasificador al cruzarlas con las clases reales).
_RX_CLASE = re.compile(r"[a-z][a-z0-9_]{1,40}")
# Nombre de skill declarada como «fuerte» de una cuenta (P4): el mismo
# alfabeto que los nombres de skill del catálogo (letras, números, - _ .),
# sin espacios ni rutas. Que el skill EXISTA en el catálogo no se valida
# aquí (el registro no conoce el catálogo): lo valida la app al guardar
# y, si un fuerte deja de existir, al repartir simplemente cuenta 0.
_RX_FUERTE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

CUENTA_COMPAT = {
    "id": "principal",
    "nombre": "Muse principal",
    "asistente": None,
    "carril": None,
    "conexion": "servidor",
    "habilitada": True,
    "creada": None,
    "fuertes": [],
    "permisos": {"modo": "hereda", "clases_extra_denegadas": []},
}


class ErrorRegistro(Exception):
    """El registro no valida; el llamante decide (compatibilidad o aviso)."""


def nombre_secreto(cuenta_id):
    """Nombre de la credencial en la bóveda para una cuenta: muse:<id>."""
    return f"muse:{cuenta_id}"


def registro_compatibilidad(carril=None, asistente=None):
    """El registro implícito cuando no hay accounts.json válido."""
    c = dict(CUENTA_COMPAT)
    c["carril"] = carril
    c["asistente"] = asistente
    return {"version": VERSION_ESQUEMA, "compatibilidad": True,
            "revision": 0, "borradas": [],
            "migrado_secret_txt": False, "cuentas": [c]}


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
    borradas = reg.get("borradas", [])
    if not isinstance(borradas, list):
        errores.append("borradas debe ser una lista")
        borradas = []
    tumbas = {b.get("id") for b in borradas if isinstance(b, dict)}
    cuentas = reg.get("cuentas")
    if not isinstance(cuentas, list) or not cuentas:
        return errores + ["cuentas debe ser una lista con al menos una cuenta"]
    ids, carriles = set(), {}
    for c in cuentas:
        if not isinstance(c, dict):
            errores.append("hay una cuenta que no es un objeto")
            continue
        cid = c.get("id")
        if not isinstance(cid, str) or not _RX_ID.fullmatch(cid):
            errores.append(f"id de cuenta inválido: {cid!r}")
        elif cid in ids:
            errores.append(f"id de cuenta duplicado: {cid}")
        elif cid in tumbas:
            # Un id borrado no se reutiliza: heredaría el secreto y la
            # auditoría de la cuenta anterior.
            errores.append(f"id de cuenta ya usado y borrado: {cid}")
        ids.add(cid)
        if cid == "principal" and not c.get("habilitada", True):
            errores.append("la cuenta principal no se puede deshabilitar")
        asis = c.get("asistente")
        if asis is not None and (not isinstance(asis, str)
                                 or not _RX_ASISTENTE.fullmatch(asis)
                                 or ".." in asis):
            errores.append(f"{cid}: asistente inválido: {asis!r}")
        if c.get("conexion") not in CONEXIONES:
            errores.append(f"{cid}: conexion inválida: {c.get('conexion')!r}")
        carril = c.get("carril")
        if carril is not None and carril not in CARRILES:
            errores.append(f"{cid}: carril inválido: {carril!r}")
        if carril is not None and c.get("habilitada", True):
            if carril in carriles:
                errores.append(
                    f"carril {carril} compartido por {carriles[carril]} y {cid}")
            carriles[carril] = cid
        per = c.get("permisos") or {}
        if per.get("modo", "hereda") not in ("hereda", "restringido"):
            errores.append(f"{cid}: permisos.modo inválido: {per.get('modo')!r}")
        for clase in per.get("clases_extra_denegadas") or []:
            if not isinstance(clase, str) or not _RX_CLASE.fullmatch(clase):
                errores.append(f"{cid}: clase denegada inválida: {clase!r}")
        fuertes = c.get("fuertes")
        if fuertes is not None:
            if not isinstance(fuertes, list):
                errores.append(f"{cid}: fuertes debe ser una lista de "
                               "nombres de skill")
            else:
                for f in fuertes:
                    if not isinstance(f, str) or not _RX_FUERTE.fullmatch(f):
                        errores.append(f"{cid}: fuerte inválido: {f!r}")
    return errores


def cargar(base_dir, carril=None, asistente=None):
    """Lee accounts.json. Ante cualquier problema devuelve compatibilidad.

    Nunca lanza por archivo ausente o corrupto: el arranque no puede
    depender del registro (eso es lo que lo hace seguro de desplegar).
    """
    path = Path(base_dir) / ARCHIVO
    try:
        reg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return registro_compatibilidad(carril, asistente)
    if validar(reg):
        return registro_compatibilidad(carril, asistente)
    reg.setdefault("compatibilidad", False)
    reg.setdefault("migrado_secret_txt", False)
    reg.setdefault("revision", 0)
    reg.setdefault("borradas", [])
    return reg


@contextlib.contextmanager
def _bloqueo_registro(base_dir):
    """Lock de archivo entre procesos para el ciclo leer-modificar-escribir.

    Dos carriles y la UI pueden tocar el registro a la vez: os.replace evita
    lecturas rotas, pero no las actualizaciones perdidas. El lock es un
    archivo creado con O_EXCL; si queda huérfano más de 15 s se rompe.
    """
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
        raise ErrorRegistro("el registro de cuentas está bloqueado por otro proceso")
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
    """guardar() suponiendo que el llamante ya tiene _bloqueo_registro."""
    errores = validar(reg)
    if errores:
        raise ErrorRegistro("; ".join(errores))
    disco = _revision_en_disco(base_dir)
    if reg.get("revision", 0) != disco:
        raise ErrorRegistro(
            f"el registro cambió en disco (revisión {disco}); "
            "recarga antes de guardar")
    reg["revision"] = disco + 1
    salida = dict(reg)
    salida.pop("compatibilidad", None)  # estado de lectura, no de disco
    path = Path(base_dir) / ARCHIVO
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(salida, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)
    return path


def guardar(base_dir, reg):
    """Valida y guarda con escritura atómica (tmp + os.replace).

    Control optimista: la `revision` del registro debe coincidir con la del
    disco; si otro proceso guardó antes, se rechaza para no perder su
    cambio. Al guardar, la revision sube en 1 (también en el dict pasado).
    """
    with _bloqueo_registro(base_dir):
        return _guardar_bajo_lock(base_dir, reg)


def cuenta(reg, cuenta_id):
    for c in reg.get("cuentas", []):
        if c.get("id") == cuenta_id:
            return c
    return None


def cuenta_de_carril(reg, carril):
    """La cuenta habilitada asignada a un carril, o None."""
    for c in reg.get("cuentas", []):
        if c.get("habilitada", True) and c.get("carril") == carril:
            return c
    return None


def cuentas_habilitadas(reg):
    return [c for c in reg.get("cuentas", []) if c.get("habilitada", True)]


def fuertes_de(reg, cuenta_id):
    """Los skills declarados como fuertes de una cuenta (P4), sin
    duplicados y en el orden declarado. Campo opcional: un registro sin
    `fuertes` (o con la cuenta ausente) devuelve []. Nunca lanza."""
    c = cuenta(reg, cuenta_id)
    if not c:
        return []
    out = []
    for f in c.get("fuertes") or []:
        if isinstance(f, str) and f and f not in out:
            out.append(f)
    return out


def derivar_id(nombre, existentes):
    """El identificador de una cuenta a partir del nombre que le pone el
    dueño (Reforma de cuentas): minúsculas, sin acentos (NFKD), espacios
    y caracteres no válidos a guiones, recortado al patrón de ids (2–32,
    empieza y termina en letra o dígito). Si choca con un id existente
    (la lista `existentes` debe traer los ids vivos Y las lápidas de
    `borradas`: un id borrado no se reutiliza), sufijo «-2», «-3»… Si el
    nombre no produce nada válido, la base es «cuenta»."""
    base = unicodedata.normalize("NFKD", str(nombre or ""))
    base = base.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:32].strip("-")
    if len(base) < 2 or not _RX_ID.fullmatch(base):
        base = "cuenta"
    ocupados = set(existentes or [])
    if base not in ocupados:
        return base
    n = 2
    while True:
        sufijo = f"-{n}"
        candidato = base[:32 - len(sufijo)].strip("-") + sufijo
        if candidato not in ocupados:
            return candidato
        n += 1


def carril_libre(reg):
    """El primer carril («a», luego «b») sin cuenta habilitada, o None
    si los dos están ocupados. Una cuenta deshabilitada no ocupa su
    carril (la validación del registro tampoco lo cuenta como ocupado)."""
    ocupados = {c.get("carril") for c in reg.get("cuentas", [])
                if c.get("habilitada", True) and c.get("carril")}
    for carril in CARRILES:
        if carril not in ocupados:
            return carril
    return None


def secreto_de(reg, cuenta_id, sec_get):
    """El secreto de una cuenta desde la bóveda (nunca del registro)."""
    if cuenta(reg, cuenta_id) is None and not reg.get("compatibilidad"):
        return None
    v = sec_get(nombre_secreto(cuenta_id))
    return v.strip() if v else None


def migrar(base_dir, leer_secret_txt, sec_get, sec_set,
           carril="a", asistente=None):
    """Migra secret.txt a la bóveda y crea accounts.json. Idempotente.

    - Si accounts.json ya existe y valida: no hace nada.
    - Si la bóveda ya tiene el mismo valor: solo crea el registro.
    - Si tras guardar el valor no se lee igual: aborta sin crear el
      registro (la app sigue con secret.txt como hasta ahora).
    - secret.txt NO se modifica ni se borra (reversible: basta borrar
      accounts.json para volver al comportamiento anterior).

    Devuelve {"migrado": bool, "motivo": str}.

    Todo el ciclo va bajo el lock del registro: dos procesos arrancando a
    la vez no pueden migrar dos veces ni pisarse el accounts.json.
    El valor que se guarda es exactamente el que devuelve `leer_secret_txt`
    (en la app es load_secret(), que ya normaliza con strip()).
    """
    base = Path(base_dir)
    with _bloqueo_registro(base):
        if (base / ARCHIVO).exists():
            reg = cargar(base, carril, asistente)
            if not reg.get("compatibilidad"):
                return {"migrado": False, "motivo": "accounts.json ya existe"}
        valor = leer_secret_txt()
        if not valor:
            return {"migrado": False, "motivo": "no hay secret.txt que migrar"}
        nombre = nombre_secreto("principal")
        try:
            previo = sec_get(nombre)
            if previo is None or previo.strip() != valor:
                sec_set(nombre, valor)
                if (sec_get(nombre) or "").strip() != valor:
                    return {"migrado": False,
                            "motivo": "la bóveda no devolvió el mismo valor; "
                                      "migración abortada, se sigue con secret.txt"}
        except Exception as e:  # la bóveda puede fallar: no romper el arranque
            return {"migrado": False,
                    "motivo": f"error de bóveda ({type(e).__name__}); "
                              "se sigue con secret.txt"}
        reg = registro_compatibilidad(carril, asistente)
        reg.pop("compatibilidad")
        reg["migrado_secret_txt"] = True
        reg["cuentas"][0]["creada"] = datetime.now().astimezone().isoformat(
            timespec="seconds")
        _guardar_bajo_lock(base, reg)
        return {"migrado": True, "motivo": "secret.txt migrado a la bóveda "
                                          "como cuenta «principal»"}

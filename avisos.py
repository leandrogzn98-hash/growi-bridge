# -*- coding: utf-8 -*-
"""Avisos al dueño (Fase 4 del plan multi-Muse): guardar primero, despachar
después.

Un aviso es un hecho que el dueño debe poder ver: un encargo terminado, una
prueba física esperando su decisión, una cuenta en cuarentena, una cuenta
sin latido, un dual sin resolver. La regla de oro: el aviso se GUARDA
primero en el registro compartido (``avisos.jsonl`` en la carpeta compartida
por usuario) y solo después se despacha a los destinos activos. Si todos
los destinos fallan, el aviso sigue existiendo y se puede consultar desde
la interfaz. Un destino que falla se anota y no se reintenta: un aviso
nunca bloquea al runner.

Destinos:
- ``registro``: el propio ``avisos.jsonl`` (siempre activo).
- ``local``: callback inyectado por el monolito (toast en modo ausente,
  contador silencioso en modo presente; si molesta o no lo decide
  presencia, no el aviso).
- ``canal``: transporte externo. En esta fase solo existe ``CanalNulo``
  (dice que no está disponible y no envía nada); el contrato queda fijado
  con ``registrar_canal(nombre, fabrica)`` para la Fase 5 (WhatsApp /
  Telegram, decisión del dueño).

Deduplicación: los avisos que un barrido puede repetir (sin latido, dual
sin resolver, cuarentena) se deduplican por (tipo, cuenta, raíz, tarea) en
una ventana de 10 minutos. Los demás avisos son hechos únicos y siempre se
emiten (un encargo_terminado resume el cierre entero, no gotea subtareas).
"""

import contextlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

VERSION = 1
TOPE_BYTES = 5 * 1024 * 1024          # rotación del .jsonl
VENTANA_DEDUP_S = 600                 # 10 minutos
DEDUP_TIPOS = frozenset(
    {"cuenta_sin_latido", "dual_sin_resolver", "cuenta_cuarentena"})

NIVELES = ("info", "accion")

_LOCKS = {}
_LOCKS_MU = threading.Lock()


def _lock_de(ruta):
    clave = str(ruta)
    with _LOCKS_MU:
        if clave not in _LOCKS:
            _LOCKS[clave] = threading.RLock()
        return _LOCKS[clave]


@contextlib.contextmanager
def _bloqueo(ruta_lock, espera_s=10.0):
    """Lock entre procesos con ruptura de huérfano a los 15 s (el patrón de
    tablero.py/cuentas.py). Sin lock tras la espera se sigue sin él: un
    aviso jamás debe tumbar al emisor."""
    with _lock_de(ruta_lock):
        ruta_lock = Path(ruta_lock)
        ruta_lock.parent.mkdir(parents=True, exist_ok=True)
        fd = None
        limite = time.time() + max(0.0, espera_s)
        while True:
            try:
                fd = os.open(str(ruta_lock),
                             os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    if time.time() - ruta_lock.stat().st_mtime > 15:
                        ruta_lock.unlink()
                        continue
                except OSError:
                    pass
                if time.time() >= limite:
                    break
                time.sleep(0.05)
            except OSError:
                break
        try:
            yield
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    ruta_lock.unlink()
                except OSError:
                    pass


def ruta_registro(base_dir):
    return Path(base_dir) / "avisos.jsonl"


def _ruta_config(base_dir):
    return Path(base_dir) / "avisos-config.json"


# ---------------------------------------------------------------------------
# Destinos
# ---------------------------------------------------------------------------

class DestinoRegistro:
    """El registro .jsonl: emitir ya lo escribió antes de despachar."""
    nombre = "registro"

    def enviar(self, aviso):
        return True


class DestinoLocal:
    """Callback inyectado por el monolito (toast / contador silencioso)."""
    nombre = "local"

    def __init__(self):
        self._fn = None

    def fijar(self, fn):
        self._fn = fn

    def enviar(self, aviso):
        if self._fn is None:
            return False
        return bool(self._fn(aviso))


class CanalNulo:
    """Contrato del canal externo sin transporte: en esta fase no hay
    WhatsApp ni Telegram (decisión del dueño, Fase 5). Dice que no está
    disponible y no envía nada; lo que anota es que el aviso quedó solo en
    el registro."""
    nombre = "canal"

    def disponible(self):
        return False

    def enviar(self, aviso):
        return False


_LOCAL = DestinoLocal()
_CANALES = {"nulo": CanalNulo}
_DESTINOS = {"registro": DestinoRegistro(), "local": _LOCAL}


def registrar_destino(nombre, destino):
    """Registra (o sustituye) un destino despachable por nombre."""
    _DESTINOS[nombre] = destino


def fijar_destino_local(fn):
    """El monolito inyecta aquí su callback de aviso local."""
    _LOCAL.fijar(fn)


def registrar_canal(nombre, fabrica):
    """Fija el contrato del canal externo: ``fabrica()`` devuelve un objeto
    con ``nombre``, ``disponible()`` y ``enviar(aviso) -> bool``. La Fase 5
    registrará aquí el transporte real que elija el dueño."""
    _CANALES[nombre] = fabrica


def cargar_config(base_dir):
    """Config de avisos: destinos activos y canal elegido. Por defecto el
    registro y el aviso local; el canal nulo."""
    cfg = {"destinos": ["registro", "local"], "canal": "nulo"}
    try:
        datos = json.loads(_ruta_config(base_dir).read_text(encoding="utf-8"))
        if isinstance(datos, dict):
            if isinstance(datos.get("destinos"), list):
                cfg["destinos"] = [d for d in datos["destinos"]
                                   if isinstance(d, str)]
            if isinstance(datos.get("canal"), str):
                cfg["canal"] = datos["canal"]
    except (OSError, ValueError):
        pass
    return cfg


def _destinos_activos(base_dir):
    cfg = cargar_config(base_dir)
    activos = []
    for nombre in cfg["destinos"]:
        if nombre == "canal":
            fabrica = _CANALES.get(cfg.get("canal") or "nulo", CanalNulo)
            try:
                activos.append(fabrica())
            except Exception:
                activos.append(CanalNulo())
        elif nombre in _DESTINOS:
            activos.append(_DESTINOS[nombre])
    if not any(getattr(d, "nombre", "") == "registro" for d in activos):
        activos.insert(0, DestinoRegistro())
    return activos


# ---------------------------------------------------------------------------
# Emisión
# ---------------------------------------------------------------------------

def _clave_dedup(aviso):
    return (aviso.get("tipo"), aviso.get("cuenta"), aviso.get("raiz"),
            aviso.get("tarea"))


def _ya_emitido(base_dir, aviso, ahora):
    """¿Existe ya un aviso con la misma clave dentro de la ventana? Lee la
    cola del registro (acotado por la rotación a ~5 MB)."""
    ruta = ruta_registro(base_dir)
    try:
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    clave = _clave_dedup(aviso)
    for linea in reversed(lineas[-400:]):
        linea = linea.strip()
        if not linea:
            continue
        try:
            otro = json.loads(linea)
        except ValueError:
            continue
        if not isinstance(otro, dict):
            continue
        if _clave_dedup(otro) == clave:
            ts = otro.get("ts")
            return isinstance(ts, (int, float)) and ahora - ts < VENTANA_DEDUP_S
    return False


def _rotar_si_toca(ruta):
    try:
        if ruta.exists() and ruta.stat().st_size >= TOPE_BYTES:
            destino = ruta.with_name(ruta.name + ".1")
            try:
                destino.unlink()
            except OSError:
                pass
            os.replace(str(ruta), str(destino))
    except OSError:
        pass


def emitir(base_dir, tipo, texto, cuenta=None, raiz=None, tarea=None,
           nivel="info", reloj=None, log=None):
    """Guarda el aviso en el registro y después lo despacha.

    Devuelve el aviso (dict) o None si quedó suprimido por deduplicación.
    Nunca lanza: ni un registro imposible ni un destino roto tumban al
    emisor; los fallos de despacho se anotan vía ``log`` si se pasa."""
    ahora = (reloj or time.time)()
    if nivel not in NIVELES:
        nivel = "info"
    aviso = {
        "id": "av-" + uuid.uuid4().hex[:8],
        "ts": ahora,
        "tipo": tipo,
        "nivel": nivel,
        "cuenta": cuenta,
        "raiz": raiz,
        "tarea": tarea,
        "texto": str(texto)[:500],
    }
    base_dir = Path(base_dir)
    guardado = False
    try:
        with _bloqueo(base_dir / "avisos.jsonl.lock"):
            if tipo in DEDUP_TIPOS and _ya_emitido(base_dir, aviso, ahora):
                return None
            _rotar_si_toca(ruta_registro(base_dir))
            with open(ruta_registro(base_dir), "a", encoding="utf-8") as f:
                f.write(json.dumps(aviso, ensure_ascii=False) + "\n")
            guardado = True
    except Exception as e:  # el registro es el mínimo garantizado, pero ni
        if log is not None:  # siquiera él puede tumbar al emisor
            try:
                log(f"avisos: no se pudo guardar {aviso['id']}: {e}")
            except Exception:
                pass
    if not guardado:
        return aviso
    for destino in _destinos_activos(base_dir):
        try:
            destino.enviar(aviso)
        except Exception as e:
            if log is not None:
                try:
                    log(f"avisos: el destino {getattr(destino, 'nombre', '?')}"
                        f" falló con {aviso['id']}: {e}")
                except Exception:
                    pass
    return aviso


def leer_recientes(base_dir, n=50):
    """Los últimos ``n`` avisos del registro, del más reciente al más
    antiguo. Lista vacía si no hay registro o no se puede leer."""
    ruta = ruta_registro(base_dir)
    try:
        lineas = ruta.read_text(encoding="utf-8",
                                errors="replace").splitlines()
    except OSError:
        return []
    salida = []
    for linea in reversed(lineas):
        linea = linea.strip()
        if not linea:
            continue
        try:
            datos = json.loads(linea)
        except ValueError:
            continue
        if isinstance(datos, dict):
            salida.append(datos)
            if len(salida) >= max(1, n):
                break
    return salida

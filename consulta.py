# -*- coding: utf-8 -*-
"""Consulta entre Muses (Growi Bridge, Fase 2).

Una consulta es un `.task.json` normal con `"tipo": "consulta"` que el
carril de la cuenta destino ejecuta con su motor de siempre; la pregunta va
en `prompt` y la respuesta vuelve como el `.result.json` de siempre.

Topes duros (revisión de Opus 5.5 aplicada: cierran el conjunto, no solo
cada nodo), validados al crear, al entregar y al recoger:

- **Saltos derivados del padre, nunca declarados por el llamante** (B4):
  si el padre es una consulta, saltos = padre + 1; si es una tarea normal,
  saltos = 1. Máximo MAX_SALTOS: al llegar, la consulta no tiene hijas.
- **Presupuesto por raíz** (B3): libro mayor `consultas-uso.json` junto al
  tablero con el gasto y las reservas de TODA la cadena de una raíz
  (tope TOPE_RAIZ) y el nº de hijas por tarea (tope MAX_HIJAS). El
  presupuesto de una hija no puede superar lo que le queda a la raíz.
- **Reserva antes de ejecutar** (B5): `reservar_gasto` anota el gasto en el
  tracker y en el libro ANTES de correr; al recoger, el runner relee el
  `gastado` del archivo (un reintento no resetea ni duplica la reserva de
  la tarea, y el libro impide pasar del tope de la raíz).
- **Caducidad** (B5): toda consulta nace con `expira_ts` (TTL 1 h). Si
  caduca esperando, el runner la cierra como fallida con resultado: el
  origen no espera para siempre.
- **El origen lo pone el proceso que crea**, desde su cuenta de carril;
  nunca se acepta de un payload. Y `entregar` REVALIDA la tarea entera:
  un dict forjado a mano no se cuela por llamar solo a `entregar` (I7).
"""
import contextlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

MAX_SALTOS = 2
TOPE_PRESUPUESTO = 20      # por consulta
PRESUPUESTO_DEF = 10
TOPE_RAIZ = 40             # gasto + reservas de toda la cadena de una raíz
MAX_HIJAS = 3              # consultas que una misma tarea puede lanzar
TTL_DEF_S = 3600

LIBRO = "consultas-uso.json"
_LOCK_PROCESO = threading.RLock()


class ErrorConsulta(Exception):
    """La consulta no cumple las reglas; el mensaje es el motivo exacto."""


# ---------------------------------------------------------------- libro mayor

@contextlib.contextmanager
def _bloqueo_libro(base_dir):
    """Mutex en proceso + lock de archivo (mismo patrón que tablero.py)."""
    with _LOCK_PROCESO:
        lock = Path(base_dir) / (LIBRO + ".lock")
        fd = None
        for _ in range(150):
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime > 15:
                        lock.unlink()
                        continue
                except OSError:
                    pass
                time.sleep(0.02)
        if fd is None:
            raise ErrorConsulta("el libro de consultas está bloqueado por otro proceso")
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


def _libro_cargar(base_dir):
    try:
        d = json.loads((Path(base_dir) / LIBRO).read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("raices"), dict):
            return d
    except (OSError, ValueError):
        pass
    return {"version": 1, "raices": {}}


def _libro_guardar(base_dir, libro):
    path = Path(base_dir) / LIBRO
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(libro, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _raiz(libro, raiz):
    return libro["raices"].setdefault(
        raiz, {"gastado": 0, "hijas": {}, "abiertas": {}})


def _comprometido(reg_raiz):
    """Lo que la raíz ya no puede gastar: gasto real + reservas abiertas."""
    return reg_raiz.get("gastado", 0) + sum((reg_raiz.get("abiertas") or {}).values())


# ---------------------------------------------------------------- creación

def _cuenta(registro, cuenta_id):
    for c in registro.get("cuentas", []):
        if c.get("id") == cuenta_id:
            return c
    return None


def crear_consulta(registro, vista_d, origen, destino, pregunta, tarea_padre,
                   padre=None, presupuesto=None, motor="claude", base_dir=None,
                   reloj=None, ttl_s=TTL_DEF_S, max_saltos=MAX_SALTOS,
                   tope_presupuesto=TOPE_PRESUPUESTO, tope_raiz=TOPE_RAIZ,
                   max_hijas=MAX_HIJAS, cwd=None, archivos=None):
    """Construye el dict de la tarea consulta derivando saltos y raíz del
    padre (B4) y comprobando los topes de la cadena (B3, si hay base_dir).

    `padre`: el dict de la tarea que pregunta (o None si cuelga directo de
    `tarea_padre`, una tarea normal). Lanza ErrorConsulta con el motivo."""
    if origen == destino:
        raise ErrorConsulta("una cuenta no se consulta a sí misma")
    co = _cuenta(registro, origen)
    cd = _cuenta(registro, destino)
    if co is None:
        raise ErrorConsulta(f"la cuenta origen «{origen}» no existe en el registro")
    if cd is None:
        raise ErrorConsulta(f"la cuenta destino «{destino}» no existe en el registro")
    if not co.get("habilitada", True):
        raise ErrorConsulta(f"la cuenta origen «{origen}» está deshabilitada")
    if not cd.get("habilitada", True):
        raise ErrorConsulta(f"la cuenta destino «{destino}» está deshabilitada")
    if not cd.get("carril"):
        raise ErrorConsulta(f"la cuenta destino «{destino}» no tiene carril asignado")
    if not str(pregunta or "").strip():
        raise ErrorConsulta("la consulta no trae pregunta")
    if not str(tarea_padre or "").strip():
        raise ErrorConsulta("toda consulta cuelga de una tarea_padre (es por caso, no charla libre)")

    # Saltos y raíz derivados del padre (B4): el llamante no los declara.
    padre_consulta = (padre or {}).get("consulta") if isinstance(padre, dict) else None
    if padre_consulta:
        saltos = int(padre_consulta.get("saltos", 1)) + 1
        raiz = (padre or {}).get("raiz") or tarea_padre
    else:
        saltos = 1
        raiz = (padre or {}).get("raiz") or tarea_padre
    if saltos > max_saltos:
        raise ErrorConsulta(f"la consulta supera el máximo de {max_saltos} saltos")

    if presupuesto is None:
        presupuesto = PRESUPUESTO_DEF
    if (isinstance(presupuesto, bool) or not isinstance(presupuesto, (int, float))
            or presupuesto <= 0):
        raise ErrorConsulta(f"el presupuesto debe ser > 0, no {presupuesto!r}")
    if presupuesto > tope_presupuesto:
        raise ErrorConsulta(f"el presupuesto {presupuesto} supera el tope de {tope_presupuesto}")
    if padre_consulta:
        # La hija no puede prometer más de lo que le queda a su cadena.
        restante_padre = (padre_consulta.get("presupuesto", 0)
                          - padre_consulta.get("gastado", 0))
        if presupuesto > restante_padre:
            raise ErrorConsulta(
                f"el presupuesto {presupuesto} supera lo que le queda a la consulta "
                f"padre ({restante_padre})")

    estado = (vista_d.get(destino) or {}).get("estado", "activa")
    if estado in ("restringida", "cuarentena"):
        raise ErrorConsulta(
            f"la cuenta destino «{destino}» está {estado}: no se le consulta sin tokens")

    ahora = (reloj or time.time)()
    tid = f"consulta-{tarea_padre}-{saltos}-{uuid.uuid4().hex[:6]}"
    task = {
        "id": tid,
        "tipo": "consulta",
        "lane": cd["carril"],
        "motor": motor,
        "prompt": str(pregunta),
        "tarea_padre": tarea_padre,
        "raiz": raiz,
        "cuenta": destino,
        "expira_ts": ahora + ttl_s,
        "consulta": {
            "origen": origen,
            "destino": destino,
            "saltos": saltos,
            "presupuesto": presupuesto,
            "gastado": 0,
        },
    }
    if cwd:
        # La guardia del carril B exige cwd dentro de su carpeta y una
        # lista «archivos» no vacía dentro de ella (I7): sin esto, la
        # consulta sería rechazada al llegar. El archivo declarado es la
        # nota de respuesta de esta consulta en la carpeta del destino.
        task["cwd"] = str(cwd)
        if archivos is None:
            archivos = [str(Path(cwd) / "consultas" / f"{tid}.md")]
    if archivos:
        task["archivos"] = [str(a) for a in archivos]

    if base_dir is not None:
        # Topes de la cadena completa contra el libro (B3) y reserva.
        with _bloqueo_libro(base_dir):
            libro = _libro_cargar(base_dir)
            reg = _raiz(libro, raiz)
            hijas = (reg.get("hijas") or {}).get(tarea_padre, 0)
            if hijas >= max_hijas:
                raise ErrorConsulta(
                    f"la tarea «{tarea_padre}» ya lanzó {hijas} consultas "
                    f"(máximo {max_hijas})")
            if _comprometido(reg) + presupuesto > tope_raiz:
                raise ErrorConsulta(
                    f"la raíz «{raiz}» ya comprometió {_comprometido(reg)} de "
                    f"{tope_raiz}: no cabe un presupuesto de {presupuesto}")
            reg.setdefault("hijas", {})[tarea_padre] = hijas + 1
            reg.setdefault("abiertas", {})[tid] = presupuesto
            _libro_guardar(base_dir, libro)
    return task


def puede_tener_hijas(task, max_saltos=MAX_SALTOS):
    """True si de esta consulta puede nacer otra (no llegó al tope de saltos)."""
    c = task.get("consulta") or {}
    return int(c.get("saltos", 1)) < max_saltos


def caducada(task, ahora=None):
    """True si la consulta pasó su expira_ts esperando."""
    exp = task.get("expira_ts")
    if not isinstance(exp, (int, float)):
        return False
    return (time.time() if ahora is None else ahora) > exp


# ---------------------------------------------------------------- entrega

def _validar_task(task, registro=None, vista_d=None, max_saltos=MAX_SALTOS,
                  tope_presupuesto=TOPE_PRESUPUESTO):
    """Revalidación completa de una tarea consulta ya construida (I7)."""
    if not isinstance(task, dict) or task.get("tipo") != "consulta":
        raise ErrorConsulta("la tarea no es una consulta")
    c = task.get("consulta")
    if not isinstance(c, dict):
        raise ErrorConsulta("la consulta no trae su bloque «consulta»")
    origen, destino = c.get("origen"), c.get("destino")
    if not origen or not destino or origen == destino:
        raise ErrorConsulta("origen/destino de la consulta inválidos")
    saltos = c.get("saltos")
    if isinstance(saltos, bool) or not isinstance(saltos, int) or not (1 <= saltos <= max_saltos):
        raise ErrorConsulta(f"saltos fuera de rango: {saltos!r}")
    pres = c.get("presupuesto")
    if (isinstance(pres, bool) or not isinstance(pres, (int, float))
            or not (0 < pres <= tope_presupuesto)):
        raise ErrorConsulta(f"presupuesto fuera de rango: {pres!r}")
    gastado = c.get("gastado", 0)
    if not isinstance(gastado, (int, float)) or gastado < 0 or gastado > pres:
        raise ErrorConsulta(f"gastado fuera de rango: {gastado!r}")
    if not str(task.get("prompt") or "").strip():
        raise ErrorConsulta("la consulta no trae pregunta")
    if not str(task.get("tarea_padre") or "").strip():
        raise ErrorConsulta("la consulta no trae tarea_padre")
    if registro is not None:
        cd = _cuenta(registro, destino)
        if cd is None or not cd.get("habilitada", True):
            raise ErrorConsulta(f"la cuenta destino «{destino}» no existe o está deshabilitada")
        if task.get("lane") != cd.get("carril"):
            raise ErrorConsulta("el carril de la tarea no es el de la cuenta destino")
    if vista_d is not None:
        estado = (vista_d.get(destino) or {}).get("estado", "activa")
        if estado in ("restringida", "cuarentena"):
            raise ErrorConsulta(f"la cuenta destino «{destino}» está {estado}")


def entregar(task, dir_tareas, registro=None, vista_d=None):
    """Revalida y escribe el .task.json en el runner-tasks destino, atómico.

    El directorio debe existir (el carril destino está instalado): si no,
    ErrorConsulta — nada de crear rutas en silencio donde nadie mira."""
    _validar_task(task, registro=registro, vista_d=vista_d)
    d = Path(dir_tareas)
    if not d.is_dir():
        raise ErrorConsulta(f"el carril destino no está instalado: no existe {d}")
    destino = d / f"{task['id']}.task.json"
    tmp = d / f".{task['id']}.tmp"
    tmp.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, destino)
    return destino


# ---------------------------------------------------------------- gasto

def reservar_gasto(task, tracker, cantidad=1, base_dir=None, tope_raiz=TOPE_RAIZ):
    """Reserva gasto ANTES de ejecutar (B5): tracker + libro + el dict.

    Devuelve el nuevo `gastado` de la tarea, o None si ese gasto pasaría
    del presupuesto de la consulta o del tope de su raíz (no se anota
    nada). El llamador (el runner) persiste el dict en el archivo de la
    tarea: al recoger tras un corte se relee de ahí, no se resetea."""
    c = task.get("consulta") or {}
    presupuesto = c.get("presupuesto", 0)
    gastado = c.get("gastado", 0)
    if gastado + cantidad > presupuesto:
        return None
    raiz = task.get("raiz") or task.get("tarea_padre")
    if base_dir is not None:
        with _bloqueo_libro(base_dir):
            libro = _libro_cargar(base_dir)
            reg = _raiz(libro, raiz)
            if reg.get("gastado", 0) + cantidad > tope_raiz:
                return None
            tracker.registrar_uso(task.get("motor") or "claude", cantidad,
                                  cuenta=c.get("destino"))
            reg["gastado"] = reg.get("gastado", 0) + cantidad
            _libro_guardar(base_dir, libro)
    else:
        tracker.registrar_uso(task.get("motor") or "claude", cantidad,
                              cuenta=c.get("destino"))
    c["gastado"] = gastado + cantidad
    task["consulta"] = c
    return c["gastado"]


def cerrar_consulta(base_dir, task):
    """Libera la reserva abierta de la consulta en el libro (al terminar).

    Idempotente: cerrar dos veces no rompe nada."""
    if base_dir is None:
        return
    raiz = task.get("raiz") or task.get("tarea_padre")
    with _bloqueo_libro(base_dir):
        libro = _libro_cargar(base_dir)
        reg = libro["raices"].get(raiz)
        if reg and task.get("id") in (reg.get("abiertas") or {}):
            del reg["abiertas"][task["id"]]
            _libro_guardar(base_dir, libro)

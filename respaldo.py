# -*- coding: utf-8 -*-
"""Respaldo triple del estado (Growi Bridge, Fase 3).

El estado de Growi (tablero, cola, alquileres, propuestas, traspasos,
auditoría…) vive en tres patas (§7.2 del diseño):

1. **PC:** los archivos vivos + instantáneas con manifiesto en
   `respaldo/<ts>/` (rotación de 10) y una diaria protegida en
   `respaldo/diario/<fecha>/` (7 días).
2. **GitHub:** solo el código, por el flujo del §5/§6. Ningún archivo
   de estado va a GitHub: el hook de `secretos.py` los bloquea por
   nombre precisamente para que las patas no se mezclen.
3. **El espacio de cada Muse:** cada proceso copia la última
   instantánea a `respaldo-estado/` dentro de la carpeta de su carril.

Alcance honesto (corrección I11): las patas 1 y 3 comparten disco con
el estado vivo. Esto protege contra un carril corrupto, un borrado
accidental y una mala actualización, NO contra la muerte del disco;
para eso está `exportar(ruta)` (por CLI en esta fase).

Reglas (§7.1, corrección B14 e I10):
- Lista blanca CERRADA: el manifiesto solo admite los nombres de aquí;
  cualquier otro archivo de las carpetas origen se ignora, y la bóveda
  y los secretos quedan fuera por construcción.
- Los JSON se leen a través del `cargar` de su módulo dueño (con su
  lock), nunca copiando el archivo vivo a ciegas; `cola.db` se copia
  con la API de respaldo de SQLite y pasa `integrity_check` antes de
  entrar en el manifiesto.
- Antes de crear la instantánea, cada archivo se valida y se pasa por
  el escáner de secretos: un archivo inválido o con un secreto ABORTA
  la instantánea (no se respalda corrupción ni se multiplica un
  secreto por tres carpetas).
- Toda escritura es a carpeta temporal + renombrado: sin
  `manifiesto.json` completo, la instantánea no existe.
"""
import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import secretos

LISTA_COMPARTIDA = ("tablero.json", "consultas-uso.json", "alquileres.json",
                    "propuestas.json", "traspasos.json", "proyectos.json")
LISTA_CARRIL_JSON = ("accounts.json", "audit-indice.json", "settings.json")
ROTACION = 10
DIARIAS = 7
_RX_INSTANTANEA = re.compile(r"^\d{8}-\d{6}(-\d+)?$")

_LOCK_PROCESO = threading.RLock()


class ErrorRespaldo(Exception):
    """El respaldo no se pudo hacer o no verifica; el mensaje es el motivo."""


def _auditar(auditar, prompt, resultado, cuenta=None, accion=None):
    import git_trabajo
    return git_trabajo._auditar(auditar, "respaldo", prompt, resultado,
                                cuenta=cuenta, accion=accion)


@contextlib.contextmanager
def _bloqueo(base_dir):
    """Lock propio de respaldo (crear y rotar no se pisan entre procesos)."""
    with _LOCK_PROCESO:
        lock = Path(base_dir) / "respaldo.lock"
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
            raise ErrorRespaldo("el respaldo está bloqueado por otro proceso")
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


# ------------------------------------------------------------ recolección

def _leer_json_crudo(path):
    """El JSON crudo de un archivo de estado, o ErrorRespaldo si no vale."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ErrorRespaldo(f"{path.name} no es un JSON válido: {e}")


def _contenido_compartido(base_dir, nombre):
    """El contenido a respaldar de un archivo compartido, leído a través
    del `cargar` de su módulo dueño (§7.1). None si el archivo no existe."""
    path = Path(base_dir) / nombre
    if not path.is_file():
        return None
    _leer_json_crudo(path)  # valida ANTES de respaldar (I10)
    if nombre == "tablero.json":
        import tablero
        datos = tablero.cargar(base_dir)
    elif nombre == "consultas-uso.json":
        import consulta
        datos = consulta._libro_cargar(base_dir)
    elif nombre == "alquileres.json":
        import alquileres
        datos = alquileres.cargar(base_dir)
    elif nombre == "propuestas.json":
        import git_trabajo
        datos = git_trabajo.cargar_propuestas(base_dir)
    elif nombre == "traspasos.json":
        import traspaso
        datos = traspaso.cargar(base_dir)
    elif nombre == "proyectos.json":
        import git_trabajo
        datos = git_trabajo.cargar_proyectos(base_dir)
    else:  # pragma: no cover - la lista es cerrada
        datos = _leer_json_crudo(path)
    return json.dumps(datos, indent=2, ensure_ascii=False).encode("utf-8")


def _contenido_carril(carril_dir, nombre):
    """El contenido a respaldar de un archivo de un carril. None si no
    existe. `cola.db` va por la API de respaldo de SQLite (B14)."""
    path = Path(carril_dir) / nombre
    if nombre == "cola.db":
        if not path.is_file():
            return None
        return _copia_sqlite(path)
    if not path.is_file():
        return None
    if nombre == "accounts.json":
        _leer_json_crudo(path)
        import cuentas
        datos = cuentas.cargar(carril_dir)
        if datos.get("compatibilidad"):
            raise ErrorRespaldo("accounts.json existe pero no es válido: "
                                "no se respalda un registro roto")
        return json.dumps(datos, indent=2, ensure_ascii=False).encode("utf-8")
    if nombre in ("audit-indice.json", "settings.json"):
        _leer_json_crudo(path)
        return path.read_bytes()
    return path.read_bytes()  # audit-log*.json: append-only, copia directa


def _copia_sqlite(path):
    """Copia coherente de una base viva (WAL aplicado) + integrity_check."""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            dst = sqlite3.connect(tmp)
            try:
                src.backup(dst)
                ok = dst.execute("PRAGMA integrity_check").fetchone()
                if not ok or ok[0] != "ok":
                    raise ErrorRespaldo(f"la copia de {path.name} no pasa "
                                         f"integrity_check: {ok}")
            finally:
                dst.close()
        finally:
            src.close()
        return Path(tmp).read_bytes()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _recolectar(base_dir, carriles):
    """{ruta_relativa: bytes} de todo el estado de la lista blanca,
    validado y escaneado. Aborta (ErrorRespaldo) ante cualquier problema."""
    entradas = {}
    for nombre in LISTA_COMPARTIDA:
        datos = _contenido_compartido(base_dir, nombre)
        if datos is not None:
            entradas[f"compartida/{nombre}"] = datos
    for carril, carpeta in (carriles or {}).items():
        carpeta = Path(carpeta)
        if not carpeta.is_dir():
            continue
        for nombre in LISTA_CARRIL_JSON:
            datos = _contenido_carril(carpeta, nombre)
            if datos is not None:
                entradas[f"{carril}/{nombre}"] = datos
        for p in sorted(carpeta.glob("audit-log*.json")):
            entradas[f"{carril}/{p.name}"] = _contenido_carril(carpeta, p.name)
        datos = _contenido_carril(carpeta, "cola.db")
        if datos is not None:
            entradas[f"{carril}/cola.db"] = datos
    # Escaneo de secretos de todo lo textual (I10): un secreto plantado
    # aborta la instantánea, no se multiplica por tres carpetas.
    for rel, datos in entradas.items():
        if rel.endswith(".db"):
            continue
        texto = datos.decode("utf-8", "replace")
        hall = secretos.escanear_texto(texto, ruta=rel)
        if hall:
            raise ErrorRespaldo(
                f"{rel} contiene un posible secreto ({hall[0]['tipo']}): "
                "instantánea abortada")
    return entradas


# ------------------------------------------------------------ instantáneas

def _dir_respaldo(base_dir):
    return Path(base_dir) / "respaldo"


def instantaneas(base_dir):
    """Las instantáneas rotativas existentes, de más nueva a más vieja."""
    d = _dir_respaldo(base_dir)
    if not d.is_dir():
        return []
    out = [p for p in d.iterdir()
           if p.is_dir() and _RX_INSTANTANEA.match(p.name)
           and (p / "manifiesto.json").is_file()]
    return sorted(out, key=lambda p: p.name, reverse=True)


def ultima_instantanea(base_dir):
    lista = instantaneas(base_dir)
    return lista[0] if lista else None


def _manifiesto_de(entradas, ahora):
    return {"ts": datetime.fromtimestamp(ahora).strftime("%Y%m%d-%H%M%S"),
            "creada_ts": ahora,
            "archivos": {rel: {"sha256": hashlib.sha256(d).hexdigest(),
                               "bytes": len(d)}
                         for rel, d in sorted(entradas.items())}}


def crear_instantanea(base_dir, carriles=None, reloj=None, auditar=None,
                      forzar=False, cuenta=None):
    """Crea una instantánea verificada del estado (§7.2 pata 1).

    Sin cambios respecto a la última (mismos hashes), no crea otra.
    Devuelve {"creada": bool, "carpeta": Path|None, "archivos": n}."""
    ahora = (reloj or time.time)()
    base_dir = Path(base_dir)
    with _bloqueo(base_dir):
        entradas = _recolectar(base_dir, carriles)
        manifiesto = _manifiesto_de(entradas, ahora)
        ultima = ultima_instantanea(base_dir)
        if not forzar and ultima is not None:
            try:
                anterior = json.loads(
                    (ultima / "manifiesto.json").read_text(encoding="utf-8"))
                if anterior.get("archivos") == manifiesto["archivos"]:
                    return {"creada": False, "carpeta": ultima,
                            "archivos": len(entradas),
                            "motivo": "sin cambios desde la última instantánea"}
            except (OSError, ValueError):
                pass
        raiz = _dir_respaldo(base_dir)
        raiz.mkdir(parents=True, exist_ok=True)
        nombre = manifiesto["ts"]
        destino = raiz / nombre
        n = 2
        while destino.exists():
            destino = raiz / f"{nombre}-{n}"
            n += 1
        tmp = raiz / f".tmp-{nombre}-{os.getpid()}"
        if tmp.exists():
            shutil.rmtree(tmp)
        try:
            for rel, datos in entradas.items():
                f = tmp / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(datos)
            (tmp / "manifiesto.json").write_text(
                json.dumps(manifiesto, indent=2, ensure_ascii=False),
                encoding="utf-8")
            os.replace(tmp, destino)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        _rotar(base_dir)
        _diaria(base_dir, destino, ahora)
    _auditar(auditar, f"instantánea {destino.name} creada "
             f"({len(entradas)} archivos)", "ok", cuenta=cuenta,
             accion="respaldo_instantanea")
    return {"creada": True, "carpeta": destino, "archivos": len(entradas)}


def _rotar(base_dir):
    for vieja in instantaneas(base_dir)[ROTACION:]:
        shutil.rmtree(vieja, ignore_errors=True)


def _diaria(base_dir, carpeta, ahora):
    """Una instantánea diaria FUERA de la rotación (I10): con un
    disparador horario, 10 rotativas se agotan en pocas horas y una
    corrupción tardía se quedaría sin ninguna copia buena."""
    fecha = datetime.fromtimestamp(ahora).strftime("%Y-%m-%d")
    raiz = _dir_respaldo(base_dir) / "diario"
    destino = raiz / fecha
    if destino.exists():
        return
    raiz.mkdir(parents=True, exist_ok=True)
    tmp = raiz / f".tmp-{fecha}-{os.getpid()}"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(carpeta, tmp)
    os.replace(tmp, destino)
    dias = sorted((p for p in raiz.iterdir() if p.is_dir()
                   and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)),
                  key=lambda p: p.name, reverse=True)
    for vieja in dias[DIARIAS:]:
        shutil.rmtree(vieja, ignore_errors=True)


# ------------------------------------------------------- verificar/restaurar

def verificar(carpeta):
    """Comprueba el manifiesto contra los hashes reales (§7.4)."""
    carpeta = Path(carpeta)
    try:
        manifiesto = json.loads(
            (carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"ok": False, "danados": [], "ausentes": ["manifiesto.json"],
                "extranos": [], "motivo": f"manifiesto ilegible: {e}"}
    danados, ausentes = [], []
    for rel, meta in (manifiesto.get("archivos") or {}).items():
        f = carpeta / rel
        if not f.is_file():
            ausentes.append(rel)
        elif hashlib.sha256(f.read_bytes()).hexdigest() != meta.get("sha256"):
            danados.append(rel)
    conocidos = set((manifiesto.get("archivos") or {})) | {"manifiesto.json",
                                                           "RESTAURADO.md"}
    extranos = [str(p.relative_to(carpeta)) for p in carpeta.rglob("*")
                if p.is_file() and str(p.relative_to(carpeta)) not in conocidos]
    return {"ok": not danados and not ausentes, "danados": danados,
            "ausentes": ausentes, "extranos": extranos}


def restaurar(carpeta_origen, dir_destino, reloj=None, auditar=None,
              cuenta=None):
    """Restaura una instantánea en un directorio DESTINO distinto del
    vivo (§7.4): copia, verifica y SANEА — todo marcador de traspaso no
    terminal pasa a `requiere_dueno` en la copia (un marcador viejo
    resucitado no puede reofrecer tareas ya resueltas, I10)."""
    origen, destino = Path(carpeta_origen), Path(dir_destino)
    v = verificar(origen)
    if not v["ok"]:
        raise ErrorRespaldo(f"la instantánea no verifica: "
                            f"dañados={v['danados']} ausentes={v['ausentes']}")
    if destino.exists() and any(destino.iterdir()):
        raise ErrorRespaldo(f"el destino {destino} no está vacío: no se pisa")
    destino.mkdir(parents=True, exist_ok=True)
    for p in origen.rglob("*"):
        if p.is_file():
            f = destino / p.relative_to(origen)
            f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, f)
    saneados = 0
    trasp = destino / "compartida" / "traspasos.json"
    if trasp.is_file():
        import traspaso
        try:
            d = json.loads(trasp.read_text(encoding="utf-8"))
            for m in (d.get("traspasos") or {}).values():
                if isinstance(m, dict) and m.get("estado") in traspaso.ESTADOS_QUE_RETENEN:
                    if m["estado"] != "requiere_dueno":
                        m["estado"] = "requiere_dueno"
                        saneados += 1
            trasp.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        except ValueError:
            pass
    ahora = (reloj or time.time)()
    (destino / "RESTAURADO.md").write_text(
        "# Estado restaurado\n\n"
        f"- De: `{origen}`\n"
        f"- Cuándo: {datetime.fromtimestamp(ahora).isoformat(timespec='seconds')}\n"
        f"- Marcadores de traspaso saneados a «requiere_dueno»: {saneados}\n\n"
        "Notas:\n"
        "- Los `audit-log` restaurados pueden quedar por detrás del ancla "
        "`audit-indice.json` del estado vivo: la verificación de ancla lo "
        "señalará, y esa discrepancia es en sí misma el registro del "
        "incidente.\n"
        "- Pasar esta copia a producción es un acto manual con la app "
        "cerrada: copia `compartida/` a la carpeta por usuario y cada "
        "`<carril>/` a la carpeta de su copia del programa.\n",
        encoding="utf-8")
    v2 = verificar(destino)
    _auditar(auditar, f"restauración desde {origen.name} en {destino} "
             f"({saneados} marcador(es) saneados)", "ok" if v2["ok"] else "error",
             cuenta=cuenta, accion="respaldo_restaurar")
    return {"carpeta": destino, "traspasos_saneados": saneados,
            "verificacion": v2}


# ------------------------------------------------------------ pata 3 y export

def copiar_a_espacio(base_dir, dir_espacio, reloj=None, auditar=None,
                     cuenta=None):
    """Copia la última instantánea al espacio de una Muse (pata 3):
    `<dir_espacio>/respaldo-estado/`. Si ya tiene esa misma, no hace nada."""
    ultima = ultima_instantanea(base_dir)
    if ultima is None:
        return {"actualizada": False, "motivo": "no hay instantáneas"}
    destino = Path(dir_espacio) / "respaldo-estado"
    try:
        if (destino / "manifiesto.json").read_bytes() == \
                (ultima / "manifiesto.json").read_bytes():
            return {"actualizada": False, "carpeta": destino,
                    "motivo": "la copia del espacio ya es la última"}
    except OSError:
        pass
    Path(dir_espacio).mkdir(parents=True, exist_ok=True)
    tmp = Path(dir_espacio) / f".respaldo-tmp-{os.getpid()}"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(ultima, tmp)
    viejo = Path(dir_espacio) / f".respaldo-viejo-{os.getpid()}"
    if viejo.exists():
        shutil.rmtree(viejo)
    if destino.exists():
        os.replace(destino, viejo)
    os.replace(tmp, destino)
    shutil.rmtree(viejo, ignore_errors=True)
    _auditar(auditar, f"copia del espacio actualizada con {ultima.name}",
             "ok", cuenta=cuenta, accion="respaldo_copia_espacio")
    return {"actualizada": True, "carpeta": destino}


def exportar(base_dir, ruta, reloj=None, auditar=None, cuenta=None):
    """Copia verificada de la última instantánea fuera del disco (§7.2,
    la pata opcional de la corrección I11)."""
    ultima = ultima_instantanea(base_dir)
    if ultima is None:
        raise ErrorRespaldo("no hay instantáneas que exportar")
    destino = Path(ruta)
    if destino.is_dir() and (destino / "manifiesto.json").is_file():
        destino = destino / ultima.name
    elif destino.exists() and not (destino / "manifiesto.json").is_file() \
            and any(destino.iterdir()):
        destino = destino / ultima.name
    if destino.exists():
        shutil.rmtree(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ultima, destino)
    v = verificar(destino)
    if not v["ok"]:
        raise ErrorRespaldo(f"la exportación no verifica: {v}")
    _auditar(auditar, f"instantánea {ultima.name} exportada a {destino}",
             "ok", cuenta=cuenta, accion="respaldo_exportar")
    return {"carpeta": destino, "verificacion": v}

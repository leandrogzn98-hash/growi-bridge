# -*- coding: utf-8 -*-
"""Trabajo en GitHub con aislamiento (Growi Bridge, Fase 3).

Cada cuenta Muse trabaja en SU worktree sobre SU rama
(`muse/<cuenta>/<tarea>`); la rama es el punto de encuentro — propuesta,
revisión, aprobación del dueño y mezcla — nunca el directorio (§3 y §5
del diseño). Este módulo lleva:

- el registro de proyectos (`proyectos.json`, en la carpeta compartida),
- los worktrees y las ramas (crear, reusar, reanudar, liberar, limpiar),
- las propuestas de mezcla (`propuestas.json`) con su flujo completo:
  proponer -> revisar (veredicto firmado sobre un sha) -> aprobación
  humana por el circuito HMAC de `permission-layer.py` -> mezcla en
  HEAD separado (la `main` local del dueño no se toca jamás),
- `subir`: la única puerta de push de Growi, con el escaneo de objetos
  de `secretos.py` sobre el sha exacto que se sube (§6.2),
- la instalación del hook `pre-push` (capa B del §6.3) sin pisar jamás
  un hook ajeno,
- el entorno git sin credenciales para las tareas (§6.2 paso 0).

Git se invoca por un ejecutor inyectable `correr_git(args, cwd,
timeout=..., entrada=...) -> (rc, stdout, stderr)`; por defecto, el real
(subprocess sin shell, `GIT_TERMINAL_PROMPT=0`, timeouts de 120 s en
local y 300 s en red, corrección I6). Las pruebas inyectan un git falso
o usan repos temporales reales.
"""
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import alquileres
import secretos

ARCHIVO_PROYECTOS = "proyectos.json"
ARCHIVO_PROPUESTAS = "propuestas.json"
VERSION = 1
TIMEOUT_LOCAL_S = 120
TIMEOUT_RED_S = 300
LIMPIEZA_DIAS_DEF = 7

_LOCK_PROCESO = threading.RLock()
_PL = [None]  # permission-layer cargado perezosamente


class ErrorGit(Exception):
    """Fallo de git o de las reglas de la Fase 3; el mensaje es el motivo."""


# ------------------------------------------------------------- ejecutor git

def _matar_proceso(p):
    try:
        if os.name == "nt":
            p.kill()
        else:
            import signal
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def correr_git_real(args, cwd=None, timeout=TIMEOUT_LOCAL_S, entrada=None,
                    env_extra=None):
    """Ejecutor git real: (rc, stdout, stderr) en texto, sin shell."""
    if shutil.which("git") is None:
        raise ErrorGit("git no está en el PATH")
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if env_extra:
        env.update({str(k): str(v) for k, v in env_extra.items()})
    kwargs = {}
    if os.name != "nt":
        kwargs["start_new_session"] = True  # grupo propio: matar el árbol
    try:
        p = subprocess.Popen(["git", *[str(a) for a in args]],
                             cwd=str(cwd) if cwd else None, env=env,
                             stdin=subprocess.PIPE if entrada is not None
                             else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             **kwargs)
    except FileNotFoundError:
        raise ErrorGit("git no está en el PATH")
    try:
        out, err = p.communicate(input=entrada, timeout=timeout)
    except subprocess.TimeoutExpired:
        _matar_proceso(p)
        try:
            p.communicate(timeout=5)
        except Exception:
            pass
        raise ErrorGit(f"git {' '.join(str(a) for a in args[:2])} "
                       f"tardó más de {timeout} s y se mató")
    return (p.returncode,
            out.decode("utf-8", "replace"),
            err.decode("utf-8", "replace"))


def _git(args, cwd, correr=None, timeout=TIMEOUT_LOCAL_S, entrada=None,
         env_extra=None):
    correr = correr or correr_git_real
    return correr(args, cwd=cwd, timeout=timeout, entrada=entrada,
                  env_extra=env_extra)


def _git_ok(args, cwd, correr=None, **kw):
    """Como _git pero exige rc == 0: si no, ErrorGit con el motivo."""
    rc, out, err = _git(args, cwd, correr=correr, **kw)
    if rc != 0:
        raise ErrorGit(f"git {' '.join(str(a) for a in args[:3])} falló: "
                       f"{err.strip()[:240] or out.strip()[:240]}")
    return out


# ------------------------------------------------- auditoría (permission-layer)

def _cargar_permission_layer():
    if _PL[0] is None:
        ruta = Path(__file__).with_name("permission-layer.py")
        spec = importlib.util.spec_from_file_location("permission_layer", str(ruta))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _PL[0] = mod
    return _PL[0]


def _auditar(auditar, tool, prompt, resultado, cuenta=None, accion=None):
    """Registra en la auditoría por cuenta (principio 6). Con `auditar`
    inyectado se usa ese; si no, el `registrar` de permission-layer.py.
    Un fallo de auditoría no tumba la operación llamante, pero se anota
    en el resultado devuelto por quien llama cuando es crítico."""
    try:
        if auditar is not None:
            auditar(tool=tool, prompt=prompt, resultado=resultado,
                    cuenta=cuenta, accion=accion)
            return True
        pl = _cargar_permission_layer()
        pl.registrar(tool, prompt, resultado, accion=accion, cuenta=cuenta)
        return True
    except Exception:
        return False


# ------------------------------------------- entorno sin credenciales (§6.2)

ENV_GIT_SIN_CREDENCIALES = {
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "credential.helper",
    "GIT_CONFIG_VALUE_0": "",
    "GIT_TERMINAL_PROMPT": "0",
}
VARS_GIT_A_QUITAR = ("SSH_AUTH_SOCK", "GH_TOKEN")


def aplicar_entorno_sin_credenciales(env):
    """Copia del entorno de una tarea SIN credenciales de escritura git:
    la Muse puede hacer todo el git local que quiera, pero no puede
    autenticar un push propio; su único camino de subida es `subir`."""
    out = dict(env)
    for v in VARS_GIT_A_QUITAR:
        out.pop(v, None)
    out.update(ENV_GIT_SIN_CREDENCIALES)
    return out


# ------------------------------------------------- patrón lock + JSON (Fase 2)

@contextlib.contextmanager
def _bloqueo(base_dir, archivo):
    """Mutex en proceso + lock de archivo para UN archivo concreto."""
    with _LOCK_PROCESO:
        lock = Path(base_dir) / (archivo + ".lock")
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
            raise ErrorGit(f"{archivo} está bloqueado por otro proceso")
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass


def _cargar_json(base_dir, archivo, clave_dict):
    try:
        d = json.loads((Path(base_dir) / archivo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": VERSION, "revision": 0, clave_dict: {}}
    if not isinstance(d, dict) or not isinstance(d.get(clave_dict), dict):
        return {"version": VERSION, "revision": 0, clave_dict: {}}
    rev = d.get("revision", 0)
    return {"version": VERSION,
            "revision": rev if isinstance(rev, int) and not isinstance(rev, bool) else 0,
            clave_dict: {k: v for k, v in d[clave_dict].items() if isinstance(v, dict)}}


def _guardar_json(base_dir, archivo, d):
    d["revision"] = int(d.get("revision", 0)) + 1
    path = Path(base_dir) / archivo
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- proyectos

def _canon(ruta):
    return os.path.normcase(str(Path(ruta).resolve()))


def repo_id_de(ruta, correr=None):
    """El id del proyecto (§2): 16 hex del SHA-256 de la ruta canónica de
    la RAÍZ del repo (el cwd de una tarea puede ser una subcarpeta)."""
    raiz = raiz_repo(ruta, correr=correr)
    if raiz is None:
        raise ErrorGit(f"no es un repositorio git: {ruta}")
    return hashlib.sha256(_canon(raiz).encode("utf-8")).hexdigest()[:16]


def es_repo(ruta, correr=None):
    try:
        rc, out, _ = _git(["rev-parse", "--is-inside-work-tree"], cwd=ruta,
                          correr=correr)
        return rc == 0 and out.strip() == "true"
    except ErrorGit:
        return False


def raiz_repo(ruta, correr=None):
    """La raíz del repo que contiene `ruta`, o None si no está en uno."""
    try:
        rc, out, _ = _git(["rev-parse", "--show-toplevel"], cwd=ruta,
                          correr=correr)
    except ErrorGit:
        return None
    if rc != 0 or not out.strip():
        return None
    return Path(out.strip())


def cargar_proyectos(base_dir):
    return _cargar_json(base_dir, ARCHIVO_PROYECTOS, "proyectos")


def proyecto(base_dir, repo_id):
    return cargar_proyectos(base_dir)["proyectos"].get(repo_id)


def proyectos(base_dir):
    return cargar_proyectos(base_dir)["proyectos"]


def _ramas_muse_sueltas(repo, correr=None):
    """Ramas `muse/<algo>` SIN segundo nivel: bloquearían las referencias
    `muse/<cuenta>/<tarea>` (corrección I13). Solo se detectan: renombrar
    es cosa del dueño."""
    rc, out, _ = _git(["for-each-ref", "--format=%(refname:short)",
                       "refs/heads/muse/"], cwd=repo, correr=correr)
    if rc != 0:
        return []
    return [l.strip() for l in out.splitlines()
            if l.strip() and "/" not in l.strip()[len("muse/"):]]


def registrar_proyecto(base_dir, ruta, correr=None, reloj=None):
    """Registra el repo (idempotente) y deja instalada la capa B (§6.3).

    No modifica el repo salvo el hook y, en Windows, `core.longpaths`.
    Devuelve la entrada del registro."""
    raiz = raiz_repo(ruta, correr=correr)
    if raiz is None:
        raise ErrorGit(f"no es un repositorio git: {ruta}")
    rid = hashlib.sha256(_canon(raiz).encode("utf-8")).hexdigest()[:16]
    rc, out, _ = _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                      cwd=raiz, correr=correr)
    rama_base = out.strip().split("/", 1)[-1] if rc == 0 and out.strip() else "main"
    rc, out, _ = _git(["config", "--get", "core.ignorecase"], cwd=raiz,
                      correr=correr)
    ignorecase = rc == 0 and out.strip().lower() == "true"
    if os.name == "nt":
        _git(["config", "core.longpaths", "true"], cwd=raiz, correr=correr)
    sueltas = _ramas_muse_sueltas(raiz, correr=correr)
    with _bloqueo(base_dir, ARCHIVO_PROYECTOS):
        d = cargar_proyectos(base_dir)
        e = d["proyectos"].get(rid)
        if e is None:
            e = {"repo_id": rid, "ruta": str(raiz), "nombre": raiz.name,
                 "rama_base": rama_base, "mezcladora": None,
                 "contenedores": "proyecto", "limpieza_dias": LIMPIEZA_DIAS_DEF,
                 "ignorecase": ignorecase, "hook": None,
                 "ramas_muse_sueltas": sueltas,
                 "creado": datetime.now().astimezone().isoformat(timespec="seconds")}
            d["proyectos"][rid] = e
        else:
            e["ruta"] = str(raiz)
            e["ramas_muse_sueltas"] = sueltas
        _guardar_json(base_dir, ARCHIVO_PROYECTOS, d)
    if e.get("hook") != "instalado":
        res = instalar_hook(base_dir, raiz, correr=correr)
        with _bloqueo(base_dir, ARCHIVO_PROYECTOS):
            d = cargar_proyectos(base_dir)
            if rid in d["proyectos"]:
                d["proyectos"][rid]["hook"] = res["estado"]
                d["proyectos"][rid]["hook_motivo"] = res.get("motivo")
                _guardar_json(base_dir, ARCHIVO_PROYECTOS, d)
                e = d["proyectos"][rid]
    return e


def guardar_proyecto(base_dir, repo_id, **cambios):
    """Ajustes del dueño sobre un proyecto (mezcladora, contenedores…)."""
    permitidos = {"mezcladora", "contenedores", "limpieza_dias", "rama_base"}
    for k in cambios:
        if k not in permitidos:
            raise ErrorGit(f"ajuste de proyecto desconocido: {k}")
    if "contenedores" in cambios and cambios["contenedores"] not in ("proyecto", "por_cuenta"):
        raise ErrorGit("contenedores debe ser «proyecto» o «por_cuenta»")
    with _bloqueo(base_dir, ARCHIVO_PROYECTOS):
        d = cargar_proyectos(base_dir)
        e = d["proyectos"].get(repo_id)
        if e is None:
            raise ErrorGit(f"proyecto no registrado: {repo_id}")
        e.update(cambios)
        _guardar_json(base_dir, ARCHIVO_PROYECTOS, d)
        return e


# ---------------------------------------------------------------- worktrees

def sanear_tarea(tarea):
    """El trozo de rama/ruta de una tarea: minúsculas, [a-z0-9-]{1,48}."""
    s = re.sub(r"[^a-z0-9-]+", "-", str(tarea or "").lower())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:48] or "tarea"


def nombre_rama(cuenta, tarea):
    return f"muse/{cuenta}/{sanear_tarea(tarea)}"


def _norm_ruta(p):
    return os.path.normcase(str(Path(p).resolve()))


def ruta_worktree(repo, cuenta, tarea, base_dir=None, correr=None):
    """Dónde vive el worktree de (cuenta, tarea): HERMANO del repo,
    `<repo>.worktrees/<cuenta>/<tarea>/`. Si el padre no es escribible o
    está dentro de otro repo, plan B en la carpeta compartida (I13)."""
    raiz = Path(repo).resolve()
    hermano = raiz.parent / (raiz.name + ".worktrees") / cuenta / sanear_tarea(tarea)
    plan_b = False
    if not os.access(raiz.parent, os.W_OK):
        plan_b = True
    else:
        otro = raiz_repo(raiz.parent, correr=correr)
        if otro is not None and _norm_ruta(otro) != _norm_ruta(raiz):
            plan_b = True  # el padre vive dentro de OTRO repo
    if plan_b:
        if base_dir is None:
            raise ErrorGit("el worktree no cabe junto al repo y no hay "
                           "carpeta compartida para el plan B")
        rid = hashlib.sha256(_canon(raiz).encode("utf-8")).hexdigest()[:16]
        return Path(base_dir) / "worktrees" / rid / cuenta / sanear_tarea(tarea)
    return hermano


def _worktrees(repo, correr=None):
    """[{ruta, rama|None, head}] según `git worktree list --porcelain`."""
    out = _git_ok(["worktree", "list", "--porcelain"], cwd=repo, correr=correr)
    lista, actual = [], None
    for linea in out.splitlines() + [""]:
        if linea.startswith("worktree "):
            if actual:
                lista.append(actual)
            actual = {"ruta": linea[len("worktree "):].strip(), "rama": None,
                      "head": None}
        elif actual is not None and linea.startswith("HEAD "):
            actual["head"] = linea[len("HEAD "):].strip()
        elif actual is not None and linea.startswith("branch "):
            ref = linea[len("branch "):].strip()
            actual["rama"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif linea == "" and actual:
            lista.append(actual)
            actual = None
    return lista


def _rama_existe(repo, rama, correr=None):
    rc, _, _ = _git(["show-ref", "--verify", "--quiet", f"refs/heads/{rama}"],
                    cwd=repo, correr=correr)
    return rc == 0


def _sha_de(repo, ref, correr=None):
    rc, out, _ = _git(["rev-parse", "--verify", "--quiet", ref], cwd=repo,
                      correr=correr)
    return out.strip() if rc == 0 else None


def preparar_worktree(base_dir, repo, cuenta, tarea, rama_base, rama=None,
                      correr=None):
    """Deja listo el worktree de (cuenta, tarea) y devuelve su ruta (§3.2).

    La rama es `muse/<cuenta>/<tarea>` por convención; con `rama`
    explícita manda la continuidad (traspaso, propuesta: corrección B6)."""
    raiz = raiz_repo(repo, correr=correr)
    if raiz is None:
        raise ErrorGit(f"no es un repositorio git: {repo}")
    rama = rama or nombre_rama(cuenta, tarea)
    dest = ruta_worktree(raiz, cuenta, tarea, base_dir=base_dir, correr=correr)
    _git(["worktree", "prune"], cwd=raiz, correr=correr)  # I6: antes de diagnosticar
    for wt in _worktrees(raiz, correr=correr):
        if wt.get("rama") == rama:
            if _norm_ruta(wt["ruta"]) == _norm_ruta(dest):
                return Path(wt["ruta"])  # reintento: se reusa tal cual
            raise ErrorGit(
                f"la rama {rama} está ocupada por el worktree {wt['ruta']}; "
                "probablemente un traspaso a medias (lo resuelve el barrido)")
        if _norm_ruta(wt["ruta"]) == _norm_ruta(dest):
            raise ErrorGit(f"el worktree {dest} ya existe con otra rama "
                           f"({wt.get('rama')})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _rama_existe(raiz, rama, correr=correr):
        _git_ok(["worktree", "add", str(dest), rama], cwd=raiz, correr=correr)
    else:
        _git_ok(["worktree", "add", "-b", rama, str(dest), rama_base],
                cwd=raiz, correr=correr)
    return dest


def estado_worktree(ruta, correr=None):
    """{sucio, archivos, rama} de un worktree (rama None si HEAD separado)."""
    rc, out, _ = _git(["status", "--porcelain"], cwd=ruta, correr=correr)
    if rc != 0:
        raise ErrorGit(f"no se pudo leer el estado de {ruta}")
    archivos = [l[3:] for l in out.splitlines() if len(l) > 3]
    rc, out, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=ruta,
                      correr=correr)
    rama = out.strip() if rc == 0 and out.strip() != "HEAD" else None
    return {"sucio": bool(archivos), "archivos": archivos, "rama": rama}


def liberar_worktree(repo, cuenta, tarea, forzar=False, base_dir=None,
                     correr=None):
    """Quita el worktree del registro de git. Con cambios sin confirmar y
    sin `forzar` -> ErrorGit: nunca se pierde trabajo en silencio. La
    rama NO se borra (es el historial de la propuesta)."""
    raiz = raiz_repo(repo, correr=correr)
    if raiz is None:
        raise ErrorGit(f"no es un repositorio git: {repo}")
    dest = ruta_worktree(raiz, cuenta, tarea, base_dir=base_dir, correr=correr)
    ocupados = {_norm_ruta(w["ruta"]) for w in _worktrees(raiz, correr=correr)}
    if _norm_ruta(dest) not in ocupados:
        return False  # no hay worktree que liberar
    if not forzar and estado_worktree(dest, correr=correr)["sucio"]:
        raise ErrorGit(f"el worktree {dest} tiene cambios sin confirmar; "
                       "no se libera sin forzar")
    args = ["worktree", "remove"] + (["--force"] if forzar else []) + [str(dest)]
    _git_ok(args, cwd=raiz, correr=correr)
    _git(["worktree", "prune"], cwd=raiz, correr=correr)
    return True


def ruta_worktree_mezcla(repo, cuenta):
    raiz = Path(repo).resolve()
    return raiz.parent / (raiz.name + ".worktrees") / f"_mezcla-{cuenta}"


# ---------------------------------------------------------------- propuestas

def cargar_propuestas(base_dir):
    return _cargar_json(base_dir, ARCHIVO_PROPUESTAS, "propuestas")


def id_propuesta(repo_id, rama):
    return hashlib.sha256(f"{repo_id}|{rama}".encode("utf-8")).hexdigest()[:16]


def obtener_propuesta(base_dir, pid):
    return cargar_propuestas(base_dir)["propuestas"].get(pid)


def propuestas(base_dir, repo=None):
    d = cargar_propuestas(base_dir)["propuestas"]
    return [p for p in d.values() if repo is None or p.get("repo") == repo]


def _propuesta_guardar(base_dir, prop, reloj=None):
    ahora = (reloj or time.time)()
    prop["actualizada_ts"] = ahora
    with _bloqueo(base_dir, ARCHIVO_PROPUESTAS):
        d = cargar_propuestas(base_dir)
        d["propuestas"][prop["id"]] = prop
        _guardar_json(base_dir, ARCHIVO_PROPUESTAS, d)
    return prop


def crear_propuesta(base_dir, repo_id, rama, cuenta, tarea, base, sha_base,
                    sha_rama, reloj=None, auditar=None):
    """Registra la propuesta de una rama ya subida (§5.1 paso 1).

    Una propuesta por (repo, rama): si ya existe, se ACTUALIZA (la
    proponente corrigió y vuelve a proponer), no se duplica. Una rama
    sin commits propios no propone nada (corrección I7)."""
    if not sha_rama or sha_rama == sha_base:
        raise ErrorGit("propuesta vacía: la rama no tiene commits propios")
    ahora = (reloj or time.time)()
    pid = id_propuesta(repo_id, rama)
    with _bloqueo(base_dir, ARCHIVO_PROPUESTAS):
        d = cargar_propuestas(base_dir)
        p = d["propuestas"].get(pid)
        if p is None:
            p = {"id": pid, "repo": repo_id, "rama": rama, "cuenta": cuenta,
                 "tarea": tarea, "base": base, "creada_ts": ahora,
                 "estado": "propuesta", "sha_base": sha_base}
            d["propuestas"][pid] = p
        p.update({"cuenta": cuenta, "tarea": tarea, "base": base,
                  "estado": "propuesta", "sha_base": sha_base,
                  "sha_rama": sha_rama, "revisora": None, "veredicto": None,
                  "sha_revisado": None, "confirmacion_id": None,
                  "aprobada": False, "sha_resultado": None,
                  "conflictos": None, "ultimo_error": None,
                  "actualizada_ts": ahora})
        _guardar_json(base_dir, ARCHIVO_PROPUESTAS, d)
    _auditar(auditar, "git", f"propuesta {pid}: {rama} sobre {base} ({tarea})",
             "ok", cuenta=cuenta, accion="propuesta_creada")
    return p


def registrar_veredicto(base_dir, pid, revisora, veredicto, sha_revisado,
                        comentarios=None, reloj=None, auditar=None):
    """El veredicto de la revisora, firmado sobre UN sha (corrección B8)."""
    if veredicto not in ("ok", "cambios", "rechazo"):
        raise ErrorGit(f"veredicto inválido: {veredicto!r}")
    p = obtener_propuesta(base_dir, pid)
    if p is None:
        raise ErrorGit(f"propuesta inexistente: {pid}")
    p["revisora"] = revisora
    p["veredicto"] = veredicto
    p["sha_revisado"] = sha_revisado
    if comentarios:
        p["comentarios"] = str(comentarios)[:2000]
    if veredicto == "ok":
        p["estado"] = "esperando_dueno"
        _propuesta_guardar(base_dir, p, reloj=reloj)
        pedir_aprobacion(base_dir, pid, auditar=auditar)
    elif veredicto == "cambios":
        p["estado"] = "cambios_pedidos"
        _propuesta_guardar(base_dir, p, reloj=reloj)
    else:
        p["estado"] = "rechazada"
        _propuesta_guardar(base_dir, p, reloj=reloj)
    _auditar(auditar, "git", f"veredicto {veredicto} en la propuesta {pid} "
             f"(sha {str(sha_revisado)[:8]})", "ok", cuenta=revisora,
             accion="propuesta_veredicto")
    return obtener_propuesta(base_dir, pid)


def _accion_mezcla(p):
    """El payload que firma el dueño: repo|rama|sha (corrección B8)."""
    return f"mezclar:{p['repo']}|{p['rama']}|{p.get('sha_revisado')}"


def pedir_aprobacion(base_dir, pid, auditar=None):
    """Crea la confirmación humana de la mezcla en el circuito HMAC de
    permission-layer.py: solo el dueño, con caducidad, sobre un sha."""
    p = obtener_propuesta(base_dir, pid)
    if p is None:
        raise ErrorGit(f"propuesta inexistente: {pid}")
    if p.get("estado") != "esperando_dueno":
        raise ErrorGit(f"la propuesta {pid} no está esperando al dueño "
                       f"(está {p.get('estado')})")
    try:
        pl = _cargar_permission_layer()
    except Exception as e:
        raise ErrorGit(f"sin circuito de confirmaciones no hay mezcla: {e}")
    resumen = (f"Mezclar la rama {p['rama']} en {p['base']} "
               f"(propuesta {pid}, sha {str(p.get('sha_revisado'))[:8]})")
    estado, cid = pl._pedir_confirmacion(pid, "git", _accion_mezcla(p), resumen)
    p["confirmacion_id"] = cid
    _propuesta_guardar(base_dir, p)
    return cid


def refrescar_aprobacion(base_dir, pid, auditar=None):
    """El estado de la aprobación del dueño: aprobada|rechazada|
    pendiente|ninguna. Si fue rechazada, la propuesta pasa a rechazada."""
    p = obtener_propuesta(base_dir, pid)
    if p is None:
        raise ErrorGit(f"propuesta inexistente: {pid}")
    try:
        pl = _cargar_permission_layer()
    except Exception as e:
        raise ErrorGit(f"sin circuito de confirmaciones no hay mezcla: {e}")
    estado, _cid = pl._estado_confirmacion(pid, "git", _accion_mezcla(p))
    if estado == "aprobada" and not p.get("aprobada"):
        p["aprobada"] = True
        _propuesta_guardar(base_dir, p)
    elif estado == "rechazada" and p.get("estado") == "esperando_dueno":
        p["estado"] = "rechazada"
        _propuesta_guardar(base_dir, p)
        _auditar(auditar, "git", f"el dueño rechazó la mezcla de {pid}",
                 "bloqueado", cuenta=None, accion="propuesta_rechazada_dueno")
    return estado


def mezclar(base_dir, pid, cuenta, correr=None, remoto="origin",
            auditar=None, entorno_push=None, reloj=None):
    """Ejecuta la mezcla aprobada (§5.1 paso 5). Devuelve un dict con
    "ok" y, según el caso, "estado"/"sha_resultado"/"conflictos"/"motivo".

    Nunca toca la `rama_base` local del dueño: mezcla en un worktree en
    HEAD separado sobre la base remota y sube `HEAD:refs/heads/<base>`.
    Sin remoto, avanza la base con `update-ref` solo si no está ocupada
    en ningún worktree; si lo está, queda `mezcla_manual_pendiente`."""
    p = obtener_propuesta(base_dir, pid)
    if p is None:
        raise ErrorGit(f"propuesta inexistente: {pid}")
    if p.get("estado") != "esperando_dueno":
        return {"ok": False, "motivo": f"la propuesta está {p.get('estado')}, "
                                        "no esperando al dueño"}
    if refrescar_aprobacion(base_dir, pid, auditar=auditar) != "aprobada":
        return {"ok": False, "motivo": "sin aprobación vigente del dueño: "
                                        "no hay mezcla"}
    p = obtener_propuesta(base_dir, pid)
    ent = proyecto(base_dir, p["repo"])
    if ent is None:
        raise ErrorGit(f"el proyecto {p['repo']} ya no está registrado")
    repo = Path(ent["ruta"])
    base = p["base"]
    # Las mezclas del mismo repo se serializan entre sí, y solo entre sí (B9).
    toma = alquileres.tomar(base_dir, p["repo"], ["@mezcla"], cuenta,
                            f"mezcla-{pid}", reloj=reloj)
    if not toma.get("ok"):
        return {"ok": False, "motivo": "hay otra mezcla en curso en este repo"}
    try:
        return _mezclar_bajo_alquiler(base_dir, p, ent, repo, base, cuenta,
                                      correr, remoto, auditar, entorno_push,
                                      reloj)
    finally:
        alquileres.soltar(base_dir, cuenta, f"mezcla-{pid}")


def _mezclar_bajo_alquiler(base_dir, p, ent, repo, base, cuenta, correr,
                           remoto, auditar, entorno_push, reloj):
    pid = p["id"]
    rc, out, _ = _git(["remote"], cwd=repo, correr=correr)
    hay_remoto = rc == 0 and remoto in out.split()
    if hay_remoto:
        _git_ok(["fetch", remoto], cwd=repo, correr=correr,
                timeout=TIMEOUT_RED_S)
        ref_rama = f"refs/remotes/{remoto}/{p['rama']}"
        ref_base = f"{remoto}/{base}"
    else:
        ref_rama = f"refs/heads/{p['rama']}"
        ref_base = f"refs/heads/{base}"
    sha_rama_ahora = _sha_de(repo, ref_rama, correr=correr)
    if sha_rama_ahora != p.get("sha_revisado"):
        # La rama se movió tras la revisión: lo aprobado ya no es esto (B8).
        p["estado"] = "en_revision"
        p["veredicto"] = None
        p["aprobada"] = False
        p["confirmacion_id"] = None
        p["ultimo_error"] = ("la rama se movió tras la revisión; "
                             "vuelve a revisión")
        _propuesta_guardar(base_dir, p, reloj=reloj)
        _auditar(auditar, "git", f"propuesta {pid}: la rama se movió tras "
                 "la revisión; vuelve a en_revision", "error", cuenta=cuenta,
                 accion="propuesta_devuelta_a_revision")
        return {"ok": False, "estado": "en_revision",
                "motivo": p["ultimo_error"]}
    sha_base = _sha_de(repo, ref_base, correr=correr)
    if sha_base is None:
        raise ErrorGit(f"no se encuentra la base {ref_base}")
    wt = ruta_worktree_mezcla(repo, cuenta)
    ocupados = {_norm_ruta(w["ruta"]): w for w in _worktrees(repo, correr=correr)}
    if _norm_ruta(wt) in ocupados:
        if estado_worktree(wt, correr=correr)["sucio"]:
            raise ErrorGit(f"el worktree de mezcla {wt} está sucio; no se toca")
        _git_ok(["checkout", "--detach", sha_base], cwd=wt, correr=correr)
    else:
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git_ok(["worktree", "add", "--detach", str(wt), sha_base],
                cwd=repo, correr=correr)
    resultado = _intentar_mezcla(base_dir, p, repo, wt, sha_base,
                                 p["sha_revisado"], correr, auditar, cuenta,
                                 reloj)
    if resultado.get("conflicto"):
        return {"ok": False, "estado": "conflicto",
                "conflictos": resultado["conflictos"]}
    sha_resultado = resultado["sha"]
    # El sha resultante también pasa el escaneo antes de salir (§6).
    try:
        hallazgos = secretos.escanear_objetos(
            repo, sha_resultado, remoto, correr_git=correr,
            base_dir=base_dir, repo_id=p["repo"])
    except secretos.ErrorSecretos as e:
        hallazgos = [{"tipo": "escáner", "archivo": "", "linea": None,
                      "evidencia": str(e)}]
    if hallazgos:
        p["ultimo_error"] = "la mezcla contiene secretos: no se sube"
        _propuesta_guardar(base_dir, p, reloj=reloj)
        _auditar(auditar, "git", f"propuesta {pid}: mezcla bloqueada por "
                 "secretos", "bloqueado", cuenta=cuenta,
                 accion="mezcla_bloqueada_secretos")
        return {"ok": False, "motivo": p["ultimo_error"],
                "hallazgos": hallazgos}
    if hay_remoto:
        ok, motivo = _empujar_mezcla(base_dir, p, repo, wt, base, cuenta,
                                      correr, remoto, auditar, entorno_push,
                                      reloj)
        if not ok:
            return {"ok": False, "motivo": motivo}
    else:
        ocupada = any(w.get("rama") == base for w in _worktrees(repo, correr=correr))
        if ocupada:
            p["estado"] = "mezcla_manual_pendiente"
            p["sha_resultado"] = sha_resultado
            _propuesta_guardar(base_dir, p, reloj=reloj)
            _auditar(auditar, "git", f"propuesta {pid}: la base está ocupada "
                     "por el árbol del dueño; mezcla manual pendiente",
                     "error", cuenta=cuenta, accion="mezcla_manual_pendiente")
            return {"ok": False, "estado": "mezcla_manual_pendiente",
                    "sha_resultado": sha_resultado,
                    "motivo": "la rama base está abierta en el árbol del "
                              "dueño: la mezcla la hace él a mano"}
        rc, _, err = _git(["update-ref", f"refs/heads/{base}", sha_resultado,
                           sha_base], cwd=repo, correr=correr)
        if rc != 0:
            return {"ok": False, "motivo": f"update-ref falló: {err.strip()[:200]}"}
    p["estado"] = "mezclada"
    p["sha_resultado"] = sha_resultado
    _propuesta_guardar(base_dir, p, reloj=reloj)
    _auditar(auditar, "git", f"propuesta {pid} mezclada en {base}: "
             f"{str(sha_resultado)[:8]}", "ok", cuenta=cuenta,
             accion="propuesta_mezclada")
    return {"ok": True, "estado": "mezclada", "sha_resultado": sha_resultado}


def _intentar_mezcla(base_dir, p, repo, wt, sha_base, sha, correr, auditar,
                     cuenta, reloj):
    """Mezcla `sha` sobre `sha_base` dentro del worktree de mezcla.

    Avance rápido si la base es ancestro; si no, merge --no-ff. Ante
    conflicto: aborta AL INSTANTE, marca la propuesta y devuelve la
    lista: lo resuelve quien propone, nunca la mezcladora (§5.1 paso 6)."""
    rc, _, _ = _git(["merge-base", "--is-ancestor", sha_base, sha],
                    cwd=wt, correr=correr)
    if rc == 0:
        _git_ok(["reset", "--hard", sha], cwd=wt, correr=correr)
        return {"sha": sha}
    rc, out, err = _git(["merge", "--no-ff", "-m",
                         f"Mezcla la propuesta {p['id']} (tarea {p['tarea']})",
                         sha], cwd=wt, correr=correr)
    if rc != 0:
        _, lista, _ = _git(["diff", "--name-only", "--diff-filter=U"],
                           cwd=wt, correr=correr)
        conflictos = [l for l in lista.splitlines() if l.strip()]
        _git(["merge", "--abort"], cwd=wt, correr=correr)
        p["estado"] = "conflicto"
        p["conflictos"] = conflictos
        _propuesta_guardar(base_dir, p, reloj=reloj)
        _auditar(auditar, "git", f"propuesta {p['id']}: conflicto de mezcla "
                 f"en {', '.join(conflictos[:5])}; lo resuelve la proponente",
                 "error", cuenta=cuenta, accion="propuesta_conflicto")
        return {"conflicto": True, "conflictos": conflictos}
    return {"sha": _sha_de(wt, "HEAD", correr=correr)}


def _empujar_mezcla(base_dir, p, repo, wt, base, cuenta, correr, remoto,
                    auditar, entorno_push, reloj):
    """push HEAD:refs/heads/<base> sin --force jamás. Si lo rechazan por
    no ser avance rápido, se repite UNA vez sobre la base nueva (§5.1)."""
    for intento in (1, 2):
        sha_resultado = _sha_de(wt, "HEAD", correr=correr)
        rc, _, err = _git(["push", remoto, f"{sha_resultado}:refs/heads/{base}"],
                          cwd=repo, correr=correr, timeout=TIMEOUT_RED_S,
                          env_extra=entorno_push)
        if rc == 0:
            return True, ""
        if intento == 2 or "non-fast-forward" not in err and "rejected" not in err:
            return False, f"el push de la mezcla falló: {err.strip()[:200]}"
        _git_ok(["fetch", remoto], cwd=repo, correr=correr,
                timeout=TIMEOUT_RED_S)
        nueva_base = _sha_de(repo, f"{remoto}/{base}", correr=correr)
        _git_ok(["checkout", "--detach", nueva_base], cwd=wt, correr=correr)
        r = _intentar_mezcla(base_dir, p, repo, wt, nueva_base,
                             p["sha_revisado"], correr, auditar, cuenta, reloj)
        if r.get("conflicto"):
            return False, "conflicto al reintentar la mezcla sobre la base nueva"
    return False, "el push de la mezcla falló dos veces"


def detectar_superadas(base_dir, repo_id, correr=None, remoto="origin",
                       auditar=None, reloj=None):
    """Propuestas cuyo contenido ya entró en la base sin Growi (el dueño
    mezcló a mano, o GitHub hizo squash/rebase): pasan a `superada`
    (corrección I7: también por igualdad de ÁRBOL, no solo por ancestro)."""
    ent = proyecto(base_dir, repo_id)
    if ent is None:
        return []
    repo = Path(ent["ruta"])
    rc, out, _ = _git(["remote"], cwd=repo, correr=correr)
    hay_remoto = rc == 0 and remoto in out.split()
    cambiadas = []
    for p in propuestas(base_dir, repo=repo_id):
        if p.get("estado") not in ("propuesta", "en_revision",
                                   "esperando_dueno", "cambios_pedidos"):
            continue
        ref_base = f"{remoto}/{p['base']}" if hay_remoto else f"refs/heads/{p['base']}"
        sha_base_ahora = _sha_de(repo, ref_base, correr=correr)
        if not sha_base_ahora or sha_base_ahora == p.get("sha_base"):
            continue  # la base no avanzó: nada que detectar
        ref_rama = (f"refs/remotes/{remoto}/{p['rama']}" if hay_remoto
                    else f"refs/heads/{p['rama']}")
        sha_rama = _sha_de(repo, ref_rama, correr=correr)
        if sha_rama is None:
            continue
        rc, _, _ = _git(["merge-base", "--is-ancestor", sha_rama, sha_base_ahora],
                        cwd=repo, correr=correr)
        entro = rc == 0
        if not entro:
            arbol_rama = _sha_de(repo, f"{sha_rama}^{{tree}}", correr=correr)
            arbol_base = _sha_de(repo, f"{sha_base_ahora}^{{tree}}", correr=correr)
            entro = bool(arbol_rama) and arbol_rama == arbol_base
        if entro:
            p["estado"] = "superada"
            _propuesta_guardar(base_dir, p, reloj=reloj)
            _auditar(auditar, "git", f"propuesta {p['id']}: su contenido ya "
                     "está en la base (mezcla externa); se cierra como "
                     "superada", "ok", cuenta=p.get("cuenta"),
                     accion="propuesta_superada")
            cambiadas.append(p["id"])
    return cambiadas


# -------------------------------------------------------------------- subir

def subir(base_dir, repo, rama, cuenta, tarea, remoto="origin", correr=None,
          auditar=None, entorno_push=None):
    """La única puerta de push de Growi (§6.2). Devuelve un dict con "ok".

    Verifica los alquileres de la tarea, fija el sha exacto, lo escanea
    (objetos que el remoto no tiene) y solo entonces sube ESE sha. Ante
    cualquier duda — escáner caído incluido — no hay push (fail-closed)."""
    raiz = raiz_repo(repo, correr=correr)
    if raiz is None:
        raise ErrorGit(f"no es un repositorio git: {repo}")
    rid = hashlib.sha256(_canon(raiz).encode("utf-8")).hexdigest()[:16]
    vivos = alquileres.de_tarea(base_dir, rid, tarea)
    ajenos = [e for e in vivos if e.get("cuenta") != cuenta]
    if ajenos:
        return {"ok": False,
                "motivo": f"la tarea «{tarea}» perdió sus alquileres "
                          f"(ahora los tiene «{ajenos[0].get('cuenta')}»): no se sube"}
    sha = _sha_de(raiz, f"refs/heads/{rama}", correr=correr)
    if sha is None:
        return {"ok": False, "motivo": f"la rama {rama} no existe"}
    try:
        hallazgos = secretos.escanear_objetos(raiz, sha, remoto,
                                              correr_git=correr,
                                              base_dir=base_dir, repo_id=rid)
    except secretos.ErrorSecretos as e:
        _auditar(auditar, "git", f"subida de {rama} bloqueada: el escáner "
                 f"falló ({e})", "bloqueado", cuenta=cuenta,
                 accion="subida_bloqueada")
        return {"ok": False, "sha": sha,
                "motivo": f"el escáner de secretos falló: {e}"}
    if hallazgos:
        _auditar(auditar, "git", f"subida de {rama} bloqueada: "
                 f"{len(hallazgos)} hallazgo(s) de secretos",
                 "bloqueado", cuenta=cuenta, accion="subida_bloqueada")
        return {"ok": False, "sha": sha, "hallazgos": hallazgos,
                "motivo": "secretos detectados: no se sube"}
    rc, _, err = _git(["push", remoto, f"{sha}:refs/heads/{rama}"],
                      cwd=raiz, correr=correr, timeout=TIMEOUT_RED_S,
                      env_extra=entorno_push)
    if rc != 0:
        return {"ok": False, "sha": sha,
                "motivo": f"el push falló: {err.strip()[:200]}"}
    _auditar(auditar, "git", f"subida de {rama} ({str(sha)[:8]}) por {tarea}",
             "ok", cuenta=cuenta, accion="subida")
    return {"ok": True, "sha": sha, "sin_alquiler": not vivos}


# --------------------------------------------------------------------- hook

def instalar_hook(base_dir, repo, correr=None, ruta_secreto=None):
    """Instala el hook pre-push (capa B) DONDE git lo busca de verdad.

    Nunca pisa un hook ajeno ni un core.hooksPath ajeno: en ese caso el
    proyecto queda en `conflicto` y la capa B no se instala (§6.3)."""
    raiz = raiz_repo(repo, correr=correr)
    if raiz is None:
        raise ErrorGit(f"no es un repositorio git: {repo}")
    rc, comun, _ = _git(["rev-parse", "--git-common-dir"], cwd=raiz,
                        correr=correr)
    if rc != 0:
        return {"estado": "error", "ruta": None,
                "motivo": "no se pudo resolver el directorio git"}
    comun = Path(comun.strip())
    if not comun.is_absolute():
        comun = (raiz / comun).resolve()
    hooks_defecto = comun / "hooks"
    rc, hooks_txt, _ = _git(["rev-parse", "--git-path", "hooks"], cwd=raiz,
                            correr=correr)
    hooks_dir = Path(hooks_txt.strip()) if rc == 0 else hooks_defecto
    if not hooks_dir.is_absolute():
        hooks_dir = (raiz / hooks_dir).resolve()
    rc, hp, _ = _git(["config", "--get", "core.hooksPath"], cwd=raiz,
                     correr=correr)
    if rc == 0 and hp.strip() and _norm_ruta(hooks_dir) != _norm_ruta(hooks_defecto):
        return {"estado": "conflicto", "ruta": None,
                "motivo": f"core.hooksPath apunta a {hp.strip()}: es de otra "
                          "herramienta y no se toca"}
    destino = hooks_dir / "pre-push"
    if destino.is_file():
        try:
            actual = destino.read_text(encoding="utf-8", errors="replace")
        except OSError:
            actual = ""
        if secretos.MARCA_HOOK not in actual:
            detalle = " (parece el de git-lfs)" if "git-lfs" in actual else ""
            return {"estado": "conflicto", "ruta": str(destino),
                    "motivo": f"ya existe un pre-push ajeno{detalle}: no se pisa"}
    escaner = secretos.desplegar(base_dir)
    if ruta_secreto is None:
        ruta_secreto = Path(__file__).with_name("permission-secret.key")
    texto = secretos.texto_hook(sys.executable, escaner, base_dir, ruta_secreto)
    try:
        if destino.is_file() and destino.read_text(encoding="utf-8") == texto:
            return {"estado": "instalado", "ruta": str(destino), "motivo": None}
        hooks_dir.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(texto, encoding="utf-8")
        os.replace(tmp, destino)
        if os.name != "nt":
            os.chmod(destino, 0o755)
    except OSError as e:
        return {"estado": "error", "ruta": str(destino), "motivo": str(e)}
    return {"estado": "instalado", "ruta": str(destino), "motivo": None}


# ------------------------------------------------------------------ limpieza

def limpieza(base_dir, repo_id, dias=None, correr=None, reloj=None,
             auditar=None):
    """Borra worktrees de tareas cuyas propuestas están `mezclada` o
    `rechazada` desde hace más de `dias` días, y las ramas ya mezcladas
    (§3.2). Un worktree sucio jamás se limpia automáticamente."""
    ent = proyecto(base_dir, repo_id)
    if ent is None:
        raise ErrorGit(f"proyecto no registrado: {repo_id}")
    dias = ent.get("limpieza_dias", LIMPIEZA_DIAS_DEF) if dias is None else dias
    ahora = (reloj or time.time)()
    repo = Path(ent["ruta"])
    fuera_wt, fuera_ramas, saltados = [], [], []
    for p in propuestas(base_dir, repo=repo_id):
        if p.get("estado") not in ("mezclada", "rechazada"):
            continue
        if ahora - float(p.get("actualizada_ts") or ahora) < dias * 86400:
            continue
        cuenta, tarea = p.get("cuenta"), p.get("tarea")
        try:
            dest = ruta_worktree(repo, cuenta, tarea, base_dir=base_dir,
                                 correr=correr)
        except ErrorGit:
            continue
        ocupados = {_norm_ruta(w["ruta"]) for w in _worktrees(repo, correr=correr)}
        if _norm_ruta(dest) in ocupados:
            if estado_worktree(dest, correr=correr)["sucio"]:
                saltados.append(str(dest))
                continue
            if liberar_worktree(repo, cuenta, tarea, base_dir=base_dir,
                                correr=correr):
                fuera_wt.append(str(dest))
                _auditar(auditar, "git", f"limpieza: worktree {dest} retirado "
                         f"(propuesta {p['id']} {p['estado']})", "ok",
                         cuenta=cuenta, accion="limpieza_worktree")
        if p.get("estado") == "mezclada" and _rama_existe(repo, p["rama"], correr=correr):
            rc, _, _ = _git(["branch", "-d", p["rama"]], cwd=repo, correr=correr)
            if rc == 0:
                fuera_ramas.append(p["rama"])
                _auditar(auditar, "git", f"limpieza: rama {p['rama']} borrada "
                         "(ya mezclada)", "ok", cuenta=cuenta,
                         accion="limpieza_rama")
    return {"worktrees": fuera_wt, "ramas": fuera_ramas, "saltados": saltados}

"""Fase 6 — contenedores por proyecto.

Un contenedor por proyecto con los dos worktrees dentro (decisión
registrada en la Fase 3, §9 de su diseño), como caja de arena
opcional y por proyecto para ejecutar los motores. La opción
`por_cuenta` del registro de proyectos da un contenedor por cuenta
Muse, para código no confiable.

Reglas que este módulo no puede romper ni queriendo:

- Solo se monta el área de worktrees del proyecto y su `.git` (en
  modo `por_cuenta`, el `.git` va en solo lectura y el área se
  estrecha a la de esa cuenta). El checkout de trabajo del dueño,
  el HOME, `~/.ssh`, la carpeta de la app y la carpeta compartida
  de Growi NO se montan: dentro no existen.
- Las credenciales de git no entran: el entorno del exec se filtra
  (fuera toda variable con pinta de credencial) y, antes de crear,
  se comprueba que `.git/config` no esconda un token en la URL del
  remoto — si lo hay, no se crea nada hasta limpiarlo. La subida
  sigue siendo `git_trabajo.subir()`, desde el anfitrión.
- La función que construye el argv no tiene forma de emitir
  `--publish`, `--privileged` ni `--device`: no son opciones, son
  imposibles.
- Sin runtime no hay invención: el modo del proyecto manda
  (`no` = ni se intenta; `opcional` = la tarea corre fuera con
  aviso; `requerido` = la tarea espera, nunca se degrada en
  silencio).
- Los límites salen del presupuesto de la Fase 4
  (`recursos.limites`): con contenedor no se envuelve además con
  systemd-run; el tope se aplica una sola vez, en el contenedor.

Runtime: Podman preferente (rootless, sin demonio: dentro parece
root, fuera es el dueño) y Docker si es lo que hay — declarando el
matiz: el socket de Docker equivale en la práctica a root en el
anfitrión. La sonda es real (ejecuta `info`), como la de
`systemd-run` de la Fase 4.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import git_trabajo

VERSION = 1
MODOS = ("no", "opcional", "requerido")
REDES = ("saliente", "ninguna")
MATIZ_DOCKER = ("Docker: el socket da acceso de root al anfitrión; "
                "Podman rootless no")
_CACHE = {"ts": 0.0, "valor": None}
CACHE_S = 60
PULL_TIMEOUT_S = 600

# Variables que jamás cruzan al contenedor por el exec: cualquier
# nombre con pinta de credencial. El canario de las pruebas usa una
# así; si mañana un motor trae otra, la regla es por nombre y por
# valor sospechoso no — por nombre, que es lo comprobable.
RX_CREDENCIAL = re.compile(
    r"(KEY|TOKEN|SECRET|PASSW|CREDENCIAL|BEARER|COOKIE|SSH|GH_|"
    r"GITHUB|AWS_|PRIVATE)", re.IGNORECASE)
RX_URL_CON_TOKEN = re.compile(r"://[^/@\s]+@")


class ErrorContenedores(Exception):
    """Toda negativa de esta capa, con el motivo dicho en claro."""


# ---------------------------------------------------------------- runtime

def _ejecutar_defecto(argv, timeout_s=10):
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           timeout=timeout_s)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "tiempo agotado"
    except OSError as e:
        return 127, "", str(e)


def detectar_runtime(ejecutar=None, cual=None, reloj=None):
    """{"runtime": "podman"|"docker"|None, "motivo", "matiz"}.
    Sonda real con `info`; se cachea por proceso (60 s)."""
    ahora = (reloj or time.time)()
    if _CACHE["valor"] is not None and ahora - _CACHE["ts"] < CACHE_S:
        return dict(_CACHE["valor"])
    ejecutar = ejecutar or _ejecutar_defecto
    cual = cual or shutil.which
    valor = {"runtime": None,
             "motivo": "no hay ni Podman ni Docker disponibles",
             "matiz": ""}
    for nombre in ("podman", "docker"):
        if not cual(nombre):
            continue
        try:
            rc, _out, _err = ejecutar([nombre, "info"], timeout_s=5)
        except Exception:
            rc = 1
        if rc == 0:
            valor = {"runtime": nombre,
                     "motivo": f"{nombre} responde a «info»",
                     "matiz": MATIZ_DOCKER if nombre == "docker"
                     else "Podman rootless: el contenedor corre como "
                          "el propio usuario"}
            break
        valor = {"runtime": None,
                 "motivo": f"{nombre} está en el PATH pero «info» no "
                          "responde (¿demonio parado o sin permiso?)",
                 "matiz": ""}
    _CACHE.update({"ts": ahora, "valor": valor})
    return dict(valor)


# ---------------------------------------------------------------- nombres

def nombre_contenedor(repo_id, cuenta=None):
    """Determinista: growi-<repo_id> (proyecto) o
    growi-<repo_id>-<cuenta> (por_cuenta)."""
    nombre = f"growi-{repo_id}"
    if cuenta:
        nombre += f"-{cuenta}"
    return nombre


def areas_worktrees(base_dir, proyecto):
    """Las áreas de worktrees del proyecto: la hermana del repo
    (`<repo>.worktrees`, el diseño normal de la Fase 3) y, si
    existe, la de reserva bajo la carpeta compartida."""
    raiz = Path(proyecto["ruta"])
    areas = [raiz.parent / (raiz.name + ".worktrees")]
    reserva = Path(base_dir) / "worktrees" / proyecto["repo_id"]
    if reserva.is_dir():
        areas.append(reserva)
    return areas


def huella_config(runtime, imagen, montajes, red, usuario):
    """SHA-256 de la configuración viva (runtime, imagen, montajes,
    red, usuario): si cambia, el contenedor se recrea."""
    canon = json.dumps({"runtime": runtime, "imagen": imagen,
                        "montajes": [list(m) for m in montajes],
                        "red": red, "usuario": usuario},
                       sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def credenciales_en_config_git(ruta_repo):
    """True si `.git/config` esconde credenciales en una URL de
    remoto (https://token@…): ese archivo lo leería el contenedor,
    así que con token dentro no se crea nada."""
    try:
        texto = (Path(ruta_repo) / ".git" / "config").read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        return False
    for linea in texto.splitlines():
        if "url" in linea and "=" in linea:
            valor = linea.split("=", 1)[1]
            if RX_URL_CON_TOKEN.search(valor):
                return True
    return False


# ---------------------------------------------------------------- entorno

def filtrar_entorno(env):
    """El entorno que SÍ cruza al contenedor: el del motor ya sin
    credenciales de git (Fase 3) y sin ninguna variable con pinta
    de credencial. Lo que no cruza no existe dentro."""
    limpio = git_trabajo.aplicar_entorno_sin_credenciales(env or {})
    return {k: v for k, v in limpio.items()
            if not RX_CREDENCIAL.search(str(k))}


# ---------------------------------------------------------------- argv

def _limites_argv(limites_dict):
    args = []
    if limites_dict:
        nucleos = (limites_dict.get("cpu") or {}).get(
            "nucleos_equiv")
        if nucleos:
            args += ["--cpus", f"{float(nucleos):.2f}".rstrip("0")
                     .rstrip(".")]
        ram = (limites_dict.get("ram") or {}).get("bytes_por_tarea")
        if ram:
            args += ["--memory", str(int(ram))]
    return args


def montajes_de(base_dir, proyecto, cuenta=None):
    """[(ruta, solo_lectura)]: las áreas de worktrees (en por_cuenta
    solo la de la cuenta) y el `.git` del repo (solo lectura en
    por_cuenta). Montaje espejo: la misma ruta absoluta dentro."""
    raiz = Path(proyecto["ruta"])
    montajes = []
    for area in areas_worktrees(base_dir, proyecto):
        destino = area / cuenta if cuenta else area
        montajes.append((str(destino), False))
    montajes.append((str(raiz / ".git"), bool(cuenta)))
    return montajes


def argv_crear(runtime, nombre, base_dir, proyecto, cuenta=None,
               limites_dict=None, uid=None, gid=None):
    """El argv exacto de creación. Sin --publish, sin --privileged,
    sin --device: esta función no puede emitirlos."""
    imagen = proyecto.get("contenedor_imagen")
    red = proyecto.get("contenedor_red") or "saliente"
    montajes = montajes_de(base_dir, proyecto, cuenta=cuenta)
    usuario = f"{uid}:{gid}" if runtime == "docker" and \
        uid is not None else None
    argv = [runtime, "create", "--name", nombre,
            "--label", f"growi.proyecto={proyecto['repo_id']}",
            "--label", f"growi.modo="
                       f"{'por_cuenta' if cuenta else 'proyecto'}"]
    argv += _limites_argv(limites_dict)
    for ruta, solo_lectura in montajes:
        argv += ["-v", f"{ruta}:{ruta}" + (":ro" if solo_lectura
                                           else "")]
    if red == "ninguna":
        argv += ["--network", "none"]
    if usuario:
        argv += ["--user", usuario]
    argv += [imagen, "sleep", "infinity"]
    return argv, montajes, usuario


def argv_exec(runtime, nombre, cwd, env, argv, por_cuenta=False):
    """El argv para entrar a ejecutar: [runtime, exec, -i, -w cwd,
    -e K=V…, nombre, *argv]. El entorno va filtrado; se añaden la
    marca de contenedor y, en por_cuenta, GIT_OPTIONAL_LOCKS=0
    (el `.git` es de solo lectura: ni el índice se toca)."""
    limpio = filtrar_entorno(env)
    limpio["GROWI_EN_CONTENEDOR"] = "1"
    if por_cuenta:
        limpio["GIT_OPTIONAL_LOCKS"] = "0"
    salida = [runtime, "exec", "-i", "-w", str(cwd)]
    for clave in sorted(limpio):
        salida += ["-e", f"{clave}={limpio[clave]}"]
    salida.append(nombre)
    salida += list(argv)
    return salida


def argv_update_limites(runtime, nombre, limites_dict):
    """El ajuste en vivo cuando cambia el modo de presencia (§5.5)."""
    return [runtime, "update"] + _limites_argv(limites_dict) + [nombre]


# ---------------------------------------------------------------- estado

def _inspeccionar(ejecutar, runtime, nombre):
    """{"existe", "en_marcha"} según el runtime, o motivo."""
    rc, out, _err = ejecutar(
        [runtime, "inspect", "--format", "{{.State.Running}}",
         nombre], timeout_s=10)
    if rc != 0:
        return {"existe": False, "en_marcha": False}
    return {"existe": True,
            "en_marcha": (out or "").strip().lower() == "true"}


def _guardar_estado_contenedor(base_dir, proyecto, estado):
    git_trabajo.guardar_proyecto(base_dir, proyecto["repo_id"],
                                 contenedor=estado)


# ---------------------------------------------------------------- asegurar

def asegurar(base_dir, proyecto, cuenta=None, ejecutar=None,
             reloj=None, limites_dict=None, en_curso=None, cual=None):
    """Deja el contenedor del proyecto listo, o explica qué pasa.

    Devuelve {"estado": "sin_contenedor"|"listo"|"degradado"|
    "esperar", ...}. Con modo "no" no se toca NADA (ni una sonda):
    el flujo de la Fase 3 queda exactamente como estaba.
    `en_curso` (callable → nº de tareas dentro) pospone la
    recreación cuando la huella cambió."""
    ejecutar = ejecutar or _ejecutar_defecto
    reloj = reloj or time.time
    modo = proyecto.get("contenedor_modo") or "no"
    if modo not in MODOS:
        modo = "no"
    if modo == "no":
        return {"estado": "sin_contenedor"}
    por_cuenta = proyecto.get("contenedores") == "por_cuenta"
    cuenta_c = cuenta if por_cuenta else None
    nombre = nombre_contenedor(proyecto["repo_id"], cuenta_c)

    def salida(estado, motivo):
        return {"estado": estado, "motivo": motivo, "nombre": nombre,
                "runtime": None}

    def segun_modo(motivo):
        return salida("degradado" if modo == "opcional" else "esperar",
                      motivo)

    det = detectar_runtime(ejecutar=ejecutar, reloj=reloj, cual=cual)
    runtime = det["runtime"]
    if runtime is None:
        return segun_modo(f"sin contenedor: {det['motivo']}")
    imagen = proyecto.get("contenedor_imagen")
    if not imagen:
        return segun_modo("sin contenedor: el proyecto no declara "
                          "imagen (la imagen ES el entorno del "
                          "proyecto; Growi no inventa una)")
    if credenciales_en_config_git(proyecto["ruta"]):
        return segun_modo(
            "no se crea el contenedor: la URL del remoto en "
            ".git/config lleva credenciales embebidas; cámbiala por "
            "la URL sin token (la subida usa la puerta de la Fase 3) "
            "y vuelve a intentarlo")
    uid = os.getuid() if hasattr(os, "getuid") else None
    gid = os.getgid() if hasattr(os, "getgid") else None
    argv, montajes, usuario = argv_crear(
        runtime, nombre, base_dir, proyecto, cuenta=cuenta_c,
        limites_dict=limites_dict, uid=uid, gid=gid)
    huella = huella_config(runtime, imagen, montajes,
                           proyecto.get("contenedor_red")
                           or "saliente", usuario)
    estado_guardado = proyecto.get("contenedor") or {}
    info = _inspeccionar(ejecutar, runtime, nombre)
    if info["existe"] and estado_guardado.get("huella") == huella:
        if not info["en_marcha"]:
            ejecutar([runtime, "start", nombre], timeout_s=60)
        return {"estado": "listo", "runtime": runtime,
                "nombre": nombre, "huella": huella,
                "reutilizado": True, "por_cuenta": por_cuenta}
    if info["existe"]:
        # La huella cambió: recrear, salvo que haya tareas dentro.
        if en_curso is not None and en_curso() > 0:
            if not info["en_marcha"]:
                ejecutar([runtime, "start", nombre], timeout_s=60)
            return {"estado": "listo", "runtime": runtime,
                    "nombre": nombre,
                    "huella": estado_guardado.get("huella"),
                    "reutilizado": True, "por_cuenta": por_cuenta,
                    "recreacion_pospuesta": True,
                    "motivo": "la configuración cambió pero hay "
                              "tareas dentro: se recrea al quedar "
                              "libre"}
        ejecutar([runtime, "rm", "-f", nombre], timeout_s=60)
    rc, _out, _err = ejecutar([runtime, "image", "inspect", imagen],
                              timeout_s=10)
    if rc != 0:
        rc, _out, err = ejecutar([runtime, "pull", imagen],
                                 timeout_s=PULL_TIMEOUT_S)
        if rc != 0:
            return segun_modo(f"no se pudo bajar la imagen {imagen}: "
                              f"{(err or '').strip()[:200]}")
    rc, _out, err = ejecutar(argv, timeout_s=120)
    if rc != 0:
        return segun_modo(f"no se pudo crear el contenedor: "
                          f"{(err or '').strip()[:200]}")
    rc, _out, err = ejecutar([runtime, "start", nombre],
                             timeout_s=60)
    if rc != 0:
        return segun_modo(f"el contenedor se creó pero no arrancó: "
                          f"{(err or '').strip()[:200]}")
    estado = {"runtime": runtime, "nombre": nombre, "huella": huella,
              "creado": reloj(), "estado": "en_marcha"}
    try:
        _guardar_estado_contenedor(base_dir, proyecto, estado)
    except Exception:
        pass
    return {"estado": "listo", "runtime": runtime, "nombre": nombre,
            "huella": huella, "reutilizado": False,
            "por_cuenta": por_cuenta}


def destruir(base_dir, proyecto, cuenta=None, ejecutar=None,
             cual=None):
    """Quita el contenedor (los worktrees y el `.git` son montajes:
    no se tocan). La confirmación la pone quien llama."""
    ejecutar = ejecutar or _ejecutar_defecto
    por_cuenta = proyecto.get("contenedores") == "por_cuenta"
    nombre = nombre_contenedor(proyecto["repo_id"],
                                cuenta if por_cuenta else None)
    det = detectar_runtime(ejecutar=ejecutar, cual=cual)
    if det["runtime"] is None:
        raise ErrorContenedores(det["motivo"])
    rc, _out, err = ejecutar([det["runtime"], "rm", "-f", nombre],
                             timeout_s=60)
    if rc != 0:
        raise ErrorContenedores(
            f"no se pudo destruir {nombre}: "
            f"{(err or '').strip()[:200]}")
    try:
        _guardar_estado_contenedor(base_dir, proyecto, None)
    except Exception:
        pass
    return {"nombre": nombre, "runtime": det["runtime"]}

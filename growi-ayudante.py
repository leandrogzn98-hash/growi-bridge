#!/usr/bin/env python3
"""Growi Bridge — ayudante del intermediario de root (Fase 6).

Este archivo es la pieza que sudoers autoriza, por su ruta exacta
(/usr/local/libexec/growi-ayudante.py), y NO importa nada del
proyecto a propósito: trae su propia copia de la especificación del
registro cerrado de acciones y la vuelve a validar todo antes de
ejecutar (la doble validación: la app validó al pedir, el ayudante
revalida al ejecutar). Si importara módulos de la carpeta de la app,
quien escribiera ahí tendría root.

Qué hace, en orden, con todo fail-closed:

1. Exige venir del circuito de elevación: sin SUDO_UID ni
   PKEXEC_UID en el entorno no ejecuta nada (invocarlo «a mano»,
   incluso como root, no es el circuito).
2. Lee la petición JSON por stdin (nunca texto libre por argv) y la
   valida contra el registro: la acción existe, los parámetros son
   exactamente los declarados y cada valor pasa su dominio (la
   unidad está en la lista del dueño y tiene forma válida; el
   paquete tiene forma de nombre Debian).
3. Recalcula la huella de los parámetros y la compara con la de la
   petición.
4. Exige la orden de un solo uso que el runner dejó tras la
   aprobación humana (raiz-ordenes/<acción>--<huella>.json, viva
   15 min, con la misma cuenta) y la consume al usarla.
5. Impone su propio tope de ritmo desde su propio log.
6. Ejecuta el argv exacto con subprocess (shell=False), entorno
   mínimo construido desde cero, cwd=/, stdin cerrado y el timeout
   del registro, matando el grupo de procesos al vencer.
7. Deja su asiento en su propio log encadenado por hashes
   (raiz-ayudante.jsonl, en la carpeta compartida) y responde un
   JSON por stdout.

Modos: `sonda` (responde versión y acciones; es como la app detecta
la vía) y `ejecutar` (el camino de arriba). Ningún otro.
"""

import hashlib
import json
import os
import pwd
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

VERSION = "1"
ARCHIVO_CONFIG = "raiz-config.json"
DIR_ORDENES = "raiz-ordenes"
ARCHIVO_LOG = "raiz-ayudante.jsonl"
VENTANA_ORDEN_S = 900
MAX_POR_CUENTA_HORA = 10
MAX_TOTAL_HORA = 30
MAX_PETICION = 65536
SALIDA_MAX = 65536
ENV_MINIMO = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:"
                      "/usr/bin:/sbin:/bin",
              "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": "/root"}

RX_UNIDAD = re.compile(r"^[a-z0-9][a-z0-9._@-]{0,80}$")
RX_PAQUETE = re.compile(r"^[a-z0-9][a-z0-9+.-]{1,80}$")

# La especificación del registro, espejo de raiz.py (la prueba
# test_ayudante verifica que ambas copias coinciden: mismos ids,
# mismos argv para los casos válidos, mismos timeouts).
REGISTRO = {
    "servicio-estado": {
        "argv": ["/usr/bin/systemctl", "status", "{unidad}",
                 "--no-pager"],
        "params": {"unidad": "unidad"}, "timeout_s": 30},
    "servicio-arrancar": {
        "argv": ["/usr/bin/systemctl", "start", "{unidad}"],
        "params": {"unidad": "unidad"}, "timeout_s": 120},
    "servicio-parar": {
        "argv": ["/usr/bin/systemctl", "stop", "{unidad}"],
        "params": {"unidad": "unidad"}, "timeout_s": 120},
    "servicio-reiniciar": {
        "argv": ["/usr/bin/systemctl", "restart", "{unidad}"],
        "params": {"unidad": "unidad"}, "timeout_s": 180},
    "apt-actualizar": {
        "argv": ["/usr/bin/apt-get", "update"],
        "params": {}, "timeout_s": 600},
    "apt-instalar": {
        "argv": ["/usr/bin/apt-get", "install", "-y", "{paquete}"],
        "params": {"paquete": "paquete"}, "timeout_s": 600},
    "dpkg-reparar": {
        "argv": ["/usr/bin/dpkg", "--configure", "-a"],
        "params": {}, "timeout_s": 600},
    "apt-reparar": {
        "argv": ["/usr/bin/apt-get", "install", "-f", "-y"],
        "params": {}, "timeout_s": 600},
}


def huella_params(params):
    canon = json.dumps(params or {}, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def cargar_unidades(base):
    """La lista del dueño, releída en cada petición: mismos
    criterios que la app (lo inválido se descarta, nunca amplía)."""
    unidades = set()
    try:
        datos = json.loads((Path(base) / ARCHIVO_CONFIG).read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return unidades
    if not isinstance(datos, dict):
        return unidades
    for entrada in datos.get("unidades") or []:
        nombre = entrada if isinstance(entrada, str) else (
            entrada.get("nombre") if isinstance(entrada, dict)
            else None)
        if isinstance(nombre, str) and RX_UNIDAD.match(nombre):
            unidades.add(nombre)
    return unidades


def validar(accion, params, unidades):
    """La especificación de validación, repetida: (argv, motivo).
    argv es None si hay motivo de rechazo."""
    spec = REGISTRO.get(accion)
    if spec is None:
        return None, f"acción de sistema desconocida: {accion}"
    if not isinstance(params, dict):
        return None, "los parámetros deben ser un objeto por nombre"
    esperados = set(spec["params"])
    recibidos = set(params)
    if recibidos != esperados:
        return None, (f"parámetros incorrectos para {accion}: "
                      f"esperados {sorted(esperados)}, "
                      f"recibidos {sorted(recibidos)}")
    limpios = {}
    for nombre, tipo in spec["params"].items():
        valor = params.get(nombre)
        if not isinstance(valor, str) or not valor:
            return None, f"el parámetro «{nombre}» debe ser un texto"
        if tipo == "unidad":
            if not RX_UNIDAD.match(valor):
                return None, (f"la unidad «{valor}» no tiene forma "
                              "válida")
            if valor not in unidades:
                return None, (f"la unidad «{valor}» no está en la "
                              "lista del dueño")
        elif tipo == "paquete":
            if not RX_PAQUETE.match(valor):
                return None, (f"el paquete «{valor}» no tiene forma "
                              "de nombre de paquete válido")
        limpios[nombre] = valor
    argv = [limpios[e[1:-1]] if e.startswith("{") and e.endswith("}")
            else e for e in spec["argv"]]
    return argv, None


# ---------------------------------------------------------------- su log

def _hash_entrada(prev, entrada):
    canon = json.dumps(entrada, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"))
    return hashlib.sha256((prev + canon).encode("utf-8")).hexdigest()


def _leer_log(base):
    entradas = []
    try:
        lineas = (Path(base) / ARCHIVO_LOG).read_text(
            encoding="utf-8").splitlines()
    except OSError:
        return entradas
    for linea in lineas:
        try:
            e = json.loads(linea)
        except ValueError:
            continue
        if isinstance(e, dict):
            entradas.append(e)
    return entradas


def verificar_cadena(entradas):
    """True si la cadena de hashes del log es íntegra."""
    prev = ""
    for e in entradas:
        cuerpo = {k: v for k, v in e.items()
                  if k not in ("prev_hash", "hash")}
        if e.get("prev_hash") != prev:
            return False
        if e.get("hash") != _hash_entrada(prev, cuerpo):
            return False
        prev = e["hash"]
    return True


def asentar(base, entrada):
    previas = _leer_log(base)
    prev = previas[-1]["hash"] if previas and \
        isinstance(previas[-1].get("hash"), str) else ""
    entrada = dict(entrada)
    entrada["prev_hash"] = prev
    entrada["hash"] = _hash_entrada(
        prev, {k: v for k, v in entrada.items()
               if k not in ("prev_hash", "hash")})
    with open(Path(base) / ARCHIVO_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return entrada


# ---------------------------------------------------------------- ejecución

def _ejecutar_defecto(argv, timeout_s):
    """El ejecutor real: sin shell, entorno mínimo, grupo propio."""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True,
                             env=dict(ENV_MINIMO), cwd="/",
                             start_new_session=True)
    except OSError as e:
        return 127, "", f"no se pudo lanzar: {e}"
    try:
        out, err = p.communicate(timeout=timeout_s)
        return p.returncode, out or "", err or ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            out, err = p.communicate(timeout=10)
        except Exception:
            out, err = "", ""
        return 124, out or "", (err or "") + "\n[tiempo agotado]"


def _truncar(texto):
    if len(texto) > SALIDA_MAX:
        return texto[:SALIDA_MAX] + "\n…[truncada]"
    return texto


def procesar_peticion(peticion, base, env, ejecutar=None, reloj=None):
    """El corazón del ayudante, con todo inyectable para probarlo.
    Devuelve el dict de respuesta (nunca lanza)."""
    ejecutar = ejecutar or _ejecutar_defecto
    reloj = reloj or time.time

    def responder(ok, motivo="", rc=None, salida="", dur=0.0,
                  accion=None, cuenta=None, huella=None, ejecuto=False):
        try:
            asentar(base, {
                "ts": reloj(), "resultado": "ejecutada" if ok
                else "rechazada", "ejecuto": bool(ejecuto),
                "accion": accion, "cuenta": cuenta,
                "huella": huella, "rc": rc, "motivo": motivo[:300],
                "sudo_uid": (env or {}).get("SUDO_UID")
                or (env or {}).get("PKEXEC_UID")})
        except Exception:
            pass
        return {"ok": ok, "rc": rc, "salida": salida,
                "motivo": motivo, "duracion_s": round(dur, 2)}

    if not isinstance(peticion, dict) or peticion.get("v") != 1:
        return responder(False, "petición mal formada")
    accion = peticion.get("accion")
    params = peticion.get("params") or {}
    cuenta = peticion.get("cuenta")
    huella = peticion.get("huella")
    if not isinstance(accion, str) or not isinstance(cuenta, str) \
            or not cuenta:
        return responder(False, "petición sin acción o sin cuenta",
                         accion=accion if isinstance(accion, str)
                         else None)
    # 1) El circuito de elevación: sin él, ni como root.
    if not (env or {}).get("SUDO_UID") and not (env or {}).get(
            "PKEXEC_UID"):
        return responder(False, "sin SUDO_UID ni PKEXEC_UID: el "
                                "ayudante solo actúa elevado por el "
                                "circuito (sudoers/polkit), nunca "
                                "invocado a mano",
                         accion=accion, cuenta=cuenta, huella=huella)
    # 2) y 3) Registro, dominios y huella recalculada.
    argv, motivo = validar(accion, params, cargar_unidades(base))
    if argv is None:
        return responder(False, motivo, accion=accion, cuenta=cuenta,
                         huella=huella)
    if huella != huella_params(params):
        return responder(False, "la huella no coincide con los "
                                "parámetros: petición manipulada",
                         accion=accion, cuenta=cuenta, huella=huella)
    # 4) La orden de un solo uso, viva y de esta cuenta.
    ruta_orden = Path(base) / DIR_ORDENES / f"{accion}--{huella}.json"
    try:
        orden = json.loads(ruta_orden.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return responder(False, "sin orden viva del circuito de "
                                "aprobaciones: el ayudante no ejecuta "
                                "peticiones sueltas",
                         accion=accion, cuenta=cuenta, huella=huella)
    if orden.get("cuenta") != cuenta or \
            float(orden.get("vence_ts") or 0) < reloj():
        return responder(False, "la orden no es de esta cuenta o "
                                "caducó: confirma de nuevo en la app",
                         accion=accion, cuenta=cuenta, huella=huella)
    try:
        ruta_orden.unlink()          # consumida: un solo uso
    except OSError:
        return responder(False, "la orden no se pudo consumir",
                         accion=accion, cuenta=cuenta, huella=huella)
    # 5) Su propio tope de ritmo, desde su propio log.
    ahora = reloj()
    recientes = [e for e in _leer_log(base)
                 if e.get("ejecuto")
                 and ahora - float(e.get("ts") or 0) < 3600]
    if len([e for e in recientes if e.get("cuenta") == cuenta]) \
            >= MAX_POR_CUENTA_HORA or \
            len(recientes) >= MAX_TOTAL_HORA:
        return responder(False, "tope de ritmo del ayudante: "
                                "demasiadas acciones en la última "
                                "hora", accion=accion, cuenta=cuenta,
                         huella=huella)
    # 6) Ejecutar el argv exacto.
    t0 = reloj()
    rc, out, err = ejecutar(argv, REGISTRO[accion]["timeout_s"])
    dur = reloj() - t0
    salida = _truncar(((out or "") + ("\n" if out and err else "")
                       + (err or "")).strip())
    if rc == 124:
        return responder(False, "la acción superó su tiempo y se "
                                "mató el árbol", rc=rc, salida=salida,
                         dur=dur, accion=accion, cuenta=cuenta,
                         huella=huella, ejecuto=True)
    return responder(rc == 0, "" if rc == 0 else
                     f"la acción terminó con código {rc}", rc=rc,
                     salida=salida, dur=dur, accion=accion,
                     cuenta=cuenta, huella=huella, ejecuto=True)


# ---------------------------------------------------------------- entrada

def base_desde_entorno(env):
    """La carpeta compartida, derivada como hace la app: la del
    usuario que elevó (SUDO_UID/PKEXEC_UID), no la de root."""
    if env.get("GROWI_RAIZ_BASE"):
        return Path(env["GROWI_RAIZ_BASE"])
    uid = env.get("SUDO_UID") or env.get("PKEXEC_UID")
    try:
        home = Path(pwd.getpwuid(int(uid)).pw_dir)
    except (TypeError, ValueError, KeyError):
        home = Path.home()
    xdg = env.get("XDG_DATA_HOME")
    raiz = Path(xdg) if xdg else home / ".local" / "share"
    return raiz / "GrowiBridge"


def main(argv):
    if len(argv) != 2 or argv[1] not in ("sonda", "ejecutar"):
        print(json.dumps({"ok": False,
                          "motivo": "uso: growi-ayudante.py "
                                    "sonda|ejecutar"}))
        return 2
    if argv[1] == "sonda":
        print(json.dumps({"ok": True, "version": VERSION,
                          "acciones": sorted(REGISTRO)}))
        return 0
    crudo = sys.stdin.read(MAX_PETICION + 1)
    if len(crudo) > MAX_PETICION:
        print(json.dumps({"ok": False,
                          "motivo": "petición demasiado grande"}))
        return 0
    try:
        peticion = json.loads(crudo)
    except ValueError:
        print(json.dumps({"ok": False,
                          "motivo": "la petición no es JSON"}))
        return 0
    base = base_desde_entorno(os.environ)
    print(json.dumps(procesar_peticion(peticion, base, os.environ),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

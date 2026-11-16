"""Fase 6 — el lado de la app del intermediario de root.

Filosofía (FASE-6-DISENO.md y su §14 bis): ninguna cuenta Muse conoce
ni usa la clave de root — ni la del usuario con sudo — jamás. Lo
privilegiado nace como declaración estructurada en una tarea `sistema`,
lo clasifica código, lo confirma una persona por el circuito de
aprobaciones de siempre y lo ejecuta UN ayudante
(`growi-ayudante.py`) al que sudoers autoriza por su ruta exacta.

Este módulo es el registro cerrado de acciones y todo lo que la app
necesita alrededor:

- `REGISTRO`: las únicas acciones que existen. Cada una es una
  plantilla de argv con huecos que ocupan elementos enteros, y cada
  hueco tiene un dominio cerrado (la unidad debe estar en la lista
  del dueño Y pasar una regex estricta; el paquete, una regex
  estricta de nombre Debian). Nada de shell, nunca: no hay forma de
  expresar un comando libre.
- La lista del dueño (`raiz-config.json`, en la carpeta compartida):
  qué unidades de systemd puede tocar el intermediario, y si alguna
  sube de nivel. La app la lee; ampliarla es un acto del dueño
  editando el archivo, nunca de un agente.
- Doble validación: la app valida aquí y el ayudante revalida con su
  propia copia de la especificación antes de ejecutar.
- Topes de ritmo por cuenta y en total (también los impone el
  ayudante por su lado, desde su propio log).
- Órdenes: tras una aprobación humana, el runner deja una orden de
  un solo uso y de vida corta en `raiz-ordenes/`; el ayudante solo
  ejecuta peticiones con una orden viva que coincida en acción y
  huella de parámetros, y la consume al usarla.
- Detección honesta de la vía: sudoers (regla instalada y sonda al
  ayudante respondida), pkexec (presente, sin verificar: sondearlo
  abriría un diálogo) o ninguna. Sin vía no hay intermediario y las
  tareas `sistema` esperan con ese motivo; la app nunca prueba un
  `sudo` genérico ni busca reglas anchas.

La frontera es la declarada en el diseño (§1.8): esto protege frente
al motor (el LLM y sus herramientas, acotados por la capa de
permisos), no frente a un proceso arbitrario corriendo como el
propio dueño — el mismo límite que ya tenía el sistema de
confirmaciones antes de esta fase.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

VERSION = 1
ARCHIVO_CONFIG = "raiz-config.json"
ARCHIVO_ESTADO = "raiz-estado.json"
DIR_ORDENES = "raiz-ordenes"
AYUDANTE_INSTALADO = "/usr/local/libexec/growi-ayudante.py"
ARCHIVO_SUDOERS = "/etc/sudoers.d/growi-bridge"
MAX_POR_CUENTA_HORA = 10
MAX_TOTAL_HORA = 30
VENTANA_ORDEN_S = 900          # la orden vive 15 min desde la aprobación
_CACHE_VIA = {"ts": 0.0, "valor": None}
CACHE_VIA_S = 60

# Nombre de unidad systemd: empieza en minúscula o dígito, sin
# espacios, sin metacaracteres de shell, sin guión inicial (jamás
# podrá leerse como una opción de systemctl). La pertenencia a la
# lista del dueño es la puerta de verdad; esto es defensa en
# profundidad sobre esa lista.
RX_UNIDAD = re.compile(r"^[a-z0-9][a-z0-9._@-]{0,80}$")
# Nombre de paquete Debian: minúsculas, dígitos, +, . y -; nunca
# empieza por guión (no puede convertirse en un flag de apt-get).
RX_PAQUETE = re.compile(r"^[a-z0-9][a-z0-9+.-]{1,80}$")
NIVELES = ("R1", "R2", "R3")


class ErrorRaiz(Exception):
    """Toda negativa de esta capa, con el motivo dicho en claro."""


# ---------------------------------------------------------------- registro

def _spec(argv, params, nivel, clase, descripcion, timeout_s):
    return {"argv": list(argv), "params": params, "nivel": nivel,
            "clase": clase, "descripcion": descripcion,
            "timeout_s": timeout_s}


REGISTRO = {
    "servicio-estado": _spec(
        ["/usr/bin/systemctl", "status", "{unidad}", "--no-pager"],
        {"unidad": {"tipo": "unidad"}}, "R1", "servicio",
        "Consultar el estado del servicio «{unidad}»", 30),
    "servicio-arrancar": _spec(
        ["/usr/bin/systemctl", "start", "{unidad}"],
        {"unidad": {"tipo": "unidad"}}, "R2", "servicio",
        "Arrancar el servicio «{unidad}»", 120),
    "servicio-parar": _spec(
        ["/usr/bin/systemctl", "stop", "{unidad}"],
        {"unidad": {"tipo": "unidad"}}, "R2", "servicio",
        "Parar el servicio «{unidad}»", 120),
    "servicio-reiniciar": _spec(
        ["/usr/bin/systemctl", "restart", "{unidad}"],
        {"unidad": {"tipo": "unidad"}}, "R2", "servicio",
        "Reiniciar el servicio «{unidad}»", 180),
    "apt-actualizar": _spec(
        ["/usr/bin/apt-get", "update"],
        {}, "R2", "paquetes",
        "Actualizar la lista de paquetes (apt-get update)", 600),
    "apt-instalar": _spec(
        ["/usr/bin/apt-get", "install", "-y", "{paquete}"],
        {"paquete": {"tipo": "paquete"}}, "R2", "paquetes",
        "Instalar el paquete «{paquete}»", 600),
}


def acciones():
    """Los ids del registro, ordenados: lo único que se puede pedir."""
    return sorted(REGISTRO)


# ---------------------------------------------------------------- config

def cargar_config(base_dir):
    """La lista del dueño desde `raiz-config.json` (carpeta compartida).

    Devuelve {"unidades": {nombre: {"nivel": str|None}}, "degradada":
    bool}. Una entrada inválida se descarta y marca la config como
    degradada: una config dudosa nunca amplía lo permitido, como
    mucho lo estrecha (la unidad mal escrita simplemente no está).
    Sin archivo: ninguna unidad permitida (apt sigue disponible)."""
    salida = {"unidades": {}, "degradada": False}
    try:
        datos = json.loads((Path(base_dir) / ARCHIVO_CONFIG).read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return salida
    if not isinstance(datos, dict):
        salida["degradada"] = True
        return salida
    for entrada in datos.get("unidades") or []:
        nombre, nivel = None, None
        if isinstance(entrada, str):
            nombre = entrada
        elif isinstance(entrada, dict):
            nombre = entrada.get("nombre")
            nivel = entrada.get("nivel")
        if not isinstance(nombre, str) or not RX_UNIDAD.match(nombre):
            salida["degradada"] = True
            continue
        if nivel is not None and nivel not in NIVELES:
            salida["degradada"] = True
            nivel = None
        salida["unidades"][nombre] = {"nivel": nivel}
    return salida


# ---------------------------------------------------------------- validación

def huella_params(params):
    """La huella de unos parámetros: SHA-256 del JSON canónico
    (claves ordenadas, separadores fijos), primeros 16 hex. La
    misma especificación que reimplementa el ayudante."""
    canon = json.dumps(params or {}, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def _validar_valor(nombre, valor, dominio, config):
    if not isinstance(valor, str) or not valor:
        raise ErrorRaiz(f"el parámetro «{nombre}» debe ser un texto no vacío")
    tipo = dominio.get("tipo")
    if tipo == "unidad":
        if not RX_UNIDAD.match(valor):
            raise ErrorRaiz(
                f"la unidad «{valor}» no tiene forma de nombre de unidad "
                "válido (minúsculas, dígitos y . _ @ -; sin espacios ni "
                "símbolos de shell)")
        if valor not in (config or {}).get("unidades", {}):
            raise ErrorRaiz(
                f"la unidad «{valor}» no está en la lista del dueño "
                f"({ARCHIVO_CONFIG}): el intermediario solo toca las "
                "unidades que el dueño escribió ahí")
        return valor
    if tipo == "paquete":
        if not RX_PAQUETE.match(valor):
            raise ErrorRaiz(
                f"el paquete «{valor}» no tiene forma de nombre de "
                "paquete válido (minúsculas, dígitos y + . -; sin "
                "guión inicial ni símbolos de shell)")
        return valor
    raise ErrorRaiz(f"dominio desconocido para «{nombre}»: {tipo}")


def _rango(nivel):
    return NIVELES.index(nivel)


def validar_peticion(accion, params, config):
    """Valida una petición contra el registro y los dominios.

    Devuelve {"argv", "nivel", "descripcion", "huella"} o lanza
    ErrorRaiz con el motivo. Es la primera de las dos validaciones;
    el ayudante repite exactamente esta especificación."""
    spec = REGISTRO.get(accion)
    if spec is None:
        raise ErrorRaiz(f"acción de sistema desconocida: {accion}")
    params = params or {}
    if not isinstance(params, dict):
        raise ErrorRaiz("los parámetros deben ser un objeto por nombre")
    esperados = set(spec["params"])
    recibidos = set(params)
    if recibidos - esperados:
        raise ErrorRaiz(
            "parámetros no declarados para "
            f"{accion}: {sorted(recibidos - esperados)}")
    if esperados - recibidos:
        raise ErrorRaiz(
            f"faltan parámetros para {accion}: "
            f"{sorted(esperados - recibidos)}")
    limpios = {}
    for nombre, dominio in spec["params"].items():
        limpios[nombre] = _validar_valor(nombre, params.get(nombre),
                                         dominio, config)
    argv = []
    for elemento in spec["argv"]:
        if elemento.startswith("{") and elemento.endswith("}"):
            argv.append(limpios[elemento[1:-1]])
        else:
            argv.append(elemento)
    nivel = spec["nivel"]
    unidad = limpios.get("unidad")
    if unidad:
        extra = ((config or {}).get("unidades", {}).get(unidad)
                 or {}).get("nivel")
        if extra and _rango(extra) > _rango(nivel):
            nivel = extra
    descripcion = spec["descripcion"]
    for nombre, valor in limpios.items():
        descripcion = descripcion.replace("{" + nombre + "}", valor)
    return {"argv": argv, "nivel": nivel, "descripcion": descripcion,
            "huella": huella_params(limpios)}


def nivel_de(lista_acciones, config):
    """El nivel de una tarea `sistema`: el mayor de sus acciones.

    Devuelve (nivel, detalles) o (None, motivo) si alguna acción no
    existe o no valida: la tarea no se clasifica a ciegas."""
    nivel = "R1"
    detalles = []
    for item in lista_acciones or []:
        if not isinstance(item, dict) or not isinstance(
                item.get("accion"), str):
            return None, "un elemento de «sistema» no tiene forma de acción"
        try:
            v = validar_peticion(item["accion"], item.get("params"),
                                 config)
        except ErrorRaiz as e:
            return None, str(e)
        if _rango(v["nivel"]) > _rango(nivel):
            nivel = v["nivel"]
        detalles.append({"accion": item["accion"], **v})
    if not detalles:
        return None, "la tarea no declara ninguna acción de sistema"
    return nivel, detalles


# ---------------------------------------------------------------- estado/ritmo

@contextmanager
def _bloqueo(base_dir, archivo):
    """Lock de archivo entre procesos (el patrón del proyecto)."""
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
        raise ErrorRaiz(f"{archivo} está bloqueado por otro proceso")
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except OSError:
            pass


def _cargar_estado(base_dir):
    try:
        d = json.loads((Path(base_dir) / ARCHIVO_ESTADO).read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": VERSION, "ejecuciones": []}
    if not isinstance(d, dict) or not isinstance(
            d.get("ejecuciones"), list):
        return {"version": VERSION, "ejecuciones": []}
    return d


def _guardar_estado(base_dir, d):
    path = Path(base_dir) / ARCHIVO_ESTADO
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)


def comprobar_ritmo(base_dir, cuenta, reloj=None):
    """Los topes de ritmo de la app (el ayudante impone los suyos
    desde su propio log): por cuenta y en total, por hora."""
    ahora = (reloj or time.time)()
    d = _cargar_estado(base_dir)
    recientes = [e for e in d["ejecuciones"]
                 if isinstance(e, dict)
                 and ahora - float(e.get("ts") or 0) < 3600]
    de_cuenta = [e for e in recientes if e.get("cuenta") == cuenta]
    if len(de_cuenta) >= MAX_POR_CUENTA_HORA:
        raise ErrorRaiz(
            f"tope de ritmo: la cuenta {cuenta} ya pidió "
            f"{MAX_POR_CUENTA_HORA} acciones de sistema en la última "
            "hora; el intermediario no ejecuta más hasta que pase")
    if len(recientes) >= MAX_TOTAL_HORA:
        raise ErrorRaiz(
            f"tope de ritmo global: {MAX_TOTAL_HORA} acciones de "
            "sistema en la última hora entre todas las cuentas")


def anotar_ejecucion(base_dir, cuenta, accion, reloj=None):
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir, ARCHIVO_ESTADO):
        d = _cargar_estado(base_dir)
        d["ejecuciones"] = [
            e for e in d["ejecuciones"]
            if isinstance(e, dict) and ahora - float(e.get("ts") or 0)
            < 24 * 3600]
        d["ejecuciones"].append({"ts": ahora, "cuenta": cuenta,
                                 "accion": accion})
        _guardar_estado(base_dir, d)


# ---------------------------------------------------------------- órdenes

def _ruta_orden(base_dir, accion, huella):
    return Path(base_dir) / DIR_ORDENES / f"{accion}--{huella}.json"


def crear_orden(base_dir, cuenta, accion, huella, approval_id,
                reloj=None):
    """La orden de un solo uso que el runner deja tras la aprobación
    humana: sin ella el ayudante no ejecuta nada. La llama SOLO el
    camino que sigue a una decisión del circuito de aprobaciones
    (o a la política del dueño que exime de preguntar en R1)."""
    ahora = (reloj or time.time)()
    carpeta = Path(base_dir) / DIR_ORDENES
    carpeta.mkdir(parents=True, exist_ok=True)
    datos = {"v": VERSION, "cuenta": cuenta, "accion": accion,
             "huella": huella, "approval_id": approval_id, "ts": ahora,
             "vence_ts": ahora + VENTANA_ORDEN_S}
    ruta = _ruta_orden(base_dir, accion, huella)
    tmp = ruta.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, ruta)
    return ruta


# ---------------------------------------------------------------- detección

def ruta_ayudante():
    """El ayudante: el instalado (el que autoriza sudoers) si está;
    si no, el que vive junto a este módulo (la sonda lo dirá: sin la
    regla de sudoers no habrá vía igualmente)."""
    if Path(AYUDANTE_INSTALADO).is_file():
        return AYUDANTE_INSTALADO
    return str(Path(__file__).with_name("growi-ayudante.py"))


def _ejecutar_defecto(argv, entrada=None, timeout_s=10):
    try:
        p = subprocess.run(argv, input=entrada, capture_output=True,
                           text=True, timeout=timeout_s)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "tiempo agotado"
    except OSError as e:
        return 127, "", str(e)


def detectar_via(base_dir, ejecutar=None, reloj=None,
                 ruta_sudoers=ARCHIVO_SUDOERS, cual=None):
    """Qué vía hay, de verdad: {"via", "verificada", "motivo",
    "ayudante", "acciones"}. La sonda sudoers se cachea 60 s: no se
    lanza sudo en cada latido."""
    ahora = (reloj or time.time)()
    if _CACHE_VIA["valor"] is not None and \
            ahora - _CACHE_VIA["ts"] < CACHE_VIA_S:
        return dict(_CACHE_VIA["valor"])
    ejecutar = ejecutar or _ejecutar_defecto
    cual = cual or shutil.which
    ayudante = ruta_ayudante()
    valor = {"via": "ninguna", "verificada": False,
             "motivo": "intermediario no instalado", "ayudante": ayudante,
             "acciones": acciones()}
    if Path(ruta_sudoers).is_file():
        try:
            rc, out, _err = ejecutar(
                ["sudo", "-n", "--", ayudante, "sonda"], timeout_s=6)
            sonda = json.loads((out or "").strip().splitlines()[-1])
            if rc == 0 and sonda.get("ok"):
                valor = {"via": "sudoers", "verificada": True,
                         "motivo": "regla de sudoers instalada y el "
                                   "ayudante responde a la sonda",
                         "ayudante": ayudante, "acciones": acciones()}
        except (ValueError, IndexError):
            pass
        except Exception:
            pass
        if valor["via"] == "ninguna":
            valor["motivo"] = ("hay un archivo de reglas en "
                               f"{ruta_sudoers} pero la sonda al "
                               "ayudante no respondió: la instalación "
                               "está incompleta o la regla no autoriza "
                               "a este usuario")
    if valor["via"] == "ninguna" and cual("pkexec"):
        valor = {"via": "pkexec", "verificada": False,
                 "motivo": "pkexec presente, sin verificar (sondearlo "
                           "abriría un diálogo de contraseña); se "
                           "verifica al ejecutar la primera acción "
                           "delante de la PC",
                 "ayudante": ayudante, "acciones": acciones()}
    _CACHE_VIA.update({"ts": ahora, "valor": valor})
    return dict(valor)


# ---------------------------------------------------------------- ejecución

def ejecutar(base_dir, cuenta, raiz_id, accion, params, ejecutar=None,
             reloj=None, auditar=None, detectar=None):
    """Ejecuta UNA acción ya aprobada (la orden la crea quien llama,
    tras la decisión humana). Devuelve el resultado; lanza ErrorRaiz
    solo en los fallos previos (validación, ritmo, sin vía): cuando
    el ayudante llegó a pronunciarse, su respuesta ES el resultado.
    """
    ejecutar = ejecutar or _ejecutar_defecto
    config = cargar_config(base_dir)
    v = validar_peticion(accion, params, config)
    comprobar_ritmo(base_dir, cuenta, reloj=reloj)
    via = (detectar or (lambda: detectar_via(base_dir,
                                             ejecutar=ejecutar,
                                             reloj=reloj)))()
    if via["via"] == "ninguna":
        raise ErrorRaiz("intermediario de root no disponible: "
                        + via["motivo"])
    peticion = {"v": VERSION, "accion": accion, "params": params or {},
                "huella": v["huella"], "cuenta": cuenta,
                "raiz": raiz_id}
    if via["via"] == "sudoers":
        comando = ["sudo", "-n", "--", via["ayudante"], "ejecutar"]
    else:
        comando = ["pkexec", "--disable-internal-agent",
                   via["ayudante"], "ejecutar"]
    t0 = (reloj or time.time)()
    rc, out, err = ejecutar(comando, entrada=json.dumps(peticion),
                            timeout_s=v_timeout(REGISTRO[accion]) + 30)
    dur = round((reloj or time.time)() - t0, 2)
    anotar_ejecucion(base_dir, cuenta, accion, reloj=reloj)
    try:
        resp = json.loads((out or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        resp = {"ok": False,
                "motivo": "el ayudante no respondió con un JSON válido"
                          + (f" (rc {rc})" if rc else "")
                          + (f": {err.strip()[:200]}" if err.strip()
                             else "")}
    resultado = {"ok": bool(resp.get("ok")), "rc": resp.get("rc"),
                 "salida": resp.get("salida") or "",
                 "motivo": resp.get("motivo") or "",
                 "duracion_s": resp.get("duracion_s", dur),
                 "argv": v["argv"], "nivel": v["nivel"],
                 "huella": v["huella"], "via": via["via"]}
    if auditar is not None:
        try:
            auditar(accion, v["huella"],
                    "ok" if resultado["ok"] else "error",
                    cuenta=cuenta,
                    motivo=resultado["motivo"] or None,
                    duracion_s=resultado["duracion_s"])
        except Exception:
            pass
    return resultado


def v_timeout(spec):
    return int(spec.get("timeout_s") or 120)


# ---------------------------------------------------------------- reglas

def componer_sudoers(usuario, config):
    """El texto de la regla de sudoers, compuesto desde el registro.

    Valida ANTES de componer nada: si la lista del dueño trae un
    nombre inválido, lanza ErrorRaiz y no se compone ni una línea.
    La regla autoriza al ayudante por su ruta exacta y sin
    comodines: sudoers acota el programa; los argumentos los acotan
    el registro y la doble validación (sudoers no puede expresar
    «uno de estos paquetes» sin comodines, y un comodín sobre
    argumentos es una puerta conocida)."""
    if not isinstance(usuario, str) or not re.match(
            r"^[a-z_][a-z0-9_-]*$", usuario):
        raise ErrorRaiz(f"nombre de usuario no válido: {usuario!r}")
    malas = [n for n in (config or {}).get("unidades", {})
             if not RX_UNIDAD.match(n)]
    if (config or {}).get("degradada"):
        raise ErrorRaiz(
            "la lista del dueño trae entradas inválidas que se "
            "descartaron al leerla; arréglalas en "
            f"{ARCHIVO_CONFIG} antes de generar las reglas")
    if malas:
        raise ErrorRaiz("unidades con nombre inválido en la lista "
                        f"del dueño: {malas}")
    lineas = [
        "# Growi Bridge — intermediario de root (Fase 6).",
        "# Generado por instalar-raiz.py desde el registro de raiz.py.",
        "# Autoriza SOLO al ayudante, por su ruta exacta y sin",
        "# comodines: qué acciones existen y con qué argumentos lo",
        "# acotan el registro cerrado y la doble validación del",
        "# ayudante. La app jamás escribe este archivo: lo instala",
        "# el dueño, en su terminal, con su contraseña.",
        f"{usuario} ALL=(root) NOPASSWD: {AYUDANTE_INSTALADO}",
        "",
    ]
    return "\n".join(lineas)


def comandos_instalacion(ruta_reglas="growi-bridge.sudoers",
                         ruta_ayudante="growi-ayudante.py"):
    """Los comandos exactos que el dueño pega en SU terminal."""
    return [
        f"sudo install -m 0755 -o root -g root {ruta_ayudante} "
        f"{AYUDANTE_INSTALADO}",
        f"sudo install -m 0440 -o root -g root {ruta_reglas} "
        f"{ARCHIVO_SUDOERS}",
        f"sudo visudo -cf {ARCHIVO_SUDOERS}",
    ]


def validar_sudoers(texto, ejecutar=None, cual=None):
    """Verifica el texto compuesto con `visudo -cf` si está.
    Devuelve (ok, detalle). Sin visudo: (None, motivo)."""
    cual = cual or shutil.which
    if not cual("visudo"):
        return None, "visudo no está en esta máquina: no se verificó"
    ejecutar = ejecutar or _ejecutar_defecto
    import tempfile
    fd, ruta = tempfile.mkstemp(prefix="growi-sudoers-", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
        rc, out, err = ejecutar(["visudo", "-cf", ruta], timeout_s=10)
        detalle = (out or err or "").strip()
        return rc == 0, detalle or f"visudo rc={rc}"
    finally:
        try:
            os.unlink(ruta)
        except OSError:
            pass

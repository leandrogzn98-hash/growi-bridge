# -*- coding: utf-8 -*-
"""Canales completos (Fase 5 del plan multi-Muse): la capa común.

El dueño manda y aprueba desde fuera. Esta capa no sabe nada de ningún
transporte concreto: emparejamiento con código de un solo uso, entrada
exactamente-una-vez, clasificación del mensaje (decisión / consulta /
encargo), gramática estricta de decisiones, ritmo, bandeja saliente
(guardar antes que enviar), órdenes de decisión entre carriles con
exactamente-una-vez por ``approval_id`` y el destino ``canal`` de
``avisos.py``. Los adaptadores (``canal_telegram.py`` y, como diseño,
los de WhatsApp) solo traducen: reciben mensajes normalizados y
transmiten texto al chat emparejado.

Reglas que esta capa no negocia (diseño §1 y §17 bis):
- El canal crea TAREAS, nunca comandos: todo encargo pasa por las
  puertas de siempre del runner.
- Sin emparejamiento no se procesa nada de nadie; tras emparejar, solo
  la identidad certificada por el transporte.
- Las decisiones van a ``decidir_aprobacion`` (inyectado por el
  monolito vía efectos); un pedido R3 NO ofrecido jamás se le pasa al
  circuito desde aquí (B6): el circuito lo cerraría, no solo lo
  denegaría.
- Guardar primero: el registro del canal anota antes de crear nada, y
  la bandeja saliente escribe el archivo antes de transmitir.
- Los secretos no pasan por aquí: los adaptadores los piden a la
  bóveda en el momento de usarlos, y todo texto de error se sanea con
  ``resumen_error`` antes de llegar a un log o al registro.
"""

import contextlib
import hashlib
import json
import os
import re
import secrets
import threading
import time
import uuid
from pathlib import Path

VERSION = 1
TRANSPORTES = ("telegram", "whatsapp-oficial", "whatsapp")

# Alfabeto sin ambiguos (sin 0/1/I/L/O): códigos de emparejamiento y
# códigos cortos de pedido salen de aquí.
ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODIGO_N = 8                      # emparejamiento
CODIGO_VIGENCIA_S = 600           # 10 minutos
CODIGO_MAX_INTENTOS = 5
CORTO_N = 4                       # alias corto de un pedido

LIMITE_SALIENTES_INFO = 20        # cortafuegos de salida (§7.5)
MAX_INTENTOS_SALIENTE = 5
VISTOS_MAX = 200
HOLGURA_MARCA_AGUA_S = 300        # 5 min de holgura (§5.5)
A_MEDIAS_S = 300                  # decisión a medias: 5 min (§6.3)
LIDER_VIEJO_S = 60                # latido de liderazgo viejo (§2.2)
NO_TEXTO_RESPUESTA_S = 3600       # «solo texto» como mucho 1/hora

AVISOS_INFO_DEF = ["division_hecha", "encargo_terminado",
                   "subtarea_fallida", "prueba_fisica_inicio",
                   "canal_prueba"]
LIMITES_DEF = {"mensajes_hora": 30, "encargos_hora": 10,
               "consultas_hora": 12}

TOPE_REGISTRO_BYTES = 5 * 1024 * 1024
ESTADOS_ENCARGO_TERMINALES = ("terminado", "terminado_con_fallos",
                              "cerrado", "fallido", "cancelado")

_LOCKS = {}
_LOCKS_MU = threading.Lock()


class ErrorCanal(ValueError):
    """Error de la capa de canales (validación o estado incoherente)."""


# ---------------------------------------------------------------------------
# Locks y escritura atómica (el patrón de la casa: avisos.py / relevo.py)
# ---------------------------------------------------------------------------

def _lock_de(ruta):
    clave = str(ruta)
    with _LOCKS_MU:
        if clave not in _LOCKS:
            _LOCKS[clave] = threading.RLock()
        return _LOCKS[clave]


@contextlib.contextmanager
def _bloqueo(ruta_lock, espera_s=10.0):
    """Lock entre procesos con ruptura de huérfano a los 15 s. Sin lock
    tras la espera se sigue sin él: el canal nunca tumba a su llamador."""
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


def _escribir_json(ruta, datos):
    """tmp + os.replace: ningún lector ve un JSON a medias."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def _leer_json(ruta):
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Rutas (todo vive en la carpeta compartida por usuario)
# ---------------------------------------------------------------------------

def ruta_config(base_dir):
    return Path(base_dir) / "canales.json"


def ruta_estado(base_dir):
    return Path(base_dir) / "canal-estado.json"


def ruta_registro(base_dir):
    return Path(base_dir) / "canal-registro.jsonl"


def ruta_pedidos(base_dir):
    return Path(base_dir) / "canal-pedidos.json"


def ruta_lider(base_dir):
    return Path(base_dir) / "canal-lider.json"


def dir_salientes(base_dir):
    return Path(base_dir) / "canal-salientes"


def dir_decisiones(base_dir):
    return Path(base_dir) / "canal-decisiones"


def ruta_entrantes(base_dir):
    return Path(base_dir) / "canal-entrantes.jsonl"


# ---------------------------------------------------------------------------
# Saneado de errores e identidades (ningún secreto llega a un log: I15)
# ---------------------------------------------------------------------------

_RE_TOKEN_BOT = re.compile(r"\b\d{5,12}:[A-Za-z0-9_-]{25,}\b")
_RE_BEARER = re.compile(r"(?i)(bearer|token|secret)\s*[:=]\s*\S+")


def resumen_error(e, secretos_conocidos=()):
    """El error en una línea segura para logs y registro: tipo y, si es
    un ErrorCanal o trae código HTTP, su texto ya saneado. Se borra
    cualquier patrón con forma de token de bot y cualquier secreto
    conocido que venga en el texto (la URL de la API de Telegram LLEVA
    el token: una excepción de urllib puede filtrarlo)."""
    if isinstance(e, ErrorCanal):
        texto = str(e)
    elif isinstance(e, str):
        texto = e
    else:
        texto = f"{type(e).__name__}"
    for s in secretos_conocidos or ():
        if s:
            texto = texto.replace(str(s), "•••")
    texto = _RE_TOKEN_BOT.sub("•••", texto)
    texto = _RE_BEARER.sub(r"\1: •••", texto)
    return " ".join(texto.split())[:200]


def enmascarar(identidad):
    """La identidad emparejada para pantallas y registros: nunca entera."""
    s = str(identidad or "")
    if len(s) <= 4:
        return "•••"
    return "•••" + s[-4:]


def _resumen_texto(texto, n=80):
    """Resumen de un mensaje para el registro (como el resumir() de
    permission-layer.py): el texto íntegro vive en la tarea, no aquí."""
    s = " ".join(str(texto or "").split())
    return s[:n]


# ---------------------------------------------------------------------------
# Configuración: canales.json (patrón cuentas.py: lock + revisión optimista)
# ---------------------------------------------------------------------------

def _transporte_vacio():
    return {"identidad": None, "emparejado_ts": 0, "revocado_ts": 0,
            "codigo": None, "config": {}}


def config_vacia():
    return {"version": VERSION, "revision": 0, "activo": None,
            "transportes": {}, "avisos_info": list(AVISOS_INFO_DEF),
            "limites": dict(LIMITES_DEF)}


def cargar_config(base_dir):
    """Lectura tolerante: ausente o corrupto ⇒ configuración vacía (sin
    canal activo). Nunca lanza: un JSON roto no tumba el arranque."""
    datos = _leer_json(ruta_config(base_dir))
    if datos is None:
        return config_vacia()
    cfg = config_vacia()
    rev = datos.get("revision")
    cfg["revision"] = rev if isinstance(rev, int) \
        and not isinstance(rev, bool) else 0
    if datos.get("activo") in TRANSPORTES:
        cfg["activo"] = datos["activo"]
    trs = datos.get("transportes")
    if isinstance(trs, dict):
        for nombre, t in trs.items():
            if nombre in TRANSPORTES and isinstance(t, dict):
                base_t = _transporte_vacio()
                if isinstance(t.get("identidad"), str) and t["identidad"]:
                    base_t["identidad"] = t["identidad"]
                for k in ("emparejado_ts", "revocado_ts"):
                    if isinstance(t.get(k), (int, float)):
                        base_t[k] = t[k]
                if isinstance(t.get("codigo"), dict):
                    base_t["codigo"] = t["codigo"]
                if isinstance(t.get("config"), dict):
                    base_t["config"] = t["config"]
                cfg["transportes"][nombre] = base_t
    if isinstance(datos.get("avisos_info"), list):
        cfg["avisos_info"] = [x for x in datos["avisos_info"]
                              if isinstance(x, str)]
    if isinstance(datos.get("limites"), dict):
        for k, v in datos["limites"].items():
            if k in cfg["limites"] and isinstance(v, int) \
                    and not isinstance(v, bool) and v > 0:
                cfg["limites"][k] = v
    return cfg


def guardar_config(base_dir, cfg):
    """Guarda con control optimista por revisión (como cuentas.guardar):
    si otro proceso guardó antes, se rechaza para no perder su cambio.
    Al guardar, la revisión sube en 1 (también en el dict pasado)."""
    base_dir = Path(base_dir)
    with _bloqueo(base_dir / "canales.json.lock"):
        en_disco = cargar_config(base_dir)
        if en_disco["revision"] != cfg.get("revision", 0):
            raise ErrorCanal(
                "canales.json cambió en disco (revisión "
                f"{en_disco['revision']} ≠ {cfg.get('revision', 0)}); "
                "recarga antes de guardar")
        cfg["revision"] = en_disco["revision"] + 1
        _escribir_json(ruta_config(base_dir), cfg)
    return cfg


def _mutar_config(base_dir, fn):
    """Carga → aplica fn(cfg) → guarda, con UN reintento si la revisión
    se movió entre tanto (las mutaciones del canal son frecuentes y
    pequeñas: emparejar, intentos, revocar)."""
    for _ in range(2):
        cfg = cargar_config(base_dir)
        res = fn(cfg)
        try:
            guardar_config(base_dir, cfg)
            return res
        except ErrorCanal:
            continue
    raise ErrorCanal("canales.json no dejó de cambiar; no se guardó")


def transporte_cfg(cfg, nombre):
    """La entrada de un transporte en la configuración (con sus
    valores por defecto si aún no existe)."""
    t = (cfg.get("transportes") or {}).get(nombre)
    if not isinstance(t, dict):
        t = _transporte_vacio()
        cfg.setdefault("transportes", {})[nombre] = t
    return t


def identidad_de(cfg, transporte):
    t = (cfg.get("transportes") or {}).get(transporte) or {}
    return t.get("identidad")


def emparejado(cfg, transporte):
    return bool(identidad_de(cfg, transporte))


def codigo_vigente(cfg, transporte, reloj=None):
    """¿Hay un código de emparejamiento dentro de su ventana? Es la
    única situación en la que el canal escucha sin estar emparejado:
    sin esta puerta, el ciclo del líder no recibiría nunca el código
    y emparejar sería imposible."""
    t = ((cfg or {}).get("transportes") or {}).get(transporte) or {}
    cod = t.get("codigo") or {}
    vence = cod.get("vence_ts")
    if not isinstance(vence, (int, float)) or isinstance(vence, bool):
        return False
    return vence > (reloj or time.time)()


# ---------------------------------------------------------------------------
# Estado de máquina: canal-estado.json (un solo escritor: el líder)
# ---------------------------------------------------------------------------

def _transporte_estado_vacio():
    return {"cursor": {}, "bot_id": None, "vistos": [], "en_proceso": {},
            "marca_agua_ts": 0, "ultimo_entrante_ts": 0,
            "no_texto_resp_ts": 0}


def estado_vacio():
    return {"version": VERSION, "transportes": {},
            "ritmo": {"encargos": [], "consultas": [], "mensajes": []},
            "supervision": {"acompanante_avisado_ts": 0,
                            "relanzamientos": []}}


def _estado_inicial(base_dir, reloj=None):
    """Reconstrucción segura de un estado perdido o corrupto (B4): los
    cursores nacen AL FINAL del archivo de entrantes (la historia no se
    reprocesa jamás) y la marca de agua nace ahora."""
    ahora = (reloj or time.time)()
    est = estado_vacio()
    ent = ruta_entrantes(base_dir)
    try:
        tam = ent.stat().st_size if ent.exists() else 0
    except OSError:
        tam = 0
    for nombre in TRANSPORTES:
        t = _transporte_estado_vacio()
        t["cursor"] = {"generacion": 0, "byte": tam}
        t["marca_agua_ts"] = ahora
        est["transportes"][nombre] = t
    return est


def cargar_estado(base_dir, reloj=None):
    datos = _leer_json(ruta_estado(base_dir))
    if datos is None or not isinstance(datos.get("transportes"), dict):
        return _estado_inicial(base_dir, reloj=reloj)
    est = estado_vacio()
    for nombre, t in datos["transportes"].items():
        if nombre in TRANSPORTES and isinstance(t, dict):
            base_t = _transporte_estado_vacio()
            if isinstance(t.get("cursor"), dict):
                base_t["cursor"] = t["cursor"]
            if isinstance(t.get("bot_id"), (str, int)):
                base_t["bot_id"] = t["bot_id"]
            if isinstance(t.get("vistos"), list):
                base_t["vistos"] = [str(x) for x in t["vistos"]][-VISTOS_MAX:]
            if isinstance(t.get("en_proceso"), dict):
                base_t["en_proceso"] = {
                    str(k): v for k, v in t["en_proceso"].items()
                    if isinstance(v, dict)}
            for k in ("marca_agua_ts", "ultimo_entrante_ts",
                      "no_texto_resp_ts"):
                if isinstance(t.get(k), (int, float)):
                    base_t[k] = t[k]
            est["transportes"][nombre] = base_t
    if isinstance(datos.get("ritmo"), dict):
        for k in est["ritmo"]:
            if isinstance(datos["ritmo"].get(k), list):
                est["ritmo"][k] = [x for x in datos["ritmo"][k]
                                   if isinstance(x, (int, float))]
    if isinstance(datos.get("supervision"), dict):
        sup = datos["supervision"]
        if isinstance(sup.get("acompanante_avisado_ts"), (int, float)):
            est["supervision"]["acompanante_avisado_ts"] = \
                sup["acompanante_avisado_ts"]
        if isinstance(sup.get("relanzamientos"), list):
            est["supervision"]["relanzamientos"] = [
                x for x in sup["relanzamientos"]
                if isinstance(x, (int, float))]
    return est


def guardar_estado(base_dir, est):
    _escribir_json(ruta_estado(base_dir), est)


def transporte_estado(est, nombre):
    t = (est.get("transportes") or {}).get(nombre)
    if not isinstance(t, dict):
        t = _transporte_estado_vacio()
        est.setdefault("transportes", {})[nombre] = t
    return t


# ---------------------------------------------------------------------------
# Registro del canal (auditoría de transporte: guardar primero)
# ---------------------------------------------------------------------------

def _rotar_registro(ruta):
    try:
        if ruta.exists() and ruta.stat().st_size >= TOPE_REGISTRO_BYTES:
            destino = ruta.with_name(ruta.name + ".1")
            try:
                destino.unlink()
            except OSError:
                pass
            os.replace(str(ruta), str(destino))
    except OSError:
        pass


def anotar(base_dir, evento, reloj=None, **campos):
    """Una línea en canal-registro.jsonl. Nunca lanza: si el registro
    falla, el llamador decide (a la entrada, un registro que falla
    significa NO procesar: principio 5). Devuelve True si se escribió."""
    base_dir = Path(base_dir)
    linea = {"ts": (reloj or time.time)(), "evento": evento}
    linea.update(campos)
    try:
        with _bloqueo(base_dir / "canal-registro.jsonl.lock"):
            _rotar_registro(ruta_registro(base_dir))
            with open(ruta_registro(base_dir), "a",
                      encoding="utf-8") as f:
                f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def leer_registro(base_dir, n=100):
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


# ---------------------------------------------------------------------------
# Emparejamiento y revocación (§4)
# ---------------------------------------------------------------------------

def _hash_codigo(transporte, codigo):
    return hashlib.sha256(f"{transporte}:{codigo}".encode("utf-8")).hexdigest()


def forma_de_codigo(texto):
    """¿Tiene el mensaje EXACTAMENTE la forma de un código? (8 caracteres
    del alfabeto sin ambiguos, nada más). Solo eso gasta intentos (I1):
    un «hola» o un /start de un curioso no matan el código del dueño."""
    s = " ".join(str(texto or "").split()).upper()
    return len(s) == CODIGO_N and all(c in ALFABETO for c in s)


def generar_codigo(base_dir, transporte, reloj=None):
    """Genera el código de emparejamiento y guarda SOLO su SHA-256 (con
    el transporte como sal). Generar uno nuevo mata el anterior.
    Devuelve el código en claro: es para mostrarlo en la app una vez."""
    if transporte not in TRANSPORTES:
        raise ErrorCanal(f"transporte desconocido: {transporte}")
    ahora = (reloj or time.time)()
    codigo = "".join(secrets.choice(ALFABETO) for _ in range(CODIGO_N))

    def _poner(cfg):
        t = transporte_cfg(cfg, transporte)
        t["codigo"] = {"sha256": _hash_codigo(transporte, codigo),
                       "creado_ts": ahora, "vence_ts": ahora + CODIGO_VIGENCIA_S,
                       "intentos": 0}
        return codigo

    _mutar_config(base_dir, _poner)
    anotar(base_dir, "codigo_generado", reloj=reloj, transporte=transporte)
    return codigo


def intentar_emparejar(base_dir, transporte, remitente, texto, reloj=None):
    """El baile del §4.1. Devuelve un dict con «resultado»:
    - "no_es_codigo": el texto no tiene forma de código (no es un
      intento; el llamador lo trata como mensaje de un desconocido).
    - "sin_codigo": forma de código pero no hay código vivo.
    - "emparejado": coincidió; la identidad queda atada y el código
      quemado.
    - "rechazado": no coincidió; el intento quedó contado (a los 5 el
      código muere). No se responde nada hacia fuera."""
    ahora = (reloj or time.time)()
    if not forma_de_codigo(texto):
        return {"resultado": "no_es_codigo"}
    candidato = " ".join(str(texto).split()).upper()
    salida = {}

    def _intentar(cfg):
        t = transporte_cfg(cfg, transporte)
        cod = t.get("codigo")
        if not isinstance(cod, dict) or ahora > (cod.get("vence_ts") or 0):
            if isinstance(cod, dict):
                t["codigo"] = None  # vencido: muere en silencio
            salida["resultado"] = "sin_codigo"
            return salida
        if _hash_codigo(transporte, candidato) == cod.get("sha256"):
            t["identidad"] = str(remitente)
            t["emparejado_ts"] = ahora
            t["codigo"] = None
            salida["resultado"] = "emparejado"
            salida["identidad"] = str(remitente)
            return salida
        cod["intentos"] = int(cod.get("intentos") or 0) + 1
        salida["intentos"] = cod["intentos"]
        if cod["intentos"] >= CODIGO_MAX_INTENTOS:
            t["codigo"] = None
            salida["codigo_muerto"] = True
        salida["resultado"] = "rechazado"
        return salida

    _mutar_config(base_dir, _intentar)
    if salida["resultado"] == "emparejado":
        anotar(base_dir, "emparejado", reloj=reloj, transporte=transporte,
               identidad=enmascarar(remitente))
    elif salida["resultado"] == "rechazado":
        anotar(base_dir, "codigo_rechazado", reloj=reloj,
               transporte=transporte, intentos=salida.get("intentos"))
    return salida


def revocar(base_dir, transporte, reloj=None):
    """Revocación en un clic (§4.2): la identidad se lee de canales.json
    en cada mensaje, así que el efecto es inmediato, sin cachés."""
    ahora = (reloj or time.time)()

    def _revocar(cfg):
        t = transporte_cfg(cfg, transporte)
        t["identidad"] = None
        t["codigo"] = None
        t["revocado_ts"] = ahora
        return True

    _mutar_config(base_dir, _revocar)
    anotar(base_dir, "revocado", reloj=reloj, transporte=transporte)


def invalidar_por_cambio_bot(base_dir, transporte, reloj=None):
    """El token pegado es de OTRO bot (I3): sus update_id no significan
    nada aquí. Se invalida el emparejamiento y el llamador reinicia el
    cursor y la dedup de ese transporte."""
    def _inv(cfg):
        t = transporte_cfg(cfg, transporte)
        t["identidad"] = None
        t["codigo"] = None
        t["revocado_ts"] = (reloj or time.time)()
        return True

    _mutar_config(base_dir, _inv)
    anotar(base_dir, "bot_cambiado", reloj=reloj, transporte=transporte)


# ---------------------------------------------------------------------------
# Liderazgo con época (§2.2, corrección B3)
# ---------------------------------------------------------------------------

def lider_actual(base_dir):
    return _leer_json(ruta_lider(base_dir))


def tomar_liderazgo(base_dir, carril, pid, reloj=None):
    """Toma el liderazgo bajo lock: la época crece en cada toma. El
    líder relee su época antes de cada acción con efecto (soy_lider):
    un líder depuesto a mitad de ciclo se detiene en el acto."""
    ahora = (reloj or time.time)()
    base_dir = Path(base_dir)
    with _bloqueo(base_dir / "canal-lider.json.lock"):
        actual = lider_actual(base_dir) or {}
        epoca = int(actual.get("epoca") or 0) + 1
        _escribir_json(ruta_lider(base_dir),
                       {"carril": carril, "pid": pid, "epoca": epoca,
                        "latido_ts": ahora})
    return epoca


def latir(base_dir, carril, epoca, reloj=None):
    """Renueva el latido si la época sigue siendo la mía. El latido lo
    escribe el mismo bucle que procesa, nunca un hilo aparte."""
    actual = lider_actual(base_dir)
    if not actual or actual.get("carril") != carril \
            or actual.get("epoca") != epoca:
        return False
    _escribir_json(ruta_lider(base_dir),
                   dict(actual, latido_ts=(reloj or time.time)()))
    return True


def soy_lider(base_dir, carril, epoca):
    actual = lider_actual(base_dir)
    return bool(actual) and actual.get("carril") == carril \
        and actual.get("epoca") == epoca


def liderazgo_vencido(base_dir, reloj=None):
    actual = lider_actual(base_dir)
    if not actual:
        return True
    lat = actual.get("latido_ts")
    if not isinstance(lat, (int, float)):
        return True
    return (reloj or time.time)() - lat > LIDER_VIEJO_S


def paso_liderazgo(base_dir, carril, pid, reloj=None):
    """Un paso del servicio: si soy el líder renuevo el latido; si el
    liderazgo está vencido lo tomo; si lo tiene otro, sigo de seguidor.
    Devuelve (es_lider, epoca|None)."""
    actual = lider_actual(base_dir)
    if actual and actual.get("carril") == carril \
            and isinstance(actual.get("epoca"), int):
        epoca = actual["epoca"]
        if latir(base_dir, carril, epoca, reloj=reloj):
            return True, epoca
        return False, None
    if liderazgo_vencido(base_dir, reloj=reloj):
        return True, tomar_liderazgo(base_dir, carril, pid, reloj=reloj)
    return False, None


# ---------------------------------------------------------------------------
# Bandeja saliente (§7.5): guardar antes que enviar
# ---------------------------------------------------------------------------

def encolar_saliente(base_dir, tipo, texto, meta=None, nivel=None,
                     reloj=None):
    """Deja un mensaje en canal-salientes/ (tmp + replace). Devuelve el
    mensaje (dict) o None si se descartó: con más de
    LIMITE_SALIENTES_INFO esperando, los «info» nuevos no entran (los
    «accion» nunca se descartan). El aviso original sigue en su
    registro: la bandeja nunca es la única copia de nada."""
    base_dir = Path(base_dir)
    carpeta = dir_salientes(base_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    if nivel == "info":
        try:
            esperando = [p for p in carpeta.glob("*.json")
                         if p.is_file()]
        except OSError:
            esperando = []
        if len(esperando) > LIMITE_SALIENTES_INFO:
            return None
    ahora = (reloj or time.time)()
    mid = uuid.uuid4().hex[:8]
    nombre = f"{int(ahora * 1000)}-{mid}.json"
    mensaje = {"id": mid, "creado_ts": ahora, "tipo": tipo,
               "texto": str(texto), "meta": dict(meta or {}),
               "intentos": 0}
    _escribir_json(carpeta / nombre, mensaje)
    return mensaje


def salientes_pendientes(base_dir):
    """[(ruta, mensaje)] ordenados por creación (el nombre ya ordena)."""
    carpeta = dir_salientes(base_dir)
    salida = []
    try:
        rutas = sorted(carpeta.glob("*.json"))
    except OSError:
        return salida
    for ruta in rutas:
        if not ruta.is_file():
            continue
        datos = _leer_json(ruta)
        if datos is not None:
            salida.append((ruta, datos))
    return salida


def retirar_saliente(ruta):
    try:
        Path(ruta).unlink()
        return True
    except OSError:
        return False


def registrar_intento_saliente(base_dir, ruta, reloj=None):
    """Un intento de transmisión fallido: suma el contador en el propio
    archivo; al quinto, el mensaje se mueve a fallidos/ y se anota.
    Devuelve "reintentar" | "fallido"."""
    ruta = Path(ruta)
    datos = _leer_json(ruta) or {}
    datos["intentos"] = int(datos.get("intentos") or 0) + 1
    if datos["intentos"] >= MAX_INTENTOS_SALIENTE:
        carpeta = dir_salientes(base_dir) / "fallidos"
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            _escribir_json(carpeta / ruta.name, datos)
            ruta.unlink()
        except OSError:
            pass
        anotar(base_dir, "error_transporte", reloj=reloj,
               motivo="saliente agotó sus intentos",
               saliente=datos.get("id"))
        return "fallido"
    try:
        _escribir_json(ruta, datos)
    except OSError:
        pass
    return "reintentar"


# ---------------------------------------------------------------------------
# Resumen de cierre encolado (§7.2): la marca que suprime el aviso duplicado
# ---------------------------------------------------------------------------

def marcar_resumen_encolado(base_dir, raiz, reloj=None):
    """Anota que el resumen de cierre de esta raíz YA salió (o va a
    salir) por el canal: el aviso «encargo_terminado» no debe
    duplicarlo. Marca en archivo (el barrido que cierra y el destino
    que despacha pueden no ser el mismo instante)."""
    base_dir = Path(base_dir)
    try:
        with _bloqueo(base_dir / "canal-resumenes.jsonl.lock"):
            with open(base_dir / "canal-resumenes.jsonl", "a",
                      encoding="utf-8") as f:
                f.write(json.dumps(
                    {"raiz": raiz, "ts": (reloj or time.time)()}) + "\n")
        return True
    except Exception:
        return False


def resumen_encolado(base_dir, raiz, ventana_s=3600, reloj=None):
    if not raiz:
        return False
    ahora = (reloj or time.time)()
    # Un resumen aún en la bandeja también cuenta como encolado.
    for _ruta, datos in salientes_pendientes(base_dir):
        if datos.get("tipo") == "resumen" \
                and (datos.get("meta") or {}).get("raiz") == raiz:
            return True
    try:
        lineas = (Path(base_dir) / "canal-resumenes.jsonl").read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for linea in reversed(lineas[-200:]):
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("raiz") == raiz \
                and isinstance(d.get("ts"), (int, float)) \
                and ahora - d["ts"] < ventana_s:
            return True
    return False


# ---------------------------------------------------------------------------
# Pedidos ofrecidos: canal-pedidos.json (§6.1 y §6.2, correcciones B2 e I5)
# ---------------------------------------------------------------------------

def _pedidos_vacio():
    return {"version": VERSION, "pedidos": {}, "decision_en_curso": None}


def cargar_pedidos(base_dir):
    datos = _leer_json(ruta_pedidos(base_dir))
    if datos is None or not isinstance(datos.get("pedidos"), dict):
        return _pedidos_vacio()
    salida = _pedidos_vacio()
    salida["pedidos"] = {k: v for k, v in datos["pedidos"].items()
                         if isinstance(v, dict)}
    if isinstance(datos.get("decision_en_curso"), dict):
        salida["decision_en_curso"] = datos["decision_en_curso"]
    return salida


@contextlib.contextmanager
def _con_pedidos(base_dir):
    """Carga canal-pedidos.json bajo su lock, cede el dict y lo guarda
    al salir: todas las mutaciones de pedidos pasan por aquí (los dos
    carriles ofrecen a la vez; el código corto nace bajo este lock)."""
    base_dir = Path(base_dir)
    with _bloqueo(base_dir / "canal-pedidos.json.lock"):
        datos = cargar_pedidos(base_dir)
        yield datos
        _escribir_json(ruta_pedidos(base_dir), datos)


def _codigo_corto_unico(pedidos):
    """4 caracteres del alfabeto sin ambiguos, únicos entre los pedidos
    pendientes ofrecidos, y nunca «solo dígitos» (I5: «aplazar 1024»
    sería ambiguo entre código y minutos). Se llama con el lock tomado."""
    usados = {e.get("codigo") for e in pedidos.values()
              if e.get("ofrecido") and not e.get("resuelto")}
    while True:
        codigo = "".join(secrets.choice(ALFABETO) for _ in range(CORTO_N))
        if codigo.isdigit() or codigo in usados:
            continue
        return codigo


def ofrecer_pedido(base_dir, row, carril, reloj=None):
    """Anota un pedido en canal-pedidos.json. Idempotente por
    approval_id (B2): si ya existe, se conserva su código y su
    mensaje_id y no se vuelve a ofrecer. Devuelve (entrada, creada).

    R1/R2: ofrecido con código corto. R3: anotado con ofrecido=False,
    sin código: solo se notifica (§7.3), jamás es objetivo decidible."""
    ahora = (reloj or time.time)()
    aid = row["approval_id"]
    with _con_pedidos(base_dir) as datos:
        pedidos = datos["pedidos"]
        if aid in pedidos:
            return dict(pedidos[aid]), False
        nivel = row.get("nivel")
        ofrecido = nivel in ("R1", "R2")
        entrada = {
            "carril": carril,
            "nivel": nivel,
            "raiz": row.get("raiz"),
            "tarea": row.get("tarea"),
            "motivo": str(row.get("motivo") or "")[:160],
            "codigo": _codigo_corto_unico(pedidos) if ofrecido else None,
            "vence_ts": row.get("vence_ts"),
            "ofrecido_ts": ahora,
            "mensaje_id": None,
            "transmitido_ts": None,
            "ofrecido": ofrecido,
            "resuelto": None,
        }
        pedidos[aid] = entrada
        return dict(entrada), True


def marcar_transmitido(base_dir, approval_id, mensaje_id, reloj=None):
    """El líder transmitió el mensaje del pedido (o su notificación
    R3): ese mensaje_id es el que permite resolver por cita (§6.2)."""
    with _con_pedidos(base_dir) as datos:
        entrada = datos["pedidos"].get(approval_id)
        if entrada is None:
            return False
        entrada["mensaje_id"] = str(mensaje_id)
        entrada["transmitido_ts"] = (reloj or time.time)()
        return True


def reconciliar_pedidos(base_dir, carril, estado_de, reloj=None):
    """Cada carril contrasta SUS entradas contra SU cola (B2): lo que
    ya no esté «pendiente» (decidido en la app, vencido, aplicado por
    una orden) se marca resuelto y deja de contar como objetivo. El
    ``estado_de(approval_id)`` inyectado devuelve el estado de la fila
    o None si no se sabe (entonces no se toca). Nunca se abre la base
    del otro carril."""
    marcados = 0
    with _con_pedidos(base_dir) as datos:
        for aid, entrada in datos["pedidos"].items():
            if entrada.get("carril") != carril or entrada.get("resuelto"):
                continue
            try:
                estado = estado_de(aid)
            except Exception:
                estado = None
            if estado and estado != "pendiente":
                entrada["resuelto"] = estado
                marcados += 1
    return marcados


def pedidos_vigentes(datos_pedidos, recepcion_ts=None):
    """Los objetivos VÁLIDOS de una decisión (§6.2): ofrecidos, no
    resueltos y YA transmitidos antes de la recepción del mensaje
    entrante. Un pedido que el dueño aún no ha podido ver no se decide
    «a ciegas» por un «sí» que venía de antes."""
    salida = {}
    for aid, e in (datos_pedidos.get("pedidos") or {}).items():
        if not e.get("ofrecido") or e.get("resuelto"):
            continue
        if e.get("mensaje_id") is None:
            continue
        if recepcion_ts is not None:
            tt = e.get("transmitido_ts")
            if not isinstance(tt, (int, float)) or tt > recepcion_ts:
                continue
        salida[aid] = e
    return salida


def resolver_objetivo(datos_pedidos, cita_id=None, codigo=None,
                      recepcion_ts=None):
    """Resolución en el orden del §6.2 y en ningún otro: cita, código,
    único pendiente. Devuelve {"approval_id", "via", "validos"}; con
    ambigüedad o vacío, approval_id es None y NO se decide nada."""
    validos = pedidos_vigentes(datos_pedidos, recepcion_ts=recepcion_ts)
    if cita_id is not None:
        for aid, e in validos.items():
            if str(e.get("mensaje_id")) == str(cita_id):
                return {"approval_id": aid, "via": "cita",
                        "validos": validos}
    if codigo:
        for aid, e in validos.items():
            if e.get("codigo") == codigo:
                return {"approval_id": aid, "via": "codigo",
                        "validos": validos}
    if len(validos) == 1:
        aid = next(iter(validos))
        return {"approval_id": aid, "via": "unico", "validos": validos}
    return {"approval_id": None, "via": None, "validos": validos}


def objetivo_r3(datos_pedidos, cita_id=None):
    """¿La cita apunta a la NOTIFICACIÓN de un R3? Esos pedidos no se
    ofrecen (ofrecido=False) y no son decidibles por ningún camino;
    detectarlos sirve para responder «solo en la app» sin tocar el
    circuito (B6). Devuelve (approval_id, entrada) o None."""
    if cita_id is None:
        return None
    for aid, e in (datos_pedidos.get("pedidos") or {}).items():
        if e.get("ofrecido") or e.get("resuelto"):
            continue
        if e.get("mensaje_id") is not None \
                and str(e.get("mensaje_id")) == str(cita_id):
            return aid, e
    return None


# ---------------------------------------------------------------------------
# Decisión a medias (§6.3): dura 5 minutos y nunca sobrevive a un
# cambio de objetivo
# ---------------------------------------------------------------------------

def fijar_decision_en_curso(base_dir, datos_curso, reloj=None):
    datos_curso = dict(datos_curso)
    datos_curso["vence_ts"] = (reloj or time.time)() + A_MEDIAS_S
    with _con_pedidos(base_dir) as datos:
        datos["decision_en_curso"] = datos_curso
    return datos_curso


def decision_en_curso(base_dir, reloj=None):
    datos = cargar_pedidos(base_dir)
    curso = datos.get("decision_en_curso")
    if not isinstance(curso, dict):
        return None
    vence = curso.get("vence_ts")
    if not isinstance(vence, (int, float)) \
            or (reloj or time.time)() > vence:
        limpiar_decision_en_curso(base_dir)
        return None
    return curso


def limpiar_decision_en_curso(base_dir):
    with _con_pedidos(base_dir) as datos:
        datos["decision_en_curso"] = None


# ---------------------------------------------------------------------------
# Órdenes de decisión entre carriles (§6.4, corrección B1):
# exactamente-una-vez por approval_id, no por id de orden
# ---------------------------------------------------------------------------

def _ruta_orden(base_dir, orden_id):
    return dir_decisiones(base_dir) / f"{orden_id}.json"


def orden_abierta_para(base_dir, approval_id):
    """La orden en vuelo para este approval_id (creada y aún sin
    resultado leído), o None. Si ya la hay, el líder NO crea otra: la
    decisión del dueño se adjunta a la existente."""
    carpeta = dir_decisiones(base_dir)
    try:
        rutas = sorted(carpeta.glob("*.json"))
    except OSError:
        return None
    for ruta in rutas:
        datos = _leer_json(ruta)
        if datos and datos.get("approval_id") == approval_id:
            if resultado_orden(base_dir, datos.get("id")) is None:
                return datos
    return None


def crear_orden(base_dir, approval_id, decision, minutos, canal,
                reloj=None):
    """Deja la orden para el carril dueño del pedido. Devuelve
    (orden, creada): si ya había una en vuelo, se devuelve esa con
    creada=False y no se escribe nada."""
    existente = orden_abierta_para(base_dir, approval_id)
    if existente is not None:
        return existente, False
    orden = {"id": uuid.uuid4().hex[:12], "approval_id": approval_id,
             "decision": decision, "minutos": minutos, "canal": canal,
             "pedida_ts": (reloj or time.time)()}
    carpeta = dir_decisiones(base_dir)
    carpeta.mkdir(parents=True, exist_ok=True)
    _escribir_json(_ruta_orden(base_dir, orden["id"]), orden)
    return orden, True


def ordenes_pendientes(base_dir):
    """[(ruta, orden)] aún sin resultado, en orden de creación."""
    carpeta = dir_decisiones(base_dir)
    salida = []
    try:
        rutas = sorted(carpeta.glob("*.json"))
    except OSError:
        return salida
    for ruta in rutas:
        datos = _leer_json(ruta)
        if datos and resultado_orden(base_dir, datos.get("id")) is None:
            salida.append((ruta, datos))
    return salida


def tomar_claim(base_dir, approval_id, reloj=None):
    """Claim atómico del carril dueño antes de aplicar (os.O_EXCL): si
    ya existe, la aplicación ya la tomó alguien (este proceso antes de
    morir, típicamente) y no se aplica dos veces por esta vía."""
    carpeta = dir_decisiones(base_dir) / "consumidas"
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(carpeta / approval_id),
                     os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        return False
    try:
        os.write(fd, json.dumps(
            {"pid": os.getpid(), "ts": (reloj or time.time)()}
        ).encode("utf-8"))
    finally:
        os.close(fd)
    return True


def dejar_resultado(base_dir, orden, hecho, mensaje, reloj=None):
    carpeta = dir_decisiones(base_dir) / "hechas"
    carpeta.mkdir(parents=True, exist_ok=True)
    resultado = {"id": orden["id"], "approval_id": orden["approval_id"],
                 "hecho": bool(hecho), "mensaje": str(mensaje),
                 "ts": (reloj or time.time)()}
    _escribir_json(carpeta / f"{orden['id']}.json", resultado)
    return resultado


def resultado_orden(base_dir, orden_id):
    if not orden_id:
        return None
    return _leer_json(dir_decisiones(base_dir) / "hechas"
                      / f"{orden_id}.json")


def aplicar_orden_local(base_dir, orden, decidir_fn, reloj=None):
    """El carril dueño consume una orden (§6.4). ``decidir_fn`` es el
    decidir_aprobacion local del monolito: (approval_id, decision,
    canal, minutos) -> (hecho, mensaje).

    - Si ya hay resultado, se devuelve ese (nada se reaplica).
    - Se toma el claim; si ya existía pero no hay resultado, el
      proceso murió entre leer y aplicar: se resuelve llamando a
      decidir_fn igualmente, porque el contrato del circuito es que
      sobre una fila ya resuelta devuelve el camino de tardía SIN
      cambiar la decisión (B1). Si la fila sigue pendiente, la llamada
      la aplica: en ambos casos el resultado es el del circuito."""
    previo = resultado_orden(base_dir, orden["id"])
    if previo is not None:
        return previo
    tomar_claim(base_dir, orden["approval_id"], reloj=reloj)
    hecho, mensaje = decidir_fn(orden["approval_id"], orden["decision"],
                                orden.get("canal") or "telegram",
                                orden.get("minutos"))
    return dejar_resultado(base_dir, orden, hecho, mensaje, reloj=reloj)


def ordenes_para_confirmar(base_dir):
    """Órdenes con resultado cuyo aviso de confirmación aún no salió:
    el líder las confirma como mensaje aparte en el ciclo en que el
    resultado aparece (B3: la confirmación es asíncrona)."""
    carpeta = dir_decisiones(base_dir) / "hechas"
    salida = []
    try:
        rutas = sorted(carpeta.glob("*.json"))
    except OSError:
        return salida
    for ruta in rutas:
        if ruta.name.endswith(".confirmada.json"):
            continue
        datos = _leer_json(ruta)
        if datos and not (carpeta / f"{ruta.stem}.confirmada").exists():
            salida.append(datos)
    return salida


def marcar_confirmada(base_dir, orden_id):
    carpeta = dir_decisiones(base_dir) / "hechas"
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(carpeta / f"{orden_id}.confirmada"),
                     os.O_CREAT | os.O_WRONLY)
        os.close(fd)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Gramática de decisiones (§6.3 + corrección B5: el corazón delicado)
# ---------------------------------------------------------------------------

_PUNTOS = ".,;:!?¡¿\"'()«»"

# «sí» SOLO con tilde en el texto original (ver normalizar): «si» sin
# tilde jamás es un verbo.
VERBOS_APROBAR = {"aprobar", "aprobado", "sí", "ok", "vale", "dale",
                  "adelante", "hazlo"}
VERBOS_RECHAZAR = {"rechazar", "rechazado", "no", "cancelar",
                   "descartar"}
VERBOS_APLAZAR = {"aplazar", "aplaza", "espera", "esperar", "posponer"}

CONSULTAS_EXACTAS = ("estado", "tablero", "pendientes", "ayuda")
_RESP_ENCARGO = {"encargo"}
_RESP_PEDIDO = {"pedido", "el pedido", "al pedido", "es el pedido",
                "era el pedido"}


def _sin_tildes(s):
    return (s.replace("á", "a").replace("é", "e").replace("í", "i")
             .replace("ó", "o").replace("ú", "u").replace("ü", "u"))


def normalizar(texto):
    """Minúsculas, sin tildes EXCEPTO en «sí» (B5: ahí la tilde es la
    diferencia entre aprobar y una condición), sin puntuación de borde
    y espacios colapsados."""
    s = str(texto or "").lower().strip()
    s = s.replace("¡", " ").replace("¿", " ")
    tokens = []
    for t in s.split():
        t = t.strip(_PUNTOS)
        if t == "sí":
            tokens.append("sí")
        elif t:
            tokens.append(_sin_tildes(t))
    return " ".join(tokens)


def _tokens(texto):
    """Tokens normalizados conservando la forma original de «sí»."""
    salida = []
    for t in str(texto or "").lower().replace("¡", " ").replace(
            "¿", " ").split():
        t = t.strip(_PUNTOS)
        if not t:
            continue
        salida.append("sí" if t == "sí" else _sin_tildes(t))
    return salida


def _es_codigo_corto(tok):
    return len(tok) == CORTO_N and all(c in ALFABETO for c in tok.upper())


def _duracion_en(tokens, i):
    """Duración empezando en tokens[i]: (minutos, tokens_consumidos) o
    (None, 0). Formas: «30», «30 min», «30m», «2 h», «1 hora»,
    «media hora»=30, «cuarto de hora»=15 (con «un» delante también).
    La validación de rango (1..1440) es del circuito, no del parser."""
    if i >= len(tokens):
        return None, 0
    t = tokens[i]
    if t in ("media", "medio") and i + 1 < len(tokens) \
            and tokens[i + 1] == "hora":
        return 30, 2
    if t == "cuarto" and i + 2 < len(tokens) \
            and tokens[i + 1] == "de" and tokens[i + 2] == "hora":
        return 15, 3
    if t == "un" and i + 3 < len(tokens) and tokens[i + 1] == "cuarto" \
            and tokens[i + 2] == "de" and tokens[i + 3] == "hora":
        return 15, 4
    m = re.fullmatch(r"(\d+)(min|mins|minuto|minutos|m|h|hora|horas)?", t)
    if not m:
        return None, 0
    n = int(m.group(1))
    unidad = m.group(2)
    if unidad:
        return (n * 60 if unidad in ("h", "hora", "horas") else n), 1
    if i + 1 < len(tokens):
        u = tokens[i + 1]
        if u in ("min", "mins", "minuto", "minutos", "m"):
            return n, 2
        if u in ("h", "hora", "horas"):
            return n * 60, 2
    return n, 1  # número a secas: minutos


def parsear_decision(texto, codigos_validos=()):
    """La gramática estricta del §6.3/B5. Devuelve un dict:
    - tipo "aprobar" | "rechazar": decisión limpia, con «codigo» si lo
      llevaba (o None).
    - tipo "aplazar": con «minutos» (la duración es obligatoria).
    - tipo "aplazar_sin_duracion": verbo de aplazar sin duración.
    - tipo "duracion": solo una duración (completa una decisión a
      medias o aplaza el único pedido válido).
    - tipo "sobra": HAY verbo (o duración) pero sobran palabras: zona
      gris. Nunca se ejecuta; el llamador pregunta.
    - tipo None: no hay decisión.

    Una decisión es válida solo si, quitando verbo, código, duración y
    cortesía («por favor», «gracias»), NO QUEDA NINGUNA PALABRA. Por
    eso «si puedes revisa el log» no aprueba nada (ni «si» es verbo ni
    sobraría silencio), «sí, pero primero haz copia» no aprueba (sobra)
    y «no borres el archivo grande» no rechaza (sobra)."""
    tokens = _tokens(texto)
    if not tokens:
        return {"tipo": None}
    validos = {str(c).upper() for c in codigos_validos or ()}
    verbo = None
    verbo_tipo = None
    codigo = None
    minutos = None
    resto = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "por" and i + 1 < len(tokens) and tokens[i + 1] == "favor":
            i += 2
            continue
        if t == "gracias":
            i += 1
            continue
        if verbo is None and t in VERBOS_APROBAR:
            verbo, verbo_tipo = t, "aprobar"
            i += 1
            continue
        if verbo is None and t in VERBOS_RECHAZAR:
            verbo, verbo_tipo = t, "rechazar"
            i += 1
            continue
        if verbo is None and t in VERBOS_APLAZAR:
            verbo, verbo_tipo = t, "aplazar"
            i += 1
            continue
        if codigo is None and (t.upper() in validos
                               or (minutos is None and verbo is not None
                                   and _es_codigo_corto(t))):
            codigo = t.upper()
            i += 1
            continue
        if minutos is None:
            valor, consume = _duracion_en(tokens, i)
            if valor is not None:
                minutos = valor
                i += consume
                continue
        resto.append(t)
        i += 1
    if resto:
        if verbo is not None or minutos is not None:
            return {"tipo": "sobra", "verbo": verbo_tipo,
                    "codigo": codigo, "minutos": minutos,
                    "resto": resto}
        return {"tipo": None}
    if verbo_tipo in ("aprobar", "rechazar"):
        if minutos is not None:
            return {"tipo": "sobra", "verbo": verbo_tipo,
                    "codigo": codigo, "minutos": minutos, "resto": []}
        return {"tipo": verbo_tipo, "verbo": verbo_tipo,
                "codigo": codigo, "minutos": None}
    if verbo_tipo == "aplazar":
        if minutos is None:
            return {"tipo": "aplazar_sin_duracion", "verbo": verbo_tipo,
                    "codigo": codigo, "minutos": None}
        return {"tipo": "aplazar", "verbo": verbo_tipo,
                "codigo": codigo, "minutos": minutos}
    if minutos is not None:
        return {"tipo": "duracion", "verbo": None, "codigo": codigo,
                "minutos": minutos}
    if codigo is not None:
        # Un código a secas no es una decisión: es una referencia.
        return {"tipo": None, "codigo": codigo}
    return {"tipo": None}


# ---------------------------------------------------------------------------
# Clasificación y enrutado (§5.4 y §5.5)
# ---------------------------------------------------------------------------

def es_consulta(texto):
    """Consulta SOLO si el mensaje entero es la palabra (I11): «estado
    del repo X, revísalo» es un encargo, no una consulta."""
    return normalizar(texto) in CONSULTAS_EXACTAS


def clasificar(texto, codigos_validos=(), hay_pedidos_vigentes=False):
    """La clase del mensaje ya emparejado: "consulta" | "decision" |
    "aplazar_sin_duracion" | "duracion" | "aclarar" | "encargo".
    El orden manda: consulta exacta, decisión limpia, zona gris (solo
    si hay pedidos vigentes a los que podría referirse), encargo."""
    if es_consulta(texto):
        return {"clase": "consulta", "consulta": normalizar(texto)}
    p = parsear_decision(texto, codigos_validos)
    if p["tipo"] in ("aprobar", "rechazar", "aplazar"):
        return {"clase": "decision", "parse": p}
    if p["tipo"] == "aplazar_sin_duracion":
        return {"clase": "aplazar_sin_duracion", "parse": p}
    if p["tipo"] == "duracion":
        return {"clase": "duracion", "parse": p}
    if p["tipo"] == "sobra" and hay_pedidos_vigentes:
        return {"clase": "aclarar", "parse": p}
    return {"clase": "encargo", "parse": p}


def enrutar(texto, cuentas):
    """Enrutado explícito (I10). ``cuentas``: [{"id", "carril"}] de
    cuentas Muse habilitadas con carril. Devuelve (prompt, cuenta_id,
    error):
    - «@cuenta texto»: enrutado explícito; @cuenta desconocida ⇒ error
      (no se crea nada).
    - «cuenta: texto» SOLO enruta si el prefijo es una cuenta real;
      si no, el texto entero es un encargo normal, sin error.
    - Sin prefijo: (texto, None, None) — decide el carril receptor."""
    s = str(texto or "").strip()
    cuentas = cuentas or []
    if s.startswith("@"):
        m = re.match(r"@(\S+)\s*(.*)$", s, re.S)
        if m:
            nombre = _sin_tildes(m.group(1).lower())
            for c in cuentas:
                if _sin_tildes(str(c["id"]).lower()) == nombre:
                    return m.group(2).strip(), c["id"], None
            ids = ", ".join(c["id"] for c in cuentas) or "(ninguna)"
            return None, None, ("No conozco la cuenta "
                                f"«@{m.group(1)}». Cuentas: {ids}.")
    m = re.match(r"^([^:\s]{1,40}):\s+(.+)$", s, re.S)
    if m:
        nombre = _sin_tildes(m.group(1).lower())
        for c in cuentas:
            if _sin_tildes(str(c["id"]).lower()) == nombre:
                return m.group(2).strip(), c["id"], None
    return s, None, None


def carril_de_cuenta(cuentas, cuenta_id, defecto):
    for c in cuentas or []:
        if c.get("id") == cuenta_id:
            return c.get("carril") or defecto
    return defecto


# ---------------------------------------------------------------------------
# Ritmo (§5.6, corrección I2): por instalación, no por transporte
# ---------------------------------------------------------------------------

def _podar_ritmo(est, ahora):
    ritmo = est.setdefault("ritmo", {"encargos": [], "consultas": [],
                                     "mensajes": []})
    for clave in ritmo:
        ritmo[clave] = [t for t in ritmo[clave]
                        if isinstance(t, (int, float))
                        and ahora - t < 3600]
    return ritmo


def ritmo_permite(est, clase, limites, reloj=None):
    """¿Cabe un mensaje más de esta clase en la ventana de 1 h? Las
    decisiones NO se cuentan ni se cortan jamás (un aplazamiento
    perdido es peor que un encargo de más): se llaman solo con
    clase encargo/consulta."""
    ahora = (reloj or time.time)()
    ritmo = _podar_ritmo(est, ahora)
    lim = dict(LIMITES_DEF)
    if isinstance(limites, dict):
        lim.update({k: v for k, v in limites.items()
                    if k in lim and isinstance(v, int) and v > 0})
    if len(ritmo["mensajes"]) >= lim["mensajes_hora"]:
        return False
    if clase == "encargo" and len(ritmo["encargos"]) >= lim["encargos_hora"]:
        return False
    if clase == "consulta" \
            and len(ritmo["consultas"]) >= lim["consultas_hora"]:
        return False
    return True


def ritmo_anotar(est, clase, reloj=None):
    ahora = (reloj or time.time)()
    ritmo = _podar_ritmo(est, ahora)
    ritmo["mensajes"].append(ahora)
    if clase in ("encargo", "consulta"):
        ritmo[clase + "s" if clase == "consulta" else "encargos"].append(ahora)


# ---------------------------------------------------------------------------
# Identidad de tarea derivada del mensaje (B4) y derivación al carril B
# ---------------------------------------------------------------------------

def tid_de_mensaje(transporte, id_mensaje, reloj=None):
    """t-<fecha>-<hash16 del (transporte, id_mensaje)>: el MISMO
    mensaje produce siempre la MISMA tarea, así una retransmisión tras
    una muerte no puede duplicar el encargo."""
    ahora = (reloj or time.time)()
    fecha = time.strftime("%Y%m%d", time.localtime(ahora))
    h = hashlib.sha256(
        f"{transporte}:{id_mensaje}".encode("utf-8")).hexdigest()[:16]
    return f"t-{fecha}-{h}"


def escribir_tarea(dir_tareas, tarea):
    """La tarea .task.json en el inbox del carril destino: tmp +
    os.replace (el lector del runner nunca ve una tarea a medias)."""
    carpeta = Path(dir_tareas)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{tarea['id']}.task.json"
    _escribir_json(ruta, tarea)
    return ruta


def derivar_tarea_carril_b(dir_carril_b, tarea_id, prompt, canal):
    """El encargo del carril B sin contexto git (§5.3, patrón de
    relevo.entregar y consulta.py): el .md con el prompt se escribe
    PRIMERO y la tarea lo referencia; cwd = la carpeta del carril B.
    Devuelve la tarea lista para escribir en su inbox."""
    base_b = Path(dir_carril_b)
    carpeta = base_b / "encargos"
    carpeta.mkdir(parents=True, exist_ok=True)
    md = carpeta / f"{tarea_id}.md"
    contenido = (f"# Encargo {tarea_id}\n\n"
                 f"- canal: {canal}\n"
                 f"- carril: b\n\n"
                 f"{prompt}\n")
    tmp = md.with_name(md.name + ".tmp")
    tmp.write_text(contenido, encoding="utf-8")
    os.replace(tmp, md)
    return {"id": tarea_id, "tipo": "encargo", "prompt": prompt,
            "canal": canal, "lane": "b", "cwd": str(base_b),
            "archivos": [str(md)]}


# ---------------------------------------------------------------------------
# Consultas (§5.4): solo archivos compartidos, nunca la cola de otro carril
# ---------------------------------------------------------------------------

def _hhmm(ts):
    try:
        return time.strftime("%H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "?"


def _texto_tablero(base_dir):
    try:
        import tablero as _tablero
        vista = _tablero.vista(base_dir)
    except Exception:
        vista = {}
    if not vista:
        return "Tablero vacío: ninguna cuenta Muse ha publicado aún."
    lineas = ["Tablero:"]
    for cid, e in sorted(vista.items()):
        pct = e.get("pct_efectivo")
        pct_txt = f"{pct:.0f} %" if isinstance(pct, (int, float)) else "?"
        tarea = e.get("tarea")
        lineas.append(f"• {cid}: {e.get('estado', '?')}, "
                      f"{pct_txt} libre"
                      + (f", en «{str(tarea)[:60]}»" if tarea else ""))
    return "\n".join(lineas)


def _texto_estado(base_dir):
    lineas = []
    try:
        import presencia as _presencia
        modo = _presencia.leer_estado(base_dir).get("modo")
    except Exception:
        modo = None
    lineas.append(f"Modo: {modo or 'presente'} (el dueño "
                  + ("está en el PC" if modo == "presente"
                     else "no está en el PC") + ").")
    lineas.append(_texto_tablero(base_dir))
    try:
        import relevo as _relevo
        abiertos = [e for e in _relevo.listar(base_dir)
                    if e.get("estado") not in ESTADOS_ENCARGO_TERMINALES]
    except Exception:
        abiertos = []
    if abiertos:
        lineas.append(f"Encargos abiertos: {len(abiertos)}")
        for e in abiertos[:5]:
            subs = e.get("subtareas") or []
            hechas = sum(1 for s in subs
                         if isinstance(s, dict)
                         and s.get("estado") in ("terminada", "fallida"))
            lineas.append(f"• {e.get('raiz')}: {e.get('estado')}, "
                          f"{hechas}/{len(subs)} subtareas")
    datos_p = cargar_pedidos(base_dir)
    vig = pedidos_vigentes(datos_p)
    if vig:
        lineas.append(f"Pedidos esperando decisión: {len(vig)} "
                      "(di «pendientes» para verlos).")
    return "\n".join(lineas)


def _texto_pendientes(base_dir):
    datos_p = cargar_pedidos(base_dir)
    vig = pedidos_vigentes(datos_p)
    if not vig:
        return "No hay pedidos esperando decisión."
    lineas = ["Pedidos esperando decisión:"]
    for aid, e in vig.items():
        vence = e.get("vence_ts")
        lineas.append(
            f"• [{e.get('codigo')}] {e.get('nivel')}: "
            f"{str(e.get('motivo') or '')[:80]}"
            + (f" (vence {_hhmm(vence)})"
               if isinstance(vence, (int, float)) else "")
            + f"\n  Responde: aprobar {e.get('codigo')} · "
              f"rechazar {e.get('codigo')} · espera 30 {e.get('codigo')}")
    return "\n".join(lineas)


TEXTO_AYUDA = (
    "Esto es lo que entiendo:\n"
    "• Un encargo: escríbelo sin más («revisa el informe y súbelo»). "
    "Con «@cuenta» delante va a esa cuenta Muse.\n"
    "• «estado», «tablero», «pendientes»: te cuento cómo va todo.\n"
    "• Decisiones sobre un pedido: responde a su mensaje o di "
    "«aprobar XKCD», «rechazar XKCD» o «espera 30 XKCD» (XKCD es el "
    "código del pedido; «espera» sin tiempo te pregunta cuánto).\n"
    "• Los pedidos R3 no se deciden por aquí: solo en la app, con el "
    "PC delante.")


def respuesta_consulta(base_dir, consulta):
    if consulta == "tablero":
        return _texto_tablero(base_dir)
    if consulta == "pendientes":
        return _texto_pendientes(base_dir)
    if consulta == "ayuda":
        return TEXTO_AYUDA
    return _texto_estado(base_dir)


# ---------------------------------------------------------------------------
# El destino «canal» de avisos.py (§7)
# ---------------------------------------------------------------------------

class DestinoCanal:
    """El destino que avisos.py despacha cuando avisos-config.json lo
    activa. ``enviar`` solo ENCOLA en la bandeja compartida (guardar
    antes que enviar): la transmisión es del líder, en su bucle.
    Sin transporte activo o sin emparejar, no encola nada y devuelve
    False: el aviso sigue en avisos.jsonl, que es su registro."""

    nombre = "canal"

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)

    def disponible(self):
        cfg = cargar_config(self.base_dir)
        activo = cfg.get("activo")
        return bool(activo) and emparejado(cfg, activo)

    def enviar(self, aviso):
        cfg = cargar_config(self.base_dir)
        activo = cfg.get("activo")
        if not activo or not emparejado(cfg, activo):
            return False
        nivel = aviso.get("nivel")
        tipo = aviso.get("tipo")
        texto = str(aviso.get("texto") or "")
        if nivel == "accion":
            encolar_saliente(self.base_dir, "aviso", "⚠️ " + texto,
                             meta={"aviso_id": aviso.get("id"),
                                   "tipo": tipo},
                             nivel="accion")
            return True
        # info: solo los tipos suscritos, y sin duplicar lo que el
        # canal ya cuenta por su propio camino (§7.2).
        if tipo not in (cfg.get("avisos_info") or []):
            return False
        if tipo == "encargo_recibido":
            try:
                import relevo as _relevo
                ent = None
                for e in _relevo.listar(self.base_dir):
                    if aviso.get("tarea") in (e.get("tareas") or []) \
                            or e.get("raiz") == aviso.get("raiz"):
                        ent = e
                        break
                if ent is not None and ent.get("canal") == activo:
                    return False  # la respuesta inmediata ya lo confirmó
            except Exception:
                pass  # ante la duda, se envía
        if tipo == "encargo_terminado" \
                and resumen_encolado(self.base_dir, aviso.get("raiz")):
            return False
        encolar_saliente(self.base_dir, "aviso", texto,
                         meta={"aviso_id": aviso.get("id"), "tipo": tipo},
                         nivel="info")
        return True


def destino_canal(base_dir):
    return DestinoCanal(base_dir)


# ---------------------------------------------------------------------------
# La puerta de entrada: procesar (§5.1, §5.5 y §6)
# ---------------------------------------------------------------------------

_VERBO_TXT = {"aprobar": "apruebo", "rechazar": "rechazo",
              "aplazar": "aplazo"}


def _verbo_de_parse(p):
    """La decisión que un parseo lleva dentro: la limpia, o el verbo
    de una «sobra» (el texto guardado de una decisión a medias parsea
    como sobra: su verbo es lo que el dueño quiso decir). Devuelve
    (decision, minutos) o (None, None)."""
    if p.get("tipo") in ("aprobar", "rechazar", "aplazar"):
        return p["tipo"], p.get("minutos")
    if p.get("verbo") in ("aprobar", "rechazar", "aplazar"):
        return p["verbo"], p.get("minutos")
    return None, None


def _finalizar_estado(est, te, idm, mensaje, ahora):
    """Cierre de un mensaje procesado: sale de en_proceso, entra en
    vistos (con su tope) y la marca de agua avanza SOLO con mensajes
    procesados. El llamador guarda el estado."""
    te["en_proceso"].pop(idm, None)
    vistos = te.setdefault("vistos", [])
    if idm not in vistos:
        vistos.append(idm)
    del vistos[:-VISTOS_MAX]
    ts_t = mensaje.get("ts_transporte")
    marca = ts_t if isinstance(ts_t, (int, float)) else ahora
    if marca > (te.get("marca_agua_ts") or 0):
        te["marca_agua_ts"] = marca
    te["ultimo_entrante_ts"] = ahora


def _descripcion_pedido(entrada):
    return (f"{entrada.get('codigo') or '····'} "
            f"({entrada.get('nivel')}: "
            f"{str(entrada.get('motivo') or '')[:60]})")


def _aplicar_y_confirmar(base_dir, efectos, transporte, aid, entrada,
                         decision, minutos, via, reloj):
    """Aplica una decisión ya resuelta y compone la confirmación del
    §6.5: qué se entendió, de qué pedido, y el mensaje LITERAL del
    circuito. Con orden entre carriles, la confirmación es la de
    «recibido» y la definitiva llega asíncrona (B3)."""
    res = efectos["aplicar_decision"](aid, decision, minutos, transporte)
    verbo = _VERBO_TXT.get(decision, decision)
    if decision == "aplazar" and minutos:
        verbo += f" {minutos} min"
    desc = _descripcion_pedido(entrada)
    if res.get("modo") == "orden":
        texto = res.get("mensaje") or (
            f"Recibido: {verbo} el pedido {desc}.")
    else:
        texto = (f"Entendido: {verbo} el pedido {desc}. "
                 f"{res.get('mensaje') or ''}").strip()
    efectos["responder"](texto)
    anotar(base_dir, "decision", reloj=reloj, transporte=transporte,
           approval_id=aid, decision=decision, minutos=minutos, via=via,
           modo=res.get("modo"))
    return {"resultado": "decision", "approval_id": aid,
            "decision": decision, "modo": res.get("modo"),
            "hecho": res.get("hecho")}


def _preguntar_duracion(base_dir, efectos, transporte, aid, entrada,
                        reloj):
    """Un aplazamiento sin duración se queda a medias (§6.3): se
    fija la decisión en curso y se pregunta cuánto, una sola vez."""
    fijar_decision_en_curso(
        base_dir, {"tipo": "aplazar", "approval_id": aid,
                   "transporte": transporte}, reloj=reloj)
    efectos["responder"](
        f"¿Cuánto tiempo aplazo el pedido "
        f"{_descripcion_pedido(entrada)}? Di «30», «30 min» o «2 h».")
    return {"resultado": "aplazar_pregunta", "approval_id": aid}


def _sin_objetivo(base_dir, efectos, transporte, validos, reloj):
    """Ningún objetivo válido o ambiguo: no se decide nada y se listan
    los pedidos decidibles con su código (§6.2)."""
    anotar(base_dir, "decision_sin_objetivo", reloj=reloj,
           transporte=transporte)
    if validos:
        lineas = ["No sé a qué pedido te refieres. "
                  "Los que esperan decisión:"]
        for e in validos.values():
            lineas.append(f"• [{e.get('codigo')}] {e.get('nivel')}: "
                          f"{str(e.get('motivo') or '')[:80]}")
        lineas.append("Contéstame con el código: «aprobar XKCD».")
        efectos["responder"]("\n".join(lineas))
    else:
        efectos["responder"](
            "Ahora mismo no hay ningún pedido esperando decisión "
            "por este canal.")
    return {"resultado": "sin_objetivo"}


def _ejecutar_decision(base_dir, mensaje, efectos, parse, reloj):
    """El camino de una decisión (también de una duración suelta):
    primero el muro del R3 (B6), después la resolución de objetivo,
    y solo al final el circuito — vía efectos, nunca directo."""
    transporte = mensaje["transporte"]
    ahora = (reloj or time.time)()
    datos_p = cargar_pedidos(base_dir)
    cita = mensaje.get("cita_id")
    if cita is not None:
        r3 = objetivo_r3(datos_p, cita)
        if r3 is not None:
            aid_r3, _e = r3
            anotar(base_dir, "decision_r3_no_ofrecida", reloj=reloj,
                   transporte=transporte, approval_id=aid_r3)
            efectos["responder"](
                "Ese pedido es R3: solo se decide en la app, con el "
                "PC delante. Aquí no lo toco.")
            return {"resultado": "r3_no_ofrecida", "approval_id": aid_r3}
    res = resolver_objetivo(datos_p, cita_id=cita,
                            codigo=parse.get("codigo"),
                            recepcion_ts=ahora)
    if res["approval_id"] is None:
        return _sin_objetivo(base_dir, efectos, transporte,
                             res["validos"], reloj)
    aid = res["approval_id"]
    return _aplicar_y_confirmar(
        base_dir, efectos, transporte, aid, res["validos"][aid],
        parse["tipo"] if parse["tipo"] in ("aprobar", "rechazar",
                                           "aplazar") else "aplazar",
        parse.get("minutos"), res["via"], reloj)


def _ejecutar_encargo(base_dir, mensaje, efectos, ctx, texto, est, te,
                      idm, reloj):
    """Crea la tarea del encargo en el carril destino. El registro
    en_proceso se actualiza (con el carril) y se guarda ANTES de crear
    nada: si el proceso muere aquí, la recuperación sabe dónde mirar."""
    transporte = mensaje["transporte"]
    ahora = (reloj or time.time)()
    cuentas = ctx.get("cuentas") or []
    prompt, cuenta_id, error = enrutar(texto, cuentas)
    if error:
        efectos["responder"](error)
        return {"resultado": "error_enrutado"}
    if cuenta_id:
        carril = carril_de_cuenta(cuentas, cuenta_id,
                                  ctx.get("carril_propio"))
    else:
        carril = ctx.get("carril_propio")
        cuenta_id = next((c["id"] for c in cuentas
                          if c.get("carril") == carril), None)
    tid = tid_de_mensaje(transporte, idm, reloj=reloj)
    te["en_proceso"][idm] = {"tid": tid, "ts": ahora, "carril": carril}
    guardar_estado(base_dir, est)
    if carril == "b" and ctx.get("dir_carril_b"):
        tarea = derivar_tarea_carril_b(ctx["dir_carril_b"], tid, prompt,
                                       transporte)
    else:
        tarea = {"id": tid, "tipo": "encargo", "prompt": prompt,
                 "canal": transporte}
    ok, motivo = efectos["crear_tarea"](tarea, carril)
    if not ok:
        efectos["responder"](
            f"No pude registrar el encargo: {motivo or 'error'}")
        anotar(base_dir, "error_transporte", reloj=reloj,
               transporte=transporte, motivo="crear_tarea",
               detalle=resumen_error(str(motivo or "")))
        return {"resultado": "error_creacion", "tid": tid}
    anotar(base_dir, "encargo_creado", reloj=reloj,
           transporte=transporte, tid=tid, carril=carril,
           cuenta=cuenta_id)
    receptora = cuenta_id or carril
    efectos["responder"](
        f"Encargo recibido ✓ lo registra {receptora}. "
        "Te aviso cuando se divida y cuando se cierre.")
    return {"resultado": "encargo", "tid": tid, "carril": carril,
            "cuenta": cuenta_id}


def procesar(base_dir, mensaje, efectos, ctx, reloj=None):
    """Procesa UN mensaje normalizado de un adaptador. Es la única
    puerta de entrada (§5.1) y aplica las compuertas en orden:
    duplicado → marca de agua → identidad/emparejamiento → registro →
    en_proceso duradero → clasificación → ritmo → ejecución.

    ``mensaje``: {transporte, id_mensaje (se trata como str siempre,
    I3), remitente, texto|None, cita_id|None, ts_transporte|None}.
    ``efectos``: {crear_tarea(tarea, carril)->(ok, motivo),
    aplicar_decision(approval_id, decision, minutos, canal)->dict,
    responder(texto, meta=None), tarea_existe(tid, carril)->bool
    (opcional)}.
    ``ctx``: {cuentas: [{id, carril}], carril_propio, dir_carril_b}.

    Devuelve un dict con «resultado». Si es "sin_registro", el
    llamador NO debe avanzar su cursor: el mensaje se reintentará."""
    base_dir = Path(base_dir)
    ahora = (reloj or time.time)()
    transporte = mensaje["transporte"]
    idm = str(mensaje["id_mensaje"])
    remitente = str(mensaje.get("remitente") or "")
    texto = mensaje.get("texto")
    cfg = cargar_config(base_dir)
    est = cargar_estado(base_dir, reloj=reloj)
    te = transporte_estado(est, transporte)
    tcfg = (cfg.get("transportes") or {}).get(transporte) or {}

    # 1) Duplicado ya finalizado: se confirma y no se hace nada.
    if idm in te["vistos"]:
        return {"resultado": "duplicado"}

    # 1b) Quedó a medias (muerte entre registrar y crear): si la tarea
    # ya existe, cuenta como procesado; si no, se reprocesa entero.
    previo = te["en_proceso"].get(idm)
    if previo is not None:
        existe_fn = efectos.get("tarea_existe")
        if previo.get("tid") and callable(existe_fn):
            try:
                if existe_fn(previo["tid"], previo.get("carril")):
                    _finalizar_estado(est, te, idm, mensaje, ahora)
                    guardar_estado(base_dir, est)
                    return {"resultado": "duplicado"}
            except Exception:
                pass

    # 2) Marca de agua: lo anterior al emparejamiento (con holgura) o
    # muy anterior al último procesado se descarta como viejo (B4).
    ts_t = mensaje.get("ts_transporte")
    if isinstance(ts_t, (int, float)):
        emp_ts = tcfg.get("emparejado_ts") or 0
        marca = te.get("marca_agua_ts") or 0
        if (emp_ts and ts_t < emp_ts) \
                or ts_t < marca - HOLGURA_MARCA_AGUA_S:
            anotar(base_dir, "mensaje_ignorado", reloj=reloj,
                   transporte=transporte, motivo="viejo",
                   remitente=enmascarar(remitente))
            _finalizar_estado(est, te, idm, mensaje, ahora)
            guardar_estado(base_dir, est)
            return {"resultado": "viejo"}

    # 3) Identidad: sin emparejar, solo el baile del código; emparejado,
    # solo la identidad certificada. El resto: silencio y registro.
    identidad = tcfg.get("identidad")
    if not identidad:
        res = intentar_emparejar(base_dir, transporte, remitente, texto,
                                 reloj=reloj)
        _finalizar_estado(est, te, idm, mensaje, ahora)
        guardar_estado(base_dir, est)
        if res["resultado"] == "emparejado":
            efectos["responder"](
                "Emparejado ✓. Escríbeme un encargo, o «ayuda» para "
                "ver qué entiendo.")
            return {"resultado": "emparejado",
                    "identidad": res.get("identidad")}
        return {"resultado": "ignorado", "detalle": res["resultado"]}
    if remitente != str(identidad):
        anotar(base_dir, "mensaje_ignorado", reloj=reloj,
               transporte=transporte, motivo="remitente",
               remitente=enmascarar(remitente))
        _finalizar_estado(est, te, idm, mensaje, ahora)
        guardar_estado(base_dir, est)
        return {"resultado": "ignorado", "detalle": "remitente"}

    # 4) Guardar primero: el registro anota ANTES de clasificar; si el
    # registro no se puede escribir, no se procesa (principio 5).
    if not anotar(base_dir, "mensaje_recibido", reloj=reloj,
                  transporte=transporte, remitente=enmascarar(remitente),
                  resumen=_resumen_texto(texto)):
        return {"resultado": "sin_registro"}

    # 5) en_proceso duradero ANTES de crear nada (exactamente-una-vez).
    tid = tid_de_mensaje(transporte, idm, reloj=reloj)
    te["en_proceso"][idm] = {"tid": tid, "ts": ahora, "carril": None}
    guardar_estado(base_dir, est)

    def _fin(res):
        _finalizar_estado(est, te, idm, mensaje, ahora)
        guardar_estado(base_dir, est)
        return res

    # 6) Sin texto: una respuesta amable por hora como mucho.
    if texto is None:
        if ahora - (te.get("no_texto_resp_ts") or 0) \
                >= NO_TEXTO_RESPUESTA_S:
            te["no_texto_resp_ts"] = ahora
            efectos["responder"](
                "Solo entiendo texto: escríbeme el encargo o la "
                "decisión como un mensaje normal.")
        anotar(base_dir, "mensaje_ignorado", reloj=reloj,
               transporte=transporte, motivo="no_texto")
        return _fin({"resultado": "no_texto"})

    datos_p = cargar_pedidos(base_dir)
    validos = pedidos_vigentes(datos_p, recepcion_ts=ahora)
    codigos = [e.get("codigo") for e in validos.values() if e.get("codigo")]

    # 7) Decisión a medias viva: manda sobre la clasificación nueva.
    curso = decision_en_curso(base_dir, reloj=reloj)
    if curso is not None:
        if curso.get("tipo") == "aplazar":
            p = parsear_decision(texto, codigos)
            if p["tipo"] == "duracion":
                aid = curso.get("approval_id")
                entrada = (datos_p.get("pedidos") or {}).get(aid) or {}
                limpiar_decision_en_curso(base_dir)
                return _fin(_aplicar_y_confirmar(
                    base_dir, efectos, transporte, aid, entrada,
                    "aplazar", p["minutos"], "a_medias", reloj))
            limpiar_decision_en_curso(base_dir)
        elif curso.get("tipo") == "aclarar":
            norm = normalizar(texto)
            p = parsear_decision(texto, codigos)
            if norm in _RESP_ENCARGO:
                limpiar_decision_en_curso(base_dir)
                return _fin(_ejecutar_encargo(
                    base_dir, mensaje, efectos, ctx,
                    curso.get("texto") or "", est, te, idm, reloj))
            if norm in _RESP_PEDIDO:
                guardado = parsear_decision(curso.get("texto") or "",
                                            codigos)
                aid = curso.get("approval_id")
                entrada = (datos_p.get("pedidos") or {}).get(aid) or {}
                limpiar_decision_en_curso(base_dir)
                decision, minutos = _verbo_de_parse(guardado)
                if decision in ("aprobar", "rechazar") and aid:
                    return _fin(_aplicar_y_confirmar(
                        base_dir, efectos, transporte, aid, entrada,
                        decision, None, "a_medias", reloj))
                if decision == "aplazar" and aid:
                    if minutos:
                        return _fin(_aplicar_y_confirmar(
                            base_dir, efectos, transporte, aid, entrada,
                            "aplazar", minutos, "a_medias", reloj))
                    return _fin(_preguntar_duracion(
                        base_dir, efectos, transporte, aid, entrada,
                        reloj))
                return _fin({"resultado": "a_medias_rota"})
            if p["tipo"] in ("aprobar", "rechazar", "aplazar"):
                limpiar_decision_en_curso(base_dir)
                # decisión limpia nueva: sigue a la clasificación
            elif p["tipo"] is None and p.get("codigo"):
                res_obj = resolver_objetivo(datos_p, codigo=p["codigo"],
                                            recepcion_ts=ahora)
                guardado = parsear_decision(curso.get("texto") or "",
                                            codigos)
                limpiar_decision_en_curso(base_dir)
                decision, minutos = _verbo_de_parse(guardado)
                if res_obj["approval_id"] and decision in (
                        "aprobar", "rechazar"):
                    aid = res_obj["approval_id"]
                    return _fin(_aplicar_y_confirmar(
                        base_dir, efectos, transporte, aid,
                        res_obj["validos"][aid], decision, None,
                        "a_medias", reloj))
                if res_obj["approval_id"] and decision == "aplazar":
                    aid = res_obj["approval_id"]
                    if minutos:
                        return _fin(_aplicar_y_confirmar(
                            base_dir, efectos, transporte, aid,
                            res_obj["validos"][aid], "aplazar", minutos,
                            "a_medias", reloj))
                    return _fin(_preguntar_duracion(
                        base_dir, efectos, transporte, aid,
                        res_obj["validos"][aid], reloj))
                return _fin({"resultado": "a_medias_rota"})
            else:
                # Cualquier otra cosa: el texto guardado se convierte
                # en encargo y ESTE mensaje se clasifica por su cuenta.
                # El guardado usa un id sintético: su tid no puede
                # chocar con el del mensaje nuevo si este también
                # resulta ser un encargo.
                limpiar_decision_en_curso(base_dir)
                _ejecutar_encargo(base_dir, mensaje, efectos, ctx,
                                  curso.get("texto") or "", est, te,
                                  idm + "#previo", reloj)

    # 8) Clasificación, 9) ritmo (decisiones exentas), 10) ejecución.
    clase = clasificar(texto, codigos, hay_pedidos_vigentes=bool(validos))
    if clase["clase"] in ("encargo", "consulta"):
        if not ritmo_permite(est, clase["clase"], cfg.get("limites"),
                             reloj=reloj):
            anotar(base_dir, "mensaje_ignorado", reloj=reloj,
                   transporte=transporte, motivo="ritmo")
            efectos["responder"](
                "Voy al límite de mensajes de esta hora; lo retomamos "
                "en un rato. Las decisiones sobre pedidos sí pasan "
                "siempre.")
            return _fin({"resultado": "ritmo"})
        ritmo_anotar(est, clase["clase"], reloj=reloj)
        guardar_estado(base_dir, est)

    if clase["clase"] == "consulta":
        anotar(base_dir, "consulta", reloj=reloj, transporte=transporte,
               consulta=clase["consulta"])
        efectos["responder"](respuesta_consulta(base_dir,
                                                clase["consulta"]))
        return _fin({"resultado": "consulta",
                     "consulta": clase["consulta"]})

    if clase["clase"] == "decision":
        return _fin(_ejecutar_decision(base_dir, mensaje, efectos,
                                       clase["parse"], reloj))

    if clase["clase"] == "duracion":
        return _fin(_ejecutar_decision(base_dir, mensaje, efectos,
                                       clase["parse"], reloj))

    if clase["clase"] == "aplazar_sin_duracion":
        parse = clase["parse"]
        if mensaje.get("cita_id") is not None:
            r3 = objetivo_r3(datos_p, mensaje["cita_id"])
            if r3 is not None:
                return _fin(_ejecutar_decision(base_dir, mensaje,
                                               efectos,
                                               {"tipo": "aprobar",
                                                "codigo": None,
                                                "minutos": None},
                                               reloj))
        res = resolver_objetivo(datos_p, cita_id=mensaje.get("cita_id"),
                                codigo=parse.get("codigo"),
                                recepcion_ts=ahora)
        if res["approval_id"] is None:
            return _fin(_sin_objetivo(base_dir, efectos, transporte,
                                      res["validos"], reloj))
        aid = res["approval_id"]
        return _fin(_preguntar_duracion(base_dir, efectos, transporte,
                                        aid, res["validos"][aid],
                                        reloj))

    if clase["clase"] == "aclarar":
        parse = clase["parse"]
        res = resolver_objetivo(datos_p, cita_id=mensaje.get("cita_id"),
                                codigo=parse.get("codigo"),
                                recepcion_ts=ahora)
        if res["approval_id"] is not None:
            aid = res["approval_id"]
            entrada = res["validos"][aid]
            fijar_decision_en_curso(
                base_dir,
                {"tipo": "aclarar", "texto": texto, "approval_id": aid,
                 "transporte": transporte}, reloj=reloj)
            efectos["responder"](
                f"Antes de tocar nada: ¿esto es una respuesta al "
                f"pedido {_descripcion_pedido(entrada)} o un encargo "
                "nuevo? Contesta «el pedido» o «encargo».")
            return _fin({"resultado": "aclarar", "approval_id": aid})
        # Sin objetivo al que agarrarse: es un encargo con condiciones.

    return _fin(_ejecutar_encargo(base_dir, mensaje, efectos, ctx,
                                  texto, est, te, idm, reloj))

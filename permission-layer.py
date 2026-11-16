# -*- coding: utf-8 -*-
"""Growi Bridge 0.6.0 'Harness' - Fase H3: capa de permisos + auditoria.

Principios (el chequeo es CODIGO, nunca un prompt al LLM):
  1. LISTA BLANCA de tools y, dentro de cada tool, de ACCIONES concretas
     (responder_pregunta, resumir_o_clasificar, redactar_texto, ...). No hay lista
     negra de palabras: una peticion se divide en fragmentos y CADA fragmento tiene
     que coincidir con una accion permitida; lo que no se reconoce se bloquea
     (fail closed). Ofuscar un verbo ("b0rra") no ayuda: deja de reconocerse.
  2. ALCANCE por tool (texto / lectura_proyecto / archivos_proyecto): las acciones
     que escriben archivos solo valen dentro de la raiz del proyecto.
  3. CONFIRMACION HUMANA: solo la hace una persona desde la app (o por consola con
     TTY) con resolver_confirmacion(); el agente no tiene ningun parametro ni funcion
     para auto-confirmar. Se pide UNA vez por sesion y accion (no spamea). Cada
     decision va firmada con HMAC (clave en permission-secret.key).
  4. AUDITORIA append-only con cadena de hashes SHA-256 entre entradas
     (audit-log.json, un objeto JSON por linea). Si no se puede escribir, la accion
     se bloquea. Rotacion a audit-log-YYYY-MM.json al pasar de 10 MB (la cadena
     continua en el archivo nuevo). Se guarda solo un resumen (100 chars) del prompt.

CLI:
    python permission-layer.py --verificar-log
    python permission-layer.py --pendientes
    python permission-layer.py --confirmar ID | --rechazar ID     (pide TTY y escribir SI)
"""
import hashlib
import hmac
import json
import os
import re
import sys
import threading
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime

try:
    import msvcrt
except ImportError:  # pragma: no cover
    msvcrt = None

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_PROYECTO = AQUI
RAICES_LECTURA = (AQUI, r"C:\Users\forte\growi-bridge")

AUDIT_PATH = os.environ.get("GROWI_AUDIT_LOG") or os.path.join(AQUI, "audit-log.json")
CONFIRM_PATH = os.environ.get("GROWI_CONFIRMACIONES") or os.path.join(AQUI, "confirmaciones.json")
SECRET_PATH = os.environ.get("GROWI_PERM_SECRET") or os.path.join(AQUI, "permission-secret.key")
AUDIT_MAX_BYTES = int(os.environ.get("GROWI_AUDIT_MAX_BYTES") or 10 * 1024 * 1024)
RESUMEN_MAX = 100
CONFIRM_VIGENCIA_S = 8 * 3600
GENESIS = "0" * 64

# --------------------------------------------------------------- Lista blanca
_TEXTO = {"requiere_confirmacion": False}
_ARCHIVOS = {"requiere_confirmacion": True}  # escribir en el proyecto: lo confirma un humano
_DESTRUCTIVA = {"requiere_confirmacion": True}  # borrar/eliminar/format/drop: SOLO con confirmacion humana
ACCION_DESTRUCTIVA = "accion_destructiva"
# Raices de verbos destructivos. SE USA: _RX_DESTRUCTIVA se construye a partir de esta lista y el clasificador
# marca como accion_destructiva cualquier fragmento que contenga uno de ellos EN CUALQUIER POSICION (no solo al
# principio): "explica como borrar todo" tambien exige confirmacion. Es una clase de la allowlist (solo claude_cli y
# codex_cli la tienen y siempre exige confirmacion humana); lo no reconocido (p. ej. "b0rra") sigue bloqueado.
ACCIONES_DESTRUCTIVAS = ["delete", "borrar", "eliminar", "rm ", "format", "drop",
                         "suprimir", "truncar", "truncate", "remove", "destruir", "erase", "wipe", "rmdir"]
# Raiz de conjugacion por entrada (None = palabra exacta). Evita falsos positivos: borrador, formato, dropshipping.
_RAICES = {"delete": r"delet\w*", "borrar": r"borr(?!ador)\w*", "eliminar": r"elimin\w*", "rm ": r"rm",
           "format": r"format(?:ea\w*|ee\w*|ear|e|ing|ed)?", "drop": r"drop(?:s|ped|ping)?",
           "suprimir": r"suprim\w*", "truncar": r"trunc\w*", "truncate": r"truncat\w*", "remove": r"remov\w*",
           "destruir": r"destru\w*", "erase": r"eras\w*", "wipe": r"wip\w*", "rmdir": r"rmdir"}


def _patron_destructivo(entrada):
    return _RAICES.get(entrada) or (re.escape(entrada.strip()) + r"\w*")


_RX_DESTRUCTIVA = re.compile(r"\b(?:%s)\b" % "|".join(_patron_destructivo(e) for e in ACCIONES_DESTRUCTIVAS))
_RX_DESTRUCTIVA_INICIO = re.compile(r"^(?:del|rd)\s")  # comandos de Windows; "del" suelto es "de el" en espanol


def es_destructivo(texto):
    t = _limpiar_fragmento(texto)
    return bool(_RX_DESTRUCTIVA.search(t) or _RX_DESTRUCTIVA_INICIO.match(t))


TOOLS_PERMITIDAS = {
    "claude_cli": {
        "nivel": "alto", "requiere_confirmacion": False, "alcance": ["texto", "lectura_proyecto", "archivos_proyecto"],
        "acciones": {"consulta_motor": _TEXTO, "responder_pregunta": _TEXTO, "resumir_o_clasificar": _TEXTO,
                     "redactar_texto": _TEXTO, "analizar_o_revisar": _TEXTO, "generar_codigo": _TEXTO,
                     "modificar_archivos": _ARCHIVOS, ACCION_DESTRUCTIVA: _DESTRUCTIVA},
    },
    "codex_cli": {
        "nivel": "alto", "requiere_confirmacion": False, "alcance": ["texto", "lectura_proyecto", "archivos_proyecto"],
        "acciones": {"consulta_motor": _TEXTO, "responder_pregunta": _TEXTO, "resumir_o_clasificar": _TEXTO,
                     "redactar_texto": _TEXTO, "analizar_o_revisar": _TEXTO, "generar_codigo": _TEXTO,
                     "modificar_archivos": _ARCHIVOS, ACCION_DESTRUCTIVA: _DESTRUCTIVA},
    },
    "gemini_cli": {
        "nivel": "medio", "requiere_confirmacion": False, "alcance": ["texto"],
        "acciones": {"consulta_motor": _TEXTO, "responder_pregunta": _TEXTO, "resumir_o_clasificar": _TEXTO,
                     "redactar_texto": _TEXTO, "analizar_o_revisar": _TEXTO},
    },
    "llama_local": {
        "nivel": "bajo", "requiere_confirmacion": False, "alcance": ["texto"],
        "acciones": {"consulta_motor": _TEXTO, "responder_pregunta": _TEXTO, "resumir_o_clasificar": _TEXTO,
                     "redactar_texto": _TEXTO},
    },
}
ACCIONES_ESCRITURA = ("modificar_archivos", ACCION_DESTRUCTIVA)
MOTOR_DE = {"claude_cli": "claude", "codex_cli": "codex", "gemini_cli": "gemini", "llama_local": "llama"}

# --------------------------------------------------- Clasificador de acciones
# Solo reconoce lo que SI se permite (el verbo debe abrir el fragmento).
_CLASES = [
    # Orden importa: "crea un archivo" debe verse como modificar_archivos antes que redactar.
    ("modificar_archivos", re.compile(
        r"^(?:crea\w*|escrib\w+|guard\w+|modific\w+|edit\w+|renombr\w+|actualiz\w+|genera\w*)\b.*"
        r"\b(?:archivos?|ficheros?|files?|carpetas?|disco)\b")),
    ("generar_codigo", re.compile(
        r"^(?:(?:un|una|el|la)\s+)?(?:implement\w+|program\w+|codific\w+|refactor\w*|debug\w*|depur\w+|corrig\w+|"
        r"codigo|script|funcion|clase|test\w*|(?:crea\w*|escrib\w+|genera\w*|haz|hace)\s+(?:un|una|el|la|unos|unas)?\s*"
        r"(?:script|funcion|clase|codigo|programa|test\w*|query|regex))\b")),
    ("analizar_o_revisar", re.compile(
        r"^(?:(?:un|una|el|la)\s+)?(?:analiz\w+|revis\w+|evalu\w+|audit\w+|diagnostic\w+|inspeccion\w+|compar\w+|"
        r"analisis|revision|comparacion|critic\w+|valid\w+|verific\w+)\b")),
    ("resumir_o_clasificar", re.compile(
        r"^(?:(?:un|una|el|la)\s+)?(?:resum\w+|sintetiz\w+|clasific\w+|categoriz\w+|traduc\w+|list\w+|enumer\w+|"
        r"extra\w+|ordena\w*|agrup\w+|etiquet\w+|lista|traduccion|clasificacion)\b")),
    ("redactar_texto", re.compile(
        r"^(?:(?:un|una|el|la)\s+)?(?:redact\w+|escrib\w+|genera\w*|crea\w*|propon\w+|sugier\w+|suger\w+|"
        r"elabor\w+|prepar\w+|borrador|ejemplo|idea\w*|plan|titulo\w*|slogan\w*|correo|mensaje|texto|post|copy)\b")),
    ("responder_pregunta", re.compile(
        r"^(?:(?:un|una|el|la)\s+)?(?:explic\w+|defin\w+|describ\w+|cuent\w+|dime|dec\w+|muestr\w+|ensen\w+|"
        r"calcul\w+|cuant\w+|cual\w*|que|como|por que|porque|para que|cuando|donde|quien\w*|cuanto\w*|"
        r"sabes|conoces|hay|existe\w*|es|son|sirve\w*|ayud\w+|dame|dar|di|menciona\w*|indica\w*|responde\w*|"
        r"explicacion|definicion|what|how|why|when|where|who|explain|define|describe|tell|show|list|summarize)\b")),
]
_PREFIJOS = re.compile(
    r"^(?:por favor|porfa|please|hola|growi|oye|ok|vale|bueno|quiero que|necesito que|quisiera que|te pido que|"
    r"me puedes|me podrias|puedes|podrias|podria|puede|quiero|necesito|quisiera|me|ayudame a|ayudame con|"
    r"can you|could you|i want you to|i need)\s+")
_ARTICULOS_CONTINUACION = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "para", "por", "con", "sin", "en", "a",
    "al", "mi", "tu", "su", "sus", "mis", "tus", "lo", "que", "como", "cuando", "donde", "segun", "sobre", "entre",
    "the", "an", "of", "for", "with", "in", "on", "to", "its", "their", "his", "her", "my", "your", "from",
}
_SEPARADOR = re.compile(r"[\n;]+|\.(?=\s|$)|,(?=\s|$)|\s+(?:y luego|y despues|luego|despues|ademas|tambien|and then|then|y|e|o|and|or|pero)\s+",
                        re.IGNORECASE)


def _norm(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _limpiar_fragmento(f):
    f = _norm(f).strip(" \t\r\n\"'`¿?¡!:()[]{}-*")
    f = re.sub(r"\s+", " ", f)
    cambio = True
    while cambio:
        cambio = False
        m = _PREFIJOS.match(f)
        if m:
            f = f[m.end():]
            cambio = True
    return f


def _denegadas_de(cuenta):
    """Clases extra denegadas de una cuenta (accounts.json -> permisos).

    Fase 1 fija el esquema: solo deniega si la cuenta está en modo
    «restringido». Si el registro no existe o no se puede leer, no deniega
    nada: el comportamiento global de siempre (el endurecimiento del
    harness llega en la Fase 4).
    """
    try:
        path = os.environ.get("GROWI_ACCOUNTS_JSON") or os.path.join(AQUI, "accounts.json")
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
        for c in reg.get("cuentas", []):
            if c.get("id") == cuenta:
                per = c.get("permisos") or {}
                if per.get("modo") == "restringido":
                    return [str(x) for x in per.get("clases_extra_denegadas") or []]
                return []
    except Exception:
        return []
    return []


def clasificar_tarea(texto, cuenta=None):
    """-> (clases_ordenadas, motivo_error). Todos los fragmentos deben ser acciones reconocidas.

    Con `cuenta`, además de la lista blanca global se aplican las clases
    extra denegadas de esa cuenta (ver _denegadas_de)."""
    texto = str(texto or "").strip()
    if not texto:
        return [], "peticion vacia"
    fragmentos = [f for f in _SEPARADOR.split(texto) if f and f.strip()]
    if not fragmentos:
        return [], "peticion vacia"
    clases = []
    for i, original in enumerate(fragmentos):
        limpio = _limpiar_fragmento(original)
        if not limpio:
            continue
        destructivo = es_destructivo(original)
        if destructivo and ACCION_DESTRUCTIVA not in clases:
            clases.append(ACCION_DESTRUCTIVA)
        clase = next((c for c, rx in _CLASES if rx.match(limpio)), None)
        if clase:
            if clase not in clases:
                clases.append(clase)
            continue
        if destructivo:
            continue  # la accion destructiva ya quedo registrada: exige confirmacion humana
        primera = limpio.split(" ")[0]
        original_limpio = original.strip(" \t\"'`¿?¡!:()[]{}-*")
        capitalizada = bool(original_limpio) and (original_limpio[0].isupper() or original_limpio[0].isdigit())
        if i > 0 and (primera in _ARTICULOS_CONTINUACION or capitalizada):
            continue  # continuacion de la accion anterior (lista de objetos), no una accion nueva
        return clases, "accion no reconocida en la lista blanca: «%s»" % original.strip()[:60]
    if not clases:
        return [], "no se reconoce ninguna accion permitida"
    if cuenta:
        den = set(_denegadas_de(cuenta))
        malas = [c for c in clases if c in den]
        if malas:
            return clases, "accion denegada para la cuenta %s: %s" % (cuenta, ", ".join(malas))
    return clases, ""


def _es_candidata_ruta(tok):
    if "://" in tok:
        return False
    if re.match(r"^[A-Za-z]:", tok) or tok.startswith(("\\\\", "//", "/", "\\", "~", "./", ".\\", "..")):
        return True
    partes = re.split(r"[\\/]", tok)
    if ".." in partes:
        return True
    seps = len(partes) - 1
    return seps >= 2 or (seps == 1 and bool(re.search(r"\.\w{1,6}$", tok)))


def _rutas_fuera_de_alcance(texto):
    """Normaliza con realpath TODA ruta que aparezca en el texto (absoluta, relativa con .., UNC, /ruta, ~)
    y devuelve las que caen fuera de RAIZ_PROYECTO."""
    raiz = os.path.normcase(os.path.realpath(RAIZ_PROYECTO))
    fuera = []
    for tok in re.split(r"[\s\"'`<>|*?]+", str(texto)):
        tok = tok.lstrip("([{¿¡").rstrip(".,;:)]}?!")
        if not tok or not _es_candidata_ruta(tok):
            continue
        t = os.path.expanduser(tok) if tok.startswith("~") else tok
        if t.startswith(("\\\\", "//")):  # UNC: siempre fuera
            fuera.append(tok[:60])
            continue
        if os.path.isabs(t) or re.match(r"^[A-Za-z]:", t) or t.startswith(("/", "\\")):
            real = os.path.realpath(t)  # "/x" cuelga de la unidad actual: fuera salvo que sea el proyecto
        else:
            real = os.path.realpath(os.path.join(RAIZ_PROYECTO, t))
        real = os.path.normcase(real)
        if real != raiz and not real.startswith(raiz + os.sep):
            fuera.append(tok[:60])
    return fuera


# -------------------------------------------------------------- Auditoria
class AuditoriaError(Exception):
    pass


_HILO = threading.RLock()


@contextmanager
def _bloqueo(path):
    with _HILO:
        f = None
        try:
            f = open(path + ".lock", "a+b")
            if msvcrt:
                for _ in range(50):
                    try:
                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise AuditoriaError("no se pudo bloquear %s" % path)
            yield
        except AuditoriaError:
            raise
        except OSError as e:
            raise AuditoriaError("bloqueo de auditoria: %s" % e)
        finally:
            if f is not None:
                try:
                    if msvcrt:
                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
                f.close()


def _hash_entrada(prev, entrada):
    cuerpo = json.dumps(entrada, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((prev + cuerpo).encode("utf-8")).hexdigest()


def _ultimo_hash(path):
    """Hash de la ultima entrada; GENESIS si no hay archivo/esta vacio; AuditoriaError si esta danado."""
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return GENESIS
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        tam = f.tell()
        f.seek(max(0, tam - 65536))
        cola = f.read().decode("utf-8", errors="replace")
    lineas = [l for l in cola.splitlines() if l.strip()]
    if not lineas:
        return GENESIS
    try:
        ult = json.loads(lineas[-1])
        h = ult["hash"]
    except Exception as e:  # noqa: BLE001
        raise AuditoriaError("ultima entrada del audit log danada (%s)" % type(e).__name__)
    if not re.fullmatch(r"[0-9a-f]{64}", str(h)):
        raise AuditoriaError("hash invalido en el audit log")
    return h


CUENTA_DEFECTO = "principal"
_RX_CUENTA = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")


def audit_path_de(cuenta=None):
    """El archivo de auditoría de una cuenta (Fase 1): la de defecto conserva
    audit-log.json intacto; cada otra cuenta tiene el suyo, con su propia
    cadena de hashes, en la misma carpeta."""
    if not cuenta or cuenta == CUENTA_DEFECTO:
        return AUDIT_PATH
    if not _RX_CUENTA.match(str(cuenta)):
        raise AuditoriaError("cuenta inválida para auditoría: %r" % (cuenta,))
    return os.path.join(os.path.dirname(AUDIT_PATH), "audit-log-%s.json" % cuenta)


def auditoria_disponible(cuenta=None):
    """Comprueba (sin escribir entradas) que el log se puede leer/escribir. -> (ok, motivo)"""
    path = audit_path_de(cuenta)
    try:
        with _bloqueo(path):
            _ultimo_hash(path)
            with open(path, "ab"):
                pass
        return True, ""
    except (AuditoriaError, OSError) as e:
        return False, "auditoria no disponible: %s" % e


def _rotar_si_hace_falta(path):
    if os.path.isfile(path) and os.path.getsize(path) > AUDIT_MAX_BYTES:
        raiz = os.path.splitext(os.path.basename(path))[0]
        base = os.path.join(os.path.dirname(path), "%s-%s.json" % (raiz, datetime.now().strftime("%Y-%m")))
        destino, n = base, 1
        while os.path.exists(destino):  # nunca se pisa un archivo
            n += 1
            destino = base[:-5] + "-%d.json" % n
        os.rename(path, destino)


def resumir(prompt):
    return re.sub(r"\s+", " ", str(prompt or "")).strip()[:RESUMEN_MAX]


def registrar(tool, prompt, resultado, motivo_bloqueo=None, duracion_s=0.0, accion=None, cuenta=None):
    """Anade una entrada encadenada. Lanza AuditoriaError si no se pudo escribir.

    Con `cuenta` (Fase 1), la entrada va al audit log de esa cuenta, con su
    propia cadena de hashes, y lleva los campos `v: 2` y `cuenta`."""
    if resultado not in ("ok", "bloqueado", "error"):
        raise AuditoriaError("resultado invalido: %r" % resultado)
    path = audit_path_de(cuenta)
    entrada = {
        "v": 2,
        "cuenta": cuenta or CUENTA_DEFECTO,
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "motor": MOTOR_DE.get(tool, str(tool)),
        "tool": str(tool),
        "accion": resumir(prompt),
        "resultado": resultado,
        "motivo_bloqueo": motivo_bloqueo or None,
        "duracion_s": round(float(duracion_s), 2),
    }
    if accion:
        entrada["accion_clase"] = accion
    try:
        with _bloqueo(path):
            prev = _ultimo_hash(path)
            _rotar_si_hace_falta(path)
            entrada["prev_hash"] = prev
            entrada["hash"] = _hash_entrada(prev, {k: v for k, v in entrada.items()})
            linea = json.dumps(entrada, ensure_ascii=False, sort_keys=False) + "\n"
            with open(path, "ab") as f:  # append-only: nunca se reescribe
                f.write(linea.encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
            _actualizar_ancla(path, entrada)
    except AuditoriaError:
        raise
    except OSError as e:
        raise AuditoriaError("no se pudo escribir el audit log: %s" % e)
    return entrada


def _ruta_indice(path):
    return os.path.join(os.path.dirname(path), "audit-indice.json")


def _actualizar_ancla(path, entrada):
    """Ancla externa de la cadena (Fase 1): cabeza y nº de entradas por
    archivo, en audit-indice.json. Borrar o truncar un log entero ya no
    pasa inadvertido: verificar_ancla() compara el archivo con su ancla."""
    ruta = _ruta_indice(path)
    try:
        with open(ruta, encoding="utf-8") as f:
            indice = json.load(f)
        if not isinstance(indice, dict):
            indice = {}
    except (OSError, ValueError):
        indice = {}
    nombre = os.path.basename(path)
    datos = indice.get(nombre) or {}
    if datos.get("cabeza") == entrada["prev_hash"]:
        n = int(datos.get("entradas") or 0) + 1
    else:
        # Primera entrada, rotación o índice perdido: se cuenta el archivo.
        try:
            with open(path, "rb") as f:
                n = sum(1 for linea_f in f if linea_f.strip())
        except OSError:
            n = 1
    indice[nombre] = {"cabeza": entrada["hash"], "entradas": n}
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(indice, f, indent=2, sort_keys=True)
    os.replace(tmp, ruta)


def verificar_ancla(cuenta=None):
    """(ok, motivo): el log de la cuenta coincide con su ancla (misma
    cabeza y mismo nº de entradas). Sin ancla devuelve (False, motivo):
    puede ser un log anterior a la Fase 1 o un borrado completo."""
    path = audit_path_de(cuenta)
    try:
        with open(_ruta_indice(path), encoding="utf-8") as f:
            indice = json.load(f)
        datos = (indice or {}).get(os.path.basename(path))
    except (OSError, ValueError):
        datos = None
    if not datos:
        return False, "sin ancla registrada para %s" % os.path.basename(path)
    try:
        cabeza = _ultimo_hash(path)
        with open(path, "rb") as f:
            n = sum(1 for linea_f in f if linea_f.strip())
    except (AuditoriaError, OSError) as e:
        return False, "no se pudo leer el log: %s" % e
    if cabeza != datos.get("cabeza"):
        return False, "la cabeza del log no coincide con el ancla"
    if n != datos.get("entradas"):
        return False, ("el nº de entradas (%d) no coincide con el ancla (%s)"
                       % (n, datos.get("entradas")))
    return True, ""


def verificar_cadena(path=None):
    """-> (ok, n_entradas, detalle). Recorre el log y comprueba la cadena de hashes."""
    path = path or AUDIT_PATH
    if not os.path.isfile(path):
        return True, 0, "sin log"
    prev, n = None, 0
    with open(path, "r", encoding="utf-8") as f:
        for i, linea in enumerate(f, 1):
            if not linea.strip():
                continue
            try:
                e = json.loads(linea)
            except ValueError:
                return False, n, "linea %d no es JSON" % i
            h = e.pop("hash", None)
            if prev is not None and e.get("prev_hash") != prev:
                return False, n, "cadena rota en la linea %d" % i
            if _hash_entrada(e.get("prev_hash", ""), e) != h:
                return False, n, "hash no coincide en la linea %d" % i
            prev, n = h, n + 1
    return True, n, "cadena integra"


# ---------------------------------------------------------- Confirmaciones
def _secreto():
    if not os.path.isfile(SECRET_PATH):
        tmp = SECRET_PATH + ".tmp"
        with open(tmp, "wb") as f:
            f.write(os.urandom(32))
        os.replace(tmp, SECRET_PATH)
    with open(SECRET_PATH, "rb") as f:
        return f.read()


def _firma(reg):
    msg = "|".join(str(reg.get(k, "")) for k in ("id", "sesion", "tool", "accion", "estado", "resuelta"))
    return hmac.new(_secreto(), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _leer_confirmaciones():
    try:
        with open(CONFIRM_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar_confirmaciones(d):
    tmp = CONFIRM_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIRM_PATH)


def _id_confirmacion(sesion, tool, accion):
    return hashlib.sha256(("%s|%s|%s" % (sesion, tool, accion)).encode()).hexdigest()[:12]


def _estado_confirmacion(sesion, tool, accion):
    """-> (estado, id): 'aprobada' | 'rechazada' | 'pendiente' | 'ninguna'. Firma y vigencia verificadas."""
    cid = _id_confirmacion(sesion, tool, accion)
    with _HILO:
        reg = _leer_confirmaciones().get(cid)
    if not reg:
        return "ninguna", cid
    if reg.get("estado") in ("aprobada", "rechazada"):
        if not hmac.compare_digest(str(reg.get("firma", "")), _firma(reg)):
            return "ninguna", cid  # manipulada: se ignora y se vuelve a pedir
        try:
            edad = time.time() - datetime.fromisoformat(reg["resuelta"]).timestamp()
        except Exception:  # noqa: BLE001
            return "ninguna", cid
        if edad > CONFIRM_VIGENCIA_S:
            return "ninguna", cid
    return reg.get("estado", "ninguna"), cid


def _pedir_confirmacion(sesion, tool, accion, resumen):
    estado, cid = _estado_confirmacion(sesion, tool, accion)
    if estado == "ninguna":
        with _HILO:
            d = _leer_confirmaciones()
            d[cid] = {"id": cid, "sesion": sesion, "tool": tool, "accion": accion, "resumen": resumen,
                      "estado": "pendiente", "creada": datetime.now().astimezone().isoformat(timespec="seconds")}
            _guardar_confirmaciones(d)
        estado = "pendiente"
    return estado, cid


def resolver_confirmacion(cid, aprobar, origen):
    """SOLO para la app/persona. El harness y los motores nunca llaman a esta funcion.
    origen debe ser 'app-humano' o 'consola-humano'."""
    if origen not in ("app-humano", "consola-humano"):
        raise PermissionError("origen no autorizado para confirmar")
    with _HILO:
        d = _leer_confirmaciones()
        reg = d.get(cid)
        if not reg:
            raise KeyError("confirmacion inexistente: %s" % cid)
        reg["estado"] = "aprobada" if aprobar else "rechazada"
        reg["resuelta"] = datetime.now().astimezone().isoformat(timespec="seconds")
        reg["origen"] = origen
        reg["firma"] = _firma(reg)
        d[cid] = reg
        _guardar_confirmaciones(d)
    return reg


# --------------------------------------------------------------- Decisiones
class Decision:
    def __init__(self, estado, motivo="", alternativa="", clases=None, confirmacion_id=None):
        self.estado = estado  # permitir | bloquear | confirmar
        self.motivo = motivo
        self.alternativa = alternativa
        self.clases = clases or []
        self.confirmacion_id = confirmacion_id

    @property
    def permitido(self):
        return self.estado == "permitir"

    def mensaje(self):
        if self.estado == "permitir":
            return "permitido"
        if self.estado == "confirmar":
            return ("BLOQUEADO: requiere confirmacion de una persona (id %s). La confirma el usuario desde la app; "
                    "el agente no puede confirmarla. Alternativa: %s" % (self.confirmacion_id, self.alternativa))
        return "BLOQUEADO por la capa de permisos: %s. Alternativa: %s" % (self.motivo, self.alternativa)


def _alternativa(clases, tool=None):
    if not clases:
        return "reformula la peticion con una accion permitida (explicar, resumir, clasificar, traducir, analizar, redactar o generar codigo)"
    aptas = [t for t, c in TOOLS_PERMITIDAS.items() if all(x in c["acciones"] for x in clases) and t != tool]
    if aptas:
        return "usa " + " o ".join(aptas)
    return "pide solo la parte de texto/analisis y aplica el cambio a mano"


class CapaPermisos:
    def __init__(self, sesion=None, cuenta=None):
        self.sesion = sesion or os.environ.get("GROWI_SESION") or "s%d-%d" % (os.getpid(), int(time.time()))
        # Fase 4: la cuenta Muse dueña de la ejecución. Con cuenta, la
        # clasificación aplica sus clases extra denegadas y la auditoría
        # cae en su audit-log-<cuenta>.json. Sin cuenta (None), el
        # comportamiento histórico de la Fase 1.
        self.cuenta = cuenta
        self._tarea_ok = False
        self._tarea_resumen = ""

    def _chequear(self, tool, clases, prompt):
        cfg = TOOLS_PERMITIDAS.get(tool)
        if cfg is None:
            return Decision("bloquear", "tool «%s» no esta en la lista blanca" % tool,
                            "usa una de: " + ", ".join(TOOLS_PERMITIDAS), clases)
        for c in clases:
            if c not in cfg["acciones"]:
                return Decision("bloquear", "la accion «%s» no esta permitida para %s" % (c, tool),
                                _alternativa(clases, tool), clases)
        if any(c in ACCIONES_ESCRITURA for c in clases):
            fuera = _rutas_fuera_de_alcance(prompt)
            if fuera:
                return Decision("bloquear", "ruta fuera del alcance del proyecto: %s" % fuera[0],
                                "limita el cambio a archivos dentro de %s" % RAIZ_PROYECTO, clases)
        conf = [c for c in clases if cfg["acciones"][c]["requiere_confirmacion"] or cfg["requiere_confirmacion"]]
        for c in conf:
            clave = c
            if c == ACCION_DESTRUCTIVA:  # aprobar "borra a" no aprueba "borra b": la clave incluye la peticion
                clave = "%s:%s" % (c, hashlib.sha256(_norm(prompt).strip().encode("utf-8")).hexdigest()[:10])
            estado, cid = _pedir_confirmacion(self.sesion, tool, clave, resumir(prompt))
            if estado == "rechazada":
                return Decision("bloquear", "la persona rechazo la accion «%s»" % c, _alternativa(clases, tool), clases, cid)
            if estado != "aprobada":
                return Decision("confirmar", "requiere confirmacion humana", 
                                "pide al usuario que confirme el id %s en la app (sesion %s)" % (cid, self.sesion),
                                clases, cid)
        return Decision("permitir", clases=clases)

    def verificar_permiso(self, tool, prompt, accion=None):
        """Antes de cada tool call. accion=None -> se clasifica el prompt (peticion del usuario).
        accion='consulta_motor' lo pone el codigo del harness para las llamadas del loop."""
        ok, motivo = auditoria_disponible()
        if not ok:
            return Decision("bloquear", motivo, "revisa permisos de escritura de audit-log.json")
        if tool not in TOOLS_PERMITIDAS:
            return Decision("bloquear", "tool «%s» no esta en la lista blanca" % tool,
                            "usa una de: " + ", ".join(TOOLS_PERMITIDAS))
        if accion is not None:
            if accion != "consulta_motor":
                return Decision("bloquear", "accion interna desconocida «%s»" % accion, "usa consulta_motor")
            if not self._tarea_ok:
                return Decision("bloquear", "la peticion del usuario no fue autorizada antes de llamar al motor",
                                "pasa primero por verificar_permiso con la peticion")
            return self._chequear(tool, ["consulta_motor"], prompt)
        clases, error = clasificar_tarea(prompt, cuenta=self.cuenta)
        if error:
            return Decision("bloquear", error, _alternativa([]))
        d = self._chequear(tool, clases, prompt)
        if d.permitido:
            self._tarea_ok = True
            self._tarea_resumen = resumir(prompt)
        return d

    def verificar_tarea(self, prompt, cadena):
        """Peticion del usuario contra la cadena de motores del router: vale si algun motor la permite."""
        mejor = None
        for tool in cadena:
            d = self.verificar_permiso(tool, prompt)
            if d.permitido:
                return d, tool
            if mejor is None or (d.estado == "confirmar" and mejor[0].estado == "bloquear"):
                mejor = (d, tool)
        return mejor if mejor else (Decision("bloquear", "cadena de motores vacia", _alternativa([])), None)

    def ejecutar_con_permiso(self, tool, prompt, funcion, accion="consulta_motor"):
        """Chequea -> ejecuta funcion(prompt) -> audita. Siempre devuelve texto (nunca lanza)."""
        d = self.verificar_permiso(tool, prompt, accion)
        # en el loop el prompt es el contexto interno del agente: el log resume la peticion del usuario
        visible = ("[%s] %s" % (accion, self._tarea_resumen)) if (accion == "consulta_motor" and self._tarea_resumen) else prompt
        if not d.permitido:
            try:
                registrar(tool, visible, "bloqueado", d.motivo, 0.0, accion,
                          cuenta=self.cuenta)
            except AuditoriaError:
                pass
            return d.mensaje()
        t0 = time.time()
        try:
            salida = str(funcion(prompt))
            resultado = "error" if salida.startswith("ERROR") else "ok"
        except Exception as e:  # noqa: BLE001
            salida, resultado = "ERROR: %s: %s" % (type(e).__name__, e), "error"
        try:
            registrar(tool, visible, resultado, None, time.time() - t0,
                      accion, cuenta=self.cuenta)
        except AuditoriaError as e:
            return "BLOQUEADO: la accion no se pudo auditar (%s); se descarta el resultado" % e
        return salida

    def registrar_bloqueo(self, tool, prompt, decision):
        try:
            registrar(tool or "ninguna", prompt, "bloqueado", decision.motivo or "requiere confirmacion humana",
                      0.0, ",".join(decision.clases) or None,
                      cuenta=self.cuenta)
            return True
        except AuditoriaError:
            return False


# Instancia por defecto + API de modulo
_DEFECTO = CapaPermisos()


def verificar_permiso(tool, prompt, accion=None):
    return _DEFECTO.verificar_permiso(tool, prompt, accion)


def nueva_capa(sesion=None, cuenta=None):
    global _DEFECTO
    _DEFECTO = CapaPermisos(sesion, cuenta)
    return _DEFECTO


# ---------------------------------------------------------------------- CLI
def _main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    if len(argv) >= 2 and argv[1] == "--verificar-log":
        ok, n, det = verificar_cadena()
        print("%s: %d entradas, %s" % ("OK" if ok else "FALLA", n, det))
        return 0 if ok else 1
    if len(argv) >= 2 and argv[1] == "--pendientes":
        for r in _leer_confirmaciones().values():
            if r.get("estado") == "pendiente":
                print("%s  %s/%s  sesion=%s  %s" % (r["id"], r["tool"], r["accion"], r["sesion"], r.get("resumen", "")))
        return 0
    if len(argv) >= 3 and argv[1] in ("--confirmar", "--rechazar"):
        if not (sys.stdin and sys.stdin.isatty()):
            print("Solo una persona en una consola interactiva puede confirmar (o la app Growi Bridge).")
            return 2
        reg = _leer_confirmaciones().get(argv[2])
        if not reg or reg.get("estado") != "pendiente":
            print("No hay una confirmacion pendiente con ese id.")
            return 1
        print("%s/%s: %s" % (reg["tool"], reg["accion"], reg.get("resumen", "")))
        if input("Escribe SI para %s: " % ("confirmar" if argv[1] == "--confirmar" else "rechazar")).strip() != "SI":
            print("Cancelado.")
            return 1
        resolver_confirmacion(argv[2], argv[1] == "--confirmar", "consola-humano")
        print("Hecho.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv))

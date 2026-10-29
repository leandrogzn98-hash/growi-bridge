"""Supervisor local de Growi Bridge (el "subgerente").

Cada pasada lee el estado del Bridge en este equipo, se lo da a un modelo (el proveedor del YAML) con las reglas de
escalación y, si hace falta una decisión humana, avisa por correo (Resend) al canal del gerente general. NUNCA
corrige nada: solo lee, juzga e informa. Nunca pone claves ni tokens en el prompt ni en el correo.

  python supervisor.py                 una pasada (lo que corre la tarea programada)
  python supervisor.py --dry-run       veredicto y correo por pantalla, sin enviar ni llamar a ninguna API
  python supervisor.py --configurar    asistente de primera corrida: escribe supervisor-config.yaml
  python supervisor.py --verificar     chequeo de salud OK/FAIL por punto
  python supervisor.py --intervalo     imprime el intervalo en minutos (lo usan los instaladores)
  python supervisor.py --evals         evals del juez: estados sintéticos con su veredicto esperado (sin correo)

Opciones: --config RUTA (otro YAML), --bridge CARPETA (otra instalación del Bridge, p. ej. una de prueba).
"""

import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import proveedores  # noqa: E402

CONFIG_POR_DEFECTO = AQUI / "supervisor-config.yaml"
SERVICIO_LLAVERO = "growi-supervisor"
VEREDICTOS = ("TODO_BIEN", "NECESITA_DECISION")
OBLIGATORIOS = ("subgerente.proveedor", "subgerente.modelo", "subgerente.clave.origen", "subgerente.intervalo_minutos",
                "gerente_general.nombre", "gerente_general.reportes.from", "gerente_general.reportes.to",
                "gerente_general.reportes.prefijo_asunto", "gerente_general.reportes.clave_resend.origen",
                "gerente_general.reportes.clave_resend.nombre", "bridge.carpeta", "bridge.share",
                "bridge.puerto_gateway", "escalacion.reaviso_horas", "programacion.nombre_tarea", "datos")


class ErrorConfig(RuntimeError):
    pass


# ---------------------------------------------------------------- configuración y claves

def _get(d, ruta, defecto=None):
    for parte in ruta.split("."):
        if not isinstance(d, dict) or parte not in d:
            return defecto
        d = d[parte]
    return d


def cargar_config(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorConfig(f"no existe {ruta}: corre «supervisor.py --configurar» para crearlo")
    try:
        cfg = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErrorConfig(f"{ruta.name} no es YAML válido: {e}") from None
    faltan = [k for k in OBLIGATORIOS if _get(cfg, k) in (None, "")]
    if faltan:
        raise ErrorConfig(f"{ruta.name} está incompleto, falta: {', '.join(faltan)}")
    if cfg["subgerente"]["clave"]["origen"] not in ("entorno", "llavero"):
        raise ErrorConfig("subgerente.clave.origen debe ser «entorno» o «llavero» (las claves nunca van en el YAML)")
    proveedores.cargar(cfg["subgerente"]["proveedor"])  # ValueError claro si no existe
    return cfg


def ruta_usuario(texto):
    return Path(os.path.expanduser(str(texto)))


def leer_clave(spec):
    """La clave según {origen, nombre}; None si no está. Nunca se imprime."""
    nombre = (spec or {}).get("nombre") or ""
    if not nombre:
        return None
    if spec.get("origen") == "llavero":
        import keyring
        return keyring.get_password(SERVICIO_LLAVERO, nombre)
    return os.environ.get(nombre) or None


def donde_clave(spec):
    if spec.get("origen") == "llavero":
        return f"el llavero del sistema (servicio «{SERVICIO_LLAVERO}», entrada «{spec.get('nombre')}»)"
    return f"la variable de entorno {spec.get('nombre')}"


def clave_subgerente(cfg):
    mod = proveedores.cargar(cfg["subgerente"]["proveedor"])
    if not mod.CLAVE_POR_DEFECTO:  # proveedores sin clave (ollama, mock)
        return ""
    clave = leer_clave(cfg["subgerente"]["clave"])
    if not clave:
        raise ErrorConfig(f"falta la clave de {cfg['subgerente']['proveedor']}: no está en "
                          f"{donde_clave(cfg['subgerente']['clave'])}. Ponla ahí o corre «supervisor.py --configurar»")
    return clave


# ---------------------------------------------------------------- sin secretos

_SECRETOS = [re.compile(p) for p in (
    r"(?i)\b(sk|rk|pk|re|ghp|gho|xox[abp])[-_][A-Za-z0-9_\-]{12,}",
    r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}",
    r"(?i)\b(api[_-]?key|token|secret|password|clave|contraseña)\b\s*[:=]\s*\S+",
    r"\b[A-Fa-f0-9]{32,}\b",
    r"\b[A-Za-z0-9+/_\-]{40,}={0,2}",
)]


def sin_secretos(texto):
    texto = str(texto)
    for rx in _SECRETOS:
        texto = rx.sub("[oculto]", texto)
    return texto


# ---------------------------------------------------------------- estado del Bridge

def _fecha(txt):
    if not txt:
        return None
    try:
        d = datetime.fromisoformat(str(txt).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.astimezone()


def _leer_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def recoger_estado(cfg, ahora, desde):
    """Foto operativa del Bridge (nada de claves). desde = la pasada anterior: lo más nuevo cuenta como «nuevo»."""
    b, esc = cfg["bridge"], cfg.get("escalacion") or {}
    carpeta, share = ruta_usuario(b["carpeta"]), ruta_usuario(b["share"])
    est = {"hora": ahora.isoformat(timespec="seconds"), "carpeta_existe": carpeta.is_dir()}
    # app supuestamente abierta: su log se tocó hace poco o hay gateway.lock
    log_app = carpeta / "growi-bridge.log"
    abierta_min = esc.get("app_abierta_min", 15)
    reciente = log_app.is_file() and (ahora.timestamp() - log_app.stat().st_mtime) < abierta_min * 60
    est["app_deberia_estar_abierta"] = bool(reciente or (carpeta / "gateway.lock").is_file())
    s = requests.Session()
    s.trust_env = False  # 127.0.0.1: nunca por un proxy
    try:
        r = s.get(f"http://127.0.0.1:{b['puerto_gateway']}/gateway/salud", timeout=3)
        est["gateway"] = "arriba" if r.ok else f"responde {r.status_code}"
    except requests.RequestException as e:
        est["gateway"] = f"no responde ({type(e).__name__})"
    # runner
    st = _leer_json(share / "outbox" / "runner-status.json") or {}
    lp = _fecha(st.get("last_poll"))
    est["runner"] = {"latido_hace_min": None if lp is None else round((ahora - lp).total_seconds() / 60, 1),
                     "tarea_en_curso": (st.get("current") or {}).get("id") if isinstance(st.get("current"), dict)
                     else st.get("current")}
    # resultados recientes
    ventana = ahora - timedelta(hours=esc.get("ventana_horas", 24))
    decision, errores = [], []
    for p in sorted((share / "outbox" / "runner-results").glob("*.result.json")):
        d = _leer_json(p)
        if not isinstance(d, dict):
            continue
        fin = _fecha(d.get("finished_at") or d.get("revisado_at")) or datetime.fromtimestamp(p.stat().st_mtime).astimezone()
        if fin < ventana:
            continue
        tid = str(d.get("id") or p.name.split(".")[0])
        motivo = sin_secretos(str(d.get("motivo_decision") or d.get("motivo") or d.get("error") or "")[:200])
        if d.get("estado") == "necesita_decision":
            decision.append({"id": tid, "desde": fin.isoformat(timespec="minutes"), "motivo": motivo})
        elif (d.get("estado") == "fallida" or d.get("status") in ("error", "timeout")) and fin > desde:
            errores.append({"id": tid, "cuando": fin.isoformat(timespec="minutes"),
                            "estado": d.get("estado") or d.get("status"), "motivo": motivo})
    est["tareas_necesita_decision"], est["errores_nuevos_runner"] = decision, errores
    # cadenas
    cadenas = []
    for patron in b.get("cadenas") or []:
        for p in sorted(share.glob(patron)):
            d = _leer_json(p)
            if isinstance(d, dict):
                cadenas.append({"archivo": p.name, "fase": d.get("fase"),
                                "detenido": sin_secretos(d["detenido"])[:200] if d.get("detenido") else None,
                                "ultimo_enviado": d.get("ultimo_enviado")})
    est["cadenas"] = cadenas
    # logs: solo líneas de error posteriores a la pasada anterior
    lineas = []
    for rel in b.get("logs") or []:
        p = carpeta / rel
        if not p.is_file():
            continue
        try:
            cola = p.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
        except OSError:
            continue
        for ln in cola:
            t = _fecha(ln[:25].strip())
            if t and t > desde and re.search(r"(?i)traceback|\berror\b|falló|fallo\b", ln):
                lineas.append(f"{rel}: {sin_secretos(ln[:240])}")
    est["log_errores_nuevos"] = lineas[-esc.get("lineas_log", 40):]
    return est


def candidatas(est, cfg):
    """Lo que PODRÍA necesitar una decisión, con clave estable (para no repetir) y firma (para re-avisar si cambia).
    grave = lo que las reglas consideran NECESITA_DECISION; el modelo puede confirmar, descartar o sumar del resto."""
    esc = cfg.get("escalacion") or {}
    out = []

    def add(clave, titulo, detalle, grave):
        firma = hashlib.sha256(json.dumps(detalle, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        out.append({"clave": clave, "titulo": titulo, "detalle": detalle, "grave": grave, "firma": firma})

    for c in est["cadenas"]:
        if c["detenido"]:
            add(f"cadena:{c['archivo']}", f"Cadena detenida ({c['archivo']})",
                {"fase": c["fase"], "detenido": c["detenido"]}, True)
    for t in est["tareas_necesita_decision"]:
        add(f"tarea:{t['id']}", f"Tarea {t['id']} espera tu decisión", t, True)
    if est["gateway"] != "arriba":
        add("gateway", "El gateway del Bridge no responde", {"gateway": est["gateway"],
            "app_deberia_estar_abierta": est["app_deberia_estar_abierta"]}, est["app_deberia_estar_abierta"])
    for e in est["errores_nuevos_runner"]:
        add(f"error:{e['id']}", f"Error nuevo del runner en {e['id']}", e, True)
    lat = est["runner"]["latido_hace_min"]
    if est["app_deberia_estar_abierta"] and (lat is None or lat > esc.get("latido_runner_min", 10)):
        add("runner:latido", "El runner no da señales", {"latido_hace_min": lat}, False)
    if est["log_errores_nuevos"]:
        add("log:errores", "Líneas de error nuevas en los logs", {"n": len(est["log_errores_nuevos"])}, False)
    return out


# ---------------------------------------------------------------- juicio (desconfía del modelo por diseño)

REGLAS = """Eres el subgerente (supervisor) de Growi Bridge en el PC de su dueño. Solo lees, juzgas e informas:
nunca propones reiniciar, borrar ni reintentar nada por tu cuenta.

NECESITA_DECISION (hay que escribirle al dueño) cuando hay al menos uno de estos:
- una cadena de tareas detenida (campo "detenido" con texto);
- una tarea en estado necesita_decision que nadie ha atendido;
- el gateway no responde y la app debería estar abierta;
- errores nuevos del runner (tareas fallidas, con error o timeout desde la pasada anterior).

Es RUIDO y se ignora: el gateway caído con la app cerrada a propósito, una línea de error suelta en el log sin tarea
fallida, un latido algo viejo con la app cerrada, avisos ya resueltos.

Responde SOLO con un objeto JSON, sin texto antes ni después, con EXACTAMENTE estas tres claves:
{"veredicto": "TODO_BIEN" o "NECESITA_DECISION",
 "evidencia": [frases copiadas del <estado> que justifican el veredicto],
 "confianza": un número entre 0 y 1}"""


def armar_prompt(est, cands, cfg):
    vista = [{k: c[k] for k in ("clave", "titulo", "detalle", "grave")} for c in cands]
    return (f"{REGLAS}\n\nGerente general: {cfg['gerente_general']['nombre']}.\n\n<estado>\n"
            f"{json.dumps(est, ensure_ascii=False, indent=1)}\n</estado>\n\n<candidatas>\n"
            f"{json.dumps(vista, ensure_ascii=False)}\n</candidatas>")


def _largo(est):
    return len(json.dumps(est, ensure_ascii=False, indent=1))


def recortar_estado(est, tope):
    """El estado cabe en tope caracteres: primero se recortan las líneas de log, luego las listas largas."""
    largo = _largo(est)
    if largo <= tope:
        return est, None
    est = json.loads(json.dumps(est))
    est["recortado"] = []  # dentro del recorte: la propia marca también cuenta para el tope
    for campo in ("log_errores_nuevos", "errores_nuevos_runner", "tareas_necesita_decision", "cadenas"):
        while est.get(campo) and _largo(est) > tope:
            est[campo] = est[campo][:-1]
            if campo not in est["recortado"]:
                est["recortado"].append(campo)
    return est, (f"estado de {largo} caracteres recortado a {_largo(est)} (tope {tope}): "
                 f"{', '.join(est['recortado'])}")


def hash_estado(est):
    sin_hora = {k: v for k, v in est.items() if k != "hora"}
    return hashlib.sha256(json.dumps(sin_hora, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def validar_veredicto(texto):
    """(dict, None) si es JSON con EXACTAMENTE {veredicto, evidencia, confianza} válidos; (None, motivo) si no."""
    t = (texto or "").strip()
    if t.startswith("```"):  # un bloque de código alrededor del JSON se tolera; nada más
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        d = json.loads(t)
    except ValueError:
        return None, f"no es JSON: {t[:120]!r}"
    if not isinstance(d, dict) or set(d) != {"veredicto", "evidencia", "confianza"}:
        return None, f"schema distinto: claves {sorted(d) if isinstance(d, dict) else type(d).__name__}"
    if d["veredicto"] not in VEREDICTOS:
        return None, f"veredicto desconocido: {d['veredicto']!r}"
    if not isinstance(d["evidencia"], list) or not all(isinstance(x, str) for x in d["evidencia"]):
        return None, "evidencia no es una lista de textos"
    c = d["confianza"]
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        return None, f"confianza fuera de 0..1: {c!r}"
    return d, None


def juicio_reglas(cands, motivo="reglas"):
    graves = [c for c in cands if c["grave"]]
    return {"veredicto": "NECESITA_DECISION" if graves else "TODO_BIEN", "alertas": graves,
            "evidencia": [c["titulo"] for c in graves], "confianza": None, "fuente": motivo,
            "resumen": f"{len(graves)} asunto(s) necesitan una decisión." if graves else "Nada que decidir."}


def _contador_dia(mem, ahora):
    hoy = ahora.date().isoformat()
    if (mem.get("dia") or {}).get("fecha") != hoy:
        mem["dia"] = {"fecha": hoy, "llamadas": 0, "gasto_usd": 0.0}
    return mem["dia"]


def _alerta_del_modelo(evidencia):
    firma = hashlib.sha256("|".join(evidencia).encode()).hexdigest()
    return {"clave": "modelo:" + firma[:10], "titulo": "El supervisor ve algo que requiere decisión", "grave": True,
            "detalle": {"evidencia": evidencia}, "firma": firma[:16]}


def juzgar(est, cands, cfg, mem, ahora, log):
    """Llama al modelo con presupuesto y schema estricto, con un reintento. Devuelve el juicio o FALLO_DE_JUICIO."""
    jz = cfg.get("juez") or {}
    est_p, aviso = recortar_estado(est, jz.get("tope_estado_caracteres", 8000))
    if aviso:
        log(f"AVISO presupuesto: {aviso}")
    prompt = armar_prompt(est_p, cands, cfg)
    dia = _contador_dia(mem, ahora)
    precio = jz.get("precio_usd_por_millon_tokens")
    costo = (len(prompt) / 4) * float(precio) / 1e6 if precio else 0.0  # ~4 caracteres por token: estimación
    tope_llamadas, tope_usd = jz.get("max_llamadas_dia", 48), float(jz.get("tope_gasto_diario_usd", 0.5))
    mod = proveedores.cargar(cfg["subgerente"]["proveedor"])
    clave = clave_subgerente(cfg)
    motivos = []
    for intento in (1, 2):
        if dia["llamadas"] >= tope_llamadas:
            log(f"AVISO presupuesto: {dia['llamadas']} llamadas hoy (tope {tope_llamadas}): turno abreviado, "
                "solo reglas locales")
            return juicio_reglas(cands, "reglas (tope de llamadas)")
        if precio and dia["gasto_usd"] + costo > tope_usd:
            log(f"AVISO presupuesto: gasto estimado hoy ${dia['gasto_usd']:.4f} + ${costo:.4f} pasa el tope "
                f"${tope_usd:.2f}: turno abreviado, solo reglas locales")
            return juicio_reglas(cands, "reglas (tope de gasto)")
        dia["llamadas"] += 1
        dia["gasto_usd"] = round(dia["gasto_usd"] + costo, 6)
        texto = mod.completar(prompt, modelo=cfg["subgerente"]["modelo"], clave=clave, ajustes=cfg["subgerente"])
        d, motivo = validar_veredicto(texto)
        if d:
            ev = [sin_secretos(x)[:200] for x in d["evidencia"]][:10]
            alertas = []
            if d["veredicto"] == "NECESITA_DECISION":  # las alertas salen de las candidatas locales, no del texto
                alertas = [c for c in cands if c["grave"]] or cands or [_alerta_del_modelo(ev)]
            return {"veredicto": d["veredicto"], "alertas": alertas, "evidencia": ev, "confianza": d["confianza"],
                    "fuente": f"modelo (intento {intento})",
                    "resumen": ("; ".join(ev[:3]) or "sin evidencia citada") if alertas else "Nada que decidir."}
        motivos.append(motivo)
        log(f"FALLO_DE_JUICIO intento {intento}: {sin_secretos(motivo)}")
    return {"veredicto": "FALLO_DE_JUICIO", "alertas": [], "evidencia": [], "confianza": None, "fuente": "modelo",
            "resumen": f"respuesta inválida dos veces ({'; '.join(motivos)[:200]})"}


# ---------------------------------------------------------------- correo y memoria

def armar_correo(cfg, juicio, est):
    rep = cfg["gerente_general"]["reportes"]
    asunto = f"{rep['prefijo_asunto']} {len(juicio['alertas'])} asunto(s) necesitan tu decisión"
    lineas = [f"Hola. Soy el subgerente de {cfg['gerente_general']['nombre']} en este PC ({platform.node()}).",
              "", juicio["resumen"], "", "Qué necesita decisión:"]
    for a in juicio["alertas"]:
        lineas.append(f"- {a['titulo']}: {json.dumps(a['detalle'], ensure_ascii=False)}")
    lineas += ["", f"Gateway: {est['gateway']}. Runner: latido hace {est['runner']['latido_hace_min']} min, "
               f"tarea en curso {est['runner']['tarea_en_curso'] or 'ninguna'}.",
               f"Revisado a las {est['hora']}. No he cambiado nada: solo informo."]
    return asunto, sin_secretos("\n".join(lineas))


def enviar_resend(cfg, asunto, cuerpo):
    rep = cfg["gerente_general"]["reportes"]
    clave = leer_clave(rep["clave_resend"])
    if not clave:
        raise ErrorConfig(f"falta la clave de Resend: no está en {donde_clave(rep['clave_resend'])}")
    r = requests.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {clave}"},
                      json={"from": rep["from"], "to": [rep["to"]], "subject": asunto, "text": cuerpo}, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Resend respondió {r.status_code}: {r.text[:200]}")
    return r.json().get("id")


def _memoria_ruta(cfg):
    return ruta_usuario(cfg["datos"]) / "supervisor-memoria.json"


def leer_memoria(cfg):
    return _leer_json(_memoria_ruta(cfg)) or {"ultima_pasada": None, "enviadas": {}}


def guardar_memoria(cfg, mem):
    p = _memoria_ruta(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def filtrar_repetidas(alertas, mem, ahora, reaviso_h):
    """Solo lo nuevo, lo que cambió (otra firma) o lo que lleva reaviso_h sin avisarse."""
    out = []
    for a in alertas:
        prev = mem["enviadas"].get(a["clave"])
        if prev and prev["firma"] == a["firma"] and ahora - _fecha(prev["at"]) < timedelta(hours=reaviso_h):
            continue
        out.append(a)
    return out


def anotar(cfg, texto):
    p = ruta_usuario(cfg["datos"]) / "supervisor.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().astimezone().isoformat(timespec='seconds')} {sin_secretos(texto)}\n")


# ---------------------------------------------------------------- una pasada

def pasada(cfg, modo="real", salida=print, esperar=None):
    """modo: real (modelo + correo); dry (sin ninguna API: reglas locales, nada se envía ni se guarda);
    eval (modelo y debounce como en real, pero nunca envía correo). esperar(seg): la pausa del debounce."""
    import time
    esperar = esperar or time.sleep
    ahora = datetime.now().astimezone()
    mem = leer_memoria(cfg)
    desde = _fecha(mem.get("ultima_pasada")) or (ahora - timedelta(hours=2))
    rastro = []

    def log(texto):
        rastro.append(texto)
        if modo != "dry":
            anotar(cfg, texto)

    est = recoger_estado(cfg, ahora, desde)
    cands = candidatas(est, cfg)
    h = hash_estado(est)
    juicio = juicio_reglas(cands) if modo == "dry" else juzgar(est, cands, cfg, mem, ahora, log)
    log(f"TURNO estado={h} veredicto={juicio['veredicto']} confianza={juicio['confianza']} "
        f"fuente={juicio['fuente']} proveedor={cfg['subgerente']['proveedor']}")
    nuevas = filtrar_repetidas(juicio["alertas"], mem, ahora, cfg["escalacion"]["reaviso_horas"])
    persisten = nuevas
    if juicio["veredicto"] == "NECESITA_DECISION" and nuevas and modo != "dry":
        espera = (cfg.get("juez") or {}).get("debounce_s", 300)
        log(f"DEBOUNCE {[a['clave'] for a in nuevas]}: vuelvo a mirar en {espera} s antes de avisar")
        esperar(espera)
        est2 = recoger_estado(cfg, datetime.now().astimezone(), desde)
        graves2 = {c["clave"]: c for c in candidatas(est2, cfg) if c["grave"]}
        persisten = [graves2.get(a["clave"], a) for a in nuevas
                     if a["clave"] in graves2 or a["clave"].startswith("modelo:")]
        resueltas = [a["clave"] for a in nuevas if a["clave"] not in {p["clave"] for p in persisten}]
        if resueltas:
            log(f"FLAPPING se resolvió solo en {espera} s, no se avisa: {resueltas} (estado={hash_estado(est2)})")
        est = est2
    resultado = {"veredicto": juicio["veredicto"], "fuente": juicio["fuente"], "resumen": juicio["resumen"],
                 "confianza": juicio["confianza"], "evidencia": juicio["evidencia"], "hash_estado": h,
                 "alertas": [a["clave"] for a in juicio["alertas"]], "a_enviar": [a["clave"] for a in persisten],
                 "correo": None, "enviado": False, "rastro": rastro}
    if juicio["veredicto"] == "NECESITA_DECISION" and persisten:
        asunto, cuerpo = armar_correo(cfg, dict(juicio, alertas=persisten), est)
        resultado["correo"] = {"from": cfg["gerente_general"]["reportes"]["from"],
                               "to": cfg["gerente_general"]["reportes"]["to"], "asunto": asunto, "cuerpo": cuerpo}
        if modo == "real":
            resultado["id_resend"] = enviar_resend(cfg, asunto, cuerpo)
            resultado["enviado"] = True
            for a in persisten:
                mem["enviadas"][a["clave"]] = {"firma": a["firma"], "at": ahora.isoformat(timespec="seconds")}
    if modo == "dry":
        salida(resultado["veredicto"])
        salida(f"Resumen: {resultado['resumen']}")
        if resultado["correo"]:
            c = resultado["correo"]
            salida(f"\nCorreo que se enviaría (NO se envía en --dry-run; en una pasada real antes se espera el "
                   f"debounce y se vuelve a mirar):\nDe: {c['from']}\nPara: {c['to']}\nAsunto: {c['asunto']}\n\n"
                   f"{c['cuerpo']}")
        elif juicio["veredicto"] == "NECESITA_DECISION":
            salida("Ya avisado antes y sin cambios: no se repetiría el correo.")
        return resultado
    if modo == "real":
        mem["ultima_pasada"] = ahora.isoformat(timespec="seconds")
    guardar_memoria(cfg, mem)
    log(f"FIN {resultado['veredicto']} alertas={resultado['alertas']} "
        f"enviadas={resultado['a_enviar'] if resultado['enviado'] else []} - {resultado['resumen']}")
    return resultado


# ---------------------------------------------------------------- --verificar

def tarea_programada_existe(nombre):
    sistema = platform.system()
    try:
        if sistema == "Windows":
            r = subprocess.run(["schtasks", "/Query", "/TN", nombre], capture_output=True, text=True, timeout=20)
            return r.returncode == 0, "Programador de tareas"
        if sistema == "Darwin":
            r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=20)
            return f"local.{nombre}" in r.stdout, "launchd"
        r = subprocess.run(["systemctl", "--user", "is-enabled", f"{nombre}.timer"], capture_output=True, text=True,
                           timeout=20)
        if r.returncode == 0:
            return True, "systemd (usuario)"
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=20)
        return f"# {nombre}" in r.stdout, "cron"
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"no se pudo consultar ({type(e).__name__})"


def verificar(ruta_cfg, salida=print, llamar=True):
    puntos = []

    def punto(nombre, ok, detalle, omitido=False):
        puntos.append(ok)
        salida(f"[{'OMITIDO' if omitido else 'OK' if ok else 'FAIL'}] {nombre}: {detalle}")

    try:
        cfg = cargar_config(ruta_cfg)
        punto("configuración", True, f"{Path(ruta_cfg).name} válido y completo")
    except (ErrorConfig, ValueError) as e:
        punto("configuración", False, str(e))
        return 1
    sub = cfg["subgerente"]
    try:
        clave = clave_subgerente(cfg)
        punto("clave del proveedor", True, "no hace falta" if clave == "" else
              f"presente en {donde_clave(sub['clave'])} (no se muestra)")
    except ErrorConfig as e:
        punto("clave del proveedor", False, str(e))
        clave = None
    if clave is None:
        punto("proveedor alcanzable", False, "sin clave no se puede probar")
    elif not llamar:
        punto("proveedor alcanzable", True, "no probado (--sin-llamadas)", omitido=True)
    else:
        try:
            r = proveedores.cargar(sub["proveedor"]).completar("Responde solo con la palabra OK.", modelo=sub["modelo"],
                                                               clave=clave, ajustes=sub)
            punto("proveedor alcanzable", True, f"{sub['proveedor']} / {sub['modelo']} respondió ({len(r)} caracteres)")
        except Exception as e:  # noqa: BLE001 - cualquier fallo del proveedor es un FAIL legible
            punto("proveedor alcanzable", False, f"{sub['proveedor']}: {sin_secretos(e)}")
    rep = cfg["gerente_general"]["reportes"]
    kr = leer_clave(rep["clave_resend"])
    if not kr:
        punto("Resend", False, f"falta la clave de Resend en {donde_clave(rep['clave_resend'])}")
    elif not llamar:
        punto("Resend", True, "clave presente; dominio no probado (--sin-llamadas)", omitido=True)
    else:
        dominio = str(rep["from"]).split("@")[-1]
        try:
            r = requests.get("https://api.resend.com/domains", headers={"Authorization": f"Bearer {kr}"}, timeout=20)
            if r.status_code >= 400:
                punto("Resend", False, f"la API respondió {r.status_code}: {r.text[:160]}")
            else:
                doms = {d.get("name"): d.get("status") for d in r.json().get("data", [])}
                ok = doms.get(dominio) == "verified"
                punto("Resend", ok, f"dominio {dominio}: {doms.get(dominio) or 'no está en la cuenta'}")
        except requests.RequestException as e:
            punto("Resend", False, f"no se pudo llamar a la API ({type(e).__name__})")
    ok, como = tarea_programada_existe(cfg["programacion"]["nombre_tarea"])
    punto("tarea programada", ok, f"«{cfg['programacion']['nombre_tarea']}» en {como}" if ok else
          f"no hay tarea «{cfg['programacion']['nombre_tarea']}» en {como}: corre el instalador de tu sistema")
    return 0 if all(puntos) else 1


# ---------------------------------------------------------------- --configurar

def configurar(ruta_cfg, entrada=input, secreto=getpass.getpass, salida=print):
    """Asistente de primera corrida. Propone lo que ya hay en el YAML (o el ejemplo) y confirma cada valor."""
    base_txt = Path(ruta_cfg).read_text(encoding="utf-8") if Path(ruta_cfg).is_file() else \
        CONFIG_POR_DEFECTO.read_text(encoding="utf-8")
    cfg = yaml.safe_load(base_txt) or {}

    def preguntar(texto, defecto, opciones=None):
        while True:
            r = entrada(f"{texto} [{defecto}]: ").strip() or str(defecto)
            if not opciones or r in opciones:
                salida(f"  -> {r}")
                return r
            salida(f"  Elige una de: {', '.join(opciones)}")

    salida("Configuración del supervisor (Intro = dejar el valor entre corchetes).")
    sub = cfg.setdefault("subgerente", {})
    lista = [p for p in proveedores.disponibles() if p != "mock"]
    prov_antes = sub.get("proveedor")
    prov = preguntar(f"Proveedor del subgerente ({', '.join(lista)})", sub.get("proveedor") or lista[0], lista)
    mod = proveedores.cargar(prov)
    modelo_def = sub.get("modelo") if prov == sub.get("proveedor") and sub.get("modelo") else mod.MODELO_POR_DEFECTO
    sub.update(proveedor=prov, modelo=preguntar("Modelo", modelo_def))
    if mod.CLAVE_POR_DEFECTO:
        origen = preguntar("¿Dónde guardo la clave? (entorno = variable de entorno, llavero = llavero del sistema)",
                           (sub.get("clave") or {}).get("origen") or "llavero", ["entorno", "llavero"])
        nombre = ((sub.get("clave") or {}).get("nombre") if prov == prov_antes else "") or mod.CLAVE_POR_DEFECTO
        sub["clave"] = {"origen": origen, "nombre": nombre}
        if origen == "llavero":
            k = secreto(f"Pega la clave de {prov} (no se verá en pantalla; Intro = no cambiarla): ")
            if k:
                import keyring
                keyring.set_password(SERVICIO_LLAVERO, nombre, k)
                salida(f"  -> clave guardada en el llavero del sistema como «{nombre}» (no se muestra)")
            else:
                salida("  -> no se cambió la clave del llavero")
        else:
            salida(f"  -> pon la clave en la variable de entorno {nombre} (Windows: setx {nombre} \"...\"; "
                   f"Linux/macOS: export {nombre}=... en tu perfil). No se guarda aquí.")
    else:
        sub["clave"] = {"origen": "entorno", "nombre": ""}
        salida(f"  -> {prov} no necesita clave")
    rep = cfg.setdefault("gerente_general", {}).setdefault("reportes", {})
    rep["from"] = preguntar("Correo que envía los avisos (de un dominio verificado en Resend)", rep.get("from") or "")
    rep["to"] = preguntar("Correo que recibe los avisos", rep.get("to") or "")
    sub["intervalo_minutos"] = int(preguntar("Cada cuántos minutos revisar", sub.get("intervalo_minutos") or 60))
    texto = ("# Supervisor local de Growi Bridge (\"subgerente\"). Escrito por supervisor.py --configurar.\n"
             "# Las claves NUNCA van aquí: solo dónde están. Ver README, sección «Roles».\n\n"
             + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    Path(ruta_cfg).write_text(texto, encoding="utf-8")
    cargar_config(ruta_cfg)  # lo escrito tiene que ser válido
    salida(f"Listo: {ruta_cfg} escrito. Comprueba todo con «supervisor.py --verificar».")
    return cfg


# ---------------------------------------------------------------- entrada

def main(argv=None):
    ap = argparse.ArgumentParser(description="Supervisor local de Growi Bridge (subgerente).")
    ap.add_argument("--config", default=str(CONFIG_POR_DEFECTO))
    ap.add_argument("--bridge", help="otra carpeta del Bridge (p. ej. una instalación de prueba)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--configurar", action="store_true")
    g.add_argument("--verificar", action="store_true")
    g.add_argument("--intervalo", action="store_true")
    g.add_argument("--programacion", action="store_true", help="imprime «minutos nombre_tarea» (instaladores)")
    g.add_argument("--evals", action="store_true", help="evals del juez con el proveedor del YAML (sin correo)")
    ap.add_argument("--sin-llamadas", action="store_true", help="--verificar sin llamar a ninguna API")
    a = ap.parse_args(argv)
    try:
        if a.configurar:
            configurar(a.config)
            return 0
        if a.verificar:
            return verificar(a.config, llamar=not a.sin_llamadas)
        cfg = cargar_config(a.config)
        if a.intervalo:
            print(int(cfg["subgerente"]["intervalo_minutos"]))
            return 0
        if a.programacion:
            print(int(cfg["subgerente"]["intervalo_minutos"]), cfg["programacion"]["nombre_tarea"])
            return 0
        if a.bridge:
            cfg["bridge"].update(carpeta=a.bridge, share=str(Path(a.bridge) / "share"))
        if a.evals:
            import evals
            return evals.correr(cfg, salida=print)
        pasada(cfg, modo="dry" if a.dry_run else "real")
        return 0
    except (ErrorConfig, ValueError) as e:
        print(f"supervisor: {e}", file=sys.stderr)
        try:
            anotar(yaml.safe_load(Path(a.config).read_text(encoding="utf-8")), f"ERROR {e}")
        except Exception:  # noqa: BLE001 - sin config legible no hay dónde anotar
            pass
        return 2
    except Exception as e:  # noqa: BLE001 - un fallo del proveedor o de la red no debe quedar mudo
        msg = f"{type(e).__name__}: {sin_secretos(e)}"
        print(f"supervisor: {msg}", file=sys.stderr)
        try:
            anotar(cargar_config(a.config), f"ERROR {msg}")
        except Exception:  # noqa: BLE001
            pass
        return 3


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Relevo telefónico (Fase 4 del plan multi-Muse): el encargo del dueño.

El dueño, desde fuera, le escribe a UNA cuenta Muse. Esa cuenta recibe un
**encargo**: una tarea con ``"tipo": "encargo"``. El código receptor —no
el payload— genera la raíz de correlación ``enc-<yyyymmdd>-<uuid8>`` y la
heredan todas las subtareas (ids ``<raíz>-s<n>``), sus resultados y sus
avisos: cualquier cosa se puede reconstruir siguiendo la raíz.

División en tres peldaños, en orden: (a) subtareas declaradas en el
payload, validadas; (b) plan del harness planificador, validado igual;
(c) plan de reserva: una sola subtarea con el encargo entero para la
receptora. Un encargo jamás se pierde porque no se sepa dividirlo.

La asignación usa ``tablero.elegir_cuenta`` con un contador simulado que
crece dentro de la propia división (dos subtareas seguidas no caen
«gratis» en la misma cuenta). La asignación se escribe en
``encargos.json`` (carpeta compartida) ANTES de entregar nada, y la
entrega sigue el orden seguro: escribir ``<id>.task.json.tmp`` en el
destino, anotar ``entregada`` en el registro y solo entonces
``os.replace`` al nombre final. Si algo falla a mitad, el barrido de
supervisión reconcilia el hueco.

El cierre de un encargo NO puede leer los ``runner-results/`` del otro
carril (cada copia del programa tiene los suyos): la autoridad del cierre
es el buzón compartido ``relevo-resultados/<raíz>/<subtarea>.result.json``
que cada carril alimenta con los resultados de SUS subtareas.
"""

import contextlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

import tablero as _tb

VERSION = 1
MAX_SUBTAREAS = 12
TOPE_TIMEOUT_MIN = 120          # alineado con la duración máxima (§5.3)
PLAZO_ENCARGO_S = 6 * 3600      # plazo global del encargo (6 h)
CLASES_PRUEBA = ("medicion", "ejecutar_proyecto", "abrir_programa")
TERMINALES = ("terminado", "terminado_con_fallos")

_LOCKS = {}
_LOCKS_MU = threading.Lock()
_PROBLEMA = {"texto": None}


class ErrorRelevo(ValueError):
    """Plan o petición de relevo no válida."""


def _lock_de(ruta):
    clave = str(ruta)
    with _LOCKS_MU:
        if clave not in _LOCKS:
            _LOCKS[clave] = threading.RLock()
        return _LOCKS[clave]


@contextlib.contextmanager
def _bloqueo(base_dir, espera_s=10.0):
    """Lock propio del registro de encargos (el patrón de la casa:
    mutex en proceso + lock de archivo con ruptura de huérfano a 15 s)."""
    ruta_lock = Path(base_dir) / "encargos.lock"
    with _lock_de(ruta_lock):
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


def _ruta(base_dir):
    return Path(base_dir) / "encargos.json"


def problema(base_dir=None):
    return _PROBLEMA["texto"]


def _vacio():
    return {"version": VERSION, "revision": 0, "encargos": {}}


def _cargar(base_dir):
    """Nunca lanza: corrupto → registro vacío y el problema anotado (el
    barrido reconstruye lo cerrable desde las colas y los resultados)."""
    try:
        datos = json.loads(_ruta(base_dir).read_text(encoding="utf-8"))
        if isinstance(datos, dict) and datos.get("version") == VERSION \
                and isinstance(datos.get("encargos"), dict):
            _PROBLEMA["texto"] = None
            base = _vacio()
            base.update(datos)
            return base
        _PROBLEMA["texto"] = "encargos.json con formato no reconocido"
    except FileNotFoundError:
        _PROBLEMA["texto"] = None
        return _vacio()
    except (OSError, ValueError) as e:
        _PROBLEMA["texto"] = f"encargos.json ilegible: {e}"
    return _vacio()


def _guardar(base_dir, datos):
    datos["revision"] = int(datos.get("revision") or 0) + 1
    ruta = _ruta(base_dir)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(str(tmp), str(ruta))


def cargar(base_dir):
    return _cargar(base_dir)


def obtener(base_dir, raiz):
    ent = _cargar(base_dir)["encargos"].get(raiz)
    return json.loads(json.dumps(ent)) if isinstance(ent, dict) else None


def listar(base_dir):
    return json.loads(json.dumps(_cargar(base_dir)["encargos"]))


# ---------------------------------------------------------------------------
# Registro del encargo (la identidad la genera el código, no el payload)
# ---------------------------------------------------------------------------

def nueva_raiz(ahora=None, sufijo=None):
    fecha = time.strftime("%Y%m%d", time.localtime(ahora or time.time()))
    return f"enc-{fecha}-{sufijo or uuid.uuid4().hex[:8]}"


def registrar_encargo(base_dir, tarea, receptora, reloj=None):
    """Registra el encargo y devuelve su raíz de correlación. Lo que el
    payload trajera como raíz o cuenta se ignora: la raíz nace aquí y la
    receptora es la cuenta del carril que recibió el encargo."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = _cargar(base_dir)
        raiz = nueva_raiz(ahora)
        while raiz in datos["encargos"]:
            raiz = nueva_raiz(ahora)
        datos["encargos"][raiz] = {
            "tarea": tarea.get("id"),
            "receptora": receptora,
            "canal": tarea.get("canal"),
            "prompt": tarea.get("prompt") or "",
            "cwd": tarea.get("cwd"),
            "creado_ts": ahora,
            "plazo_ts": ahora + PLAZO_ENCARGO_S,
            "estado": "abierto",
            "plan_tipo": None,
            "dividido_ts": None,
            "cerrado_ts": None,
            "subtareas": {},
        }
        _guardar(base_dir, datos)
        return raiz


# ---------------------------------------------------------------------------
# Validación de planes (declarado o del planificador: el mismo rasero)
# ---------------------------------------------------------------------------

def _extraer_json(datos):
    if isinstance(datos, (dict, list)):
        return datos
    if not isinstance(datos, str):
        raise ErrorRelevo("el plan no es un objeto JSON")
    inicio = datos.find("{")
    if inicio < 0:
        raise ErrorRelevo("el plan no trae ningún objeto JSON")
    profundidad = 0
    en_cadena = False
    escape = False
    for i in range(inicio, len(datos)):
        c = datos[i]
        if en_cadena:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                en_cadena = False
            continue
        if c == '"':
            en_cadena = True
        elif c == "{":
            profundidad += 1
        elif c == "}":
            profundidad -= 1
            if profundidad == 0:
                try:
                    return json.loads(datos[inicio:i + 1])
                except ValueError as e:
                    raise ErrorRelevo(f"JSON del plan no válido: {e}")
    raise ErrorRelevo("el plan trae un JSON sin cerrar")


def _validar_prueba(bloque, donde):
    if bloque is None:
        return None
    if not isinstance(bloque, dict):
        raise ErrorRelevo(f"{donde}: prueba_fisica debe ser un objeto o null")
    clase = bloque.get("clase")
    if clase not in CLASES_PRUEBA:
        raise ErrorRelevo(
            f"{donde}: clase de prueba no válida: {clase!r} (válidas: "
            + ", ".join(CLASES_PRUEBA) + ")")
    detalle = bloque.get("detalle")
    if not isinstance(detalle, str) or not detalle.strip():
        raise ErrorRelevo(f"{donde}: la prueba física necesita un detalle")
    dur = bloque.get("duracion_est_min")
    if dur is not None and (isinstance(dur, bool)
                            or not isinstance(dur, int) or dur <= 0):
        raise ErrorRelevo(f"{donde}: duracion_est_min debe ser un entero > 0")
    impacto = bloque.get("impacto")
    if impacto is not None and not isinstance(impacto, str):
        raise ErrorRelevo(f"{donde}: impacto debe ser texto")
    return {"clase": clase, "detalle": detalle.strip(),
            "duracion_est_min": dur if dur is not None else 15,
            "impacto": impacto or "sin describir"}


def validar_plan(datos, motores, raiz=None, max_prompt=100_000):
    """Valida un plan entero y devuelve las subtareas normalizadas.

    ``motores``: iterable con los ids de motor de engines.json (o el propio
    dict). ``depende_de`` se expresa en posiciones 1..N del plan y se
    normaliza a ids ``<raíz>-s<n>`` si se pasa la raíz. Cualquier plan
    inválido se rechaza entero: no hay planes a medias."""
    datos = _extraer_json(datos)
    if isinstance(datos, list):
        crudas = datos
    elif isinstance(datos, dict):
        crudas = datos.get("subtareas")
    else:
        raise ErrorRelevo("el plan no es un objeto con «subtareas»")
    if not isinstance(crudas, list) or not crudas:
        raise ErrorRelevo("el plan no trae subtareas")
    if len(crudas) > MAX_SUBTAREAS:
        raise ErrorRelevo(
            f"el plan trae {len(crudas)} subtareas y el máximo es "
            f"{MAX_SUBTAREAS}")
    conocidos = set(motores.keys()) if isinstance(motores, dict) \
        else set(motores or ())
    n = len(crudas)
    salida = []
    for i, cruda in enumerate(crudas):
        donde = f"subtarea {i + 1}"
        if not isinstance(cruda, dict):
            raise ErrorRelevo(f"{donde}: debe ser un objeto")
        prompt = cruda.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ErrorRelevo(f"{donde}: prompt vacío")
        if len(prompt) > max_prompt:
            raise ErrorRelevo(
                f"{donde}: prompt de {len(prompt)} caracteres supera el "
                f"límite del puente ({max_prompt})")
        motor = cruda.get("motor")
        if motor is not None and motor not in conocidos:
            raise ErrorRelevo(f"{donde}: motor desconocido: {motor!r}")
        timeout = cruda.get("timeout_min")
        if timeout is not None and (isinstance(timeout, bool)
                                    or not isinstance(timeout, int)
                                    or not 1 <= timeout <= TOPE_TIMEOUT_MIN):
            raise ErrorRelevo(
                f"{donde}: timeout_min fuera de 1..{TOPE_TIMEOUT_MIN}: "
                f"{timeout!r}")
        archivos = cruda.get("archivos") or []
        if not isinstance(archivos, list) or \
                any(not isinstance(a, str) for a in archivos):
            raise ErrorRelevo(f"{donde}: archivos debe ser una lista de "
                              "rutas")
        deps = cruda.get("depende_de") or []
        if not isinstance(deps, list) or any(
                isinstance(d, bool) or not isinstance(d, int) for d in deps):
            raise ErrorRelevo(f"{donde}: depende_de debe ser una lista de "
                              "posiciones (enteros)")
        for d in deps:
            if not 1 <= d <= n:
                raise ErrorRelevo(
                    f"{donde}: depende_de apunta a {d}, fuera de 1..{n}")
            if d == i + 1:
                raise ErrorRelevo(f"{donde}: depende de sí misma")
        salida.append({
            "prompt": prompt,
            "motor": motor,
            "archivos": list(archivos),
            "git": cruda.get("git"),
            "timeout_min": timeout,
            "depende_de": [f"{raiz}-s{d}" if raiz else d for d in deps],
            "prueba_fisica": _validar_prueba(cruda.get("prueba_fisica"),
                                             donde),
            "_deps_pos": list(deps),
        })
    # Ciclos: DFS sobre las posiciones.
    grafo = {i + 1: s["_deps_pos"] for i, s in enumerate(salida)}
    visitado, en_curso = set(), set()

    def _visitar(nodo):
        if nodo in en_curso:
            raise ErrorRelevo("el plan tiene dependencias circulares")
        if nodo in visitado:
            return
        en_curso.add(nodo)
        for dep in grafo[nodo]:
            _visitar(dep)
        en_curso.discard(nodo)
        visitado.add(nodo)

    for nodo in grafo:
        _visitar(nodo)
    for s in salida:
        del s["_deps_pos"]
    return salida


def plan_reserva(prompt):
    """El plan que nunca falla: una sola subtarea con el encargo entero."""
    return [{"prompt": prompt, "motor": None, "archivos": [], "git": None,
             "timeout_min": None, "depende_de": [], "prueba_fisica": None}]


# ---------------------------------------------------------------------------
# Asignación (antes de entregar nada) y reasignación
# ---------------------------------------------------------------------------

def _cuenta_del_registro(registro, cuenta_id):
    for c in (registro or {}).get("cuentas") or []:
        if isinstance(c, dict) and c.get("id") == cuenta_id:
            return c
    return None


def _elegir(vista_d, registro, activas_sim, excluir=()):
    if not excluir:
        return _tb.elegir_cuenta(vista_d, activas_sim, registro)
    filtrado = dict(registro or {})
    filtrado["cuentas"] = [c for c in (registro or {}).get("cuentas") or []
                           if c.get("id") not in excluir]
    return _tb.elegir_cuenta(vista_d, activas_sim, filtrado)


# Pesos de la fórmula de reparto con fuertes (P4, del diseño de equipo):
# el fuerte manda, luego el peso declarado (topado por el propio fuerte),
# luego los tokens libres y por último la carga. Son constantes a la
# vista: la resolución deja los puntos guardados en cada subtarea.
PESO_FUERTE = 0.4
PESO_PESO = 0.3
PESO_TOKENS = 0.2
PESO_CARGA = 0.1


def _elegir_por_puntos(vista_d, registro, activas_sim, spec, fuertes_fn,
                       excluir=()):
    """Elige por la fórmula de puntos cuando hay fuertes declarados.

    Candidatas: las mismas de ``tablero.elegir_cuenta`` (habilitada, con
    carril, estado activa en la vista). ``fuertes_fn(cuenta, spec)``
    devuelve (factor 0..1, nombre del skill o None). El peso declarado
    de la subtarea (``spec["pesos"][cuenta]``, 0-100) entra topado por
    el propio factor fuerte — nadie se autoasigna más peso del que su
    fuerte justifica — y sin peso declarado el factor hace de peso.
    Devuelve (cuenta, fuerte, skill, puntos) o (None, 0.0, None, None).
    Determinista: desempate por fuerte, % conocido, % mayor, menos
    activas e id ascendente."""
    candidatas = []
    for c in (registro or {}).get("cuentas") or []:
        if not isinstance(c, dict):
            continue
        if not c.get("habilitada", True) or not c.get("carril"):
            continue
        if c["id"] in excluir:
            continue
        v = vista_d.get(c["id"]) or {}
        if v.get("estado", "activa") != "activa":
            continue
        candidatas.append(c["id"])
    if not candidatas:
        return None, 0.0, None, None
    max_carga = max([activas_sim.get(cid, 0) for cid in candidatas] + [0])
    pesos = spec.get("pesos") if isinstance(spec, dict) else None
    filas = []
    for cid in candidatas:
        try:
            fuerte, skill = fuertes_fn(cid, spec)
            fuerte = max(0.0, min(1.0, float(fuerte)))
        except Exception:
            fuerte, skill = 0.0, None
        declarado = None
        if isinstance(pesos, dict):
            try:
                declarado = max(0.0, min(100.0, float(pesos.get(cid))))
            except (TypeError, ValueError):
                declarado = None
        peso_ef = (min(declarado / 100.0, fuerte) if declarado is not None
                   else fuerte)
        v = vista_d.get(cid) or {}
        pct = v.get("pct_puerta", v.get("pct_efectivo"))
        conocido = isinstance(pct, (int, float)) and not isinstance(pct, bool)
        pct_n = max(0.0, min(100.0, float(pct))) if conocido else 0.0
        carga = activas_sim.get(cid, 0)
        carga_norm = (carga / max_carga) if max_carga else 0.0
        puntos = (PESO_FUERTE * fuerte + PESO_PESO * peso_ef
                  + PESO_TOKENS * (pct_n / 100.0)
                  + PESO_CARGA * (1.0 - carga_norm))
        filas.append((cid, fuerte, skill, round(puntos, 4), conocido,
                      pct_n, carga))
    filas.sort(key=lambda f: (-f[3], -f[1], 0 if f[4] else 1, -f[5],
                              f[6], f[0]))
    cid, fuerte, skill, puntos = filas[0][:4]
    return cid, fuerte, skill, puntos


def _es_fase_codigo(spec):
    """La subtarea produce código: trae bloque git o archivos."""
    return bool(spec.get("git")) or bool(spec.get("archivos"))


def _excluidas_texto(spec, registro, motor_fn, motores_texto):
    """Cuentas vetadas para ESTA subtarea (P5): su motor efectivo — el
    de la subtarea o el propio de la cuenta, vía ``motor_fn`` — es solo
    de texto y la fase es de código. Un motor de chat planifica,
    responde y revisa, pero no ejecuta fases que producen código
    (diseño de equipo, B5: sin un runner agéntico nombrado, fail-closed)."""
    if not motores_texto or not _es_fase_codigo(spec):
        return set()
    out = set()
    for c in (registro or {}).get("cuentas") or []:
        if not isinstance(c, dict):
            continue
        efectivo = spec.get("motor") or (motor_fn(c.get("id"))
                                          if motor_fn else None)
        if efectivo and efectivo in motores_texto:
            out.add(c.get("id"))
    return out


def asignar(base_dir, raiz, subtareas, vista_d, registro, activas,
            plan_tipo=None, margen_fn=None, reloj=None, fuertes_fn=None,
            motor_fn=None, motores_texto=None):
    """Asigna cada subtarea a una cuenta y lo deja escrito ANTES de que se
    entregue nada. Devuelve {sid: cuenta o None}.

    El contador de activas es simulado y crece dentro de la división. Si
    una subtarea trae motor y la elegida no tiene margen para ese
    (motor, cuenta) según ``margen_fn``, se reintenta excluyéndola.

    Con ``fuertes_fn`` (P4) la elección usa la fórmula de puntos de
    ``_elegir_por_puntos`` y cada subtarea guarda `fuerte`,
    `skill_fuerte` y `puntos` para que el reparto sea explicable; sin
    ella, la elección es la de siempre (tablero.elegir_cuenta).

    Con ``motor_fn`` + ``motores_texto`` (P5), las cuentas cuyo motor
    efectivo es solo de texto quedan vetadas para las fases de código
    (ver ``_excluidas_texto``); si el veto deja la fase sin nadie, el
    motivo lo dice tal cual."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = _cargar(base_dir)
        ent = datos["encargos"].get(raiz)
        if ent is None:
            raise ErrorRelevo(f"encargo desconocido: {raiz}")
        if ent["estado"] in TERMINALES:
            raise ErrorRelevo(f"el encargo {raiz} ya está cerrado")
        sim = dict(activas or {})
        # Vista simulada de la división: cada subtarea asignada descuenta
        # una parte igual del encargo (100/n) del % de puerta simulado de
        # su cuenta. Sin esto, elegir_cuenta (que ordena por % antes que
        # por tareas activas) daría TODAS las subtareas a la cuenta con
        # más % ante cualquier diferencia, y la otra no trabajaría nunca
        # mientras hubiera una brecha, por pequeña que fuera. Con el
        # descuento, el reparto equilibra dentro del encargo y una cuenta
        # solo se lo queda todo si su ventaja supera al propio encargo.
        vista_sim = {cid: dict(v) for cid, v in (vista_d or {}).items()}
        resultado = {}
        for i, spec in enumerate(subtareas):
            sid = f"{raiz}-s{i + 1}"
            info_puntos = {}
            vetadas = _excluidas_texto(spec, registro, motor_fn,
                                       motores_texto)
            if fuertes_fn is not None:
                elegida, f_, sk_, pt_ = _elegir_por_puntos(
                    vista_sim, registro, sim, spec, fuertes_fn,
                    excluir=vetadas)
                if elegida:
                    info_puntos = {"fuerte": f_, "skill_fuerte": sk_,
                                   "puntos": pt_}
            else:
                elegida = _elegir(vista_sim, registro, sim,
                                  excluir=vetadas)
            motivo = None
            if elegida is None and vetadas and \
                    _elegir(vista_sim, registro, sim):
                motivo = ("la fase es de código y las cuentas "
                          "candidatas tienen un motor solo de texto")
            if elegida and margen_fn is not None and spec.get("motor"):
                margen = margen_fn(elegida, spec["motor"])
                if margen is False:
                    if fuertes_fn is not None:
                        otra, f_, sk_, pt_ = _elegir_por_puntos(
                            vista_sim, registro, sim, spec, fuertes_fn,
                            excluir={elegida} | vetadas)
                        if otra:
                            info_puntos = {"fuerte": f_,
                                           "skill_fuerte": sk_,
                                           "puntos": pt_}
                    else:
                        otra = _elegir(vista_sim, registro, sim,
                                       excluir={elegida} | vetadas)
                    if otra:
                        elegida = otra
                    else:
                        motivo = (f"sin margen para el motor "
                                  f"{spec['motor']} en ninguna cuenta "
                                  "activa")
                        elegida = None
                        info_puntos = {}
            if elegida:
                sim[elegida] = sim.get(elegida, 0) + 1
                v_sim = vista_sim.get(elegida) or {}
                pct_sim = v_sim.get("pct_puerta", v_sim.get("pct_efectivo"))
                if isinstance(pct_sim, (int, float)) and \
                        not isinstance(pct_sim, bool):
                    v_sim["pct_puerta"] = max(
                        0, pct_sim - 100.0 / max(1, len(subtareas)))
                cuenta = _cuenta_del_registro(registro, elegida)
                ent["subtareas"][sid] = {
                    "n": i + 1,
                    "cuenta": elegida,
                    "carril": (cuenta or {}).get("carril"),
                    "estado": "asignada",
                    "motivo": None,
                    "spec": spec,
                    "asignada_ts": ahora,
                    "entregada_ts": None,
                    "terminada_ts": None,
                    "resultado": None,
                    "pasadas_sin_archivo": 0,
                    **info_puntos,
                }
            else:
                ent["subtareas"][sid] = {
                    "n": i + 1,
                    "cuenta": None,
                    "carril": None,
                    "estado": "pendiente_entrega",
                    "motivo": motivo or "sin cuentas activas para asignar",
                    "spec": spec,
                    "asignada_ts": None,
                    "entregada_ts": None,
                    "terminada_ts": None,
                    "resultado": None,
                    "pasadas_sin_archivo": 0,
                }
            resultado[sid] = elegida
        ent["plan_tipo"] = plan_tipo
        ent["dividido_ts"] = ahora
        ent["estado"] = "trabajando"
        _guardar(base_dir, datos)
        return resultado


def reasignar(base_dir, raiz, vista_d, registro, activas, reloj=None):
    """Reasigna lo asignado y aún no entregado cuya cuenta cayó en
    cuarentena o quedó deshabilitada, y lo pendiente que se quedó sin
    cuenta. Lo ya entregado no se toca jamás. Devuelve la lista de
    cambios [(sid, cuenta_anterior, cuenta_nueva)]."""
    ahora = (reloj or time.time)()
    cambios = []
    with _bloqueo(base_dir):
        datos = _cargar(base_dir)
        ent = datos["encargos"].get(raiz)
        if ent is None or ent["estado"] in TERMINALES:
            return cambios
        sim = dict(activas or {})
        for sid, sub in ent["subtareas"].items():
            if sub.get("entregada_ts"):
                continue
            if sub["estado"] not in ("asignada", "pendiente_entrega"):
                continue
            actual = sub.get("cuenta")
            mala = actual is None
            if actual:
                entrada = (vista_d or {}).get(actual) or {}
                cuenta_reg = _cuenta_del_registro(registro, actual)
                if entrada.get("estado") == "cuarentena" or \
                        cuenta_reg is None or \
                        not cuenta_reg.get("habilitada", True):
                    mala = True
            if not mala:
                continue
            nueva = _elegir(vista_d, registro, sim,
                            excluir={actual} if actual else ())
            if nueva:
                cuenta = _cuenta_del_registro(registro, nueva)
                sub["cuenta"] = nueva
                sub["carril"] = (cuenta or {}).get("carril")
                sub["estado"] = "asignada"
                sub["motivo"] = None
                sub["asignada_ts"] = ahora
                sim[nueva] = sim.get(nueva, 0) + 1
                cambios.append((sid, actual, nueva))
            elif actual:
                sub["cuenta"] = None
                sub["carril"] = None
                sub["estado"] = "pendiente_entrega"
                sub["motivo"] = ("la cuenta asignada cayó y no hay otra "
                                 "cuenta activa")
                cambios.append((sid, actual, None))
        if cambios:
            _guardar(base_dir, datos)
        return cambios


# ---------------------------------------------------------------------------
# Entrega (orden seguro: tmp → anotar → replace)
# ---------------------------------------------------------------------------

def _prompt_subtarea(ent, sub):
    resumen = " ".join((ent.get("prompt") or "").split())[:120]
    return (f"[Encargo {ent.get('raiz', '')} · parte {sub['n']} · encargo "
            f"del dueño: «{resumen}»]\n\n{sub['spec']['prompt']}")


def entregar(base_dir, raiz, sid, dir_tareas, base_carril=None, reloj=None):
    """Entrega una subtarea asignada en la carpeta de tareas de su carril.

    Orden: se escribe ``<id>.task.json.tmp``, se anota ``entregada`` en el
    registro y solo entonces ``os.replace`` al nombre final. Si la carpeta
    destino no existe, la subtarea queda pendiente con el motivo anotado.
    """
    ahora = (reloj or time.time)()
    dir_tareas = Path(dir_tareas)
    with _bloqueo(base_dir):
        datos = _cargar(base_dir)
        ent = datos["encargos"].get(raiz)
        if ent is None:
            return {"ok": False, "motivo": f"encargo desconocido: {raiz}"}
        sub = ent["subtareas"].get(sid)
        if sub is None:
            return {"ok": False, "motivo": f"subtarea desconocida: {sid}"}
        if sub["estado"] == "entregada":
            return {"ok": True, "motivo": "ya estaba entregada"}
        if sub["estado"] not in ("asignada", "pendiente_entrega") \
                or not sub.get("cuenta"):
            return {"ok": False,
                    "motivo": f"la subtarea está {sub['estado']} y no se "
                              "puede entregar"}
        if not dir_tareas.is_dir():
            sub["motivo"] = f"la carpeta de tareas no existe: {dir_tareas}"
            _guardar(base_dir, datos)
            return {"ok": False, "motivo": sub["motivo"]}
        ent_ctx = dict(ent)
        ent_ctx["raiz"] = raiz
        spec = sub["spec"]
        tarea = {
            "id": sid,
            "prompt": _prompt_subtarea(ent_ctx, sub),
            "cuenta": sub["cuenta"],
            "raiz": raiz,
            "tarea_padre": ent.get("tarea"),
            "canal": ent.get("canal"),
        }
        if sub.get("carril"):
            tarea["lane"] = sub["carril"]
        if spec.get("motor"):
            tarea["motor"] = spec["motor"]
        if spec.get("timeout_min"):
            tarea["timeout_min"] = spec["timeout_min"]
        if spec.get("git") or spec.get("archivos"):
            if ent.get("cwd"):
                tarea["cwd"] = ent["cwd"]
            if spec.get("archivos"):
                tarea["archivos"] = list(spec["archivos"])
            if spec.get("git"):
                tarea["git"] = spec["git"]
        elif sub.get("carril") == "b" and base_carril is not None:
            # Carril B sin contexto git: la derivación de la consulta.
            base = Path(base_carril)
            tarea["cwd"] = str(base)
            tarea["archivos"] = [str(base / "encargos" / f"{sid}.md")]
        elif ent.get("cwd"):
            tarea["cwd"] = ent["cwd"]
        if spec.get("prueba_fisica"):
            tarea["tipo"] = "prueba_fisica"
            tarea["prueba"] = spec["prueba_fisica"]
        final = dir_tareas / f"{sid}.task.json"
        tmp = dir_tareas / f"{sid}.task.json.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(tarea, f, ensure_ascii=False, indent=1)
        except OSError as e:
            return {"ok": False, "motivo": f"no se pudo escribir la "
                                           f"entrega: {e}"}
        sub["estado"] = "entregada"
        sub["entregada_ts"] = ahora
        sub["motivo"] = None
        _guardar(base_dir, datos)
        try:
            os.replace(str(tmp), str(final))
        except OSError as e:
            # El registro dice «entregada» sin archivo: el barrido
            # reconcilia el hueco (vuelve a pendiente tras 3 pasadas).
            return {"ok": False,
                    "motivo": f"anotada como entregada pero el replace "
                              f"falló: {e}"}
        return {"ok": True, "ruta": str(final)}


# ---------------------------------------------------------------------------
# Buzón compartido de resultados (la autoridad del cierre)
# ---------------------------------------------------------------------------

def ruta_buzon(base_dir, raiz=None):
    base = Path(base_dir) / "relevo-resultados"
    return base / raiz if raiz else base


def escribir_en_buzon(base_dir, resultado):
    """Copia un resultado de subtarea al buzón compartido. Solo entran
    resultados cuyo id sea una subtarea registrada de su raíz."""
    if not isinstance(resultado, dict):
        return False
    raiz = resultado.get("raiz")
    tid = resultado.get("id")
    if not raiz or not tid:
        return False
    ent = obtener(base_dir, raiz)
    if ent is None or tid not in (ent.get("subtareas") or {}):
        return False
    carpeta = ruta_buzon(base_dir, raiz)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{tid}.result.json"
        tmp = carpeta / f"{tid}.result.json.tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=1)
        os.replace(str(tmp), str(destino))
        return True
    except OSError:
        return False


def leer_de_buzon(base_dir, raiz, sid):
    try:
        datos = json.loads((ruta_buzon(base_dir, raiz)
                            / f"{sid}.result.json").read_text(
                                encoding="utf-8"))
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Marcas y cierre atómico
# ---------------------------------------------------------------------------

def marcar_subtarea(base_dir, raiz, sid, reloj=None, **campos):
    with _bloqueo(base_dir):
        datos = _cargar(base_dir)
        ent = datos["encargos"].get(raiz)
        if ent is None or sid not in ent["subtareas"]:
            return False
        ent["subtareas"][sid].update(campos)
        _guardar(base_dir, datos)
        return True


def cerrar(base_dir, raiz, estado, reloj=None):
    """Cierre atómico: solo el proceso que cambia el estado dentro del
    lock escribe el resumen y emite el aviso. Devuelve True si este
    proceso ganó el cierre."""
    if estado not in TERMINALES:
        raise ErrorRelevo(f"estado de cierre no válido: {estado!r}")
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = _cargar(base_dir)
        ent = datos["encargos"].get(raiz)
        if ent is None or ent["estado"] in TERMINALES:
            return False
        ent["estado"] = estado
        ent["cerrado_ts"] = ahora
        _guardar(base_dir, datos)
        return True


def resumen(base_dir, raiz):
    """El resumen de cierre de un encargo, desde el registro."""
    ent = obtener(base_dir, raiz)
    if ent is None:
        return None
    subs = []
    conteo = {}
    for sid, sub in sorted((ent.get("subtareas") or {}).items(),
                           key=lambda par: par[1].get("n") or 0):
        conteo[sub["estado"]] = conteo.get(sub["estado"], 0) + 1
        res = sub.get("resultado") or {}
        subs.append({"id": sid, "cuenta": sub.get("cuenta"),
                     "estado": sub["estado"],
                     "resumen": res.get("resumen")})
    total = len(subs)
    terminadas = conteo.get("terminada", 0)
    fallidas = conteo.get("fallida", 0)
    texto = (f"Encargo {raiz}: {terminadas} de {total} subtareas "
             f"terminadas")
    if fallidas:
        texto += f", {fallidas} fallidas"
    detalle = "; ".join(
        f"{s['id']} ({s['cuenta'] or 'sin cuenta'}): {s['estado']}"
        + (f" — {s['resumen']}" if s["resumen"] else "")
        for s in subs)
    return {"raiz": raiz, "estado": ent["estado"], "total": total,
            "por_estado": conteo, "subtareas": subs,
            "texto": texto + (f". {detalle}" if detalle else "")}

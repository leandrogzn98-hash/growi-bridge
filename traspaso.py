# -*- coding: utf-8 -*-
"""Traspaso en cuarentena con activación exactamente-una-vez (Fase 3).

Cuando una cuenta Muse entra en cuarentena (cuota a 0, sesión muerta,
ban…) a mitad de tarea, la tarea no se pierde ni se duplica: pasa a la
otra cuenta con su rama y su commit de rescate. El protocolo (§8 del
diseño, correcciones B1–B5 e I5/I8/I9/I10 de Opus 5.5) vive en un
marcador persistido en `traspasos.json` (carpeta compartida), escrito
ANTES que cualquier efecto lateral:

    crear → ofrecido ──(paso 1: SOLO el proceso del origen)──▶ parada
    del origen + commit de rescate ──(paso 3)──▶ entregado
    ──(paso 4: puerta del destino, UNA sola vez)──▶ aceptado →
    confirmado

Invariantes:
- **La parada del origen precede a todo** (B1): sin `origen_detenido_ts`
  no hay rescate ni oferta. Un resultado tardío del origen se descarta
  en el monolito (la fila queda «traspasando», no «terminada»).
- **Solo el proceso del origen ejecuta los pasos 1–3** (B4): toma un
  «alquiler de ejecutor» con latido; otro proceso solo puede tomarlo si
  el latido lleva más de `TTL_EJECUTOR_S` sin renovarse (muerte del
  ejecutor), y el robo queda auditado.
- **La reclamación es el único punto de activación** (B2/B3): un solo
  reclamante pasa a aceptado; el mismo reclamante tras un cierre vuelve
  a ver «reanudar»; otro ve «duplicado». Los marcadores en
  `ESTADOS_QUE_RETENEN` bloquean la recuperación de la tarea por el
  origen — incluido `requiere_dueno`, porque su significado es «nadie
  ejecuta hasta que el dueño decida».
- **El destino no se queda sin nada que hacer** (I9): `ofrecido` y
  `entregado` caducan por TTL y el barrido los devuelve a `devuelto`;
  de `devuelto` el origen puede recuperar la tarea SOLO si ya salió de
  cuarentena, y no se reofrece al mismo destino que la dejó caducar.

Este módulo no conoce el monolito: recibe ganchos (`detener`,
`dict_tarea`, carpetas) y el ejecutor git inyectable de `git_trabajo`.
"""
import contextlib
import json
import os
import threading
import time
from pathlib import Path

import alquileres
import git_trabajo
import secretos

ARCHIVO = "traspasos.json"
VERSION = 1
TTL_OFRECIDO_S = 600        # ofrecido y entregado caducan a los 10 min (I9)
TTL_EJECUTOR_S = 120        # latido del ejecutor del protocolo
TTL_SUPERVISION_S = 600     # confirmado sin latido del destino → dueño

# Estados que impiden que el origen recupere la tarea (B2). `devuelto`
# NO está: es el camino de vuelta legítimo.
ESTADOS_QUE_RETENEN = ("sin_destino", "ofrecido", "entregado", "aceptado",
                       "confirmado", "requiere_dueno")
ESTADOS_TERMINALES = ("devuelto",)

_LOCK = threading.RLock()
_LOCKS_POR_ARCHIVO = {}


class ErrorTraspaso(Exception):
    """El traspaso no puede avanzar; el mensaje es el motivo."""


# ----------------------------------------------------------------- candado

@contextlib.contextmanager
def _bloqueo(base_dir):
    base_dir = Path(base_dir)
    clave = str(base_dir.resolve())
    with _LOCK:
        lock = _LOCKS_POR_ARCHIVO.setdefault(clave, threading.RLock())
    with lock:
        ruta = base_dir / "traspasos.lock"
        fd = None
        for _ in range(150):
            try:
                fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                try:
                    if time.time() - ruta.stat().st_mtime > 15:
                        ruta.unlink()
                        continue
                except OSError:
                    pass
                time.sleep(0.02)
        if fd is None:
            raise ErrorTraspaso("traspasos.json está bloqueado por otro proceso")
        try:
            yield
        finally:
            os.close(fd)
            try:
                ruta.unlink()
            except OSError:
                pass


# ------------------------------------------------------------------ lectura

def _ruta(base_dir):
    return Path(base_dir) / ARCHIVO


def cargar(base_dir):
    try:
        datos = json.loads(_ruta(base_dir).read_text(encoding="utf-8"))
        if isinstance(datos, dict) and isinstance(datos.get("traspasos"), dict):
            return datos
    except (OSError, ValueError):
        pass
    return {"version": VERSION, "revision": 0, "traspasos": {}}


def _guardar(base_dir, datos):
    datos["revision"] = int(datos.get("revision") or 0) + 1
    tmp = _ruta(base_dir).with_suffix(f".json.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, _ruta(base_dir))


def obtener(base_dir, marcador_id):
    m = cargar(base_dir)["traspasos"].get(marcador_id)
    return dict(m) if isinstance(m, dict) else None


def todos(base_dir):
    return {k: dict(v) for k, v in cargar(base_dir)["traspasos"].items()
            if isinstance(v, dict)}


def ultimo_de(base_dir, tarea_id):
    """El marcador más reciente de una tarea (o None)."""
    candidatos = [m for m in todos(base_dir).values()
                  if m.get("tarea") == tarea_id]
    if not candidatos:
        return None
    return max(candidatos, key=lambda m: m.get("creado_ts") or 0)


def marcador_vivo_de(base_dir, tarea_id):
    """El marcador en un estado que RETIENE la tarea, si lo hay (B2)."""
    m = ultimo_de(base_dir, tarea_id)
    if m and m.get("estado") in ESTADOS_QUE_RETENEN:
        return m
    return None


def _transicion(base_dir, marcador_id, auditar=None, **cambios):
    with _bloqueo(base_dir):
        datos = cargar(base_dir)
        m = datos["traspasos"].get(marcador_id)
        if not isinstance(m, dict):
            raise ErrorTraspaso(f"no existe el marcador {marcador_id}")
        m.update(cambios)
        _guardar(base_dir, datos)
        copia = dict(m)
    if auditar:
        git_trabajo._auditar(auditar, "traspaso",
                             f"{marcador_id}: {copia.get('tarea')} "
                             f"{copia.get('origen')}→{copia.get('destino')} "
                             f"estado={copia.get('estado')}", "ok",
                             cuenta=copia.get("origen"),
                             accion=f"traspaso_{copia.get('estado')}")
    return copia


# ------------------------------------------------------------------- crear

def crear(base_dir, tarea_id, origen, destino=None, repo_id=None, rama=None,
          motivo="cuarentena", reloj=None, auditar=None):
    """Crea el marcador (paso 0: ANTES de cualquier efecto lateral).

    Idempotente: si ya hay un marcador vivo de la tarea, se devuelve tal
    cual. Si el último es `devuelto` para el MISMO destino, no se crea
    otro (I9: sin bucle de reoferta; solo lo reabre el dueño o un
    destino distinto). Devuelve (marcador|None, creado)."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = cargar(base_dir)
        vivos = [m for m in datos["traspasos"].values()
                 if isinstance(m, dict) and m.get("tarea") == tarea_id]
        for m in vivos:
            if m.get("estado") in ESTADOS_QUE_RETENEN:
                return dict(m), False
        previos = [m for m in vivos if m.get("estado") == "devuelto"]
        if previos:
            ultimo = max(previos, key=lambda m: m.get("creado_ts") or 0)
            if ultimo.get("destino") == destino:
                return None, False
        n = len(vivos) + 1
        mid = f"traspaso-{tarea_id}-{n}"
        while mid in datos["traspasos"]:
            n += 1
            mid = f"traspaso-{tarea_id}-{n}"
        m = {"id": mid, "tarea": tarea_id, "origen": origen,
             "destino": destino, "repo": repo_id, "rama": rama,
             "estado": "ofrecido" if destino else "sin_destino",
             "motivo": motivo, "creado_ts": ahora,
             "expira_ts": ahora + TTL_OFRECIDO_S if destino else None,
             "ejecutor": None, "ejecutor_latido_ts": None,
             "origen_detenido_ts": None, "reclamante": None,
             "commit_rescate": None, "ignorados_no_viajan": [],
             "aceptado_ts": None, "confirmado_ts": None}
        datos["traspasos"][mid] = m
        _guardar(base_dir, datos)
    if auditar:
        git_trabajo._auditar(auditar, "traspaso",
                             f"{mid}: creado para {tarea_id} "
                             f"({origen}→{destino})", "ok", cuenta=origen,
                             accion="traspaso_creado")
    return dict(m), True


# ------------------------------------------------------------- ejecutor (B4)

def tomar_ejecutor(base_dir, marcador_id, ejecutor, reloj=None, auditar=None):
    """Toma el alquiler de ejecutor del protocolo. Solo se puede robar
    con el latido caducado (>TTL_EJECUTOR_S): muerte del ejecutor."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = cargar(base_dir)
        m = datos["traspasos"].get(marcador_id)
        if not isinstance(m, dict):
            raise ErrorTraspaso(f"no existe el marcador {marcador_id}")
        actual = m.get("ejecutor")
        latido = m.get("ejecutor_latido_ts") or 0
        if actual and actual != ejecutor and ahora - latido <= TTL_EJECUTOR_S:
            return False
        robo = bool(actual and actual != ejecutor)
        m["ejecutor"] = ejecutor
        m["ejecutor_latido_ts"] = ahora
        _guardar(base_dir, datos)
    if robo and auditar:
        git_trabajo._auditar(auditar, "traspaso",
                             f"{marcador_id}: ejecutor robado por {ejecutor} "
                             f"(latido caducado)", "ok",
                             accion="traspaso_ejecutor_robado")
    return True


def latido_ejecutor(base_dir, marcador_id, ejecutor, reloj=None):
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = cargar(base_dir)
        m = datos["traspasos"].get(marcador_id)
        if isinstance(m, dict) and m.get("ejecutor") == ejecutor:
            m["ejecutor_latido_ts"] = ahora
            _guardar(base_dir, datos)
            return True
    return False


# ------------------------------------------------------------- pasos 1b–2–3

def marcar_detenido(base_dir, marcador_id, reloj=None):
    """Paso 1b confirmado: el origen ya no ejecuta la tarea (B1)."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = cargar(base_dir)
        m = datos["traspasos"].get(marcador_id)
        if not isinstance(m, dict):
            raise ErrorTraspaso(f"no existe el marcador {marcador_id}")
        if not m.get("origen_detenido_ts"):
            m["origen_detenido_ts"] = ahora
        _guardar(base_dir, datos)
        return dict(m)


def ofrecer(base_dir, marcador_id, destino, reloj=None, auditar=None):
    """sin_destino → ofrecido. Exige la parada del origen ya marcada."""
    ahora = (reloj or time.time)()
    m = obtener(base_dir, marcador_id)
    if not m:
        raise ErrorTraspaso(f"no existe el marcador {marcador_id}")
    if not m.get("origen_detenido_ts"):
        raise ErrorTraspaso("no se puede ofrecer sin la parada del origen "
                            "confirmada (B1)")
    return _transicion(base_dir, marcador_id, auditar, destino=destino,
                       estado="ofrecido", expira_ts=ahora + TTL_OFRECIDO_S)


def a_requiere_dueno(base_dir, marcador_id, motivo, auditar=None):
    return _transicion(base_dir, marcador_id, auditar,
                       estado="requiere_dueno", motivo_dueno=motivo)


def rescatar(base_dir, marcador_id, correr_git=None, auditar=None):
    """Paso 2: commit de rescate del worktree del origen y liberación
    de la rama. Devuelve el marcador actualizado."""
    m = obtener(base_dir, marcador_id)
    if not m:
        raise ErrorTraspaso(f"no existe el marcador {marcador_id}")
    if not m.get("origen_detenido_ts"):
        raise ErrorTraspaso("rescate sin parada del origen confirmada (B1)")
    if not m.get("repo"):
        raise ErrorTraspaso("el marcador no tiene repo: el rescate no aplica")
    correr = correr_git or git_trabajo.correr_git_real
    proyecto = git_trabajo.proyecto(base_dir, m["repo"])
    if not proyecto:
        return a_requiere_dueno(base_dir, marcador_id,
                                "el proyecto ya no está registrado", auditar)
    repo = Path(proyecto["ruta"])
    wt = git_trabajo.ruta_worktree(repo, m["origen"], m["tarea"],
                                   base_dir=base_dir, correr=correr)
    if not wt.exists():
        # El worktree ya no está: nada que rescatar (idempotente).
        git_trabajo._git(["worktree", "prune"], cwd=repo, correr=correr)
        return m
    gitdir = wt / ".git"
    gd = gitdir.read_text(encoding="utf-8").strip() if gitdir.is_file() else ""
    real = Path(gd.split(":", 1)[1].strip()) if gd.startswith("gitdir:") else None
    if real and any((real / x).exists()
                    for x in ("MERGE_HEAD", "rebase-merge", "rebase-apply")):
        return a_requiere_dueno(
            base_dir, marcador_id,
            "el worktree del origen quedó a mitad de una mezcla: "
            "lo resuelve el dueño (I5)", auditar)
    _rc, st, _err = git_trabajo._git(["status", "--porcelain"], cwd=wt,
                                     correr=correr)
    ignorados = []
    _rc, st_ig, _err = git_trabajo._git(
        ["status", "--porcelain", "--ignored"], cwd=wt, correr=correr)
    for linea in st_ig.splitlines():
        if linea.startswith("!! "):
            ignorados.append(linea[3:])
    if st.strip():
        git_trabajo._git_ok(["add", "-A"], cwd=wt, correr=correr)
        hall = secretos.escanear_staged(wt, correr)
        if hall:
            return a_requiere_dueno(
                base_dir, marcador_id,
                "el rescate contiene un posible secreto: no se confirma "
                "nada y lo revisa el dueño", auditar)
        git_trabajo._git_ok(["-c", "user.name=Growi Bridge",
                             "-c", "user.email=growi@localhost",
                             "commit", "--no-verify", "-m",
                             f"wip: rescate por traspaso {marcador_id}"],
                            cwd=wt, correr=correr)
        sha = git_trabajo._sha_de(wt, "HEAD", correr=correr)
        m = _transicion(base_dir, marcador_id, auditar, commit_rescate=sha)
    _transicion(base_dir, marcador_id, auditar,
                ignorados_no_viajan=ignorados)
    git_trabajo.liberar_worktree(repo, m["origen"], m["tarea"], forzar=True,
                                 base_dir=base_dir, correr=correr)
    return obtener(base_dir, marcador_id)


def entregar(base_dir, marcador_id, tarea_original, dir_tareas_destino,
             carril_destino=None, reloj=None, auditar=None):
    """Paso 3: la tarea derivada en la bandeja del destino. El marcador
    ya decía `ofrecido` desde el paso 0: un fallo aquí no pierde nada."""
    m = obtener(base_dir, marcador_id)
    if not m:
        raise ErrorTraspaso(f"no existe el marcador {marcador_id}")
    if m.get("estado") == "entregado":
        return m
    if m.get("estado") not in ("ofrecido",):
        raise ErrorTraspaso(f"no se puede entregar desde el estado "
                            f"{m.get('estado')}")
    carpeta = Path(dir_tareas_destino)
    if not carpeta.is_dir():
        raise ErrorTraspaso(f"la bandeja del destino no existe: {carpeta}")
    derivada = dict(tarea_original)
    derivada["id"] = marcador_id
    encabezado = (f"Continúas la tarea {m['tarea']} de la cuenta "
                  f"{m['origen']}; su trabajo va por el commit "
                  f"{m.get('commit_rescate') or '(sin commit de rescate)'} "
                  f"en la rama {m.get('rama') or '(sin rama)'}; "
                  "no repitas lo ya hecho.")
    derivada["prompt"] = encabezado + "\n\n" + str(
        tarea_original.get("prompt") or "")
    derivada["traspaso"] = {"de": m["origen"], "marcador": marcador_id,
                            "tarea": m["tarea"], "rama": m.get("rama")}
    if m.get("destino"):
        derivada["cuenta"] = m["destino"]
    if carril_destino:
        derivada["lane"] = carril_destino
    f = carpeta / f"{marcador_id}.task.json"
    tmp = carpeta / f".{marcador_id}.tmp-{os.getpid()}"
    tmp.write_text(json.dumps(derivada, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, f)
    ahora = (reloj or time.time)()
    return _transicion(base_dir, marcador_id, auditar, estado="entregado",
                       expira_ts=ahora + TTL_OFRECIDO_S)


def ejecutar_origen(base_dir, marcador_id, ganchos, correr_git=None,
                    reloj=None, auditar=None):
    """Los pasos 1–3 ejecutados SOLO por el proceso del origen (B4).

    ganchos: {"detener": fn(tarea_id)->bool, "dict_tarea": fn(tarea_id)->dict|None,
              "dir_tareas": Path, "carril_destino": str|None,
              "destino": str|None, "ejecutor": str}.
    Idempotente y reanudable: cada paso comprueba el marcador antes."""
    reloj = reloj or time.time
    m = obtener(base_dir, marcador_id)
    if not m:
        raise ErrorTraspaso(f"no existe el marcador {marcador_id}")
    if m.get("estado") in ("entregado", "aceptado", "confirmado"):
        return m
    if m.get("estado") in ("requiere_dueno", "devuelto"):
        return m
    ejecutor = ganchos.get("ejecutor") or "origen"
    if not tomar_ejecutor(base_dir, marcador_id, ejecutor, reloj=reloj,
                          auditar=auditar):
        actual = obtener(base_dir, marcador_id)
        if actual and actual.get("estado") == "entregado":
            return actual
        raise ErrorTraspaso("otro proceso está ejecutando el protocolo "
                            "de este traspaso")
    # Paso 1b: detener al origen ANTES de tocar nada más (B1).
    if not m.get("origen_detenido_ts"):
        detener = ganchos.get("detener")
        if detener is None or not detener(m["tarea"]):
            return a_requiere_dueno(
                base_dir, marcador_id,
                "la parada del origen no se confirmó a tiempo: "
                "nadie toca la tarea hasta que el dueño decida", auditar)
        m = marcar_detenido(base_dir, marcador_id, reloj=reloj)
    # Sin destino elegido aún: se ofrece en cuanto hay uno.
    if m.get("estado") == "sin_destino":
        destino = ganchos.get("destino") or m.get("destino")
        if not destino:
            return m
        m = ofrecer(base_dir, marcador_id, destino, reloj=reloj,
                    auditar=auditar)
    # Paso 2: rescate (con repo) o exigencia de idempotencia (I8).
    tarea_original = (ganchos.get("dict_tarea") or (lambda _t: None))(m["tarea"])
    if m.get("repo"):
        m = rescatar(base_dir, marcador_id, correr_git=correr_git,
                     auditar=auditar)
        if m.get("estado") == "requiere_dueno":
            return m
    else:
        if not tarea_original or tarea_original.get("idempotente") is not True:
            return a_requiere_dueno(
                base_dir, marcador_id,
                "tarea sin repo y sin «idempotente»: no se puede garantizar "
                "que no se duplique (I8)", auditar)
    # Paso 3: entrega.
    if tarea_original is None:
        raise ErrorTraspaso("no se encontró la tarea original para entregarla")
    return entregar(base_dir, marcador_id, tarea_original,
                    ganchos["dir_tareas"],
                    carril_destino=ganchos.get("carril_destino"),
                    reloj=reloj, auditar=auditar)


# ------------------------------------------------------------ paso 4: puerta

def reclamar(base_dir, marcador_id, cuenta, carril=None, instancia=None,
             reloj=None, auditar=None):
    """La reclamación del destino: el ÚNICO punto de activación (§8.4).

    Devuelve {"resultado": "aceptado"|"reanudar"|"duplicado"|"esperar"|
    "no_valido", ...}. La transición y la reasignación de alquileres
    van bajo el mismo paraguas, con orden de locks traspasos →
    alquileres (B5)."""
    ahora = (reloj or time.time)()
    with _bloqueo(base_dir):
        datos = cargar(base_dir)
        m = datos["traspasos"].get(marcador_id)
        if not isinstance(m, dict):
            return {"resultado": "no_valido",
                    "motivo": "el marcador no existe"}
        estado = m.get("estado")
        if estado in ("devuelto", "requiere_dueno", "sin_destino"):
            return {"resultado": "no_valido",
                    "motivo": f"el marcador está en «{estado}»"}
        if estado == "ofrecido":
            return {"resultado": "esperar",
                    "motivo": "el origen aún no ha entregado la tarea"}
        if estado == "entregado":
            if m.get("expira_ts") and ahora > m["expira_ts"]:
                m["estado"] = "devuelto"
                _guardar(base_dir, datos)
                return {"resultado": "no_valido",
                        "motivo": "la entrega caducó sin reclamarse"}
            m["estado"] = "aceptado"
            m["reclamante"] = {"cuenta": cuenta, "carril": carril,
                               "instancia": instancia}
            m["aceptado_ts"] = ahora
            _guardar(base_dir, datos)
            reasignados = 0
            if m.get("repo"):
                reasignados = alquileres.reasignar(
                    base_dir, m["repo"], m["tarea"], m["origen"], cuenta)
            datos = cargar(base_dir)
            m = datos["traspasos"][marcador_id]
            m["estado"] = "confirmado"
            m["confirmado_ts"] = ahora
            _guardar(base_dir, datos)
            resultado = {"resultado": "aceptado", "reasignados": reasignados,
                         "marcador": dict(m)}
        elif estado in ("aceptado", "confirmado"):
            r = m.get("reclamante") or {}
            if r.get("cuenta") == cuenta and r.get("carril") == carril:
                resultado = {"resultado": "reanudar", "marcador": dict(m)}
            else:
                resultado = {"resultado": "duplicado",
                             "motivo": "la tarea ya la reclamó otra cuenta",
                             "marcador": dict(m)}
        else:  # pragma: no cover - estados cerrados arriba
            resultado = {"resultado": "no_valido",
                         "motivo": f"estado inesperado «{estado}»"}
    if resultado["resultado"] == "aceptado" and auditar:
        git_trabajo._auditar(auditar, "traspaso",
                             f"{marcador_id}: reclamada por {cuenta} "
                             f"(carril {carril})", "ok", cuenta=cuenta,
                             accion="traspaso_reclamado")
    return resultado


# ------------------------------------------------------------------ barrido

def barrido(base_dir, reloj=None, destino_sin_latido=None, auditar=None):
    """Caduca lo caducable (I9) y vigila lo confirmado (§8.4).

    - ofrecido/entregado pasado su `expira_ts` → devuelto.
    - confirmado hace más de TTL_SUPERVISION_S y el destino sin latido
      (según el callable `destino_sin_latido(cuenta)->bool`) →
      requiere_dueno: ni se reofrece ni el origen la recupera solo.
    Devuelve [(marcador_id, nuevo_estado)]."""
    ahora = (reloj or time.time)()
    cambios = []
    with _bloqueo(base_dir):
        datos = cargar(base_dir)
        for mid, m in datos["traspasos"].items():
            if not isinstance(m, dict):
                continue
            estado = m.get("estado")
            if estado in ("ofrecido", "entregado") \
                    and m.get("expira_ts") and ahora > m["expira_ts"]:
                m["estado"] = "devuelto"
                cambios.append((mid, "devuelto"))
            elif estado == "confirmado" and destino_sin_latido is not None \
                    and m.get("confirmado_ts") \
                    and ahora - m["confirmado_ts"] > TTL_SUPERVISION_S \
                    and destino_sin_latido(m.get("destino")):
                m["estado"] = "requiere_dueno"
                m["motivo_dueno"] = ("el destino confirmó la tarea pero "
                                     "lleva sin latido más de "
                                     f"{TTL_SUPERVISION_S} s")
                cambios.append((mid, "requiere_dueno"))
        if cambios:
            _guardar(base_dir, datos)
    if auditar:
        for mid, nuevo in cambios:
            git_trabajo._auditar(auditar, "traspaso",
                                 f"{mid}: barrido → {nuevo}", "ok",
                                 accion="traspaso_barrido")
    return cambios

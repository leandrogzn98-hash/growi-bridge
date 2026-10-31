"""Protocolo por archivos oficina <-> Bridge (t-oficina-protocolo-050, spec 5 de 18).

Este modulo NO usa pygame: es el protocolo, igual para Pygame-ce y para Godot (alli se reescribe
en GDScript con las mismas constantes y la misma regla). Solo lee archivos; su unica escritura
fuera de su carpeta de datos es encolar, y eso lo hace oficina\\encolar\\encolar.py (la misma
funcion que «Pedirle algo» de la app).

Lo que lee (todo en solo lectura):
  share\\outbox\\runner-live.json    cada 2 s con tarea en curso, cada 10 s sin ella
  share\\outbox\\cola-live.json      cada 5 s
  share\\outbox\\runner-status.json  cada 10 s
  <app>\\engines.json + skills       al arrancar y cada 60 s
  share\\outbox\\bridge-latido.json  cada 1 s (el Bridge lo reescribe cada 5 s mientras la oficina vive)
Si el Bridge cae (latido o runner-status sin senal), todo se sigue leyendo, como mucho cada 10 s.

Lectura segura: 3 intentos separados 100 ms; JSON roto (escritura a medias) = «viejo»: se
queda el ultimo valor bueno con su edad, nunca un error ni un valor inventado. Cada archivo se
lee en su propio hilo: el render nunca espera a una lectura; si una tarda mas de 200 ms, el
render sigue con el ultimo valor bueno y muestra su edad.
"""
import ctypes
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

# ---- constantes del protocolo (las mismas en Godot)
REINTENTOS = 3
PAUSA_REINTENTO_S = 0.100
PLAZO_LECTURA_S = 0.200          # mas = «lectura lenta»: ultimo valor bueno con su edad
PERIODO_LIVE_ACTIVO_S = 2
PERIODO_LIVE_REPOSO_S = 10
PERIODO_COLA_S = 5
PERIODO_STATUS_S = 10
PERIODO_CONFIG_S = 60            # engines.json + skills
PERIODO_LATIDO_S = 1
PERIODO_SIN_BRIDGE_S = 10        # si el Bridge cae: se sigue intentando, cada 10 s
LATIDO_CADA_S = 5                # lo escribe el Bridge
LATIDO_LIMITE_S = 15             # sin latido fresco 15 s = «Bridge no disponible» y autocierre
# Umbrales de frescura: los de la regla de referencia oficina_estado_tarea() de
# growi-bridge-app\growi-bridge.py (t-oficina-consumo-vivo-050).
LIVE_FRESCO_S = 15
LIVE_TERMINADO_S = 60
STATUS_FRESCO_S = 120            # el runner libre reescribe runner-status.json cada 60 s
COLA_FRESCA_S = 45               # el runner reescribe cola-live.json cada <= 10 s

# Gancho SOLO de prueba: GROWI_OFICINA_LENTO="runner-live:0.8,cola-live:0.5" retrasa esas lecturas.
_LENTO = {}
for _p in (os.environ.get("GROWI_OFICINA_LENTO") or "").split(","):
    if ":" in _p:
        _k, _v = _p.split(":", 1)
        try:
            _LENTO[_k.strip()] = float(_v)
        except ValueError:
            pass


def edad_iso(iso, ahora=None):
    """Segundos desde una marca ISO del Bridge; None si no hay marca o no se entiende."""
    ahora = time.time() if ahora is None else ahora
    try:
        return ahora - datetime.fromisoformat(str(iso)).timestamp()
    except (TypeError, ValueError):
        return None


def leer_json(path, nombre=""):
    """Una lectura segura: (estado, datos, detalle, intentos). estado = ok | ausente | roto | error."""
    ultimo = ("error", "sin intentar")
    for i in range(REINTENTOS):
        if nombre in _LENTO:
            time.sleep(_LENTO[nombre])
        try:
            d = json.loads(Path(path).read_bytes().decode("utf-8"))
            return "ok", d, "", i + 1
        except FileNotFoundError:
            ultimo = ("ausente", "el archivo no existe")
        except (UnicodeDecodeError, ValueError) as e:
            ultimo = ("roto", f"JSON roto ({type(e).__name__})")
        except OSError as e:  # PermissionError mientras el Bridge hace os.replace
            ultimo = ("error", f"{type(e).__name__}: {e}")
        if i < REINTENTOS - 1:
            time.sleep(PAUSA_REINTENTO_S)
    return ultimo[0], None, ultimo[1], REINTENTOS


def _pid_vivo(pid):
    """Windows: OpenProcess + WaitForSingleObject(0). No bloquea."""
    if not pid:
        return False
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(0x00100000 | 0x1000, False, int(pid))  # SYNCHRONIZE | QUERY_LIMITED
        if not h:
            return ctypes.GetLastError() == 5  # acceso denegado = existe (proceso elevado)
        try:
            return k32.WaitForSingleObject(ctypes.c_void_p(h), 0) == 0x102  # WAIT_TIMEOUT = vivo
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))
    except Exception:
        return False


class Fuente:
    """Un archivo leido en su propio hilo. El render solo llama a vista() (lock de microsegundos)."""

    def __init__(self, nombre, path, periodo, marca=None, limite=None, leer=None, registro=None):
        self.nombre, self.path = nombre, Path(path)
        self.periodo = periodo            # funcion -> segundos hasta la siguiente lectura
        self.marca = marca                # funcion(datos) -> marca ISO del contenido, o None
        self.limite = limite              # segundos para dejar de estar «fresco», o None
        self._leer = leer or (lambda: leer_json(self.path, self.nombre))
        self.registro = registro          # funcion(dict) para las metricas
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._despertar = threading.Event()
        self.datos = None                 # ultimo valor BUENO
        self.t_bueno = None               # time.time() de la ultima lectura buena
        self.estado = "pendiente"         # resultado de la ultima lectura
        self.detalle = ""
        self.leyendo_desde = None
        self.lecturas = 0
        self.a_tiempo = 0
        self.latencias = []               # ms de las ultimas 2000 lecturas
        self.hilo = threading.Thread(target=self._bucle, name=f"leer-{nombre}", daemon=True)

    def arrancar(self):
        self.hilo.start()
        return self

    def parar(self):
        self._stop.set()
        self._despertar.set()

    def ya(self):
        self._despertar.set()

    def _bucle(self):
        while not self._stop.is_set():
            with self._lock:
                self.leyendo_desde = time.perf_counter()
            t0 = time.perf_counter()
            try:
                est, d, det, n = self._leer()
            except Exception as e:  # nunca tumbar el hilo
                est, d, det, n = "error", None, f"{type(e).__name__}: {e}", 1
            ms = (time.perf_counter() - t0) * 1000
            with self._lock:
                self.leyendo_desde = None
                self.estado, self.detalle = est, det
                self.lecturas += 1
                self.a_tiempo += ms <= PLAZO_LECTURA_S * 1000
                self.latencias.append(ms)
                del self.latencias[:-2000]
                if est == "ok":
                    self.datos, self.t_bueno = d, time.time()
            if self.registro:
                self.registro({"lectura": self.nombre, "ms": round(ms, 2), "estado": est, "intentos": n,
                               "a_tiempo": ms <= PLAZO_LECTURA_S * 1000})
            espera = max(0.05, float(self.periodo()))
            self._despertar.wait(espera)
            self._despertar.clear()

    def vista(self, ahora=None):
        """Lo que pinta el render. clase: fresco | viejo | ausente | roto | pendiente."""
        ahora = time.time() if ahora is None else ahora
        with self._lock:
            datos, t_bueno, est, det = self.datos, self.t_bueno, self.estado, self.detalle
            lento = (self.leyendo_desde is not None
                     and time.perf_counter() - self.leyendo_desde > PLAZO_LECTURA_S)
            ult = self.latencias[-1] if self.latencias else None
            lecturas, a_tiempo = self.lecturas, self.a_tiempo
        edad_lectura = None if t_bueno is None else ahora - t_bueno
        marca = self.marca(datos) if (self.marca and isinstance(datos, dict)) else None
        edad_contenido = edad_iso(marca, ahora) if marca else None
        if datos is None:
            clase = {"ausente": "ausente", "roto": "roto", "pendiente": "pendiente"}.get(est, "ausente")
        elif est != "ok":
            clase = "viejo"  # JSON roto o error: ultimo valor bueno, marcado viejo
        elif self.limite is not None and (edad_contenido is None or edad_contenido >= self.limite):
            clase = "viejo"
        else:
            clase = "fresco"
        return {"nombre": self.nombre, "clase": clase, "estado": est, "detalle": det, "datos": datos,
                "edad_lectura": edad_lectura, "edad_contenido": edad_contenido, "lento": lento,
                "ultima_ms": ult, "lecturas": lecturas, "a_tiempo": a_tiempo,
                "ejemplo": bool(isinstance(datos, dict) and datos.get("_ejemplo"))}

    def resumen(self):
        with self._lock:
            lat = sorted(self.latencias)
            n, ok = self.lecturas, self.a_tiempo
        if not lat:
            return {"lecturas": n, "a_tiempo": ok}
        pct = lambda p: round(lat[min(len(lat) - 1, int(p * len(lat)))], 2)  # noqa: E731
        return {"lecturas": n, "a_tiempo": ok, "tarde": n - ok, "p50_ms": pct(0.5), "p95_ms": pct(0.95),
                "max_ms": round(lat[-1], 2)}


class Latido:
    """Heartbeat: el Bridge reescribe bridge-latido.json cada 5 s ({pid, t, cerrar}); la oficina
    lo mira cada 1 s y comprueba que el pid del Bridge sigue vivo. 15 s sin latido fresco, o el
    pid muerto = «Bridge no disponible»."""

    def __init__(self, fuente, bridge_pid=None):
        self.fuente, self.bridge_pid = fuente, bridge_pid
        self.t_arranque = time.time()
        self.ultimo_ok = None

    def comprobar(self, ahora=None):
        """-> (estado, motivo, segundos_sin_latido). estado: vivo | cerrar | no_disponible | esperando."""
        ahora = time.time() if ahora is None else ahora
        v = self.fuente.vista(ahora)
        d = v["datos"] if isinstance(v["datos"], dict) else None
        if self.bridge_pid and not _pid_vivo(self.bridge_pid):
            return "no_disponible", f"el proceso del Bridge (pid {self.bridge_pid}) ya no existe", None
        t = None
        if d is not None:
            try:
                t = float(d.get("t"))
            except (TypeError, ValueError):
                t = None
        pid_ok = d is not None and (not self.bridge_pid or d.get("pid") == self.bridge_pid)
        if pid_ok and d.get("cerrar"):
            return "cerrar", "la app pidió cerrar la oficina", 0
        if pid_ok and t is not None and ahora - t <= LATIDO_LIMITE_S:
            self.ultimo_ok = max(self.ultimo_ok or 0, t)
        ref = self.ultimo_ok if self.ultimo_ok is not None else self.t_arranque
        sin = ahora - ref
        if sin > LATIDO_LIMITE_S:
            if d is None:
                motivo = f"sin {v['nombre']} ({v['clase']}) desde hace {sin:.0f} s"
            elif not pid_ok:
                motivo = f"el latido es de otro proceso (pid {d.get('pid')})"
            else:
                motivo = f"el Bridge no responde: último latido hace {sin:.0f} s"
            return "no_disponible", motivo, sin
        if self.ultimo_ok is None:
            return "esperando", "esperando el primer latido del Bridge", sin
        return "vivo", f"latido hace {sin:.0f} s", sin


# ---- estado derivado (provisional: el definitivo es derivar_estado() del spec 8)
TRABAJANDO, EN_COLA, SIN_TAREA, SIN_SENAL, SIN_INSTALAR = (
    "trabajando", "en cola", "sin tarea", "sin señal", "sin instalar")
EN_COLA_DB = ("en_cola", "esperando_aprobacion", "esperando_leandro", "reintento", "pendiente")

# Roster de la escena: 14 personajes + Runa + vigilante = 16 (Leandro es el jugador, fuera).
# (id, nombre, departamento, tipo, clave). tipo: modelo | motor | lider | gerente | skill | despacho | vigilante
ROSTER = [
    ("growi", "Growi", "gerencia", "gerente", None),
    ("clau", "Clau", "claude", "lider", "claude"),
    ("sonny", "Sonny", "claude", "modelo", ("claude", "sonnet")),
    ("opus", "Opus", "claude", "modelo", ("claude", "opus")),
    ("haiku", "Haiku", "claude", "modelo", ("claude", "haiku")),
    ("cody", "Cody", "codex", "lider", "codex"),
    ("dex", "Dex", "codex", "motor", "codex"),
    ("luma", "Luma", "local", "lider", "local"),
    ("hermes_directo", "Hermes Directo", "local", "motor", "llama"),
    ("hermes_ollama", "Hermes Ollama", "local", "motor", "ollama"),
    ("gemi", "Gemi", "gemini", "lider", "gemini"),
    ("mensajero", "Mensajero 3D", "taller3d", "motor", "meshy"),
    ("blender", "Blender", "especialistas", "skill", "blender"),
    ("tripo", "Tripo", "especialistas", "skill", "tripo"),
    ("runa", "Runa", "despacho", "despacho", None),
    ("vigilante", "Vigilante", "noche", "vigilante", None),
]
DEPTO_MOTORES = {"claude": ("claude",), "codex": ("codex",), "local": ("llama", "ollama"),
                 "gemini": ("gemini", "agy")}


def personaje_de(motor, modelo):
    """De (motor, modelo) de una tarea al id del personaje que la hace."""
    motor = (motor or "").lower()
    modelo = (modelo or "").lower()
    if motor == "claude":
        for m in ("opus", "haiku", "sonnet"):
            if m in modelo:
                return m if m != "sonnet" else "sonny"
        return "sonny"  # sin modelo: el de por defecto de Claude Code (FALTA confirmarlo por tarea)
    return {"codex": "dex", "llama": "hermes_directo", "ollama": "hermes_ollama",
            "meshy": "mensajero", "gemini": "gemi", "agy": "gemi"}.get(motor)


def estado_tarea(tid, live, status, cola, ahora=None):
    """La regla de referencia oficina_estado_tarea() (growi-bridge-app) con UNA correccion: una
    tarea en_cola mientras el runner corre OTRA (current = otra) es «en_cola», no «sin_senal»
    (el runner es serie: casi siempre hay cola mientras algo corre). live/status/cola = dicts o None."""
    ahora = time.time() if ahora is None else ahora
    fila = None
    ec = edad_iso((cola or {}).get("actualizado"), ahora) if isinstance(cola, dict) else None
    if ec is not None and ec < COLA_FRESCA_S:
        fila = next((t for t in cola.get("tareas") or [] if isinstance(t, dict) and t.get("id") == tid), None)
    if isinstance(live, dict) and live.get("task_id") == tid:
        e = edad_iso(live.get("actualizado"), ahora)
        if e is not None:
            if live.get("estado") == "terminado":
                if e < LIVE_TERMINADO_S:
                    return "terminado", f"live terminado hace {e:.0f} s"
            elif e < LIVE_FRESCO_S:
                return "trabajando", f"runner-live de hace {e:.0f} s"
    es = edad_iso((status or {}).get("last_poll"), ahora) if isinstance(status, dict) else None
    if es is None or es >= STATUS_FRESCO_S:
        return "sin_senal", "sin live fresco y runner-status ausente o viejo"
    if fila is None:
        return "sin_senal", "sin live fresco y cola-live ausente, vieja o sin esta tarea"
    cur = status.get("current")
    cur_id = cur.get("id") if isinstance(cur, dict) else None
    if cur_id == tid:
        if fila.get("estado") == "en_curso":
            return "trabajando_degradado", "sin live fresco; runner-status.current y cola-live coinciden"
        return "sin_senal", f"runner-status dice que corre pero cola-live la da {fila.get('estado')}"
    if fila.get("estado") in EN_COLA_DB:
        return "en_cola", f"cola-live la da {fila.get('estado')}"
    if fila.get("estado") in ("terminada", "fallida", "necesita_decision"):
        return "terminado", f"cola-live la da {fila.get('estado')}"
    return "sin_senal", "las fuentes no coinciden"


def derivar(v, bridge, ahora=None):
    """v = {nombre: vista}; bridge = estado del Latido. -> {id: (estado, motivo)} para los 16."""
    ahora = time.time() if ahora is None else ahora
    out = {}
    st = v["runner-status"]
    status = st["datos"] if st["clase"] == "fresco" else None
    cl = v["cola-live"]
    cola = cl["datos"] if cl["clase"] == "fresco" else None
    live = v["runner-live"]["datos"]
    eng = v["engines"]["datos"] if isinstance(v["engines"]["datos"], dict) else None
    motores = set((eng.get("motores") or {}).keys()) if isinstance(eng, dict) and "motores" in eng else None
    sk = v["skills"]["datos"] if isinstance(v["skills"]["datos"], dict) else None
    skills = set(sk.get("skills") or []) if sk else None

    if bridge != "vivo":
        motivo = "Bridge no disponible (sin latido)"
        return {r[0]: (SIN_SENAL, motivo) for r in ROSTER}
    if status is None:
        motivo = f"runner-status.json {st['clase']}"
        return {r[0]: (SIN_SENAL, motivo) for r in ROSTER}

    # tareas que se ven en alguna fuente
    tareas = {}
    if isinstance(live, dict) and live.get("task_id"):
        tareas[live["task_id"]] = (live.get("motor"), live.get("modelo"))
    cur = status.get("current")
    if isinstance(cur, dict) and cur.get("id"):
        tareas.setdefault(cur["id"], (cur.get("motor"), cur.get("modelo")))
    if isinstance(cola, dict):
        for t in cola.get("tareas") or []:
            if isinstance(t, dict) and t.get("id"):
                tareas.setdefault(t["id"], (t.get("motor"), t.get("modelo")))
    por_pj = {}
    for tid, (motor, modelo) in tareas.items():
        est, por = estado_tarea(tid, live, status, cola, ahora)
        pj = personaje_de(motor, modelo)
        if pj and est != "terminado":
            por_pj.setdefault(pj, []).append((est, tid, por))

    def _uno(pj):
        lst = por_pj.get(pj) or []
        for est, tid, por in lst:
            if est.startswith("trabajando"):
                return TRABAJANDO, f"{tid}: {por}"
        for est, tid, por in lst:
            if est == "sin_senal":
                return SIN_SENAL, f"{tid}: {por}"
        for est, tid, por in lst:
            if est == "en_cola":
                return EN_COLA, f"{tid}: {por}"
        if cola is None:
            return SIN_SENAL, f"cola-live.json {cl['clase']}: no se puede saber si tiene tarea"
        return SIN_TAREA, "ni live ni cola-live le dan tarea"

    prio = {TRABAJANDO: 0, SIN_SENAL: 1, EN_COLA: 2, SIN_TAREA: 3, SIN_INSTALAR: 4}
    for pid_, _n, depto, tipo, clave in ROSTER:
        if tipo in ("modelo", "motor"):
            motor = clave[0] if isinstance(clave, tuple) else clave
            if motores is not None and motor not in motores:
                out[pid_] = (SIN_INSTALAR, f"el motor «{motor}» no está en engines.json")
            else:
                out[pid_] = _uno(pid_)
        elif tipo == "skill":
            if skills is not None and clave not in skills:
                out[pid_] = (SIN_INSTALAR, f"la skill «{clave}» no está en skills")
            elif skills is None:
                out[pid_] = (SIN_SENAL, "no se pudo leer la lista de skills")
            else:  # ningun archivo dice que skill usa una tarea: sala de espera (FALTA)
                out[pid_] = (SIN_TAREA, "sala de espera: ningún archivo dice qué skill usa la tarea")
    for pid_, _n, depto, tipo, clave in ROSTER:
        if tipo == "lider":
            miembros = [r[0] for r in ROSTER if r[2] == depto and r[3] in ("modelo", "motor")]
            if clave == "gemini":
                ok = motores is None or any(m in motores for m in DEPTO_MOTORES["gemini"])
                out[pid_] = ((SIN_SENAL if cola is None else SIN_TAREA, "departamento sin empleados") if ok
                             else (SIN_INSTALAR, "Gemini no está en engines.json: en obras"))
                continue
            ests = [out[m] for m in miembros if out[m][0] != SIN_INSTALAR]
            out[pid_] = (min(ests, key=lambda e: prio[e[0]]) if ests
                         else (SIN_INSTALAR, "ningún motor del departamento instalado"))
            if ests:
                out[pid_] = (out[pid_][0], "su departamento: " + out[pid_][1])
    ests = [out[r[0]] for r in ROSTER if r[3] in ("modelo", "motor") and out[r[0]][0] != SIN_INSTALAR]
    g = min(ests, key=lambda e: prio[e[0]]) if ests else (SIN_SENAL, "sin datos")
    out["growi"] = (g[0], "la oficina: " + g[1])
    if cola is None:
        out["runa"] = (SIN_SENAL, f"cola-live.json {cl['clase']}")
    else:
        pend = cola.get("cola_pendiente")
        n = pend if isinstance(pend, int) else sum(
            1 for t in cola.get("tareas") or [] if isinstance(t, dict) and t.get("estado") in EN_COLA_DB)
        out["runa"] = (EN_COLA, f"{n} en la cola") if n else (SIN_TAREA, "la cola está vacía")
    out["vigilante"] = (SIN_TAREA, "runner-status fresco (el turno de noche lo decide el spec 8)")
    return out


def skills_presentes(app_dir):
    """Lista de skills: carpetas con SKILL.md en <app>\\skills y en ~\\.claude\\skills."""
    vistos = []
    for base in (Path(app_dir) / "skills", Path.home() / ".claude" / "skills"):
        try:
            for p in base.iterdir():
                if p.is_dir() and (p / "SKILL.md").is_file():
                    vistos.append(p.name.lower())
        except OSError:
            continue
    return sorted(set(vistos))


class Borradores:
    """Encargos escritos sin Bridge: se guardan en disco (escritura atomica) como «pendiente de
    enviar» y se envian cuando vuelve la senal. Nunca se fingen enviados."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        est, d, _det, _n = leer_json(self.path)
        self.items = d if (est == "ok" and isinstance(d, list)) else []

    def _guardar(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def nuevo(self, texto):
        with self.lock:
            it = {"texto": texto, "creado": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "estado": "pendiente de enviar", "id": None, "error": None}
            self.items.append(it)
            self._guardar()
            return it

    def marcar(self, it, **kw):
        with self.lock:
            it.update(kw)
            self._guardar()

    def pendientes(self):
        with self.lock:
            return [it for it in self.items if it.get("estado") == "pendiente de enviar"]

# -*- coding: utf-8 -*-
"""Presencia del dueño (Fase 4 del plan multi-Muse): ¿está usando la PC?

El segundo plano silencioso es SOLO para cuando el dueño está presente
(jugando, viendo una serie, trabajando): porcentaje compartido y ninguna
ventana sorpresa. Si está ausente, las cuentas Muse pueden usar la
máquina hasta el máximo configurado y las ventanas no importan.

Principio rector: **ante la duda, presente** (no molestar). Solo se entra
en ausente con evidencia positiva y sostenida:

- Entrar en ausente exige 3 evaluaciones seguidas en «ausente» (una cada
  ~30 s). Volver a presente es inmediato: en cuanto una señal dice que el
  dueño está, se está.
- El override manual del dueño manda siempre mientras viva; al caducar
  vuelve el modo automático y queda anotado.
- Sin señal de reposo conocida (Wayland) el sistema se queda en presente,
  salvo la excepción de la sesión bloqueada sin ninguna señal positiva.

Las señales llegan como un dict; ``None`` (o clave ausente) significa
«no lo sé», nunca un cero inventado:

- ``idle_s``: segundos desde la última entrada (teclado/ratón).
- ``pantalla_completa``: hay una app a pantalla completa (juego, vídeo).
- ``sesion_bloqueada``: la sesión está bloqueada.
- ``proceso_absorbente``: corre un proceso de la lista (steam, vlc, ...).
- ``gpu_ajena_cargada``: la GPU va cargada por procesos que no son de
  Growi (un juego sin foco también es presencia).

El estado vive en ``presencia.json`` (carpeta compartida): modo vigente,
desde cuándo, la última evaluación con las señales que decidieron, el
override y la marca ``supervision_ts`` del barrido de supervisión. La
evaluación corre en su propio hilo (~30 s); el latido del tablero solo lee
el modo ya calculado.
"""

import contextlib
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

VERSION = 1
CONFIRMACIONES_AUSENTE = 3

CONFIG_DEF = {
    "idle_presente_s": 120,
    "idle_ausencia_s": 900,
    "procesos_absorbentes": [
        "steam", "steamwebhelper", "vlc", "mpv", "kodi", "mpc-hc64",
        "mpc-hc", "wmplayer", "netflix", "spotify", "obs64", "obs",
        "VirtualDesktop", "vrserver",
    ],
}

SENALES = ("idle_s", "pantalla_completa", "sesion_bloqueada",
           "proceso_absorbente", "gpu_ajena_cargada")

_LOCKS = {}
_LOCKS_MU = threading.Lock()


def _lock_de(ruta):
    clave = str(ruta)
    with _LOCKS_MU:
        if clave not in _LOCKS:
            _LOCKS[clave] = threading.RLock()
        return _LOCKS[clave]


@contextlib.contextmanager
def _bloqueo(ruta_lock, espera_s=10.0):
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


def _ruta(base_dir):
    return Path(base_dir) / "presencia.json"


def _ruta_config(base_dir):
    return Path(base_dir) / "presencia-config.json"


def cargar_config(base_dir):
    cfg = dict(CONFIG_DEF)
    try:
        datos = json.loads(_ruta_config(base_dir).read_text(encoding="utf-8"))
        if isinstance(datos, dict):
            for clave in ("idle_presente_s", "idle_ausencia_s"):
                valor = datos.get(clave)
                if isinstance(valor, (int, float)) and not isinstance(
                        valor, bool) and valor > 0:
                    cfg[clave] = valor
            lista = datos.get("procesos_absorbentes")
            if isinstance(lista, list):
                cfg["procesos_absorbentes"] = [str(x) for x in lista
                                               if isinstance(x, str)]
    except (OSError, ValueError):
        pass
    return cfg


def _vacio():
    return {
        "version": VERSION,
        "revision": 0,
        "modo": "presente",
        "desde_ts": None,
        "override": None,
        "override_ts": None,
        "override_hasta_ts": None,
        "racha_ausente": 0,
        "ultima": None,
        "supervision_ts": None,
        "historial": [],
    }


def _cargar(base_dir):
    """Nunca lanza: un presencia.json corrupto equivale a «presente»."""
    try:
        datos = json.loads(_ruta(base_dir).read_text(encoding="utf-8"))
        if isinstance(datos, dict) and datos.get("version") == VERSION:
            base = _vacio()
            base.update(datos)
            return base
    except (OSError, ValueError):
        pass
    return _vacio()


def _guardar(base_dir, estado):
    estado["revision"] = int(estado.get("revision") or 0) + 1
    ruta = _ruta(base_dir)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)
    os.replace(str(tmp), str(ruta))


# ---------------------------------------------------------------------------
# La tabla de verdad (función pura)
# ---------------------------------------------------------------------------

def evaluar(senales, config=None):
    """«presente» | «ausente» para unas señales dadas. Función pura: no lee
    archivos ni el reloj; lo desconocido nunca empuja a ausente."""
    cfg = dict(CONFIG_DEF)
    if config:
        cfg.update({k: v for k, v in config.items() if v is not None})
    s = senales or {}
    idle = s.get("idle_s")
    if isinstance(idle, bool) or not isinstance(idle, (int, float)):
        idle = None
    completa = s.get("pantalla_completa") is True
    bloqueada = s.get("sesion_bloqueada") is True
    absorbente = s.get("proceso_absorbente") is True
    gpu_ajena = s.get("gpu_ajena_cargada") is True

    # --- Señales positivas de presencia (cualquiera basta) ---
    if completa:
        return "presente"
    if idle is not None and idle < cfg["idle_presente_s"]:
        return "presente"
    if (s.get("sesion_bloqueada") is False and absorbente
            and idle is not None and idle < 3600):
        return "presente"
    if gpu_ajena and idle is not None and idle < 3600:
        return "presente"

    # --- Ausencia (evidencia positiva, nunca por descarte) ---
    # Excepción: sesión bloqueada sin ninguna señal positiva de presencia
    # basta (si no, en Wayland sin señal de reposo el presupuesto de
    # ausente sería inalcanzable: bloqueada y lejos es el caso normal).
    if bloqueada:
        return "ausente"
    if (idle is not None and idle > cfg["idle_ausencia_s"]
            and not completa and not absorbente
            and idle > 3600):
        return "ausente"
    return "presente"


# ---------------------------------------------------------------------------
# Máquina de estados con histéresis y override
# ---------------------------------------------------------------------------

def _anotar(estado, ahora, de, a, motivo):
    hist = estado.setdefault("historial", [])
    hist.append({"ts": ahora, "de": de, "a": a, "motivo": motivo})
    del hist[:-20]


def _override_vivo(estado, ahora):
    if estado.get("override") not in ("presente", "ausente"):
        return False
    hasta = estado.get("override_hasta_ts")
    return hasta is None or ahora <= hasta


def tick(base_dir, senales, config=None, reloj=None):
    """Una evaluación: aplica override, histéresis y guarda el estado.
    Devuelve el estado completo."""
    ahora = (reloj or time.time)()
    cfg = config if config is not None else cargar_config(base_dir)
    with _bloqueo(_ruta(base_dir).with_suffix(".lock")):
        estado = _cargar(base_dir)
        veredicto = evaluar(senales, cfg)
        estado["ultima"] = {
            "ts": ahora,
            "senales": {k: (senales or {}).get(k) for k in SENALES},
            "veredicto": veredicto,
        }
        if estado.get("override") in ("presente", "ausente") \
                and not _override_vivo(estado, ahora):
            _anotar(estado, ahora, estado["override"], estado["modo"],
                    "override caducado; vuelve el modo automático")
            estado["override"] = None
            estado["override_ts"] = None
            estado["override_hasta_ts"] = None
        if _override_vivo(estado, ahora):
            deseado = estado["override"]
            estado["racha_ausente"] = 0
            if estado["modo"] != deseado:
                _anotar(estado, ahora, estado["modo"], deseado,
                        "override del dueño")
                estado["modo"] = deseado
                estado["desde_ts"] = ahora
        elif veredicto == "presente":
            estado["racha_ausente"] = 0
            if estado["modo"] != "presente":
                _anotar(estado, ahora, estado["modo"], "presente",
                        "una señal dice que el dueño está")
                estado["modo"] = "presente"
                estado["desde_ts"] = ahora
        else:  # veredicto ausente: exige confirmaciones seguidas
            estado["racha_ausente"] = int(estado.get("racha_ausente") or 0) + 1
            if estado["racha_ausente"] >= CONFIRMACIONES_AUSENTE \
                    and estado["modo"] != "ausente":
                _anotar(estado, ahora, estado["modo"], "ausente",
                        f"{CONFIRMACIONES_AUSENTE} evaluaciones seguidas "
                        "en ausente")
                estado["modo"] = "ausente"
                estado["desde_ts"] = ahora
        if estado["desde_ts"] is None:
            estado["desde_ts"] = ahora
        _guardar(base_dir, estado)
        return estado


def leer_estado(base_dir):
    return _cargar(base_dir)


def modo_efectivo(base_dir, reloj=None):
    """El modo que manda ahora mismo (override vivo incluido), sin
    escribir nada. Ante cualquier duda: «presente»."""
    try:
        ahora = (reloj or time.time)()
        estado = _cargar(base_dir)
        if _override_vivo(estado, ahora):
            return estado["override"]
        return estado.get("modo") or "presente"
    except Exception:
        return "presente"


def poner_override(base_dir, modo, hasta_ts=None, reloj=None):
    """Fija (modo «presente»/«ausente») o quita (None) el override manual.
    El override manda siempre mientras viva."""
    if modo is not None and modo not in ("presente", "ausente"):
        raise ValueError(f"override no válido: {modo!r}")
    ahora = (reloj or time.time)()
    with _bloqueo(_ruta(base_dir).with_suffix(".lock")):
        estado = _cargar(base_dir)
        estado["override"] = modo
        estado["override_ts"] = ahora if modo else None
        estado["override_hasta_ts"] = hasta_ts if modo else None
        if modo and estado["modo"] != modo:
            _anotar(estado, ahora, estado["modo"], modo,
                    "override del dueño")
            estado["modo"] = modo
            estado["desde_ts"] = ahora
        if not modo:
            estado["racha_ausente"] = 0
        _guardar(base_dir, estado)
        return estado


def marcar_supervision_ts(base_dir, ts):
    """El barrido de supervisión deja aquí su marca en cada pasada."""
    with _bloqueo(_ruta(base_dir).with_suffix(".lock")):
        estado = _cargar(base_dir)
        estado["supervision_ts"] = ts
        _guardar(base_dir, estado)


# ---------------------------------------------------------------------------
# Adaptadores de señales (best-effort: lo que no se sabe queda en None)
# ---------------------------------------------------------------------------

def _idle_windows():
    try:
        import ctypes

        class _LII(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint),
                        ("dwTime", ctypes.c_uint)]

        lii = _LII()
        lii.cbSize = ctypes.sizeof(_LII)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        tick = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (tick - lii.dwTime) / 1000.0)
    except Exception:
        return None


def _idle_linux_x11():
    display = os.environ.get("DISPLAY")
    if not display:
        return None
    try:
        import ctypes
        x11 = ctypes.CDLL("libX11.so.6")
        xss = ctypes.CDLL("libXss.so.1")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        disp = x11.XOpenDisplay(None)
        if not disp:
            return None
        try:
            ev = ctypes.c_int(0)
            err = ctypes.c_int(0)
            if not xss.XScreenSaverQueryExtension(ctypes.c_void_p(disp),
                                                  ctypes.byref(ev),
                                                  ctypes.byref(err)):
                return None

            class _Info(ctypes.Structure):
                _fields_ = [("window", ctypes.c_ulong),
                            ("state", ctypes.c_int),
                            ("kind", ctypes.c_int),
                            ("til_or_since", ctypes.c_ulong),
                            ("idle", ctypes.c_ulong),
                            ("eventMask", ctypes.c_ulong)]

            x11.XDefaultRootWindow.restype = ctypes.c_ulong
            root = x11.XDefaultRootWindow(ctypes.c_void_p(disp))
            info = _Info()
            if not xss.XScreenSaverQueryInfo(ctypes.c_void_p(disp),
                                             ctypes.c_ulong(root),
                                             ctypes.byref(info)):
                return None
            return float(info.idle) / 1000.0
        finally:
            x11.XCloseDisplay(ctypes.c_void_p(disp))
    except Exception:
        pass
    exe = shutil.which("xprintidle")
    if exe:
        try:
            salida = subprocess.run([exe], capture_output=True, text=True,
                                    timeout=5)
            return float(salida.stdout.strip()) / 1000.0
        except Exception:
            return None
    return None


def _pantalla_completa_windows():
    try:
        import ctypes
        estado = ctypes.c_int(0)
        res = ctypes.windll.shell32.SHQueryUserNotificationState(
            ctypes.byref(estado))
        if res != 0:
            return None
        # 2 = ocupado (pantalla completa), 3 = D3D a pantalla completa,
        # 4 = modo presentación.
        return estado.value in (2, 3, 4)
    except Exception:
        return None


def _pantalla_completa_linux():
    """_NET_WM_STATE_FULLSCREEN de la ventana activa vía xprop (X11). En
    Wayland no hay API estándar: None (no lo sé)."""
    if not os.environ.get("DISPLAY"):
        return None
    xprop = shutil.which("xprop")
    if not xprop:
        return None
    try:
        activa = subprocess.run([xprop, "-root", "_NET_ACTIVE_WINDOW"],
                                capture_output=True, text=True, timeout=5)
        wid = None
        for trozo in activa.stdout.replace("=", " ").split():
            if trozo.startswith("0x"):
                wid = trozo
        if not wid or wid == "0x0":
            return None
        estado = subprocess.run([xprop, "-id", wid, "_NET_WM_STATE"],
                                capture_output=True, text=True, timeout=5)
        return "_NET_WM_STATE_FULLSCREEN" in estado.stdout
    except Exception:
        return None


def _bloqueada_windows():
    try:
        import ctypes
        # Si el escritorio de entrada no se puede abrir, la sesión está en
        # la pantalla segura (bloqueada).
        desk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0001)
        if not desk:
            return True
        ctypes.windll.user32.CloseDesktop(desk)
        return False
    except Exception:
        return None


def _bloqueada_linux():
    sesion = os.environ.get("XDG_SESSION_ID")
    loginctl = shutil.which("loginctl")
    if not sesion or not loginctl:
        return None
    try:
        salida = subprocess.run(
            [loginctl, "show-session", sesion, "-p", "LockedHint",
             "--value"], capture_output=True, text=True, timeout=5)
        valor = salida.stdout.strip().lower()
        if valor == "yes":
            return True
        if valor == "no":
            return False
    except Exception:
        pass
    return None


def _absorbente(config):
    try:
        import psutil
    except Exception:
        return None
    nombres = {str(n).lower() for n in
               (config or CONFIG_DEF)["procesos_absorbentes"]}
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                nombre = (proc.info.get("name") or "").lower()
            except Exception:
                continue
            if nombre in nombres or \
                    os.path.splitext(nombre)[0] in nombres:
                return True
        return False
    except Exception:
        return None


def _gpu_ajena(pids_propios):
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        uso = subprocess.run(
            [exe, "--query-gpu=utilization.gpu", "--format=csv,noheader,"
             "nounits"], capture_output=True, text=True, timeout=8)
        util = float(uso.stdout.strip().splitlines()[0])
        apps = subprocess.run(
            [exe, "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=8)
        pids = set()
        for linea in apps.stdout.splitlines():
            linea = linea.strip()
            if linea.isdigit():
                pids.add(int(linea))
        if not pids:
            return False
        ajenos = pids - set(pids_propios or ())
        return bool(util > 80 and ajenos)
    except Exception:
        return None


def recoger_senales(base_dir=None, pids_propios=(), config=None):
    """Recoge las señales de la plataforma. Todo lo que no se puede saber
    queda en None; esta función nunca lanza."""
    cfg = config
    if cfg is None and base_dir is not None:
        cfg = cargar_config(base_dir)
    if os.name == "nt":
        return {
            "idle_s": _idle_windows(),
            "pantalla_completa": _pantalla_completa_windows(),
            "sesion_bloqueada": _bloqueada_windows(),
            "proceso_absorbente": _absorbente(cfg),
            "gpu_ajena_cargada": _gpu_ajena(pids_propios),
        }
    return {
        "idle_s": _idle_linux_x11(),
        "pantalla_completa": _pantalla_completa_linux(),
        "sesion_bloqueada": _bloqueada_linux(),
        "proceso_absorbente": _absorbente(cfg),
        "gpu_ajena_cargada": _gpu_ajena(pids_propios),
    }

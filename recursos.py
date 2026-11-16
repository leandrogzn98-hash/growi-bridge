# -*- coding: utf-8 -*-
"""Recursos de la PC por porcentajes (Fase 4 del plan multi-Muse).

Los límites no son cifras fijas: el programa detecta el hardware de la PC
donde se instala y el dueño asigna PORCENTAJES por modo de presencia
(ausente / presente). El presupuesto es del programa entero: las dos
cuentas Muse lo comparten y se reparte a partes iguales entre las tareas
vivas de AMBOS carriles (el estado compartido lleva una sección por
carril y el reparto se calcula sobre la suma).

Traducción del % a cada plataforma, sin prometer lo que no se puede:

- Linux con systemd de usuario (solo tras una SONDA REAL al arrancar:
  ``systemd-run --user --scope -p CPUQuota=50% -- /bin/true``):
  ``CPUQuota = % × núcleos lógicos`` (en systemd, 100 % = un núcleo) y
  ``MemoryMax = RAM total × %``.
- Linux sin systemd: prioridad nice (10 en presente, 0 en ausente) +
  medición; ciclo de trabajo SIGSTOP/SIGCONT solo sobre las hojas motor.
- Windows: prioridad de proceso + Job Objects por ctypes (CpuRate en
  centésimas de punto porcentual, límite de memoria por proceso); si el
  Job falla, prioridad + medición, declarado en el estado.
- GPU: no hay tope por proceso alcanzable desde Python; se gobierna por
  ADMISIÓN: una tarea de modelo local arranca solo si la VRAM comprometida
  más su necesidad cabe en el % asignado. Sin estimación en la tarea, la
  necesidad supuesta es el 25 % de la VRAM libre.
- RAM sin systemd/Job: gobierno por medición (3 muestras sobre el % →
  no arrancan tareas nuevas; matar por RAM sigue el camino de la
  duración máxima, nunca un kill silencioso).

La detección se guarda en ``recursos.json`` (carpeta compartida) con una
firma (núcleos + RAM total + VRAM total + volumen de los worktrees); al
arrancar solo se redetecta si la firma cambió o el archivo no existe.
Los specs nuevos aplican a las tareas SIGUIENTES, nunca a las vivas.
"""

import contextlib
import json
import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

VERSION = 1
SUELO_RAM_BYTES = 256 * 1024 * 1024     # suelo de cordura por tarea
SUELO_CPU_PCT_MAQUINA = 0.5             # ~5 % de un núcleo, en % máquina
                                        # se expresa en núcleos: ver limites()

ASIGNACION_DEF = {
    "ausente": {"cpu": 100, "ram": 100, "gpu": 100},
    "presente": {"cpu": 50, "ram": 50, "gpu": 50},
}

MODOS = ("ausente", "presente")
CLAVES = ("cpu", "ram", "gpu")

_LOCKS = {}
_LOCKS_MU = threading.Lock()


class ErrorRecursos(ValueError):
    """Asignación o petición de recursos no válida."""


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


def _ruta(base_dir, nombre="recursos.json"):
    return Path(base_dir) / nombre


def _guardar_json(base_dir, nombre, datos):
    ruta = _ruta(base_dir, nombre)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(str(tmp), str(ruta))


def _leer_json(base_dir, nombre):
    try:
        datos = json.loads(_ruta(base_dir, nombre).read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Detección de hardware
# ---------------------------------------------------------------------------

def _cpu_nombre():
    if os.name == "nt":
        return os.environ.get("PROCESSOR_IDENTIFIER") or None
    try:
        for linea in Path("/proc/cpuinfo").read_text(
                encoding="utf-8", errors="replace").splitlines():
            if linea.lower().startswith("model name"):
                return linea.split(":", 1)[1].strip() or None
    except OSError:
        pass
    return platform.processor() or None


def _ram_total():
    try:
        import psutil
        return int(psutil.virtual_memory().total)
    except Exception:
        pass
    if os.name != "nt":
        try:
            for linea in Path("/proc/meminfo").read_text(
                    encoding="utf-8", errors="replace").splitlines():
                if linea.startswith("MemTotal:"):
                    return int(linea.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            pass
    else:
        try:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
                return int(ms.ullTotalPhys)
        except Exception:
            pass
    return None


def _gpu_detectar(ejecutar=None):
    """{nombre, vram_total (bytes)} vía nvidia-smi, o None honesto."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    correr = ejecutar or (lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, timeout=10))
    try:
        salida = correr([exe, "--query-gpu=name,memory.total",
                         "--format=csv,noheader,nounits"])
        texto = (salida.stdout or "").strip().splitlines()
        if not texto:
            return None
        nombre, _, mib = texto[0].rpartition(",")
        return {"nombre": nombre.strip() or None,
                "vram_total": int(float(mib.strip())) * 1024 * 1024}
    except Exception:
        return None


def detectar(ruta_trabajo=None, inyectadas=None, ejecutar=None):
    """Specs de la máquina. ``inyectadas`` (solo pruebas, vía el entorno
    del proceso padre) sustituye a la detección real."""
    if inyectadas is not None:
        return _normalizar_specs(inyectadas, ruta_trabajo)
    ruta = str(ruta_trabajo or Path.home())
    fisicos = None
    try:
        import psutil
        fisicos = psutil.cpu_count(logical=False)
    except Exception:
        fisicos = None
    disco = {"ruta": ruta, "total": None, "libre": None}
    try:
        uso = shutil.disk_usage(ruta)
        disco = {"ruta": ruta, "total": int(uso.total),
                 "libre": int(uso.free)}
    except OSError:
        pass
    return {
        "cpu": {"fisicos": fisicos, "logicos": os.cpu_count() or 1,
                "nombre": _cpu_nombre()},
        "ram_total": _ram_total(),
        "gpu": _gpu_detectar(ejecutar),
        "disco": disco,
        "detectado_ts": time.time(),
    }


def _normalizar_specs(datos, ruta_trabajo=None):
    if not isinstance(datos, dict):
        raise ErrorRecursos("specs inyectadas no válidas")
    cpu = datos.get("cpu") or {}
    gpu = datos.get("gpu")
    disco = datos.get("disco") or {}
    return {
        "cpu": {"fisicos": cpu.get("fisicos"),
                "logicos": int(cpu.get("logicos") or 1),
                "nombre": cpu.get("nombre")},
        "ram_total": datos.get("ram_total"),
        "gpu": ({"nombre": gpu.get("nombre"),
                 "vram_total": gpu.get("vram_total")}
                if isinstance(gpu, dict) else None),
        "disco": {"ruta": disco.get("ruta") or str(ruta_trabajo or ""),
                  "total": disco.get("total"), "libre": disco.get("libre")},
        "detectado_ts": datos.get("detectado_ts") or time.time(),
    }


def firma_de(specs):
    cpu = specs.get("cpu") or {}
    gpu = specs.get("gpu") or {}
    disco = specs.get("disco") or {}
    volumen = disco.get("ruta") or ""
    try:
        volumen = f"{volumen}#{os.stat(volumen).st_dev}"
    except OSError:
        pass
    return "|".join(str(x) for x in (
        cpu.get("logicos"), specs.get("ram_total"), gpu.get("vram_total"),
        volumen))


# ---------------------------------------------------------------------------
# recursos.json: specs + asignación del dueño
# ---------------------------------------------------------------------------

def _vacio():
    return {"version": VERSION, "revision": 0, "specs": None,
            "firma": None, "asignacion": json.loads(
                json.dumps(ASIGNACION_DEF))}


def _cargar(base_dir):
    datos = _leer_json(base_dir, "recursos.json")
    if datos and datos.get("version") == VERSION:
        base = _vacio()
        base.update(datos)
        return base
    return _vacio()


def asegurar(base_dir, ruta_trabajo=None, inyectadas=None, ejecutar=None,
             reloj=None):
    """Devuelve los specs vigentes: redetecta solo si no hay archivo o la
    firma cambió. La asignación del dueño se conserva siempre."""
    frescas = detectar(ruta_trabajo, inyectadas=inyectadas,
                       ejecutar=ejecutar)
    firma = firma_de(frescas)
    with _bloqueo(_ruta(base_dir).with_suffix(".lock")):
        datos = _cargar(base_dir)
        if datos.get("specs") is None or datos.get("firma") != firma:
            datos["specs"] = frescas
            datos["firma"] = firma
            datos["revision"] = int(datos.get("revision") or 0) + 1
            _guardar_json(base_dir, "recursos.json", datos)
        return datos["specs"]


def asignacion_de(base_dir):
    datos = _cargar(base_dir)
    asig = datos.get("asignacion") or {}
    salida = {}
    for modo in MODOS:
        salida[modo] = {}
        for clave in CLAVES:
            valor = (asig.get(modo) or {}).get(clave)
            if isinstance(valor, int) and not isinstance(valor, bool) \
                    and 1 <= valor <= 100:
                salida[modo][clave] = valor
            else:
                salida[modo][clave] = ASIGNACION_DEF[modo][clave]
    return salida


def validar_asignacion(asignacion):
    """Valida una asignación (completa o parcial por modo): % enteros de
    1 a 100. Lanza ErrorRecursos con el motivo."""
    if not isinstance(asignacion, dict):
        raise ErrorRecursos("la asignación debe ser un objeto por modo")
    for modo, valores in asignacion.items():
        if modo not in MODOS:
            raise ErrorRecursos(f"modo desconocido: {modo!r}")
        if not isinstance(valores, dict):
            raise ErrorRecursos(f"la asignación de {modo} debe ser un objeto")
        for clave, valor in valores.items():
            if clave not in CLAVES:
                raise ErrorRecursos(f"recurso desconocido: {clave!r}")
            if isinstance(valor, bool) or not isinstance(valor, int):
                raise ErrorRecursos(
                    f"{modo}.{clave} debe ser un entero (recibido "
                    f"{valor!r})")
            if not 1 <= valor <= 100:
                raise ErrorRecursos(
                    f"{modo}.{clave} fuera de rango 1..100: {valor}")
    return True


def guardar_asignacion(base_dir, asignacion):
    validar_asignacion(asignacion)
    with _bloqueo(_ruta(base_dir).with_suffix(".lock")):
        datos = _cargar(base_dir)
        actual = datos.get("asignacion") or json.loads(
            json.dumps(ASIGNACION_DEF))
        for modo, valores in asignacion.items():
            actual.setdefault(modo, {}).update(valores)
        datos["asignacion"] = actual
        datos["revision"] = int(datos.get("revision") or 0) + 1
        _guardar_json(base_dir, "recursos.json", datos)
        return datos["asignacion"]


# ---------------------------------------------------------------------------
# Traducción % → límites (funciones puras)
# ---------------------------------------------------------------------------

def limites(specs, asig_modo, n_tareas):
    """El reparto del presupuesto de un modo entre ``n_tareas`` vivas.

    - cpu_pct_maquina: % del total de la máquina por tarea.
    - cpuquota_pct: para systemd (100 % = un núcleo): % × núcleos / n.
    - cpu_rate_job: para Job Objects de Windows, en centésimas de punto
      porcentual del total (100 % = 10000).
    - ram_bytes: RAM total × % / n, con suelo de cordura por tarea.
    - gpu: presupuesto de admisión (no se divide: es un fondo común)."""
    n = max(1, int(n_tareas or 1))
    cpu = specs.get("cpu") or {}
    logicos = max(1, int(cpu.get("logicos") or 1))
    pct_cpu = asig_modo["cpu"]
    nucleos = pct_cpu / 100.0 * logicos / n
    suelos = []
    if nucleos < 0.05:
        nucleos = 0.05
        suelos.append("cpu: suelo de 5 % de un núcleo por tarea")
    ram_total = specs.get("ram_total")
    ram_bytes = None
    if ram_total:
        ram_bytes = int(ram_total * asig_modo["ram"] / 100.0 / n)
        if ram_bytes < SUELO_RAM_BYTES:
            ram_bytes = SUELO_RAM_BYTES
            suelos.append("ram: suelo de 256 MB por tarea")
    gpu = specs.get("gpu") or {}
    vram_total = gpu.get("vram_total")
    return {
        "n_tareas": n,
        "cpu": {
            "pct_maquina": pct_cpu / n,
            "nucleos_equiv": nucleos,
            "cpuquota_pct": round(nucleos * 100),
            "cpu_rate_job": int(round(pct_cpu / n * 100)),
        },
        "ram": {"bytes_por_tarea": ram_bytes, "pct": asig_modo["ram"]},
        "gpu": {
            "pct": asig_modo["gpu"],
            "vram_presupuesto": (int(vram_total * asig_modo["gpu"] / 100.0)
                                 if vram_total else None),
            "vram_total": vram_total,
        },
        "suelos": suelos,
    }


def hay_margen_gpu(specs, asig_modo, comprometida_mib, necesaria_mib=None):
    """Admisión de GPU: ¿cabe una tarea local más?

    Sin GPU detectada no hay gobierno posible (ok, no gobernada). Sin
    estimación de la tarea, la necesidad supuesta es el 25 % de la VRAM
    libre."""
    gpu = specs.get("gpu") or {}
    total = gpu.get("vram_total")
    if not total:
        return {"ok": True, "gobernada": False, "necesidad_mib": None,
                "motivo": "sin GPU detectada: la GPU no se gobierna"}
    total_mib = total / (1024 * 1024)
    presupuesto = total_mib * asig_modo["gpu"] / 100.0
    comprometida = float(comprometida_mib or 0)
    supuesta = necesaria_mib is None
    if supuesta:
        necesaria = max(0.0, (total_mib - comprometida) * 0.25)
    else:
        necesaria = float(necesaria_mib)
    if comprometida + necesaria <= presupuesto:
        return {"ok": True, "gobernada": True, "necesidad_mib": necesaria,
                "supuesta": supuesta,
                "motivo": "cabe en el presupuesto de GPU del modo"}
    return {"ok": False, "gobernada": True, "necesidad_mib": necesaria,
            "supuesta": supuesta,
            "motivo": (f"VRAM comprometida {comprometida:.0f} MiB + "
                       f"necesidad {necesaria:.0f} MiB > presupuesto "
                       f"{presupuesto:.0f} MiB ({asig_modo['gpu']} %)")}


def sobre_presupuesto(agreg, specs, asig_modo):
    """¿El uso agregado de AMBOS carriles supera el presupuesto del modo?
    (gobierno por medición de CPU y RAM)."""
    salida = {"cpu": False, "ram": False}
    if agreg.get("cpu_pct") is not None:
        salida["cpu"] = agreg["cpu_pct"] > asig_modo["cpu"]
    ram_total = specs.get("ram_total")
    if ram_total and agreg.get("rss"):
        salida["ram"] = agreg["rss"] > ram_total * asig_modo["ram"] / 100.0
    return salida


# ---------------------------------------------------------------------------
# recursos-estado.json: una sección por carril, reparto sobre la suma
# ---------------------------------------------------------------------------

def escribir_seccion_estado(base_dir, carril, seccion, reloj=None):
    """Cada proceso escribe SOLO su sección del estado compartido."""
    nombre = "recursos-estado.json"
    with _bloqueo(_ruta(base_dir, nombre).with_suffix(".lock")):
        datos = _leer_json(base_dir, nombre) or {
            "version": VERSION, "revision": 0, "carriles": {}}
        datos.setdefault("carriles", {})[carril] = seccion
        datos["revision"] = int(datos.get("revision") or 0) + 1
        _guardar_json(base_dir, nombre, datos)
        return datos


def leer_estado(base_dir):
    datos = _leer_json(base_dir, "recursos-estado.json")
    if datos and isinstance(datos.get("carriles"), dict):
        return datos
    return {"version": VERSION, "revision": 0, "carriles": {}}


def agregado(estado):
    """Suma de las secciones de ambos carriles: el reparto y el gobierno
    se calculan sobre este total, no sobre la foto de un solo carril."""
    total = {"n_tareas": 0, "cpu_pct": 0.0, "rss": 0, "vram_mib": 0.0,
             "por_cuenta": {}}
    for seccion in (estado.get("carriles") or {}).values():
        if not isinstance(seccion, dict):
            continue
        for tid, t in (seccion.get("tareas") or {}).items():
            if not isinstance(t, dict):
                continue
            total["n_tareas"] += 1
            total["cpu_pct"] += float(t.get("cpu_pct") or 0)
            total["rss"] += int(t.get("rss") or 0)
            total["vram_mib"] += float(t.get("vram_mib") or 0)
            cuenta = t.get("cuenta") or "—"
            pc = total["por_cuenta"].setdefault(
                cuenta, {"tareas": 0, "cpu_pct": 0.0, "rss": 0,
                         "vram_mib": 0.0})
            pc["tareas"] += 1
            pc["cpu_pct"] += float(t.get("cpu_pct") or 0)
            pc["rss"] += int(t.get("rss") or 0)
            pc["vram_mib"] += float(t.get("vram_mib") or 0)
    return total


# ---------------------------------------------------------------------------
# Sonda real de systemd (sin sonda verde no se promete el tope)
# ---------------------------------------------------------------------------

def sonda_systemd(ejecutar=None):
    """True solo si ``systemd-run --user --scope`` funciona de verdad en
    esta máquina. En cualquier otro caso, False (y el gobernador cae a
    nice + medición, declarándolo en el estado)."""
    if os.name == "nt" or platform.system() != "Linux":
        return False
    if not shutil.which("systemd-run"):
        return False
    correr = ejecutar or (lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, timeout=15))
    try:
        salida = correr(["systemd-run", "--user", "--scope", "-p",
                         "CPUQuota=50%", "--", "/bin/true"])
        return getattr(salida, "returncode", 1) == 0
    except Exception:
        return False

"""Rendimiento de la oficina (t-oficina-rendimiento-050, spec 17 de 18): presupuestos como topes en codigo,
escalera de degradacion de 6 niveles con histeresis, regla de oro de la VRAM, modo dormida, modo ahorro,
modo cerrado, FPS 30/15/0 y metricas en vivo. La oficina CEDE: nunca apaga el Bridge, el runner ni
llama-server, nunca escribe en la cola, nunca gasta ni descarga.

Motor fijado en el spec 6: Godot 4.7.2 (este prototipo: Pygame-ce). Los topes Tauri no aplican (anotado).
"""
import json
import subprocess
import threading
import time
from datetime import datetime

# ---- presupuestos (topes; superarlos es un bug: se registra y se degrada)
VRAM_NORMAL_MB, VRAM_PICO_MB = 128, 256
RAM_MB = {"reposo": 350, "trabajando": 450, "dormida": 150, "minimizada": 50}
RAM_TOPE_DURO_MB = 500
CPU_REPOSO_PCT_NUCLEO, CPU_TRABAJANDO_PCT_TOTAL, CPU_PICO_PCT = 2.0, 5.0, 10.0
ASSETS_MAX_MB, INSTALADO_MAX_MB, DATOS_MAX_MB, INSTALADOR_MAX_MB = 100, 150, 50, 50
SPRITE_MAX_PX = 512
TAURI_NO_APLICA = "Topes Tauri (RAM <=150 MB, tope 250 MB) no aplican: el spec 6 eligio Godot (prototipo Pygame-ce)."

NIVELES = {0: ("Normal", (52, 199, 89)), 1: ("Ahorro de FPS", (255, 204, 0)), 2: ("Sin vagancia", (255, 204, 0)),
           3: ("Solo estados", (255, 149, 0)), 4: ("Dormida", (142, 142, 147)), 5: ("Cerrada", (142, 142, 147))}
HISTERESIS_S = 30.0
SIN_MIRAR_S = 300.0
NOCHE = (23, 7)  # 23:00-07:00 (configurable)
NUNCA = ("apagar el Bridge", "apagar el runner", "matar llama-server", "borrar la cola", "escribir en la cola",
         "gastar dinero", "descargar nada")


def nivel_objetivo(s):
    """s: {ram_pct, vram_libre_mb, runner_cpu_alto, sin_mirar_s, usuario_dormir, usuario_cerrar, noche, cerrar_noche,
    ram_oficina_mb}. -> (nivel, motivo). Gana el nivel mas alto que casa."""
    ram, vl = s.get("ram_pct"), s.get("vram_libre_mb")
    cand = [(0, "todo en verde")]
    if s.get("usuario_cerrar") or (ram is not None and ram > 93) or (s.get("noche") and s.get("cerrar_noche")):
        cand.append((5, "RAM > 93 %" if ram and ram > 93 else "lo pide el usuario" if s.get("usuario_cerrar") else "horario nocturno"))
    if (ram is not None and ram > 90) or (vl is not None and vl < 200) or s.get("usuario_dormir") \
            or (s.get("sin_mirar_s") or 0) >= SIN_MIRAR_S or s.get("noche"):
        m = ("RAM > 90 %" if ram and ram > 90 else f"VRAM libre {vl:.0f} MB < 200" if vl is not None and vl < 200
             else "lo pide el usuario" if s.get("usuario_dormir") else "de noche" if s.get("noche") else "5 min sin mirar")
        cand.append((4, m))
    if (ram is not None and ram > 85) or (vl is not None and vl < 300):
        cand.append((3, "RAM > 85 %" if ram and ram > 85 else f"VRAM libre {vl:.0f} MB < 300"))
    if (ram is not None and ram > 80) or (vl is not None and vl < 400):
        cand.append((2, "RAM > 80 %" if ram and ram > 80 else f"VRAM libre {vl:.0f} MB < 400"))
    if (ram is not None and ram > 75) or (vl is not None and vl < 500) or s.get("runner_cpu_alto"):
        cand.append((1, "RAM > 75 %" if ram and ram > 75 else f"VRAM libre {vl:.0f} MB < 500" if vl is not None and vl < 500
                     else "CPU del runner alta"))
    if (s.get("ram_oficina_mb") or 0) > RAM_TOPE_DURO_MB:
        cand.append((3, f"la oficina usa {s['ram_oficina_mb']:.0f} MB > tope duro {RAM_TOPE_DURO_MB} (bug)"))
    return max(cand)


class Escalera:
    """Sube al instante (sin preguntar); baja de UNO en uno tras 30 s seguidos con el objetivo por debajo."""

    def __init__(self, registro=None):
        self.nivel = 0
        self.ahorro = False  # manual y persistente: minimo nivel 2 hasta que el usuario lo quite
        self.verde_desde = None
        self.registro = registro or (lambda d: None)
        self.cambios = []

    def efectivo(self):
        return max(self.nivel, 2 if self.ahorro and self.nivel < 4 else 0)

    def paso(self, sensores, ahora):
        obj, motivo = nivel_objetivo(sensores)
        antes = self.nivel
        if obj > self.nivel:
            self.nivel, self.verde_desde = obj, None
        elif obj < self.nivel:
            if self.verde_desde is None:
                self.verde_desde = ahora
            elif ahora - self.verde_desde >= HISTERESIS_S:
                self.nivel -= 1
                self.verde_desde = ahora
                motivo = f"recursos recuperados ({motivo}); baja un nivel tras {HISTERESIS_S:.0f} s en verde"
        else:
            self.verde_desde = None
        if self.nivel != antes:
            d = {"hora": datetime.fromtimestamp(ahora).isoformat(timespec="seconds"), "de": antes, "a": self.nivel,
                 "motivo": motivo}
            self.cambios.append(d)
            self.registro({"evento": "nivel", **d})
        return self.efectivo()


def _despertar(self, sensores, ahora, por="el usuario"):
    """Despertar NO espera la histeresis: un clic del usuario (o un evento importante) baja YA al nivel que
    dicen los recursos, si es menor que 4. Si los recursos siguen mal (VRAM/RAM), sigue dormida."""
    obj, motivo = nivel_objetivo(dict(sensores, usuario_dormir=False, sin_mirar_s=0))
    if self.nivel >= 4 and obj < 4:
        d = {"hora": datetime.fromtimestamp(ahora).isoformat(timespec="seconds"), "de": self.nivel, "a": obj,
             "motivo": f"despierta por {por} ({motivo})"}
        self.nivel, self.verde_desde = obj, None
        self.cambios.append(d)
        self.registro({"evento": "nivel", **d})
        return True
    return False


Escalera.despertar = _despertar


def fps(nivel, foco, minimizada):
    """30 con foco, 15 sin foco, 0 minimizada; nivel >= 1 -> 15; nivel >= 4 -> 0."""
    if minimizada or nivel >= 4:
        return 0
    if nivel >= 1 or not foco:
        return 15
    return 30


def color(nivel):
    return NIVELES[nivel][1]


def es_noche(hora, rango=NOCHE):
    a, b = rango
    return hora >= a or hora < b


class Sensores:
    """Lee RAM del sistema (psutil), VRAM libre (nvidia-smi) y VRAM propia (contador de Windows) en un hilo cada
    `cada_s`; el render solo mira `ultimo`. Nunca bloquea un fotograma."""

    def __init__(self, pid, cada_s=1.0):
        self.pid, self.cada = pid, cada_s
        self.ultimo = {}
        self.parar = threading.Event()
        self._vram_propia_t = 0

    def arrancar(self):
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        try:
            import psutil
            pr = psutil.Process(self.pid)
            pr.cpu_percent()
        except Exception:
            psutil, pr = None, None
        while not self.parar.is_set():
            d = {"t": time.time()}
            if psutil:
                vm = psutil.virtual_memory()
                d["ram_pct"] = vm.percent
                try:
                    d["ram_oficina_mb"] = pr.memory_info().rss / 2 ** 20
                    d["cpu_oficina_pct_nucleo"] = pr.cpu_percent()
                except Exception:
                    pass
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=3,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
                usado, total = (float(x) for x in out.strip().splitlines()[0].split(","))
                d["vram_usada_mb"], d["vram_libre_mb"], d["vram_total_mb"] = usado, total - usado, total
            except Exception:
                d["vram_libre_mb"] = None  # sin dato: no se degrada por VRAM (no se inventa)
            if time.time() - self._vram_propia_t > 5:  # contador caro: cada 5 s
                self._vram_propia_t = time.time()
                d["vram_oficina_mb"] = vram_propia(self.pid)
            else:
                d["vram_oficina_mb"] = self.ultimo.get("vram_oficina_mb")
            self.ultimo = d
            self.parar.wait(self.cada)


def vram_propia(pid):
    """VRAM dedicada del proceso (contador «GPU Process Memory(pid_*)\\Dedicated Usage», el del Administrador de
    tareas, el mismo del spec 1). None si no se puede leer; 0.0 si el proceso no tiene memoria de GPU."""
    ps = ("$c = Get-Counter -ErrorAction SilentlyContinue -Counter '\\GPU Process Memory(pid_%d*)\\Dedicated Usage'; "
          "if ($c) { ($c.CounterSamples | Measure-Object CookedValue -Sum).Sum } else { 'NADA' }" % pid)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=8,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
        if out == "NADA" or not out:
            return 0.0
        return float(out.replace(",", ".")) / 2 ** 20
    except Exception:
        return None


def metricas_texto(m, nivel, fps_actual, llama):
    def f(v, suf, nd=0):
        return "—" if v is None else f"{v:.{nd}f}{suf}"
    return (f"{fps_actual:.0f} FPS · RAM {f(m.get('ram_oficina_mb'), ' MB')} · VRAM oficina {f(m.get('vram_oficina_mb'), ' MB', 1)}"
            f" · VRAM libre {f(m.get('vram_libre_mb'), ' MB')} · CPU {f(m.get('cpu_oficina_pct_nucleo'), ' %', 1)}"
            f" · nivel {nivel} ({NIVELES[nivel][0]}) · llama: {llama}")


def resumen_json(m, nivel):
    return json.dumps({"nivel": nivel, **{k: m.get(k) for k in ("ram_pct", "ram_oficina_mb", "vram_libre_mb",
                                                               "vram_oficina_mb", "cpu_oficina_pct_nucleo")}})

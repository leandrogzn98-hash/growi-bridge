"""Mediciones C1-C3 de la oficina 0.5.0 (t-oficina-mediciones-050) en el PC real. Nada se inventa: cada cifra sale de
nvidia-smi, de los contadores de GPU de Windows (los del Administrador de tareas), de psutil o de la propia escena.

Pasos:
  1. Topes del PC: RAM total, adaptadores (¿GPU integrada?), WebView2, nvidia-smi.
  2. Arranca llama-server con Hermes 3 8B (el exe y el .gguf de la app instalada, SOLO leídos; puerto 8091, log aquí).
  3. Para Godot (export real) y para Pygame-ce: VRAM total antes, durante y después; VRAM y RAM del proceso cada
     segundo; reposo, animando, y animando con llama-server generando (contención); qué adaptador usa; FPS y tirones.
  4. Claude Code y el Bridge: memoria de sus procesos (el máximo visto durante toda la corrida).
  5. Para llama-server. Deja todo en _corridas/<fecha>/ y el resumen en pruebas/evidencia/oficina-mediciones/.

  python medir.py --app C:/ruta/a/growi-bridge     (por defecto ~/growi-bridge)
"""

import argparse
import csv
import ctypes
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
SIN_VENTANA = 0x08000000  # CREATE_NO_WINDOW: ninguna consola a la vista
PUERTO_LLAMA = 8091


def sh(cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=SIN_VENTANA,
                       encoding="utf-8", errors="replace")
    return r.stdout.strip()


def nvsmi():
    q = "memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,clocks.sm,clocks_event_reasons.active"
    v = sh(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"]).split(", ")
    return {"total_mib": int(v[0]), "usado_mib": int(v[1]), "libre_mib": int(v[2]), "temp_c": int(v[3]),
            "util_pct": int(v[4]), "sm_mhz": int(v[5]), "razones": v[6]}


def ps(script):
    return sh(["powershell", "-NoProfile", "-Command", script], timeout=120)


def topes(app):
    t = {}
    vm = psutil.virtual_memory()
    t["ram_total_gib"] = round(vm.total / 2**30, 2)
    t["ram_total_cim_bytes"] = ps("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
    t["adaptadores"] = json.loads(ps("Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,"
                                     "AdapterRAM,VideoProcessor | ConvertTo-Json"))
    t["nvidia_smi"] = sh(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,pstate", "--format=csv"])
    wv = {}
    for raiz in (r"HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients", r"HKCU:\Software\Microsoft\EdgeUpdate\Clients"):
        v = ps(f"(Get-ItemProperty '{raiz}\\{{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}}' -ErrorAction SilentlyContinue).pv")
        wv[raiz] = v or None
    t["webview2"] = wv
    t["cpu"] = ps("(Get-CimInstance Win32_Processor).Name")
    t["llama_server"] = str(app / "llama" / "llama-server.exe")
    return t


class Muestreo:
    """Contadores de GPU por proceso (typeperf, nombres en inglés) en segundo plano."""

    def __init__(self, pid, segundos, csv_ruta):
        cont = [f"\\GPU Process Memory(pid_{pid}_*)\\Dedicated Usage", f"\\GPU Process Memory(pid_{pid}_*)\\Shared Usage",
                f"\\GPU Engine(pid_{pid}_*engtype_3D)\\Utilization Percentage"]
        self.ruta = csv_ruta
        self.p = subprocess.Popen(["typeperf", *cont, "-si", "1", "-sc", str(segundos), "-f", "CSV", "-o",
                                   str(csv_ruta), "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  creationflags=SIN_VENTANA)

    def leer(self):
        self.p.wait(timeout=60)
        if not Path(self.ruta).exists():  # typeperf no escribe nada si el proceso no tiene ninguna instancia de GPU
            return {"dedicada_mib_por_luid": {}, "compartida_mib": [], "util_3d_por_luid": {},
                    "sin_instancias_gpu": True}
        filas = list(csv.reader(open(self.ruta, encoding="utf-8", errors="replace")))
        cab, datos = filas[0], filas[1:]
        out = {"dedicada_mib_por_luid": {}, "compartida_mib": [], "util_3d_por_luid": {}}
        for j, nombre in enumerate(cab[1:], 1):
            luid = nombre.split("luid_")[1].split("_phys")[0] if "luid_" in nombre else "?"
            serie = []
            for f in datos:
                try:
                    serie.append(float(f[j]))
                except (ValueError, IndexError):
                    pass
            if "Dedicated Usage" in nombre:
                out["dedicada_mib_por_luid"].setdefault(luid, []).append([round(x / 2**20, 1) for x in serie])
            elif "Shared Usage" in nombre:
                out["compartida_mib"].append([round(x / 2**20, 1) for x in serie])
            else:
                out["util_3d_por_luid"].setdefault(luid, []).append(serie)
        # varias instancias por luid: se suman por segundo
        for k in ("dedicada_mib_por_luid", "util_3d_por_luid"):
            for luid, series in out[k].items():
                n = min(map(len, series)) if series else 0
                out[k][luid] = [round(sum(s[i] for s in series), 1) for i in range(n)]
        return out


def adaptadores_luid():
    """{luid: MiB dedicados usados} de cada adaptador (para saber cuál es la NVIDIA)."""
    r = sh(["typeperf", "\\GPU Adapter Memory(*)\\Dedicated Usage", "-sc", "1"])
    lineas = [x for x in r.splitlines() if x.startswith('"')]
    cab, val = next(csv.reader([lineas[0]])), next(csv.reader([lineas[1]]))
    return {c.split("luid_")[1].split("_phys")[0]: round(float(v) / 2**20, 1)
            for c, v in zip(cab[1:], val[1:]) if "luid_" in c}


def procesos_vigilados():
    """Memoria de Claude Code y del Bridge ahora (MiB de RSS y USS, por grupo)."""
    g = {"claude_code": [0.0, 0.0, 0], "bridge": [0.0, 0.0, 0]}
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            nom, cmd = (p.info["name"] or "").lower(), " ".join(p.info["cmdline"] or []).lower()
            k = "claude_code" if (nom.startswith("claude") or ("node" in nom and "claude" in cmd)) else \
                "bridge" if "growi-bridge.py" in cmd else None
            if k:
                mi = p.memory_full_info()
                g[k][0] += mi.rss / 2**20
                g[k][1] += mi.uss / 2**20
                g[k][2] += 1
        except (psutil.Error, OSError):
            pass
    return {k: {"rss_mib": round(v[0], 1), "uss_mib": round(v[1], 1), "procesos": v[2]} for k, v in g.items()}


def ventanas_de(pid):
    """Rectángulos de las ventanas visibles del proceso (para comprobar que están fuera de pantalla)."""
    from ctypes import wintypes
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _l):
        p = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and ctypes.windll.user32.IsWindowVisible(h):
            r = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
            out.append([r.left, r.top, r.right, r.bottom])
        return True
    ctypes.windll.user32.EnumWindows(cb, 0)
    return out


def foco():
    return ctypes.windll.user32.GetForegroundWindow()


class Generador:
    """Mantiene a llama-server generando (contención de GPU) mientras está activo."""

    def __init__(self):
        self.activo, self.tokens, self.peticiones, self.errores = False, 0, 0, 0
        threading.Thread(target=self._bucle, daemon=True).start()

    def _bucle(self):
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while True:
            if not self.activo:
                time.sleep(0.2)
                continue
            body = json.dumps({"prompt": "Escribe una historia larga sobre una oficina de agentes.",
                               "n_predict": 256, "cache_prompt": False}).encode()
            try:
                r = op.open(urllib.request.Request(f"http://127.0.0.1:{PUERTO_LLAMA}/completion", data=body,
                                                   headers={"Content-Type": "application/json"}), timeout=120)
                self.tokens += json.loads(r.read()).get("tokens_predicted", 0)
                self.peticiones += 1
            except Exception:  # noqa: BLE001 - se cuenta, no se oculta
                self.errores += 1
                time.sleep(1)


def medir_motor(nombre, cmd, cwd, dirc, gen, vigilados, reposo=20, total=80, carga=(50, 75)):
    salida = dirc / f"{nombre}.jsonl"
    antes = nvsmi()
    f0 = foco()
    p = subprocess.Popen([*cmd, f"--salida={salida}", f"--reposo={reposo}", f"--total={total}"], cwd=cwd,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    proc = psutil.Process(p.pid)
    hijos = proc.children(recursive=True)  # el pythonw.exe de un venv es un lanzador: el intérprete real es su hijo
    if hijos:
        proc = hijos[0]
    ventanas = ventanas_de(proc.pid)
    cabecera = (sh(["typeperf", r"\GPU Process Memory(*)\Dedicated Usage", "-sc", "1"]).splitlines() or [""])[0]
    instancias = [c for c in cabecera.split('","') if f"pid_{proc.pid}_" in c]
    mu = Muestreo(proc.pid, total - 4, dirc / f"{nombre}-gpu.csv")
    filas, t0 = [], time.time()
    proc.cpu_percent()
    while p.poll() is None:
        t = time.time() - t0 + 2
        gen.activo = carga[0] <= t < carga[1]
        try:
            mi = proc.memory_full_info()
            fila = {"t": round(t, 1), "rss_mib": round(mi.rss / 2**20, 1), "uss_mib": round(mi.uss / 2**20, 1),
                    "cpu_pct": proc.cpu_percent(), "gen": gen.activo, **{f"gpu_{k}": v for k, v in nvsmi().items()}}
        except psutil.Error:
            break
        filas.append(fila)
        for k, v in procesos_vigilados().items():
            vigilados[k] = max(vigilados[k], v, key=lambda x: x["rss_mib"])
        time.sleep(1)
    gen.activo = False
    p.wait(timeout=30)
    f1 = foco()
    time.sleep(5)
    despues = nvsmi()
    gpu = mu.leer()
    escena = [json.loads(x) for x in salida.read_text(encoding="utf-8").splitlines()] if salida.exists() else []
    with open(dirc / f"{nombre}-muestras.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    return {"antes": antes, "despues": despues, "muestras": filas, "gpu_proceso": gpu, "escena": escena,
            "foco_cambio": f0 != f1, "codigo_salida": p.returncode, "pid_medido": proc.pid,
            "lanzador": proc.pid != p.pid, "ventanas_visibles": ventanas, "instancias_gpu_del_pid": instancias}


def resumir(r, luid_nvidia):
    fases = {"reposo": lambda f: f["t"] < 20, "animando": lambda f: 22 <= f["t"] < 48,
             "animando_con_llama": lambda f: f["gen"]}
    out = {}
    for fase, sel in fases.items():
        m = [f for f in r["muestras"] if sel(f)]
        if not m:
            continue
        out[fase] = {"ram_rss_mib_max": max(x["rss_mib"] for x in m), "ram_uss_mib_max": max(x["uss_mib"] for x in m),
                     "ram_rss_mib_media": round(statistics.mean(x["rss_mib"] for x in m), 1),
                     "cpu_pct_media": round(statistics.mean(x["cpu_pct"] for x in m), 1),
                     "vram_total_mib_max": max(x["gpu_usado_mib"] for x in m),
                     "gpu_util_pct_media": round(statistics.mean(x["gpu_util_pct"] for x in m), 1),
                     "temp_c_max": max(x["gpu_temp_c"] for x in m),
                     "razones_reloj": sorted({x["gpu_razones"] for x in m})}
    esc = [e for e in r["escena"] if "t" in e]
    for fase, sel in (("reposo", lambda e: e["t"] < 20), ("animando", lambda e: 22 <= e["t"] < 48),
                      ("animando_con_llama", lambda e: 50 <= e["t"] < 75)):
        e = [x for x in esc if sel(x)]
        if e and fase in out:
            out[fase].update(fps_medio=round(statistics.mean(x["fps"] for x in e), 1),
                             fps_min=min(x["fps"] for x in e), peor_frame_ms=max(x["peor_ms"] for x in e),
                             frames_lentos_50ms=sum(x["lentos"] for x in e))
    ded = r["gpu_proceso"]["dedicada_mib_por_luid"]
    out["vram_proceso_mib_max_por_luid"] = {k: max(v) if v else None for k, v in ded.items()}
    out["vram_proceso_nvidia_mib_max"] = max(ded.get(luid_nvidia) or [0]) if luid_nvidia else None
    util = r["gpu_proceso"]["util_3d_por_luid"]
    out["util_3d_media_por_luid"] = {k: round(statistics.mean(v), 2) if v else None for k, v in util.items()}
    out["compartida_mib_max"] = max((max(s) for s in r["gpu_proceso"]["compartida_mib"] if s), default=None)
    out["vram_total_antes_mib"] = r["antes"]["usado_mib"]
    out["vram_total_despues_mib"] = r["despues"]["usado_mib"]
    out["inicio"] = next((e for e in r["escena"] if e.get("evento") == "inicio"), None)
    out["foco_cambio"] = r["foco_cambio"]
    out["ventanas_visibles"] = r["ventanas_visibles"]
    out["pid_medido_es_hijo_del_lanzador"] = r["lanzador"]
    out["instancias_gpu_del_pid"] = r["instancias_gpu_del_pid"]
    out["sin_instancias_gpu"] = bool(r["gpu_proceso"].get("sin_instancias_gpu"))
    out["codigo_salida"] = r["codigo_salida"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=os.path.expanduser("~/growi-bridge"))
    a = ap.parse_args()
    app = Path(a.app)
    dirc = AQUI / "_corridas" / datetime.now().strftime("%Y%m%d-%H%M%S")
    dirc.mkdir(parents=True)
    res = {"fecha": datetime.now().astimezone().isoformat(timespec="seconds"), "topes": topes(app)}
    res["luid_antes"] = adaptadores_luid()
    res["vram_sin_nada"] = nvsmi()
    vig = {k: {"rss_mib": 0} for k in ("claude_code", "bridge")}
    # llama-server con Hermes 3 8B (exe y .gguf de la app instalada, solo leídos)
    log = open(dirc / "llama-server.log", "w", encoding="utf-8")
    llama = subprocess.Popen([str(app / "llama" / "llama-server.exe"), "-m", str(app / "models" / "hermes-3-8b-q4_k_m.gguf"),
                              "-c", "8192", "-ngl", "99", "-np", "1", "--host", "127.0.0.1", "--port", str(PUERTO_LLAMA)],
                             cwd=str(app / "llama"), stdout=log, stderr=subprocess.STDOUT, creationflags=SIN_VENTANA)
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(240):
            try:
                if op.open(f"http://127.0.0.1:{PUERTO_LLAMA}/health", timeout=2).status == 200:
                    break
            except Exception:  # noqa: BLE001 - todavía cargando
                time.sleep(1)
        else:
            raise SystemExit("llama-server no respondió /health en 240 s")
        time.sleep(3)
        res["vram_llama_cargado"] = nvsmi()
        res["luid_llama"] = adaptadores_luid()
        delta = {k: res["luid_llama"].get(k, 0) - res["luid_antes"].get(k, 0) for k in res["luid_llama"]}
        luid_nvidia = max(delta, key=delta.get)
        res["luid_nvidia"] = luid_nvidia
        res["llama_rss_mib"] = round(psutil.Process(llama.pid).memory_info().rss / 2**20, 1)
        gen = Generador()
        bin_ = AQUI / "_bin"
        res["godot"] = medir_motor("godot", [str(bin_ / "oficina-godot" / "oficina.exe"), "--"], str(bin_ / "oficina-godot"),
                                   dirc, gen, vig)
        res["pygame"] = medir_motor("pygame", [str(AQUI / ".venv" / "Scripts" / "pythonw.exe"),
                                               str(AQUI / "pygame_escena.py")], str(AQUI), dirc, gen, vig)
        res["generacion"] = {"peticiones": gen.peticiones, "tokens": gen.tokens, "errores": gen.errores}
        res["vigilados_max"] = vig
        res["vram_final_con_llama"] = nvsmi()
    finally:
        llama.terminate()
        llama.wait(timeout=30)
        log.close()
    time.sleep(3)
    res["vram_tras_parar_llama"] = nvsmi()
    res["resumen"] = {m: resumir(res[m], res.get("luid_nvidia")) for m in ("godot", "pygame") if m in res}
    (dirc / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    ev = REPO / "pruebas" / "evidencia" / "oficina-mediciones"
    ev.mkdir(parents=True, exist_ok=True)
    corto = {k: v for k, v in res.items() if k not in ("godot", "pygame")}
    corto["corrida"] = dirc.name
    (ev / "resumen.json").write_text(json.dumps(corto, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in dirc.iterdir():
        if f.suffix in (".csv", ".jsonl") or f.name == "llama-server.log":
            shutil.copy(f, ev / f.name)
    print(json.dumps(res["resumen"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())

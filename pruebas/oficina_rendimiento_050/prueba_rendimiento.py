"""Prueba de t-oficina-rendimiento-050. Logica de la escalera (b, e) y corridas reales del prototipo con un
Bridge falso: niveles forzados con sensores simulados e histeresis (b), dormida y despertar medido (d), cerrada
y reapertura (f), minimizada (7), presupuestos medidos (a), metricas contra psutil / nvidia-smi (g) y la lista
§8.5 buscada en el codigo (h). La cesion ante un modelo real que carga se prueba en ceder_vram.py."""
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "oficina" / "rendimiento"))
import rendimiento as RD  # noqa: E402

EV = R / "pruebas" / "evidencia" / "oficina-rendimiento-050"
EV.mkdir(parents=True, exist_ok=True)
OUT = {}

# ---- (b, e) logica: cada nivel con su disparador, histeresis de 30 s, registro, color; modo ahorro persistente
casos = {0: {"ram_pct": 50, "vram_libre_mb": 3000}, 1: {"ram_pct": 77, "vram_libre_mb": 3000},
         2: {"ram_pct": 50, "vram_libre_mb": 350}, 3: {"ram_pct": 86, "vram_libre_mb": 3000},
         4: {"ram_pct": 50, "vram_libre_mb": 150}, 5: {"ram_pct": 95, "vram_libre_mb": 3000}}
OUT["b_niveles"] = {n: RD.nivel_objetivo(s) for n, s in casos.items()}
OUT["b_disparadores_dormida"] = {k: RD.nivel_objetivo(dict(casos[0], **v))[0] for k, v in
                                 {"ram>90": {"ram_pct": 91}, "vram<200": {"vram_libre_mb": 190}, "5min": {"sin_mirar_s": 301},
                                  "usuario": {"usuario_dormir": True}, "noche": {"noche": True}}.items()}
reg = []
esc = RD.Escalera(registro=reg.append)
T0 = 1793400000.0  # base real: en Windows, timestamp() cerca de 1970 falla
t = 0.0
traza = []
for seg, s in ((0, casos[0]), (5, casos[4]), (10, casos[0])):
    pass
for k in range(0, 200):
    s = casos[4] if 5 <= k < 10 else casos[0]
    traza.append((k, esc.paso(s, T0 + k)))
bajadas = [c for c in esc.cambios if c["a"] < c["de"]]
OUT["b_histeresis"] = {"cambios": esc.cambios, "segundos_entre_bajadas": [round(datetime.fromisoformat(bajadas[i + 1]["hora"]).timestamp()
                       - datetime.fromisoformat(bajadas[i]["hora"]).timestamp()) for i in range(len(bajadas) - 1)],
                       "colores": {n: RD.color(n) for n in range(6)},
                       "ok": [c["a"] for c in esc.cambios] == [4, 3, 2, 1, 0] and all(r.get("motivo") for r in reg)}
OUT["b_ok"] = [OUT["b_niveles"][n][0] for n in range(6)] == list(range(6)) and set(OUT["b_disparadores_dormida"].values()) == {4}
e2 = RD.Escalera()
e2.ahorro = True
ef = [e2.paso(casos[0], T0 + k) for k in range(100)]
e2.ahorro = False
OUT["e_ahorro"] = {"con_ahorro_en_verde_100s": sorted(set(ef)), "al_quitarlo": e2.paso(casos[0], T0 + 101),
                   "fps_nivel_2": RD.fps(2, True, False), "ok": set(ef) == {2} and e2.paso(casos[0], T0 + 102) == 0}
OUT["fps"] = {"foco": RD.fps(0, True, False), "sin_foco": RD.fps(0, False, False), "minimizada": RD.fps(0, True, True),
              "nivel1": RD.fps(1, True, False), "dormida": RD.fps(4, True, False)}

# ---- prototipo real con un Bridge falso
PROTO = R / "oficina" / "protocolo" / "oficina_proto.py"
PYG = Path(r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Lib\site-packages")
APPDIR = Path(os.environ["USERPROFILE"]) / "growi-bridge" / "_prueba-oficina-protocolo" / "app"
BASE = Path(os.environ["USERPROFILE"]) / "growi-bridge" / "_prueba-rendimiento-050"
TIT = "Oficina Growi — prototipo de protocolo (Pygame-ce)"
u32 = ctypes.windll.user32


def iso(t):
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


class BridgeFalso:
    def __init__(self, nombre):
        self.base = BASE / nombre
        shutil.rmtree(self.base, ignore_errors=True)
        self.out = self.base / "share" / "outbox"
        (self.out / "runner-results").mkdir(parents=True)
        self.sens = self.base / "sensores.json"
        self.stop = threading.Event()
        threading.Thread(target=self._bucle, daemon=True).start()

    def escribir(self, n, d):
        tmp = self.out / (n + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        for i in range(6):
            try:
                os.replace(tmp, self.out / n)
                return
            except PermissionError:
                time.sleep(0.05)

    def _bucle(self):
        while not self.stop.is_set():
            a = time.time()
            self.escribir("cola-live.json", {"actualizado": iso(a), "guardrail": "siempre", "tareas": [
                {"id": "t-r", "estado": "en_curso", "motor": "claude", "modelo": "sonnet", "creado_en": iso(a - 60),
                 "actualizado_en": iso(a - 50)}]})
            self.escribir("runner-live.json", {"task_id": "t-r", "estado": "en curso", "lanzado_at": iso(a - 50),
                                               "started_at": iso(a - 52), "actualizado": iso(a)})
            self.escribir("runner-status.json", {"alive": True, "last_poll": iso(a), "current": {"id": "t-r"}})
            self.escribir("bridge-latido.json", {"pid": os.getpid(), "t": a, "cerrar": False})
            time.sleep(1)

    def sensores(self, **kw):
        self.sens.write_text(json.dumps(kw), encoding="utf-8")

    def oficina(self, extra=(), salir=60):
        env = dict(os.environ, PYTHONPATH=str(PYG), PYTHONIOENCODING="utf-8")
        cmd = [sys.executable, str(PROTO), "--share", str(self.base / "share"), "--app", str(APPDIR), "--bridge-pid",
               str(os.getpid()), "--datos", str(self.base / "datos"), "--mutex", f"Local\\GrowiRend{self.base.name}",
               "--sin-noche", "--sensores-falsos", str(self.sens), "--salir-a", str(salir), *extra]
        return subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def metricas(self):
        f = []
        for m in (self.base / "datos").glob("metricas-*.jsonl"):
            f += [json.loads(x) for x in m.read_text(encoding="utf-8").splitlines() if x.strip()]
        return sorted(f, key=lambda d: d["t"])


def medir(pid, n=5):
    p = psutil.Process(pid)
    p.cpu_percent()
    rss, cpu = [], []
    for _ in range(n):
        time.sleep(1)
        rss.append(p.memory_info().rss / 2 ** 20)
        cpu.append(p.cpu_percent())
    return {"rss_mb": round(max(rss), 1), "cpu_pct_nucleo": round(sum(cpu) / len(cpu), 2),
            "vram_mb": RD.vram_propia(pid)}


def esperar_ventana(tope=20):
    t0 = time.time()
    while time.time() - t0 < tope:
        h = u32.FindWindowW(None, TIT)
        if h:
            return h
        time.sleep(0.2)
    return None


# Corrida A: niveles forzados 0 -> 2 -> 3 -> 4, y bajada con histeresis; medidas de RAM/CPU/VRAM por modo
A = BridgeFalso("A")
A.sensores(ram_pct=50, vram_libre_mb=3000)
of = A.oficina(salir=70)
esperar_ventana()
time.sleep(4)
med = {"trabajando_nivel0": medir(of.pid)}
A.sensores(ram_pct=50, vram_libre_mb=450)
time.sleep(3)
A.sensores(ram_pct=50, vram_libre_mb=350)
time.sleep(3)
A.sensores(ram_pct=50, vram_libre_mb=250)
time.sleep(4)
med["solo_estados_nivel3"] = medir(of.pid, 3)
A.sensores(ram_pct=50, vram_libre_mb=150)
time.sleep(3)
med["dormida_nivel4"] = medir(of.pid)
A.sensores(ram_pct=50, vram_libre_mb=3000)
of.wait(timeout=90)
m = A.metricas()
niveles = [x for x in m if x.get("evento") == "nivel"]
fps_por_nivel = {}
for x in m:
    if "fps" in x:
        fps_por_nivel.setdefault(str(max([n["a"] for n in niveles if n["hora"] <= iso(x["t"])] or [0])), []).append(x["fps"])
OUT["A_escalera_real"] = {"cambios": [(n["hora"][11:19], n["de"], n["a"], n["motivo"]) for n in niveles], "medidas": med,
                          "fps_medidos": {k: [min(v), max(v)] for k, v in fps_por_nivel.items()},
                          "ok": [n["a"] for n in niveles][:4] == [1, 2, 3, 4] and any(n["de"] == 4 and n["a"] == 3 for n in niveles)}
A.stop.set()

# Corrida B: dormir con Z y despertar con un clic: ms medidos por la propia oficina
B = BridgeFalso("B")
B.sensores(ram_pct=50, vram_libre_mb=3000)
of = B.oficina(salir=25)
h = esperar_ventana()
time.sleep(4)
u32.PostMessageW(h, 0x0100, 0x5A, 1 | (0x2C << 16))  # Z
u32.PostMessageW(h, 0x0101, 0x5A, 1 | (0x2C << 16) | (3 << 30))
time.sleep(4)
dormida = medir(of.pid, 3)
despertares = []
for k in range(3):
    u32.PostMessageW(h, 0x0200, 0, (300 << 16) | 500)
    u32.PostMessageW(h, 0x0201, 1, (300 << 16) | 500)
    u32.PostMessageW(h, 0x0202, 0, (300 << 16) | 500)
    time.sleep(2)
    u32.PostMessageW(h, 0x0100, 0x5A, 1 | (0x2C << 16))
    u32.PostMessageW(h, 0x0101, 0x5A, 1 | (0x2C << 16) | (3 << 30))
    time.sleep(2)
of.wait(timeout=40)
mb = B.metricas()
desp = [x["ms"] for x in mb if x.get("evento") == "despertar"]
OUT["d_dormida"] = {"ram_dormida": dormida, "despertar_ms": desp, "dormidas": sum(1 for x in mb if x.get("evento") == "dormida"),
                    "ok": bool(desp) and max(desp) < 1000 and dormida["rss_mb"] <= RD.RAM_MB["dormida"]}
B.stop.set()

# Corrida C: cerrada por recursos (RAM 95 %): el proceso termina (codigo 6); al reabrir reconstruye desde los archivos
C = BridgeFalso("C")
C.sensores(ram_pct=95, vram_libre_mb=3000)
of = C.oficina(salir=20)
cod = of.wait(timeout=30)
vivo = psutil.pid_exists(of.pid)
C.sensores(ram_pct=50, vram_libre_mb=3000)
of2 = C.oficina(salir=8)
of2.wait(timeout=30)
mc = C.metricas()
estados = [x["cambios"] for x in mc if x.get("evento") == "estados"]
OUT["f_cerrada"] = {"codigo": cod, "proceso_vivo_tras_cerrar": vivo, "estados_al_reabrir": estados[-1:] if estados else None,
                    "ok": cod == 6 and not vivo and bool(estados)}
C.stop.set()

# Corrida D: minimizada = 0 FPS (sin pintar), el proceso sigue vivo
D = BridgeFalso("D")
D.sensores(ram_pct=50, vram_libre_mb=3000)
of = D.oficina(salir=16)
h = esperar_ventana()
time.sleep(5)
u32.ShowWindow(h, 6)  # SW_MINIMIZE
time.sleep(6)
min_med = medir(of.pid, 3)
of.wait(timeout=30)
md = D.metricas()
fps_seq = [x["fps"] for x in md if "fps" in x]
OUT["fps_minimizada"] = {"fps_por_segundo": fps_seq, "medida_minimizada": min_med,
                         "ok": len(fps_seq) >= 3 and min_med["rss_mb"] <= RD.RAM_MB["reposo"]}
D.stop.set()

# (a) presupuestos de disco y de sprites; (g) metricas contra psutil y nvidia-smi
assets = sum(p.stat().st_size for p in (R / "assets" / "office").rglob("*") if p.is_file()) / 2 ** 20
from PIL import Image  # noqa: E402
grandes = [str(p.relative_to(R)) for p in (R / "assets" / "office").rglob("*.png") if max(Image.open(p).size) > RD.SPRITE_MAX_PX
           and "x4" not in p.name]
codigo_mb = sum(p.stat().st_size for d in ("oficina",) for p in (R / d).rglob("*.py")) / 2 ** 20
OUT["a_presupuestos"] = {"assets_mb": round(assets, 2), "tope_assets_mb": RD.ASSETS_MAX_MB, "codigo_oficina_mb": round(codigo_mb, 2),
                         "sprites_mayores_de_512": grandes, "tauri": RD.TAURI_NO_APLICA,
                         "medidas": {"trabajando_0": OUT["A_escalera_real"]["medidas"]["trabajando_nivel0"],
                                     "solo_estados_3": OUT["A_escalera_real"]["medidas"]["solo_estados_nivel3"],
                                     "dormida": OUT["d_dormida"]["ram_dormida"], "minimizada": min_med}}

# (h) la lista §8.5 buscada en el codigo de la oficina
patrones = {"captura de pantalla": r"ImageGrab|mss\.|screenshot\(|PrintWindow", "telemetria / red externa":
            r"https?://(?!127\.0\.0\.1|localhost|www\.pixelorama)", "descargas": r"urlretrieve|requests\.get|pip install",
            "auto-actualizacion": r"auto.?update|self.?update", "escribir en la cola": r"sqlite3\.connect\([^)]*(?<!mode=ro)\)",
            "matar procesos ajenos": r"taskkill|\.kill\(\)", "3D / video": r"OpenGL|moderngl|cv2\.VideoWriter|ffmpeg"}
hallado = {}
for py in (R / "oficina").rglob("*.py"):
    if "mediciones" in py.parts or ".venv" in py.parts:
        continue
    txt = py.read_text(encoding="utf-8", errors="replace")
    for nombre, pat in patrones.items():
        for mm in re.finditer(pat, txt):
            linea = txt[: mm.start()].count("\n") + 1
            hallado.setdefault(nombre, []).append(f"{py.relative_to(R)}:{linea}: {txt.splitlines()[linea - 1].strip()[:90]}")
OUT["h_que_no_hacer"] = hallado
OUT["todo_ok"] = all(v.get("ok") for v in OUT.values() if isinstance(v, dict) and "ok" in v) and OUT["b_ok"]
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: (v.get("ok") if isinstance(v, dict) and "ok" in v else None) for k, v in OUT.items()}, ensure_ascii=False))

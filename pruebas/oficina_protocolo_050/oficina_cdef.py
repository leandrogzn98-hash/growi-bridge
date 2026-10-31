"""Verificaciones c, d, e y f de t-oficina-protocolo-050 contra una carpeta share de prueba.
Un «Bridge falso» (otro python) escribe el latido cada 5 s; nunca toca la app instalada."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

PROTO = Path(r"C:\Users\forte\growi-bridge\share\inbox\oficina\protocolo")
BASE = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\cdef")
EVID = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\evidencia")
PYG = r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Lib\site-packages"
APP = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\app")
ENV = dict(os.environ, PYTHONPATH=PYG, PYTHONIOENCODING="utf-8")
OUT = {}

FALSO = r'''
import json, os, sys, time
p = sys.argv[1]
while True:
    tmp = p + ".tmp"
    open(tmp, "w").write(json.dumps({"pid": os.getpid(), "t": time.time(), "cerrar": False}))
    os.replace(tmp, p)
    time.sleep(5)
'''


def vivo(pid):
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
    return str(pid) in r.stdout


def share(nombre, con_ejemplos):
    s = BASE / nombre / "share"
    shutil.rmtree(BASE / nombre, ignore_errors=True)
    (s / "outbox").mkdir(parents=True)
    if con_ejemplos:
        for f in (APP / "share" / "outbox").glob("*-*.json"):
            shutil.copy2(f, s / "outbox" / f.name)
    return s


def bridge_falso(s):
    pf = BASE / "falso.py"
    pf.write_text(FALSO, encoding="utf-8")
    return subprocess.Popen([sys.executable, str(pf), str(s / "outbox" / "bridge-latido.json")])


def oficina(s, bpid, datos, extra=(), mutex="Local\\GrowiOficinaPruebaCDEF"):
    cmd = [sys.executable, str(PROTO / "oficina_proto.py"), "--share", str(s), "--app", str(APP),
           "--datos", str(datos), "--mutex", mutex, *extra]
    if bpid:
        cmd += ["--bridge-pid", str(bpid)]
    return subprocess.Popen(cmd, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")


def metricas(datos):
    filas = []
    for f in sorted(Path(datos).glob("metricas-*.jsonl")):
        filas += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return filas


# (c) matar el Bridge falso a los 10 s: «Bridge no disponible» y autocierre
s = share("c", True)
bf = bridge_falso(s)
time.sleep(1.5)
datos_c = BASE / "c" / "datos"
of = oficina(s, bf.pid, datos_c, ["--captura", str(EVID / "c-no-disponible.png") + "@9.5"])
time.sleep(10)
t_kill = time.time()
bf.kill(); bf.wait()
try:
    code = of.wait(timeout=40)
except subprocess.TimeoutExpired:
    code = None
t_exit = time.time()
time.sleep(1)
m = metricas(datos_c)
ev = [x for x in m if x.get("evento") == "bridge_no_disponible"]
OUT["c_autocierre"] = {"codigo": code, "s_desde_matar_hasta_salir": round(t_exit - t_kill, 1),
                       "huerfano": vivo(of.pid), "evento": ev[:1],
                       "ok": code == 2 and not vivo(of.pid) and bool(ev)}

# (c2) sin pid: solo el latido deja de llegar -> 15 s
s = share("c2", True)
bf = bridge_falso(s)
time.sleep(1.5)
datos_c2 = BASE / "c2" / "datos"
of = oficina(s, None, datos_c2)
time.sleep(8)
t_kill = time.time()
bf.kill(); bf.wait()
try:
    code = of.wait(timeout=60)
except subprocess.TimeoutExpired:
    code = None
OUT["c2_sin_latido_15s"] = {"codigo": code, "s_desde_ultimo_latido_hasta_salir": round(time.time() - t_kill, 1),
                           "huerfano": vivo(of.pid),
                           "ok": code == 2 and not vivo(of.pid)}

# (d) archivos ausentes (solo el latido): todos «sin señal»
s = share("d", False)
bf = bridge_falso(s)
time.sleep(1.5)
datos_d = BASE / "d" / "datos"
of = oficina(s, bf.pid, datos_d, ["--captura", str(EVID / "d-ausentes.png") + "@6", "--salir-a", "8"])
code = of.wait(timeout=60)
bf.kill(); bf.wait()
est = {}
for x in metricas(datos_d):
    if x.get("evento") == "estados":
        est.update(x["cambios"])
OUT["d_ausentes"] = {"codigo": code, "estados": est,
                     "todos_sin_senal": bool(est) and all(v == "sin señal" for v in est.values()),
                     "ok": bool(est) and all(v in ("sin señal", "sin instalar") for v in est.values())
                     and not any(v == "trabajando" for v in est.values())}

# (e) segunda instancia con el mismo mutex
s = share("e", True)
bf = bridge_falso(s)
time.sleep(1.5)
o1 = oficina(s, bf.pid, BASE / "e" / "datos1", ["--salir-a", "12"])
time.sleep(4)
t2 = time.time()
o2 = oficina(s, bf.pid, BASE / "e" / "datos2")
c2 = o2.wait(timeout=20)
c1 = o1.wait(timeout=40)
bf.kill(); bf.wait()
OUT["e_mutex"] = {"primera": c1, "segunda": c2, "segunda_tardo_s": round(time.time() - t2, 1),
                  "ok": c2 == 3 and c1 == 0}

# (f) latencias de todas las lecturas medidas
lat = {}
for d in (datos_c, datos_c2, datos_d):
    for x in metricas(d):
        if x.get("evento") == "salida":
            for k, r in (x.get("resumen") or {}).items():
                lat.setdefault(k, []).append(r)
OUT["f_resumenes"] = lat
fps = [x for d in (datos_c, datos_d) for x in metricas(d) if "fps" in x]
OUT["f_frames"] = {"segundos": len(fps), "fps_min": min((x["fps"] for x in fps), default=None),
                   "peor_ms": max((x["peor_ms"] for x in fps), default=None),
                   "frames_50ms": sum(x["frames_50ms"] for x in fps)}
(EVID / "cdef-salida.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v.get("ok") if isinstance(v, dict) else None for k, v in OUT.items()}, ensure_ascii=False))

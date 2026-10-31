"""(c) de t-oficina-rendimiento-050 con sensores REALES: la oficina corre, se carga Hermes en Ollama (ocupa VRAM de
verdad, $0) y se mide cuanto tarda la oficina en ceder desde que la VRAM libre baja de 300 MB (sondeo externo de
nvidia-smi cada 0,2 s) hasta su cambio de nivel. Al final se descarga el modelo (keep_alive 0)."""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
EV = R / "pruebas" / "evidencia" / "oficina-rendimiento-050"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def vram_libre():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    u, t = (float(x) for x in out.strip().split(","))
    return t - u


def ollama(cuerpo):
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with OPENER.open(req, timeout=300) as r:
        return json.loads(r.read())


tags = json.loads(OPENER.open("http://127.0.0.1:11434/api/tags", timeout=5).read())
modelo = next(m["name"] for m in tags["models"] if "hermes" in m["name"].lower())
# el Bridge falso de la prueba de rendimiento, con sensores reales (sin --sensores-falsos)
import importlib.util  # noqa: E402
src = (Path(__file__).resolve().parent / "prueba_rendimiento.py").read_text(encoding="utf-8")
ini, fin = src.index("class BridgeFalso:"), src.index("def medir(")
ns = {"R": R}
exec("import json, os, shutil, subprocess, sys, threading, time\nfrom datetime import datetime\nfrom pathlib import Path\n"
     + src[src.index("PROTO = "):src.index("u32 = ")] + src[src.index("def iso("):fin], ns)
B = ns["BridgeFalso"]("E")
B.sens.write_text("{}", encoding="utf-8")  # sin datos falsos: manda lo real
of = B.oficina(salir=75)
time.sleep(8)
antes = vram_libre()
marcas = []
parar = threading.Event()


def sondear():
    while not parar.is_set():
        marcas.append((time.time(), vram_libre()))
        time.sleep(0.2)


threading.Thread(target=sondear, daemon=True).start()
t_carga = time.time()
r = ollama({"model": modelo, "prompt": "di hola", "stream": False, "keep_alive": "40s"})
time.sleep(15)
ollama({"model": modelo, "keep_alive": 0})  # descarga el modelo: libera la VRAM
time.sleep(5)
parar.set()
of.wait(timeout=120)
m = B.metricas()
niveles = [x for x in m if x.get("evento") == "nivel"]
cruce = next((t for t, v in marcas if v < 300), None)
reaccion = next((x for x in niveles if x["t"] >= t_carga and x["a"] >= 3), None)
res = {"modelo": modelo, "vram_libre_antes_mb": antes, "vram_libre_min_mb": min(v for _t, v in marcas),
       "cruce_300MB": cruce and datetime.fromtimestamp(cruce).isoformat(timespec="milliseconds"),
       "reaccion_oficina": reaccion, "segundos_hasta_ceder": round(reaccion["t"] - cruce, 2) if reaccion and cruce else None,
       "niveles": [(x["hora"][11:19], x["de"], x["a"], x["motivo"]) for x in niveles],
       "ollama_respondio": bool(r.get("response")), "nota": "el modelo se cargó y respondió sin error (sin OOM)"}
res["ok"] = bool(reaccion and cruce and reaccion["t"] - cruce < 1.5)
(EV / "ceder-vram.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
B.stop.set()
print(json.dumps(res, ensure_ascii=False))

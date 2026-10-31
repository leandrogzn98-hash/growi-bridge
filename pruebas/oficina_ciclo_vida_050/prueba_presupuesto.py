"""Presupuesto §8 con lo nuevo del spec 18 encendido (DEMO con 2 agentes esperando: faro, banner, paseo,
tarjeta y la camara de N): RAM y CPU de la oficina durante 30 s, con un Bridge falso que late.

  python prueba_presupuesto.py   -> evidencia\\presupuesto-salida.json
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[2]
BASE = Path.home() / "growi-bridge" / "_prueba-ciclo-vida"
EVI = BASE / "evidencia"
SHARE = BASE / "share-presupuesto"
PY = r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Scripts\python.exe"
(SHARE / "outbox").mkdir(parents=True, exist_ok=True)
LAT = SHARE / "outbox" / "bridge-latido.json"


def latido():
    LAT.write_text(json.dumps({"pid": os.getpid(), "t": time.time(), "cerrar": False}), encoding="utf-8")


latido()
cmd = [PY, str(REPO / "oficina" / "protocolo" / "oficina_proto.py"), "--share", str(SHARE), "--app", str(BASE / "app"),
       "--bridge-pid", str(os.getpid()), "--latido", str(LAT), "--datos", str(BASE / "datos-presupuesto"),
       "--mutex", "Local\\GrowiOficinaPresupuesto", "--demo", "--sin-noche", "--salir-a", "45",
       "--pulsar", "n@34", "--pulsar", "n@38"]
p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
time.sleep(6)
lanz = psutil.Process(p.pid)
proc = (lanz.children() or [lanz])[0]  # el lanzador del venv tiene un hijo: ese es el que pinta
proc.cpu_percent(None)
ncpu = psutil.cpu_count()
m = []
t0 = time.time()
while time.time() - t0 < 32 and p.poll() is None:
    latido()
    time.sleep(1)
    try:
        m.append({"rss_mb": round(proc.memory_info().rss / 2 ** 20, 1), "cpu_nucleo": proc.cpu_percent(None)})
    except psutil.NoSuchProcess:
        break
p.wait(30)
R = {"muestras": len(m), "ram_max_mb": max(x["rss_mb"] for x in m),
     "cpu_media_equipo_pct": round(sum(x["cpu_nucleo"] for x in m) / len(m) / ncpu, 2),
     "cpu_max_equipo_pct": round(max(x["cpu_nucleo"] for x in m) / ncpu, 2),
     "cpu_media_un_nucleo_pct": round(sum(x["cpu_nucleo"] for x in m) / len(m), 1),
     "nucleos": ncpu, "topes": {"ram_mb": 350, "cpu_reposo_pct": 2},
     "nota": "Con DEMO activo NO es reposo: 2 agentes esperando (faro parpadeando, paseo) y la camara de N a los 34-38 s."}
R["ok_ram"] = R["ram_max_mb"] <= 350
(EVI / "presupuesto-salida.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(R, ensure_ascii=False), flush=True)

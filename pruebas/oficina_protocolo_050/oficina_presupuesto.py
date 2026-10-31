import json, os, subprocess, sys, time, psutil
from pathlib import Path
PROTO = Path(r"C:\Users\forte\growi-bridge\share\inbox\oficina\protocolo")
BASE = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\cdef\c\share")
EVID = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\evidencia")
falso = subprocess.Popen([sys.executable, "-c", "import json,os,time,sys\nwhile True:\n open(sys.argv[1],'w').write(json.dumps({'pid':os.getpid(),'t':time.time()}));time.sleep(5)", str(BASE / "outbox" / "bridge-latido.json")])
env = dict(os.environ, PYTHONPATH=r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Lib\site-packages")
of = subprocess.Popen([sys.executable, str(PROTO / "oficina_proto.py"), "--share", str(BASE), "--app",
                       r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\app", "--bridge-pid", str(falso.pid),
                       "--datos", str(BASE.parent / "datos-presupuesto"), "--mutex", "Local\GrowiPres", "--salir-a", "40"],
                      env=env, stdout=subprocess.DEVNULL)
p = psutil.Process(of.pid)
time.sleep(8); p.cpu_percent()
rss, cpu = [], []
for _ in range(25):
    time.sleep(1); rss.append(p.memory_info().rss / 2**20); cpu.append(p.cpu_percent() / psutil.cpu_count())
g = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader"], capture_output=True, text=True).stdout
g2 = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"], capture_output=True, text=True).stdout
of.wait(timeout=30); falso.kill()
out = {"rss_mib_max": round(max(rss), 1), "rss_mib_media": round(sum(rss) / len(rss), 1),
       "cpu_pct_media_del_pc": round(sum(cpu) / len(cpu), 2), "cpu_pct_max": round(max(cpu), 2),
       "nvidia_apps": g.strip(), "gpu_mem_total_usada": g2.strip(), "nucleos": psutil.cpu_count()}
(EVID / "g-presupuesto-salida.json").write_text(json.dumps(out, indent=1), encoding="utf-8"); print(out)

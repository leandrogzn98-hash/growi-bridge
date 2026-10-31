"""Subfuncion 4b: un encargo escrito sin Bridge queda en disco como «pendiente de enviar», sobrevive
a un cierre brusco y se ve en la ventana; no se envia mientras no hay runner."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
PROTO = Path(r"C:\Users\forte\growi-bridge\share\inbox\oficina\protocolo")
sys.path.insert(0, str(PROTO))
import protocolo as P
BASE = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\cdef\borrador")
EVID = Path(r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\evidencia")
shutil.rmtree(BASE, ignore_errors=True); (BASE / "share" / "outbox").mkdir(parents=True)
datos = BASE / "datos"
b = P.Borradores(datos / "borradores.json")
b.nuevo("Resume la reunión de ayer en 5 puntos")
del b  # «cierre brusco»: otra instancia relee el disco
b2 = P.Borradores(datos / "borradores.json")
persistio = [it["estado"] for it in b2.items]
env = dict(os.environ, PYTHONPATH=r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Lib\site-packages")
of = subprocess.Popen([sys.executable, str(PROTO / "oficina_proto.py"), "--share", str(BASE / "share"),
                       "--app", r"C:\Users\forte\growi-bridge\_prueba-oficina-protocolo\app", "--datos", str(datos),
                       "--mutex", "Local\GrowiBorrador", "--captura", str(EVID / "d2-borrador-pendiente.png") + "@6",
                       "--salir-a", "8"], env=env, stdout=subprocess.DEVNULL)
code = of.wait(timeout=60)
despues = [it["estado"] for it in json.loads((datos / "borradores.json").read_text(encoding="utf-8"))]
out = {"persistio_tras_cierre": persistio, "codigo": code, "estado_tras_8s_sin_bridge": despues,
       "ok": persistio == ["pendiente de enviar"] and despues == ["pendiente de enviar"]}
(EVID / "d2-borrador-salida.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(out)

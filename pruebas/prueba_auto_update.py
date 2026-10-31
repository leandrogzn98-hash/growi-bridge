"""Prueba del auto-update blindado sobre una COPIA de growi-bridge.py (sin red, sin GUI).

Uso: python pruebas/prueba_auto_update.py [ruta a growi-bridge.py]   (por defecto, el del repo)
Carga el modulo con APP_DIR en una carpeta temporal y simula main con urlopen falso.
"""
import importlib.util
import io
import shutil
import sys
import tempfile
from pathlib import Path

src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "growi-bridge.py"
raw = src.read_bytes()
for needle in (rb'(b"\xff\xfe", b"\xfe\xff")', rb'^VERSION = "([^"\r\n]+)"'):
    print("bytes ok:" if needle in raw else "BYTES MAL:", needle.decode())

tmp = Path(tempfile.mkdtemp(prefix="gb-upd-"))
app = tmp / "app"
app.mkdir()
shutil.copy2(src, app / "growi-bridge.py")
(app / "VERSION").write_bytes("0.5.2-alpha".encode("utf-16"))  # con BOM: no debe tumbar la app
for n in ("engines.json", "README.md", "growi.ico"):
    (app / n).write_text(f"local {n}", encoding="utf-8")

spec = importlib.util.spec_from_file_location("gb_upd", app / "growi-bridge.py")
gb = importlib.util.module_from_spec(spec)
sys.argv = [str(app / "growi-bridge.py"), "--no-main"]
spec.loader.exec_module(gb)
res = {}
res["version_utf16_leida"] = gb.VERSION == "0.5.2-alpha"
res["sello_ok"] = gb._sello_version(raw) == "0.5.2-alpha"
res["sello_vacio"] = gb._sello_version(b"print(1)\n") == ""

logs = []
gb.log = lambda m: logs.append(m)
codigo_nuevo = raw.replace(b'VERSION = "0.5.2-alpha"', b'VERSION = "0.5.3-alpha"', 1)
codigo_viejo = raw.replace(b'VERSION = "0.5.2-alpha"', b'VERSION = "0.1.0-alpha"', 1)


def falso_main(codigo):
    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=0):
        name = req.full_url.rsplit("/", 1)[1]
        if name == "growi-bridge.py":
            return R(codigo)
        if name in ("engines.json", "README.md", "growi.ico", "VERSION"):
            return R(f"remoto {name}".encode())
        if name in ("models-catalog.json", "riesgos.json", "PROTOCOLO-PRUEBA-CORTE.md", "politicas.ejemplo.json"):
            raise OSError("404")
        return R(f"remoto {name}".encode())
    gb.urllib.request.urlopen = urlopen


# 1) VERSION subido sin su codigo (lo del 30 oct): rechazado, nada pisado ni respaldado
falso_main(codigo_viejo)
ok1 = gb.download_update("0.5.3-alpha")
res["viejo_rechazado"] = ok1 is False and not list(app.glob("*.new")) and not list(app.glob("*.bak")) \
    and not (app / "actualizar.bat").exists() and any("rechazada" in m for m in logs)

# 2) Codigo y VERSION coinciden: respalda cada archivo que existe y deja el .bat
falso_main(codigo_nuevo)
ok2 = gb.download_update("0.5.3-alpha")
baks = sorted(p.name for p in app.glob("*.pre-update-0.5.2-alpha-*.bak"))
res["nuevo_aceptado"] = ok2 is True and (app / "actualizar.bat").exists()
res["respaldo_de_existentes"] = all(any(b.startswith(n + ".pre-update-") for b in baks)
                                    for n in ("growi-bridge.py", "engines.json", "README.md", "growi.ico", "VERSION"))
res["respaldo_contenido_local"] = (app / [b for b in baks if b.startswith("engines.json")][0]).read_text() == "local engines.json"
res["bat_mueve_no_borra_bak"] = ".bak" not in (app / "actualizar.bat").read_text(encoding="utf-8")

# 3) Comparacion de versiones: 0.5.2-alpha (instalada) > 0.4.6 (main hoy)
res["main_046_no_actualiza"] = gb._version_tuple("0.4.6") < gb._version_tuple("0.5.2-alpha")

for k, v in res.items():
    print("OK   " if v else "FALLA", k)
print("logs:", *logs[-3:], sep="\n  ")
print("RESULTADO:", "ok" if all(res.values()) else "FALLA")
shutil.rmtree(tmp, ignore_errors=True)

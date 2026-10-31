"""Instala la oficina 0.5.0 (con el ciclo de vida del spec 18) en una app de Growi Bridge.
Lo corre Leandro, con la app CERRADA (pide reiniciarla): no se ejecuta desde ninguna tarea.

  python parches\\instalar_oficina_050.py [carpeta de la app]      (por defecto %USERPROFILE%\\growi-bridge)
         [--pygame-dir <site-packages con pygame-ce>]

1. Comprueba que la app no esta corriendo (si lo esta, sale sin tocar nada).
2. growi-bridge.py del repo -> la app, con copia growi-bridge.py.pre-oficina-050-<fecha>.bak.
3. oficina\\ del repo -> share\\inbox\\oficina\\ (la carpeta vieja queda como oficina.pre-050-<fecha>.bak).
   No copia mediciones\\, godot\\, arte\\ ni datos\\: la oficina guarda sus datos en su propia carpeta.
4. Si el Python de la app no tiene pygame-ce y settings.json no dice donde esta, escribe
   «oficina_pygame_dir» (con copia settings.json.pre-oficina-050-<fecha>.bak).
Para deshacer: restaurar los .bak.
"""
import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("app", nargs="?", default=str(Path.home() / "growi-bridge"))
ap.add_argument("--pygame-dir", default=str(Path(r"C:\Users\forte\source\growi-bridge\oficina\mediciones\.venv\Lib\site-packages")))
A = ap.parse_args()
APP = Path(A.app)
SELLO = datetime.now().strftime("%Y%m%d-%H%M%S")
if not (APP / "growi-bridge.py").is_file():
    sys.exit(f"no encuentro {APP / 'growi-bridge.py'}")
try:
    import psutil
    objetivo = str((APP / "growi-bridge.py").resolve()).lower()
    vivos = []
    for p in psutil.process_iter(["cmdline", "cwd"]):  # la app de ESTA carpeta (el .bat la lanza con ruta relativa)
        for c in p.info["cmdline"] or []:
            if c.lower().endswith("growi-bridge.py"):
                ruta = Path(c) if Path(c).is_absolute() else Path(p.info["cwd"] or ".") / c
                if str(ruta.resolve()).lower() == objetivo:
                    vivos.append(p.pid)
except Exception:  # noqa: BLE001
    vivos = []
if vivos:
    sys.exit(f"Growi Bridge está abierto (pid {vivos}): ciérralo (bandeja → Salir) y vuelve a correr esto. No toqué nada.")

shutil.copy2(APP / "growi-bridge.py", APP / f"growi-bridge.py.pre-oficina-050-{SELLO}.bak")
shutil.copy2(REPO / "growi-bridge.py", APP / "growi-bridge.py")
print(f"growi-bridge.py instalado (copia: growi-bridge.py.pre-oficina-050-{SELLO}.bak)")

dst = APP / "share" / "inbox" / "oficina"
if dst.exists():
    dst.rename(dst.with_name(f"oficina.pre-050-{SELLO}.bak"))
shutil.copytree(REPO / "oficina", dst,
                ignore=shutil.ignore_patterns("__pycache__", "mediciones", "godot", "arte", "datos", "*.bak"))
print(f"oficina copiada a {dst}")

s_path = APP / "settings.json"
s = json.loads(s_path.read_text(encoding="utf-8")) if s_path.is_file() else {}
if importlib.util.find_spec("pygame") is None and not s.get("oficina_pygame_dir") and not s.get("oficina_python"):
    if (Path(A.pygame_dir) / "pygame").is_dir():
        shutil.copy2(s_path, APP / f"settings.json.pre-oficina-050-{SELLO}.bak")
        s["oficina_pygame_dir"] = A.pygame_dir
        s_path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"settings.json: oficina_pygame_dir = {A.pygame_dir}")
    else:
        print("AVISO: este Python no tiene pygame-ce y no lo encuentro en --pygame-dir. "
              "Instálalo con: python -m pip install pygame-ce==2.5.8")
print("Listo. Abre Growi Bridge: barra lateral → Oficina → Abrir (o Ctrl+Shift+O).")

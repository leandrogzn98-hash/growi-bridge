"""Prepara la instancia aislada de t-oficina-encolar-externa-050:
C:\\Users\\forte\\growi-bridge\\_prueba-encolar-externa\\app\\ = copia de la app
instalada (growi-bridge.py ya parcheado + config), con su propia share, cola.db,
log y settings.json (guardrail de prueba). Lee la instalacion; no escribe en ella."""
import json
import shutil
import sys
from pathlib import Path

REAL = Path(r"C:\Users\forte\growi-bridge")
APP = REAL / "_prueba-encolar-externa" / "app"
guard = sys.argv[1] if len(sys.argv) > 1 else "siempre"
if APP.exists():
    shutil.rmtree(APP)  # solo la carpeta de prueba propia
APP.mkdir(parents=True)
for f in ("growi-bridge.py", "engines.json", "riesgos.json", "rules.json", "models-catalog.json",
          "availability.json", "pc-specs.json", "proxy.json", "VERSION", "growi.png", "growi.ico",
          "growi-header.png", "growi-tray.png", "growi-tray-b.png", "motores-salud.json"):
    if (REAL / f).is_file():
        shutil.copy2(REAL / f, APP / f)
for d in ("asistentes", "temas", "mascot", "skills"):
    shutil.copytree(REAL / d, APP / d)
s = json.loads((REAL / "settings.json").read_text(encoding="utf-8"))
s["guardrail"] = guard
s["onboarding_done"] = True
(APP / "settings.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
e = json.loads((APP / "engines.json").read_text(encoding="utf-8"))
srv = e["motores"]["llama"]["servidor"]
srv["exe"] = str(REAL / srv["exe"])   # el binario y el modelo reales (solo se leen)
srv["gguf"] = str(REAL / srv["gguf"])
srv["log"] = str(APP / "llama-server.log")
(APP / "engines.json").write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
for d in ("share/inbox/runner-tasks", "share/outbox/runner-results"):
    (APP / d).mkdir(parents=True, exist_ok=True)
print("instancia aislada lista:", APP, "| guardrail:", guard)

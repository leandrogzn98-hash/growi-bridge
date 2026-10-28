"""Prueba de «Verificar Groq y Gemini» (ESTADO-VERIFICAR-GROQ-GEMINI.md).

Copia aislada de growi-bridge.py SIN claves (no lee las del usuario). Hace de
verdad los sondeos sin clave (¿contesta el servidor desde esta IP, directo y
por el proxy?) y comprueba que, sin clave, la llamada real queda como FALTA y
nada entra al router. No gasta nada.

  python pruebas/prueba_verificar_nubes.py
"""

import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "verificar-nubes"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-nubes-"))
    app = tmp / "app"
    app.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "onboarding_done": True}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"))
    spec = importlib.util.spec_from_file_location("gb_nubes", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    ev = {"copia": str(tmp), "claves_en_la_copia": [c["proveedor"] for c in gb.cred_lista()],
          "hay_proxy": bool(gb.proxy_url())}
    inf = gb.verificar_nubes()
    ev["informe"] = inf
    ev["md"] = gb.NUBES_FILE.with_suffix(".md").read_text(encoding="utf-8")
    ev["router_groq_directo"] = gb.nube_verificada("Groq directo")
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "verificar nubes" in x]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (OUT / "VERIFICACION-NUBES.md").write_text(ev["md"], encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()

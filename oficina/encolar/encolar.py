"""Puerta de encolado de la oficina 0.5.0 (t-oficina-encolar-externa-050).

La UNICA escritura de la oficina es encolar, y por la MISMA funcion que usa la
app: este modulo importa growi-bridge.py (sin abrir ventana, sin arrancar el
puente ni el runner: el arranque esta tras `if __name__ == "__main__"`) y llama a
su encolar_tarea(), la que tambien llama «Pedirle algo» (_send_ask).

Lo que hace encolar_tarea(): escribe un <id>.task.json en share\\inbox\\runner-tasks\\
(atomico: .tmp + rename exclusivo). Nada mas. Despues, el runner de la app:
  1. lo apunta en cola.db (cola_registrar via _cola_ver) ANTES de recogerlo;
  2. le aplica el guardrail (_approval_needed); si retiene -> «esperando_aprobacion»
     (se aprueba en la app Tareas o por WhatsApp, nunca desde la oficina);
  3. lo corre y deja <id>.result.json en share\\outbox\\runner-results\\.

Este modulo NUNCA escribe cola.db, runner-live.json, runner-status.json,
.revision.json, .orquestacion.json ni settings.json. Para seguir una tarea, lee
cola.db en SOLO LECTURA (sqlite "mode=ro") y el .result.json.

Sin red: no abre ningun puerto ni hace peticiones; no lleva token ni credenciales.

Uso desde Python (otro proceso):
    import encolar
    r = encolar.encolar("Escribe hola.txt con la palabra hola",
                        ["el archivo hola.txt existe"], model="motor:llama")
    # r = {"ok": True, "id": "t-20261030-101500", "archivo": "...task.json", ...}
    encolar.estado(r["id"])   # {"estado": "en_cola" | "en_curso" | ... | None}

Uso por consola:
    python encolar.py "encargo" --criterio "frase" --modelo motor:llama [--esperar 600]

Carpeta de la app: GROWI_BRIDGE_APP_DIR o --app-dir (por defecto %USERPROFILE%\\growi-bridge).
Para una instancia aislada de prueba vale GROWI_BRIDGE_SHARE (lo lee growi-bridge.py).
"""
import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

_APP = {}


class EncolarNoDisponible(RuntimeError):
    """La app no esta o su growi-bridge.py no trae encolar_tarea()."""


def app_dir(ruta=None):
    return Path(ruta or os.environ.get("GROWI_BRIDGE_APP_DIR")
                or Path.home() / "growi-bridge").resolve()


def cargar_app(ruta=None):
    """Importa growi-bridge.py una vez por proceso (~0,5 s, ~20 MB medidos)."""
    d = app_dir(ruta)
    if str(d) in _APP:
        return _APP[str(d)]
    src = d / "growi-bridge.py"
    if not src.is_file():
        raise EncolarNoDisponible(f"no encuentro {src}")
    loader = importlib.machinery.SourceFileLoader("growi_bridge_app", str(src))
    spec = importlib.util.spec_from_file_location("growi_bridge_app", src, loader=loader)
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    if not callable(getattr(gb, "encolar_tarea", None)):
        raise EncolarNoDisponible(
            f"{src} no trae encolar_tarea() (es anterior a t-oficina-encolar-externa-050)")
    _APP[str(d)] = gb
    return gb


def encolar(prompt, criterios=None, model=None, ruta_app=None, origen="oficina", urgente=False,
            despues_de=None):
    """Encola como «Pedirle algo». -> dict de encolar_tarea() (ok, id, archivo,
    engine, data, error). Nunca lanza por un encargo malo: ok False + error."""
    try:
        gb = cargar_app(ruta_app)
    except EncolarNoDisponible as e:
        return {"ok": False, "error": str(e)}
    if despues_de:  # t-oficina-paseo-050
        return gb.encolar_tarea(prompt, criterios, model=model, origen=origen, urgente=urgente,
                                despues_de=despues_de)
    if urgente:  # t-oficina-llamadas-050
        return gb.encolar_tarea(prompt, criterios, model=model, origen=origen, urgente=True)
    return gb.encolar_tarea(prompt, criterios, model=model, origen=origen)


def estado(task_id, ruta_app=None):
    """Lo que dice cola.db de la tarea, en SOLO LECTURA. Si la base no se puede
    leer o la tarea aun no esta apuntada, estado None (la oficina dice «sin señal»
    o «en la bandeja», nunca inventa)."""
    gb = cargar_app(ruta_app)
    out = {"id": task_id, "estado": None, "fila": None, "resultado": None, "error": None}
    try:
        uri = Path(gb.COLA_DB).resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            r = con.execute("SELECT * FROM tareas WHERE id=?", (task_id,)).fetchone()
        finally:
            con.close()
        if r is not None:
            out["fila"] = dict(r)
            out["estado"] = r["estado"]
    except sqlite3.Error as e:
        out["error"] = f"cola.db no se pudo leer ({e})"
    res = Path(gb.RESULTS) / f"{task_id}.result.json"
    if res.is_file():
        try:
            out["resultado"] = json.loads(res.read_text(encoding="utf-8"))
        except ValueError:
            out["resultado"] = {"error": "result.json a medio escribir o roto"}
    return out


def esperar(task_id, hasta=("terminada", "fallida", "necesita_decision", "esperando_aprobacion"),
            timeout_s=600, cada_s=2, ruta_app=None):
    """Sondea estado() hasta un estado de `hasta` (o timeout). Devuelve el
    ultimo estado leido y la lista de cambios vistos [(t, estado)]."""
    vistos, t0, st = [], time.time(), None
    while time.time() - t0 < timeout_s:
        st = estado(task_id, ruta_app)
        if not vistos or vistos[-1][1] != st["estado"]:
            vistos.append((round(time.time() - t0, 1), st["estado"]))
        if st["estado"] in hasta:
            break
        time.sleep(cada_s)
    return st, vistos


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Encola una tarea en Growi Bridge como «Pedirle algo».")
    ap.add_argument("prompt")
    ap.add_argument("--criterio", action="append", default=[], help="una frase; se puede repetir")
    ap.add_argument("--modelo", default=None, help="sonnet, opus, haiku, motor:auto, motor:llama...")
    ap.add_argument("--app-dir", default=None)
    ap.add_argument("--esperar", type=int, default=0, help="segundos a esperar el estado final")
    a = ap.parse_args(argv)
    r = encolar(a.prompt, a.criterio, model=a.modelo, ruta_app=a.app_dir)
    salida = {k: r.get(k) for k in ("ok", "id", "archivo", "engine", "error")}
    if r.get("ok") and a.esperar:
        st, vistos = esperar(r["id"], timeout_s=a.esperar, ruta_app=a.app_dir)
        salida.update(estado_final=st["estado"], cambios=vistos)
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

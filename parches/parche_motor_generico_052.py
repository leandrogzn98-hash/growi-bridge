"""Parche de t-motor-generico-052 para la app INSTALADA (C:\\Users\\forte\\growi-bridge),
que es otra version de growi-bridge.py (mas vieja que la del repo).

Lleva solo lo que esa version necesita para que un task con motor codex/gemini
se ejecute con ese motor y no se rechace:
  1. growi-bridge.py: normalizar_motor() (copiada del repo, la misma funcion) y
     su llamada en validate_task(); el bloque viejo «forma vieja» queda en una
     linea. Si falta _motor_de_modelo(), se anade la del repo.
  2. engines.json: la ficha de gemini del repo (solo sesion de agy) si no esta.
No lleva los cubos de cuota (esa version no tiene router_antes).

Solo aplica si encuentra el texto original EXACTO; conserva los CRLF; deja
<archivo>.pre-motor-generico-052.bak. Sin --aplicar solo dice que haria.
Despues de aplicar hay que reiniciar la app (la lee al arrancar).

Uso: python parche_motor_generico_052.py [--app C:\\ruta\\growi-bridge] [--aplicar]
"""
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
args = sys.argv[1:]
APP = Path(args[args.index("--app") + 1]) if "--app" in args else Path.home() / "growi-bridge"
APLICAR = "--aplicar" in args
BAK = ".pre-motor-generico-052.bak"

VIEJO_LLAMADA = '''    model = data.get("modelo") if data.get("modelo") is not None else data.get("model")
    motor = data.get("motor")
    enrutado = None
'''
NUEVO_LLAMADA = '''    model = data.get("modelo") if data.get("modelo") is not None else data.get("model")
    motor, model, norm_err = normalizar_motor(data.get("motor"), model, data.get("via"))
    if norm_err:
        return None, norm_err
    enrutado = None
'''
VIEJO_BLOQUE = '''    if motor is None:
        # Forma vieja: "model": "<motor>:<modelo>" (p. ej. "ollama:default")
        # -> ese motor; "api:..." -> APIs; sin nada -> el de por defecto.
        pref = model.split(":", 1)[0] if isinstance(model, str) and ":" in model else None
        if pref == "api":
            motor = "api"
        elif pref and pref in engine_ids():
            motor, model = pref, model.split(":", 1)[1]
        else:
            motor = default_motor()
'''
NUEVO_BLOQUE = '''    if motor is None:
        # Las formas viejas ("ollama:default", "api:...", "motor:codex") ya
        # las resolvio normalizar_motor; sin nada -> el de por defecto.
        motor = default_motor()
'''


def funcion(src, nombre):
    m = re.search(rf"^def {nombre}\(.*?(?=^\S)", src, re.S | re.M)
    if not m:
        raise SystemExit(f"no encuentro {nombre}() en el repo")
    return m.group(0).rstrip("\n") + "\n\n\n"


def parche_py(problemas, hechos):
    p = APP / "growi-bridge.py"
    raw = p.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if "def normalizar_motor(" in s:
        hechos.append("growi-bridge.py: ya tiene normalizar_motor (nada que hacer)")
        return None
    repo = (REPO / "growi-bridge.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    for viejo, nombre in ((VIEJO_LLAMADA, "llamada"), (VIEJO_BLOQUE, "bloque forma vieja")):
        if s.count(viejo) != 1:
            problemas.append(f"growi-bridge.py: el {nombre} de validate_task no está exacto ({s.count(viejo)} veces)")
    if s.count("\ndef validate_task(data):\n") != 1:
        problemas.append("growi-bridge.py: no encuentro def validate_task(data)")
    if problemas:
        return None
    nuevo = funcion(repo, "normalizar_motor")
    if "\ndef _motor_de_modelo(" not in s:
        nuevo = funcion(repo, "_motor_de_modelo") + nuevo
        hechos.append("growi-bridge.py: + _motor_de_modelo() (no estaba)")
    s = s.replace(VIEJO_LLAMADA, NUEVO_LLAMADA).replace(VIEJO_BLOQUE, NUEVO_BLOQUE)
    s = s.replace("\ndef validate_task(data):\n", "\n" + nuevo + "def validate_task(data):\n")
    compile(s, str(p), "exec")
    hechos.append("growi-bridge.py: + normalizar_motor(), validate_task la llama, bloque viejo en una línea")
    return p, (s.replace("\n", "\r\n") if crlf else s)


def parche_engines(problemas, hechos):
    p = APP / "engines.json"
    raw = p.read_bytes().decode("utf-8")
    d = json.loads(raw)
    if "gemini" in (d.get("motores") or {}):
        hechos.append("engines.json: ya tiene gemini (no se toca)")
        return None
    g = json.loads((REPO / "engines.json").read_text(encoding="utf-8"))["motores"]["gemini"]
    d["motores"]["gemini"] = g
    hechos.append("engines.json: + ficha de gemini del repo (solo sesión de agy)")
    s = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    return p, (s.replace("\n", "\r\n") if "\r\n" in raw else s)


def main():
    problemas, hechos = [], []
    cambios = [c for c in (parche_py(problemas, hechos), parche_engines(problemas, hechos)) if c]
    for h in hechos:
        print("·", h)
    if problemas:
        for x in problemas:
            print("PROBLEMA:", x)
        raise SystemExit("no se aplica nada: el original no coincide")
    if not APLICAR:
        print(f"comprobado en {APP}: se puede aplicar ({len(cambios)} archivos). Añade --aplicar para hacerlo.")
        return
    for p, contenido in cambios:
        shutil.copy2(p, p.with_name(p.name + BAK))
        p.write_bytes(contenido.encode("utf-8"))
        print("aplicado:", p, "(respaldo", p.name + BAK + ")")
    print("Reinicia Growi Bridge para que lo lea.")


if __name__ == "__main__":
    main()

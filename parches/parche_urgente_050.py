"""Parche t-oficina-llamadas-050 (urgente) sobre growi-bridge.py y oficina/encolar/encolar.py:
- encolar_tarea(..., urgente=False): el .task.json lleva "urgente": true.
- El runner ordena la cola: rondas de correccion primero, luego las urgentes, luego el resto por antiguedad.
  Una urgente ADELANTA pero NUNCA interrumpe la tarea en curso (el runner solo elige al quedar libre).
- cola-live.json publica "urgente": true en esas tareas (para la posicion en cola de la oficina).

  python parche_urgente_050.py <growi-bridge.py> <encolar.py>
"""
import sys
from pathlib import Path


def aplicar(ruta, cambios, marca):
    p = Path(ruta)
    raw = p.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if marca in s:
        print(f"{p.name}: ya parcheado")
        return
    for old, new in cambios:
        assert s.count(old) == 1, (p.name, s.count(old), old[:80])
        s = s.replace(old, new)
    p.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
    print(f"{p.name}: parcheado")


GB = [
    ('def encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app"):\n',
     'def encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app", urgente=False):\n'),
    ('    if criterios:\n        data["criterios"] = criterios\n    # Escritura atomica y exclusiva',
     '    if criterios:\n        data["criterios"] = criterios\n'
     '    if urgente:  # t-oficina-llamadas-050: adelanta en la cola, nunca interrumpe la tarea en curso\n'
     '        data["urgente"] = True\n    # Escritura atomica y exclusiva'),
    ('            # Las rondas de correccion van primero (son la misma tarea).\n'
     '            candidates.sort(key=lambda p: (0 if _is_round_task(p) else 1, p.stat().st_mtime))\n',
     '            # Las rondas de correccion van primero (son la misma tarea); luego las urgentes\n'
     '            # (t-oficina-llamadas-050: adelantan, nunca interrumpen); luego el resto por antiguedad.\n'
     '            candidates.sort(key=lambda p: (0 if _is_round_task(p) else 1 if _is_urgent_task(p) else 2,\n'
     '                                           p.stat().st_mtime))\n'),
    ('def _is_round_task(path):\n',
     'def _is_urgent_task(path):\n'
     '    try:\n'
     '        data = json.loads(Path(path).read_text(encoding="utf-8"))\n'
     '        return isinstance(data, dict) and data.get("urgente") is True\n'
     '    except Exception:\n'
     '        return False\n\n\n'
     'def _is_round_task(path):\n'),
    ('                   "fase", "intentos", "reintentos", "proximo_intento", "motivo", "creado_en",\n'
     '                   "actualizado_en")\n',
     '                   "fase", "intentos", "reintentos", "proximo_intento", "motivo", "creado_en",\n'
     '                   "actualizado_en", "urgente")  # urgente: t-oficina-llamadas-050\n'),
    ('    if isinstance(r.get("proximo_intento"), (int, float)) and r["proximo_intento"] > ahora:\n'
     '        t["proximo_intento"] = _hora(r["proximo_intento"])\n',
     '    if isinstance(r.get("proximo_intento"), (int, float)) and r["proximo_intento"] > ahora:\n'
     '        t["proximo_intento"] = _hora(r["proximo_intento"])\n'
     '    if r["estado"] == "en_cola" and _cl_urgente(r):\n'
     '        t["urgente"] = True\n'),
    ('def _cl_tarea(r, ahora):\n',
     'def _cl_urgente(r):\n'
     '    """Si el encargo pide urgente (su .task.json); sin archivo legible = no (no se inventa)."""\n'
     '    try:\n'
     '        d = json.loads(Path(r.get("archivo") or "").read_text(encoding="utf-8"))\n'
     '        return isinstance(d, dict) and d.get("urgente") is True\n'
     '    except (OSError, ValueError):\n'
     '        return False\n\n\n'
     'def _cl_tarea(r, ahora):\n'),
]
ENC = [
    ('def encolar(prompt, criterios=None, model=None, ruta_app=None, origen="oficina"):\n',
     'def encolar(prompt, criterios=None, model=None, ruta_app=None, origen="oficina", urgente=False):\n'),
    ('    return gb.encolar_tarea(prompt, criterios, model=model, origen=origen)\n',
     '    if urgente:  # t-oficina-llamadas-050\n'
     '        return gb.encolar_tarea(prompt, criterios, model=model, origen=origen, urgente=True)\n'
     '    return gb.encolar_tarea(prompt, criterios, model=model, origen=origen)\n'),
]
if __name__ == "__main__":
    aplicar(sys.argv[1], GB, "_is_urgent_task")
    aplicar(sys.argv[2], ENC, "t-oficina-llamadas-050")

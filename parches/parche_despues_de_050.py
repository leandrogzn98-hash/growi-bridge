"""Parche t-oficina-paseo-050 («después de esto») sobre growi-bridge.py y oficina/encolar/encolar.py:
- encolar_tarea(..., despues_de=<id>): el .task.json lleva "despues_de": "<id>".
- El runner NO recoge esa tarea mientras <id> siga esperando aprobacion o, si se aprobo, mientras siga en
  cola o en curso (al aprobarla vuelve a la cola con mtime nuevo: sin esto la de «después» se colaba).
  Cuando <id> termina, se rechaza o vence, la recoge como cualquier otra. Explicito y con confirmacion en la oficina: nunca automatico ni silencioso.

  python parche_despues_de_050.py <growi-bridge.py> <encolar.py>
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
    ('def encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app", urgente=False):\n',
     'def encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app", urgente=False,\n'
     '                  despues_de=None):\n'),
    ('    if urgente:  # t-oficina-llamadas-050: adelanta en la cola, nunca interrumpe la tarea en curso\n'
     '        data["urgente"] = True\n',
     '    if urgente:  # t-oficina-llamadas-050: adelanta en la cola, nunca interrumpe la tarea en curso\n'
     '        data["urgente"] = True\n'
     '    if despues_de:  # t-oficina-paseo-050: «después de esto», espera a que se resuelva esa aprobacion\n'
     '        if not _safe_id(str(despues_de)):\n'
     '            return {"ok": False, "error": f"despues_de no válido: {despues_de}"}\n'
     '        data["despues_de"] = str(despues_de)\n'),
    ('                        if p.name not in espera:\n'
     '                            candidates.append(p)\n',
     '                        if p.name not in espera and not _espera_aprobacion_de(p):\n'
     '                            candidates.append(p)\n'),
    ('def _is_urgent_task(path):\n',
     'def _espera_aprobacion_de(path):\n'
     '    """t-oficina-paseo-050: True si la tarea es «después de» otra que sigue esperando aprobacion."""\n'
     '    try:\n'
     '        data = json.loads(Path(path).read_text(encoding="utf-8"))\n'
     '    except Exception:\n'
     '        return False\n'
     '    dep = data.get("despues_de") if isinstance(data, dict) else None\n'
     '    if not dep:\n'
     '        return False\n'
     '    if (WAITING / f"{dep}.task.json").exists():\n'
     '        return True\n'
     '    fila = cola_get(str(dep)) or {}\n'
     '    # «después de esto» = después de ESA tarea: mientras espera aprobación y, si se aprueba, hasta que\n'
     '    # termine (al aprobarla vuelve a la cola con mtime nuevo y si no, la de «después» se le colaba).\n'
     '    return fila.get("estado") in ("esperando_aprobacion", "esperando_leandro", "en_cola", "en_curso")\n\n\n'
     'def _is_urgent_task(path):\n'),
]
ENC = [
    ('def encolar(prompt, criterios=None, model=None, ruta_app=None, origen="oficina", urgente=False):\n',
     'def encolar(prompt, criterios=None, model=None, ruta_app=None, origen="oficina", urgente=False,\n'
     '            despues_de=None):\n'),
    ('    if urgente:  # t-oficina-llamadas-050\n'
     '        return gb.encolar_tarea(prompt, criterios, model=model, origen=origen, urgente=True)\n',
     '    if despues_de:  # t-oficina-paseo-050\n'
     '        return gb.encolar_tarea(prompt, criterios, model=model, origen=origen, urgente=urgente,\n'
     '                                despues_de=despues_de)\n'
     '    if urgente:  # t-oficina-llamadas-050\n'
     '        return gb.encolar_tarea(prompt, criterios, model=model, origen=origen, urgente=True)\n'),
]
if __name__ == "__main__":
    aplicar(sys.argv[1], GB, "_espera_aprobacion_de")
    aplicar(sys.argv[2], ENC, "t-oficina-paseo-050")

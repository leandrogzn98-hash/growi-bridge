"""Parche t-oficina-llamadas-050 (lanzado_at) sobre growi-bridge.py: al lanzar el proceso del motor de una
TAREA (no de la revision), el runner apunta en runner-live.json `lanzado_at` (hora ISO). Asi la oficina sabe
cuando termina «marcando» (el proceso ya arranco) sin adivinar: runner-live se escribe ANTES del Popen
(medido: la oficina pasaba a «timbre» 2 s antes de que el log dijera «lanzado oculto»).

  python parche_lanzado_at_050.py <growi-bridge.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "lanzado_at" in s:
    print("ya parcheado")
    sys.exit(0)
old = '        log(f"runner [{task[\'id\']}]: {motor_id} lanzado oculto ({OCULTO_TXT}), pid {proc.pid}")\n'
new = (old + '        if rol == "tarea":  # t-oficina-llamadas-050: la oficina cuelga «marcando» con esto\n'
             '            live_set("tarea", lanzado_at=_now_iso())\n'
             '            live_write(force=True)  # al instante: no esperar al ritmo de 5 s\n')
n = s.count(old)
assert n == 2, n
s = s.replace(old, new)
p.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"parcheado {p} ({n} sitios)")

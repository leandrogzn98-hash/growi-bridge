"""Parche t-agente-ventas-052 sobre growi-bridge.py: las «entradas» de la skill de un paso de workflow tambien se
rellenan con los parametros del workflow ({nicho} -> el valor), igual que su prompt y sus criterios.

  python parche_entradas_wf_052.py <growi-bridge.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-agente-ventas-052" in s:
    print("ya parcheado")
    sys.exit(0)
old = '''                for k in ("acciones", "revisar", "skill", "entradas"):  # skill: t-skills-unidades-052
                    if k in p:
                        f[k] = p[k]
'''
new = old + '''                if isinstance(f.get("entradas"), dict):  # t-agente-ventas-052: {param} tambien en las entradas
                    f["entradas"] = {str(k): _wf_rellenar(str(v), valores) for k, v in f["entradas"].items()}
'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
p.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"parcheado {p} (t-agente-ventas-052)")

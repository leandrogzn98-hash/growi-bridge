r"""(h) en la oficina NO se puede aprobar: comprobacion estatica del codigo que corre en la oficina.
Busca cualquier llamada que apruebe/rechace, escriba en cola.db o en los pedidos de aprobacion,
o una tecla/boton de aprobar. La tarjeta de la mesa del gerente solo LEE outbox\aprobaciones.

  python prueba_sin_aprobar.py   -> evidencia\h-sin-aprobar.json
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVI = Path.home() / "growi-bridge" / "_prueba-ciclo-vida" / "evidencia"
ARCH = [REPO / "oficina" / "protocolo" / "oficina_proto.py", REPO / "oficina" / "ciclo" / "ciclo.py"]
PROHIBIDO = [r"aprobar_tarea|rechazar_tarea|apr_aprobar|apr_rechazar|_apr_set|resolver_aprobacion",
             r"sqlite3\.connect", r"Allow|Deny|\[Aprobar\]|\[Rechazar\]",
             r"K_[ys]\b.*aprob", r"APR_PEDIDOS[^\n]*\.(write|unlink|rename|replace)"]
R = {"hallazgos": []}
for f in ARCH:
    for i, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        for pat in PROHIBIDO:
            if re.search(pat, l):
                R["hallazgos"].append(f"{f.name}:{i}: {l.strip()}")
cv = (REPO / "oficina" / "ciclo" / "ciclo.py").read_text(encoding="utf-8")
lp = cv[cv.index("def leer_pedidos"):cv.index("def _corta")]
R["leer_pedidos_solo_lee"] = "read_text" in lp and not re.search(r"write|unlink|replace\(|rename", lp)
tj = cv[cv.index("def tarjeta"):cv.index("def puestos_gerente")]
R["tarjeta_dice_donde_se_aprueba"] = "Aquí no se aprueba ni se rechaza nada." in tj
R["ok"] = not R["hallazgos"] and R["leer_pedidos_solo_lee"] and R["tarjeta_dice_donde_se_aprueba"]
EVI.mkdir(parents=True, exist_ok=True)
(EVI / "h-sin-aprobar.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(R, ensure_ascii=False))

"""Proveedor de prueba: no llama a nada ni gasta. Juzga como las reglas: NECESITA_DECISION si el prompt trae
alguna candidata grave, citando sus títulos como evidencia.

Sirve para probar una pasada completa (veredicto + log) sin red. Con la variable SUPERVISOR_MOCK_RESPUESTA
devuelve ese texto tal cual (para probar respuestas malformadas).
"""

import json
import os
import re

MODELO_POR_DEFECTO = "mock"
CLAVE_POR_DEFECTO = ""


def completar(prompt, *, modelo, clave, ajustes):
    fija = os.environ.get("SUPERVISOR_MOCK_RESPUESTA")
    if fija is not None:
        return fija
    m = re.search(r"<candidatas>\s*(.*?)\s*</candidatas>", prompt, re.S)
    graves = [c["titulo"] for c in (json.loads(m.group(1)) if m else []) if c.get("grave")]
    return json.dumps({"veredicto": "NECESITA_DECISION" if graves else "TODO_BIEN", "evidencia": graves,
                       "confianza": 0.9}, ensure_ascii=False)

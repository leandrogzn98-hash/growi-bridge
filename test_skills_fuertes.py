# -*- coding: utf-8 -*-
"""Pruebas de los fuertes en el monolito (Growi Private MQTT, P4):
`_f4_fuertes_fn` calcula el factor de cada cuenta contra el catálogo
real de skills, y `_skills_con_fuertes` mete el fuerte de la cuenta
como candidata prioritaria al ejecutar, solo si encaja con la tarea.

El monolito se importa con el entorno aislado (share, cola, XDG y la
carpeta de skills en temporales), como en test_chat_tarea.
Ejecutar: python3 -m unittest test_skills_fuertes
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="gb-fuertes-")
_SKILLS = Path(_TMP) / "skills"
for _nombre, _desc in (
    ("revision-profunda",
     "Revisar código a fondo buscando fallos errores y mejoras de calidad"),
    ("ahorro-tokens",
     "Ahorrar tokens y reducir el consumo de cada tarea al mínimo posible"),
):
    _d = _SKILLS / _nombre
    _d.mkdir(parents=True)
    (_d / "SKILL.md").write_text(
        f"---\nname: {_nombre}\ndescription: {_desc}\nversion: 1.0.0\n"
        f"---\nCuerpo de la skill {_nombre}.\n", encoding="utf-8")

os.environ["GROWI_BRIDGE_SHARE"] = str(Path(_TMP) / "share")
os.environ["GROWI_BRIDGE_COLA"] = str(Path(_TMP) / "cola.db")
os.environ["XDG_DATA_HOME"] = str(Path(_TMP) / "xdg")
os.environ["GROWI_BRIDGE_SKILLS"] = str(_SKILLS)

_spec = importlib.util.spec_from_file_location(
    "gb_fuertes", str(Path(__file__).with_name("growi-bridge.py")))
gb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gb)

_APP = Path(_TMP) / "app"
_APP.mkdir(exist_ok=True)
gb.APP_DIR = _APP


def _escribir_registro(fuertes_por_cuenta):
    cuentas = []
    for cid, carril in (("principal", "a"), ("segunda", "b")):
        c = {"id": cid, "nombre": cid.title(), "asistente": None,
             "carril": carril, "conexion": "ambas", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "hereda", "clases_extra_denegadas": []}}
        if fuertes_por_cuenta.get(cid):
            c["fuertes"] = fuertes_por_cuenta[cid]
        cuentas.append(c)
    (_APP / "accounts.json").write_text(json.dumps(
        {"version": 1, "revision": 0, "borradas": [],
         "migrado_secret_txt": False, "cuentas": cuentas}),
        encoding="utf-8")


class TestFuertesFn(unittest.TestCase):
    def setUp(self):
        _escribir_registro({"principal": ["revision-profunda"],
                            "segunda": ["ahorro-tokens"]})

    def test_catalogo_cargado(self):
        nombres = {sk["name"] for sk in gb.skills_indice()["skills"]}
        self.assertEqual(nombres, {"revision-profunda", "ahorro-tokens"})

    def test_factor_pleno_y_nulo(self):
        fn = gb._f4_fuertes_fn()
        self.assertIsNotNone(fn)
        f, sk = fn("principal", {"prompt": "revisa el código buscando fallos"})
        self.assertEqual((f, sk), (1.0, "revision-profunda"))
        f, sk = fn("segunda", {"prompt": "revisa el código buscando fallos"})
        self.assertEqual((f, sk), (0.0, None))
        f, sk = fn("segunda", {"prompt": "ahorra tokens en cada tarea"})
        self.assertEqual((f, sk), (1.0, "ahorro-tokens"))

    def test_sin_fuertes_no_hay_funcion(self):
        _escribir_registro({})
        self.assertIsNone(gb._f4_fuertes_fn())

    def test_fuerte_que_no_existe_no_cuenta(self):
        _escribir_registro({"principal": ["skill-inventada"]})
        self.assertIsNone(gb._f4_fuertes_fn())


class TestConFuertes(unittest.TestCase):
    def setUp(self):
        _escribir_registro({"principal": ["revision-profunda"],
                            "segunda": ["ahorro-tokens"]})

    def test_fuerte_entra_si_encaja(self):
        tarea = {"cuenta": "segunda",
                 "prompt": "ahorra tokens en cada tarea, por favor"}
        out = gb._skills_con_fuertes(tarea, [])
        self.assertEqual([c[0]["name"] for c in out], ["ahorro-tokens"])

    def test_fuerte_no_entra_sin_relacion(self):
        tarea = {"cuenta": "segunda",
                 "prompt": "dibuja un castillo medieval con torres"}
        self.assertEqual(gb._skills_con_fuertes(tarea, []), [])

    def test_sin_cuenta_no_toca_nada(self):
        tarea = {"prompt": "ahorra tokens en cada tarea"}
        self.assertEqual(gb._skills_con_fuertes(tarea, []), [])

    def test_cuenta_desde_el_entorno_de_la_tarea(self):
        # En el runner, la cuenta no viaja en el dict validado: la pone
        # _f4_fijar_entorno_tarea en _ENV_TAREA desde la fila de la cola.
        gb._ENV_TAREA["GROWI_CUENTA_ID"] = "segunda"
        try:
            tarea = {"prompt": "ahorra tokens en cada tarea, por favor"}
            out = gb._skills_con_fuertes(tarea, [])
            self.assertEqual([c[0]["name"] for c in out], ["ahorro-tokens"])
        finally:
            gb._ENV_TAREA.clear()

    def test_fuerte_va_delante_y_respeta_el_tope(self):
        idx = {sk["name"]: sk for sk in gb.skills_indice()["skills"]}
        previa = [(idx["ahorro-tokens"], 9.0, ["tokens"])]
        tarea = {"cuenta": "principal",
                 "prompt": "revisa el código buscando fallos y ahorra tokens"}
        out = gb._skills_con_fuertes(tarea, previa)
        self.assertEqual(out[0][0]["name"], "revision-profunda")
        self.assertLessEqual(len(out), max(3, len(previa)))


if __name__ == "__main__":
    unittest.main()

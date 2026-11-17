# -*- coding: utf-8 -*-
"""Pruebas de los skills «fuertes» por cuenta (Growi Private MQTT, P4):
el campo opcional `fuertes` valida su forma en el registro, los
registros sin el campo (v1) cargan igual, y `fuertes_de` devuelve la
lista limpia. Que el skill exista en el catálogo NO se valida aquí: lo
hace la app al guardar (el registro no conoce el catálogo).

Ejecutar: python3 -m unittest test_cuentas_fuertes
"""
import copy
import tempfile
import unittest
from pathlib import Path

import cuentas


def reg_base():
    return {
        "version": 1, "revision": 0, "borradas": [],
        "migrado_secret_txt": False,
        "cuentas": [
            {"id": "principal", "nombre": "Principal", "asistente": None,
             "carril": "a", "conexion": "servidor", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "hereda", "clases_extra_denegadas": []}},
            {"id": "segunda", "nombre": "Segunda", "asistente": None,
             "carril": "b", "conexion": "ambas", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "hereda", "clases_extra_denegadas": []}},
        ],
    }


class TestValidarFuertes(unittest.TestCase):
    def test_sin_fuertes_valida(self):
        self.assertEqual(cuentas.validar(reg_base()), [])

    def test_fuertes_validos(self):
        r = reg_base()
        r["cuentas"][0]["fuertes"] = ["revision-de-codigo", "ahorro"]
        r["cuentas"][1]["fuertes"] = []
        self.assertEqual(cuentas.validar(r), [])

    def test_fuertes_no_lista(self):
        r = reg_base()
        r["cuentas"][0]["fuertes"] = "revision"
        errores = cuentas.validar(r)
        self.assertTrue(any("fuertes" in e for e in errores), errores)

    def test_fuerte_con_espacios_o_ruta_no_vale(self):
        for malo in ("con espacios", "ruta/skill", "ruta\\skill", "", 42):
            r = reg_base()
            r["cuentas"][1]["fuertes"] = [malo]
            errores = cuentas.validar(r)
            self.assertTrue(any("fuerte inválido" in e for e in errores),
                            (malo, errores))


class TestFuertesDe(unittest.TestCase):
    def test_lista_limpia_sin_duplicados(self):
        r = reg_base()
        r["cuentas"][0]["fuertes"] = ["a1", "b2", "a1", "c3"]
        self.assertEqual(cuentas.fuertes_de(r, "principal"),
                         ["a1", "b2", "c3"])

    def test_sin_campo_y_cuenta_ausente(self):
        r = reg_base()
        self.assertEqual(cuentas.fuertes_de(r, "principal"), [])
        self.assertEqual(cuentas.fuertes_de(r, "nadie"), [])
        self.assertEqual(cuentas.fuertes_de({}, "principal"), [])


class TestCargaV1(unittest.TestCase):
    def test_registro_sin_fuertes_carga_y_guarda(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            r = reg_base()
            cuentas.guardar(base, copy.deepcopy(r))
            cargado = cuentas.cargar(base)
            self.assertFalse(cargado.get("compatibilidad"))
            self.assertEqual(cuentas.fuertes_de(cargado, "principal"), [])
            # Y con fuertes también hace el viaje entero.
            cargado["cuentas"][1]["fuertes"] = ["ahorro-de-tokens"]
            cuentas.guardar(base, cargado)
            otra = cuentas.cargar(base)
            self.assertEqual(cuentas.fuertes_de(otra, "segunda"),
                             ["ahorro-de-tokens"])


if __name__ == "__main__":
    unittest.main()

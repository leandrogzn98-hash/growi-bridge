# -*- coding: utf-8 -*-
"""Pruebas del motor propio por cuenta (Growi Private MQTT, P5): el
campo opcional `motor` valida su forma en el registro, los registros
sin el campo cargan igual y `motor_de` lo lee. Que el motor exista en
engines.json no se valida aquí (lo hace la app al guardar).

Ejecutar: python3 -m unittest test_cuentas_motor
"""
import copy
import tempfile
import unittest
from pathlib import Path

import cuentas
from test_cuentas_fuertes import reg_base


class TestValidarMotor(unittest.TestCase):
    def test_sin_motor_valida(self):
        self.assertEqual(cuentas.validar(reg_base()), [])

    def test_motor_valido(self):
        r = reg_base()
        r["cuentas"][1]["motor"] = "deepseek"
        self.assertEqual(cuentas.validar(r), [])

    def test_motor_invalido(self):
        for malo in ("Con Mayúsculas", "con espacios", "", 42, "a/b"):
            r = reg_base()
            r["cuentas"][0]["motor"] = malo
            errores = cuentas.validar(r)
            self.assertTrue(any("motor inválido" in e for e in errores),
                            (malo, errores))


class TestMotorDe(unittest.TestCase):
    def test_lectura(self):
        r = reg_base()
        self.assertIsNone(cuentas.motor_de(r, "principal"))
        r["cuentas"][0]["motor"] = "kimi"
        self.assertEqual(cuentas.motor_de(r, "principal"), "kimi")
        self.assertIsNone(cuentas.motor_de(r, "nadie"))
        self.assertIsNone(cuentas.motor_de({}, "principal"))

    def test_viaje_entero(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            r = reg_base()
            r["cuentas"][1]["motor"] = "deepseek"
            cuentas.guardar(base, copy.deepcopy(r))
            cargado = cuentas.cargar(base)
            self.assertFalse(cargado.get("compatibilidad"))
            self.assertEqual(cuentas.motor_de(cargado, "segunda"),
                             "deepseek")


if __name__ == "__main__":
    unittest.main()

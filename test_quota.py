# -*- coding: utf-8 -*-
"""Pruebas de quota-tracker.py con cuenta (Fase 2): contadores por
(motor, cuenta), compatibilidad total sin cuenta y reset por periodo."""
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("quota_tracker", os.path.join(AQUI, "quota-tracker.py"))
qt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qt)

CONFIG = {"motores": {
    "claude": {"nombre": "Claude", "tipo": "cuota_mensual", "limite": 100, "unidad": "USD", "reset": "mensual"},
    "gemini": {"nombre": "Gemini", "tipo": "cuota_diaria", "limite": 10, "unidad": "requests/dia", "reset": "diario"},
    "llama": {"nombre": "Llama", "tipo": "ilimitado", "limite": None, "unidad": "local", "reset": "nunca"},
}}


class Reloj:
    def __init__(self, dt):
        self.dt = dt

    def __call__(self):
        return self.dt


class TestQuotaCuenta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.tmp.name, "config-quota.json")
        self.uso = os.path.join(self.tmp.name, "quota-uso.json")
        with open(self.cfg, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f)
        self.reloj = Reloj(datetime(2026, 11, 16, 10, 0, 0))
        self.t = qt.QuotaTracker(self.cfg, self.uso, reloj=self.reloj)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dos_cuentas_contadores_separados(self):
        self.t.registrar_uso("gemini", 4, cuenta="principal")
        self.t.registrar_uso("gemini", 1, cuenta="segunda")
        self.assertEqual(self.t.obtener_estado("gemini", cuenta="principal")["usado"], 4)
        self.assertEqual(self.t.obtener_estado("gemini", cuenta="segunda")["usado"], 1)
        with open(self.uso, encoding="utf-8") as f:
            datos = json.load(f)
        self.assertIn("gemini@principal", datos)
        self.assertIn("gemini@segunda", datos)
        self.assertEqual(datos["gemini"]["usado"], 5.0)  # agregado (doble escritura)

    def test_porcentaje_por_cuenta(self):
        self.t.registrar_uso("gemini", 5, cuenta="principal")
        e = self.t.obtener_estado("gemini", cuenta="principal")
        self.assertEqual(e["porcentaje"], 50)
        self.assertEqual(e["cuenta"], "principal")
        e2 = self.t.obtener_estado("gemini", cuenta="segunda")
        self.assertEqual(e2["porcentaje"], 0)

    def test_sin_cuenta_compatibilidad_exacta(self):
        self.t.registrar_uso("gemini", 3)
        e = self.t.obtener_estado("gemini")
        self.assertNotIn("cuenta", e)
        with open(self.uso, encoding="utf-8") as f:
            datos = json.load(f)
        self.assertEqual(datos["gemini"]["usado"], 3.0)
        self.assertNotIn("gemini@principal", datos)

    def test_doble_escritura_agregado_avanza(self):
        # Revision Fase 2 (B2): con cuenta se escribe la clave por cuenta Y
        # la agregada, para que un lector legacy nunca vea cero (fail-open).
        self.t.registrar_uso("gemini", 3)
        self.t.registrar_uso("gemini", 2, cuenta="principal")
        self.t.registrar_uso("gemini", 1, cuenta="segunda")
        self.assertEqual(self.t.obtener_estado("gemini")["usado"], 6)       # total
        self.assertEqual(self.t.obtener_estado("gemini", cuenta="principal")["usado"], 2)
        self.assertEqual(self.t.obtener_estado("gemini", cuenta="segunda")["usado"], 1)
        with open(self.uso, encoding="utf-8") as f:
            datos = json.load(f)
        self.assertEqual(datos["_v"], 1)

    def test_escritor_legacy_convive(self):
        # Un proceso viejo (sin cuenta) suma al agregado; el uso por cuenta
        # queda como cota inferior, sin duplicar al leer.
        self.t.registrar_uso("gemini", 4, cuenta="principal")
        self.t.registrar_uso("gemini", 3)  # legacy, sin atribuir
        self.assertEqual(self.t.obtener_estado("gemini")["usado"], 7)
        self.assertEqual(self.t.obtener_estado("gemini", cuenta="principal")["usado"], 4)

    def test_reset_periodo_por_cuenta(self):
        self.t.registrar_uso("gemini", 7, cuenta="principal")
        self.reloj.dt = datetime(2026, 11, 17, 9, 0, 0)  # dia siguiente
        self.assertEqual(self.t.obtener_estado("gemini", cuenta="principal")["usado"], 0)
        self.t.registrar_uso("gemini", 2, cuenta="principal")
        self.assertEqual(self.t.obtener_estado("gemini", cuenta="principal")["usado"], 2)

    def test_cuenta_invalida_lanza(self):
        for mala in ("Principal", "con espacio", "-empieza-guion", "", "a" * 40, "../x"):
            with self.assertRaises(ValueError):
                self.t.registrar_uso("gemini", 1, cuenta=mala)
            with self.assertRaises(ValueError):
                self.t.obtener_estado("gemini", cuenta=mala)

    def test_motor_desconocido_sigue_none(self):
        self.assertIsNone(self.t.registrar_uso("noexiste", 1, cuenta="principal"))
        self.assertIsNone(self.t.obtener_estado("noexiste", cuenta="principal"))

    def test_ilimitado_sin_porcentaje(self):
        self.t.registrar_uso("llama", 9, cuenta="principal")
        e = self.t.obtener_estado("llama", cuenta="principal")
        self.assertIsNone(e["porcentaje"])
        self.assertTrue(e["ilimitado"])

    def test_obtener_todos_y_para_estado_con_cuenta(self):
        self.t.registrar_uso("claude", 25, cuenta="principal")
        todos = self.t.obtener_todos(cuenta="principal")
        self.assertEqual(todos["claude"]["porcentaje"], 25)
        pe = self.t.para_estado(cuenta="principal")
        self.assertEqual(pe["claude"]["usado"], 25)
        # El agregado sin cuenta tambien ve el uso (doble escritura, B2).
        self.assertEqual(self.t.para_estado()["claude"]["usado"], 25)


if __name__ == "__main__":
    unittest.main(verbosity=2)

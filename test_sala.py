#!/usr/bin/env python3
"""Pruebas de sala.py (P3 de Growi Private MQTT): el registro con
redacción y el reparto conversado."""
import json
import tempfile
import unittest
from pathlib import Path

import sala


class TestSala(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()

    def test_escribir_y_leer(self):
        sala.escribir(self.base, "dueno", "dueño", "quiero que hagan X")
        sala.escribir(self.base, "cuenta", "rayo", "yo me quedo con la 1")
        msgs = sala.leer(self.base)
        self.assertEqual([m["tipo"] for m in msgs], ["dueno", "cuenta"])
        self.assertEqual(msgs[1]["autor"], "rayo")

    def test_tipo_desconocido_rechazado(self):
        with self.assertRaises(ValueError):
            sala.escribir(self.base, "grito", "x", "hola")

    def test_redaccion_patrones_y_valores(self):
        sala.escribir(self.base, "cuenta", "lu",
                      "mi clave es ghp_1234567890abcdefghij y la tuya "
                      "CLAVESECRETA99 vale",
                      valores=["CLAVESECRETA99"])
        texto = sala.leer(self.base)[0]["texto"]
        self.assertNotIn("ghp_1234567890abcdefghij", texto)
        self.assertNotIn("CLAVESECRETA99", texto)
        self.assertIn("•••", texto)

    def test_leer_tolera_corruptas_y_deduplica(self):
        mid = sala.escribir(self.base, "sistema", "growi", "aviso")
        ruta = Path(self.base) / "sala.jsonl"
        with open(ruta, "a", encoding="utf-8") as f:
            f.write("{linea rota\n")
            f.write(json.dumps({"id": mid, "tipo": "sistema",
                                "autor": "growi", "texto": "duplicado"}) + "\n")
        msgs = sala.leer(self.base)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["texto"], "aviso")

    def test_texto_acotado(self):
        sala.escribir(self.base, "cuenta", "lu", "x" * 9000)
        self.assertLessEqual(len(sala.leer(self.base)[0]["texto"]),
                             sala.TOPE_TEXTO)


class TestReparto(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        sala.reparto_crear(self.base, "enc-1", "principal", [
            {"sid": "enc-1-s1", "titulo": "parte A", "cuenta": "principal"},
            {"sid": "enc-1-s2", "titulo": "parte B", "cuenta": "segunda"}])

    def test_aceptar_solo_la_asignada(self):
        self.assertFalse(sala.reparto_aceptar(self.base, "enc-1",
                                              "enc-1-s1", "segunda"))
        self.assertTrue(sala.reparto_aceptar(self.base, "enc-1",
                                             "enc-1-s1", "principal"))
        rep = sala.reparto_obtener(self.base, "enc-1")
        self.assertTrue(rep["fases"]["enc-1-s1"]["aceptada"])
        self.assertFalse(sala.reparto_todo_aceptado(rep))

    def test_reclamar_reasigna_y_acepta(self):
        self.assertTrue(sala.reparto_reclamar(self.base, "enc-1",
                                              "enc-1-s2", "principal",
                                              peso=80))
        rep = sala.reparto_obtener(self.base, "enc-1")
        f = rep["fases"]["enc-1-s2"]
        self.assertEqual((f["cuenta"], f["aceptada"], f["peso"]),
                         ("principal", True, 80))

    def test_reasignar_del_dueno_devuelve_a_pendiente(self):
        sala.reparto_aceptar(self.base, "enc-1", "enc-1-s1", "principal")
        sala.reparto_reasignar(self.base, "enc-1", "enc-1-s1", "segunda")
        rep = sala.reparto_obtener(self.base, "enc-1")
        f = rep["fases"]["enc-1-s1"]
        self.assertEqual((f["cuenta"], f["aceptada"]), ("segunda", False))

    def test_estados(self):
        self.assertTrue(sala.reparto_estado(self.base, "enc-1", "resuelto"))
        self.assertEqual(sala.reparto_obtener(self.base)["estado"],
                         "resuelto")
        with self.assertRaises(ValueError):
            sala.reparto_estado(self.base, "enc-1", "volando")

    def test_reparto_inexistente(self):
        self.assertIsNone(sala.reparto_obtener(self.base, "enc-999"))
        self.assertFalse(sala.reparto_aceptar(self.base, "enc-999",
                                              "s1", "principal"))


if __name__ == "__main__":
    unittest.main()

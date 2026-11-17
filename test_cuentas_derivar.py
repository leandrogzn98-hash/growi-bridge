"""Pruebas de derivar_id y carril_libre (Reforma de cuentas).

El alta nueva solo pide el nombre: el identificador se deriva y el
carril se asigna solo. Ejecutar: python3 -m unittest test_cuentas_derivar
"""
import unittest

import cuentas


def reg_con(*cuentas_lista):
    return {"version": 1, "revision": 0, "borradas": [],
            "migrado_secret_txt": False, "cuentas": list(cuentas_lista)}


def cuenta(cid, carril=None, habilitada=True):
    return {"id": cid, "nombre": cid, "asistente": None, "carril": carril,
            "conexion": "servidor", "habilitada": habilitada, "creada": None,
            "permisos": {"modo": "hereda", "clases_extra_denegadas": []}}


class TestDerivarId(unittest.TestCase):
    def test_nombre_simple(self):
        self.assertEqual(cuentas.derivar_id("Rayo", []), "rayo")
        self.assertEqual(cuentas.derivar_id("segunda", []), "segunda")

    def test_acentos_y_espacios(self):
        self.assertEqual(cuentas.derivar_id("José María", []), "jose-maria")
        self.assertEqual(cuentas.derivar_id("  Mi  Cuenta  ", []), "mi-cuenta")

    def test_correo(self):
        self.assertEqual(cuentas.derivar_id("lu@correo.com", []),
                         "lu-correo-com")

    def test_choque_con_vivo_y_con_lapida(self):
        self.assertEqual(cuentas.derivar_id("Rayo", ["rayo"]), "rayo-2")
        self.assertEqual(cuentas.derivar_id("Rayo", ["rayo", "rayo-2"]),
                         "rayo-3")
        # La lápida cuenta igual: un id borrado no se reutiliza.
        self.assertEqual(cuentas.derivar_id("Segunda", ["segunda"]),
                         "segunda-2")

    def test_nombre_sin_nada_valido(self):
        for nombre in ("", "   ", "!!!", None, "á"):
            self.assertEqual(cuentas.derivar_id(nombre, []), "cuenta", nombre)
        self.assertEqual(cuentas.derivar_id("", ["cuenta"]), "cuenta-2")

    def test_nombre_largo_recortado_y_valido(self):
        cid = cuentas.derivar_id("una cuenta con un nombre larguisimo de verdad",
                                 [])
        self.assertLessEqual(len(cid), 32)
        self.assertTrue(cuentas._RX_ID.fullmatch(cid), cid)
        # Con choque, el sufijo también cabe en 32.
        cid2 = cuentas.derivar_id("una cuenta con un nombre larguisimo de verdad",
                                  [cid])
        self.assertLessEqual(len(cid2), 32)
        self.assertTrue(cuentas._RX_ID.fullmatch(cid2), cid2)
        self.assertNotEqual(cid, cid2)

    def test_el_resultado_siempre_es_un_id_valido(self):
        for nombre in ("Rayo", "x", "123", "a b c", "Ñandú", "a-b", "--"):
            cid = cuentas.derivar_id(nombre, [])
            self.assertTrue(cuentas._RX_ID.fullmatch(cid), (nombre, cid))


class TestCarrilLibre(unittest.TestCase):
    def test_sin_cuentas(self):
        self.assertEqual(cuentas.carril_libre(reg_con()), "a")

    def test_a_ocupado_devuelve_b(self):
        reg = reg_con(cuenta("principal", carril="a"))
        self.assertEqual(cuentas.carril_libre(reg), "b")

    def test_ambos_ocupados_devuelve_none(self):
        reg = reg_con(cuenta("principal", carril="a"),
                      cuenta("segunda", carril="b"))
        self.assertIsNone(cuentas.carril_libre(reg))

    def test_deshabilitada_no_ocupa(self):
        reg = reg_con(cuenta("principal", carril="a", habilitada=False),
                      cuenta("segunda", carril="b"))
        self.assertEqual(cuentas.carril_libre(reg), "a")

    def test_sin_carril_no_ocupa(self):
        reg = reg_con(cuenta("principal", carril=None))
        self.assertEqual(cuentas.carril_libre(reg), "a")


if __name__ == "__main__":
    unittest.main(verbosity=2)

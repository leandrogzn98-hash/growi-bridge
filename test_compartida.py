"""Pruebas de la bóveda compartida (Reforma de cuentas).

El registro guarda solo NOMBRES (etiqueta, nota, fecha); los valores
viven en el almacén de credenciales con el nombre compartido:<etiqueta>
y jamás pasan por este módulo. Ejecutar: python3 -m unittest
test_compartida
"""
import json
import tempfile
import unittest
from pathlib import Path

import compartida

CENTINELA = "VALOR-CENTINELA-que-no-debe-aparecer-12345"


class TestCompartida(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_agregar_listar_quitar(self):
        e = compartida.agregar(self.base, "github", "para los repos")
        self.assertEqual(e["etiqueta"], "github")
        self.assertEqual(e["nota"], "para los repos")
        self.assertTrue(e["creada"])
        compartida.agregar(self.base, "correo")
        self.assertEqual([x["etiqueta"] for x in compartida.listar(self.base)],
                         ["github", "correo"])
        self.assertTrue(compartida.quitar(self.base, "github"))
        self.assertEqual([x["etiqueta"] for x in compartida.listar(self.base)],
                         ["correo"])
        self.assertFalse(compartida.quitar(self.base, "github"))

    def test_el_registro_no_contiene_el_valor(self):
        # El flujo real: el valor va al almacén (aquí, un dict que hace
        # de bóveda) con nombre_valor(); el registro solo ve la etiqueta.
        boveda = {}
        compartida.agregar(self.base, "github", "para los repos")
        boveda[compartida.nombre_valor("github")] = CENTINELA
        texto = (self.base / "boveda-compartida.json").read_text(
            encoding="utf-8")
        self.assertNotIn(CENTINELA, texto)
        datos = json.loads(texto)
        for entrada in datos["entradas"]:
            self.assertEqual(set(entrada), {"etiqueta", "nota", "creada"})
        self.assertEqual(compartida.nombre_valor("github"),
                         "compartido:github")

    def test_etiqueta_invalida(self):
        for mala in ("", "  ", "GitHub", "con espacios", "-empieza-guion",
                     "_empieza-bajo", "a" * 42, "ñandu", None):
            with self.assertRaises(compartida.ErrorCompartida, msg=repr(mala)):
                compartida.agregar(self.base, mala)
        self.assertEqual(compartida.listar(self.base), [])

    def test_etiqueta_duplicada(self):
        compartida.agregar(self.base, "github")
        with self.assertRaises(compartida.ErrorCompartida):
            compartida.agregar(self.base, "github")

    def test_cargar_corrupto_no_lanza(self):
        (self.base / "boveda-compartida.json").write_text("{roto",
                                                          encoding="utf-8")
        self.assertEqual(compartida.cargar(self.base)["entradas"], [])
        self.assertEqual(compartida.listar(self.base), [])

    def test_sin_archivo_registro_vacio(self):
        reg = compartida.cargar(self.base)
        self.assertEqual(reg["entradas"], [])
        self.assertEqual(reg["revision"], 0)

    def test_la_revision_sube(self):
        compartida.agregar(self.base, "github")
        self.assertEqual(compartida.cargar(self.base)["revision"], 1)
        compartida.agregar(self.base, "correo")
        self.assertEqual(compartida.cargar(self.base)["revision"], 2)
        compartida.quitar(self.base, "github")
        self.assertEqual(compartida.cargar(self.base)["revision"], 3)

    def test_guardar_con_revision_vieja_se_rechaza(self):
        reg = compartida.cargar(self.base)
        compartida.agregar(self.base, "github")  # la revisión pasa a 1
        with self.assertRaises(compartida.ErrorCompartida):
            compartida.guardar(self.base, reg)

    def test_etiquetas_al_limite(self):
        self.assertTrue(compartida.etiqueta_valida("a" * 41))
        self.assertTrue(compartida.etiqueta_valida("a"))
        self.assertTrue(compartida.etiqueta_valida("mi-clave_2"))
        self.assertFalse(compartida.etiqueta_valida("a" * 42))


if __name__ == "__main__":
    unittest.main(verbosity=2)

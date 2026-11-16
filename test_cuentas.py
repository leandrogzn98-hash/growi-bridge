"""Pruebas del registro de cuentas (Fase 1). Ejecutar: python3 test_cuentas.py"""
import json
import tempfile
import unittest
from pathlib import Path

import cuentas


class AlmacenFalso:
    """Bóveda en memoria con los nombres como claves (aislamiento por nombre)."""

    def __init__(self):
        self.d = {}

    def get(self, nombre):
        return self.d.get(nombre)

    def set(self, nombre, valor):
        self.d[nombre] = valor


def reg_dos_cuentas():
    return {
        "version": 1,
        "migrado_secret_txt": True,
        "cuentas": [
            {"id": "principal", "nombre": "Muse A", "asistente": "a.md",
             "carril": "a", "conexion": "ambas", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "hereda", "clases_extra_denegadas": []}},
            {"id": "segunda", "nombre": "Muse B", "asistente": "b.md",
             "carril": "b", "conexion": "local", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "restringido",
                          "clases_extra_denegadas": ["borrar"]}},
        ],
    }


class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_guardar_y_cargar(self):
        cuentas.guardar(self.base, reg_dos_cuentas())
        reg = cuentas.cargar(self.base)
        self.assertFalse(reg["compatibilidad"])
        self.assertEqual([c["id"] for c in reg["cuentas"]],
                         ["principal", "segunda"])
        self.assertEqual(cuentas.cuenta_de_carril(reg, "b")["id"], "segunda")

    def test_sin_archivo_compatibilidad(self):
        reg = cuentas.cargar(self.base, carril="a", asistente="x.md")
        self.assertTrue(reg["compatibilidad"])
        self.assertEqual(reg["cuentas"][0]["carril"], "a")

    def test_archivo_corrupto_compatibilidad(self):
        (self.base / "accounts.json").write_text("{esto no es json",
                                                 encoding="utf-8")
        self.assertTrue(cuentas.cargar(self.base)["compatibilidad"])

    def test_validacion(self):
        reg = reg_dos_cuentas()
        reg["cuentas"][1]["carril"] = "a"  # carril duplicado
        self.assertTrue(any("compartido" in e for e in cuentas.validar(reg)))
        reg = reg_dos_cuentas()
        reg["cuentas"][0]["id"] = "ID Malo"
        self.assertTrue(any("inválido" in e for e in cuentas.validar(reg)))
        reg = reg_dos_cuentas()
        reg["cuentas"][1]["conexion"] = "nube"
        self.assertTrue(any("conexion" in e for e in cuentas.validar(reg)))
        with self.assertRaises(cuentas.ErrorRegistro):
            cuentas.guardar(self.base, reg)

    def test_aislamiento_de_secretos(self):
        alm = AlmacenFalso()
        alm.set(cuentas.nombre_secreto("principal"), "secreto-A")
        alm.set(cuentas.nombre_secreto("segunda"), "secreto-B")
        reg = reg_dos_cuentas()
        self.assertEqual(cuentas.secreto_de(reg, "principal", alm.get),
                         "secreto-A")
        self.assertEqual(cuentas.secreto_de(reg, "segunda", alm.get),
                         "secreto-B")
        self.assertIsNone(cuentas.secreto_de(reg, "tercera", alm.get))


class TestMigracion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.alm = AlmacenFalso()

    def tearDown(self):
        self.tmp.cleanup()

    def _migrar(self, valor="secreto-historico"):
        return cuentas.migrar(self.base, lambda: valor,
                              self.alm.get, self.alm.set,
                              carril="a", asistente="a.md")

    def test_migra_y_es_idempotente(self):
        r1 = self._migrar()
        self.assertTrue(r1["migrado"])
        self.assertEqual(self.alm.get("muse:principal"), "secreto-historico")
        reg = cuentas.cargar(self.base)
        self.assertFalse(reg["compatibilidad"])
        self.assertTrue(reg["migrado_secret_txt"])
        r2 = self._migrar()  # segunda vez: no toca nada
        self.assertFalse(r2["migrado"])

    def test_sin_secret_no_migra(self):
        r = cuentas.migrar(self.base, lambda: "", self.alm.get, self.alm.set)
        self.assertFalse(r["migrado"])
        self.assertFalse((self.base / "accounts.json").exists())

    def test_aborta_si_la_boveda_no_verifica(self):
        class BovedaRota(AlmacenFalso):
            def get(self, nombre):
                return "otro-valor"
        rota = BovedaRota()
        r = cuentas.migrar(self.base, lambda: "secreto-historico",
                           rota.get, rota.set)
        self.assertFalse(r["migrado"])
        self.assertFalse((self.base / "accounts.json").exists())

    def test_el_registro_no_contiene_secretos(self):
        self._migrar()
        texto = (self.base / "accounts.json").read_text(encoding="utf-8")
        self.assertNotIn("secreto-historico", texto)
        json.loads(texto)  # y sigue siendo JSON válido


def registro_valido():
    r = reg_dos_cuentas()
    r["cuentas"] = r["cuentas"][:1]
    return r


class TestRevisionYConcurrencia(unittest.TestCase):
    def test_la_revision_sube_al_guardar(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            reg = registro_valido()
            cuentas.guardar(base, reg)
            self.assertEqual(reg["revision"], 1)
            reg["cuentas"][0]["nombre"] = "Otro nombre"
            cuentas.guardar(base, reg)
            self.assertEqual(reg["revision"], 2)
            self.assertEqual(cuentas.cargar(base)["revision"], 2)

    def test_guardar_con_revision_vieja_se_rechaza(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            reg = registro_valido()
            cuentas.guardar(base, reg)  # revision 1
            copia_vieja = registro_valido()  # revision 0, como otro proceso
            with self.assertRaises(cuentas.ErrorRegistro):
                cuentas.guardar(base, copia_vieja)


class TestInvariantesNuevas(unittest.TestCase):
    def test_id_con_guion_en_los_extremos_invalido(self):
        for malo in ("-segunda", "segunda-", "a", "Segunda"):
            reg = registro_valido()
            reg["cuentas"][0]["id"] = malo
            self.assertTrue(cuentas.validar(reg), malo)

    def test_id_borrado_no_se_reutiliza(self):
        reg = registro_valido()
        reg["cuentas"][0]["id"] = "segunda"
        reg["borradas"] = [{"id": "segunda", "ts": "2026-11-16T00:00:00"}]
        self.assertTrue(any("ya usado y borrado" in e
                            for e in cuentas.validar(reg)))

    def test_principal_no_se_puede_deshabilitar(self):
        reg = registro_valido()
        reg["cuentas"][0]["habilitada"] = False
        self.assertTrue(any("principal" in e for e in cuentas.validar(reg)))

    def test_asistente_con_ruta_invalido(self):
        reg = registro_valido()
        reg["cuentas"][0]["asistente"] = "../fuera"
        self.assertTrue(cuentas.validar(reg))
        reg["cuentas"][0]["asistente"] = "growi"
        self.assertEqual(cuentas.validar(reg), [])

    def test_clase_denegada_con_formato_invalido(self):
        reg = registro_valido()
        reg["cuentas"][0]["permisos"] = {
            "modo": "restringido", "clases_extra_denegadas": ["Borrar Todo"]}
        self.assertTrue(cuentas.validar(reg))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Pruebas de los avisos al dueño (Fase 4): guardar primero, despachar
después; deduplicación por clave en ventana; el CanalNulo no envía.

Ejecutar: python3 -m unittest test_avisos
"""
import json
import tempfile
import unittest
from pathlib import Path

import avisos


class TestAvisos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        avisos.fijar_destino_local(None)
        self.tmp.cleanup()

    def _lineas(self):
        ruta = self.base / "avisos.jsonl"
        if not ruta.exists():
            return []
        return [json.loads(l) for l in
                ruta.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_guardado_aunque_todos_los_destinos_fallen(self):
        class DestinoRoto:
            nombre = "roto"

            def enviar(self, aviso):
                raise RuntimeError("destino caído")

        avisos.registrar_destino("local", DestinoRoto())
        try:
            av = avisos.emitir(self.base, "encargo_terminado", "se cerró",
                               cuenta="principal", raiz="enc-20260101-abcdef01")
        finally:
            avisos.registrar_destino("local", avisos._LOCAL)
        self.assertIsNotNone(av)
        lineas = self._lineas()
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0]["tipo"], "encargo_terminado")
        self.assertEqual(lineas[0]["cuenta"], "principal")
        self.assertTrue(lineas[0]["id"].startswith("av-"))

    def test_destino_local_recibe_tras_guardar(self):
        recibidos = []
        avisos.fijar_destino_local(lambda a: recibidos.append(a) or True)
        avisos.emitir(self.base, "division_hecha", "dividido en 2")
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0]["tipo"], "division_hecha")
        self.assertEqual(len(self._lineas()), 1)

    def test_dedup_misma_clave_en_ventana(self):
        t = [1000.0]
        reloj = lambda: t[0]
        a1 = avisos.emitir(self.base, "cuenta_sin_latido", "caída",
                           cuenta="segunda", reloj=reloj)
        t[0] += 60
        a2 = avisos.emitir(self.base, "cuenta_sin_latido", "sigue caída",
                           cuenta="segunda", reloj=reloj)
        self.assertIsNotNone(a1)
        self.assertIsNone(a2)  # suprimido por deduplicación
        self.assertEqual(len(self._lineas()), 1)
        # Otra cuenta: otra clave, sí se emite.
        a3 = avisos.emitir(self.base, "cuenta_sin_latido", "caída",
                           cuenta="principal", reloj=reloj)
        self.assertIsNotNone(a3)
        # Fuera de la ventana (10 min), se vuelve a emitir.
        t[0] += 601
        a4 = avisos.emitir(self.base, "cuenta_sin_latido", "sigue caída",
                           cuenta="segunda", reloj=reloj)
        self.assertIsNotNone(a4)

    def test_sin_dedup_para_hechos_unicos(self):
        avisos.emitir(self.base, "encargo_terminado", "uno", raiz="enc-x")
        avisos.emitir(self.base, "encargo_terminado", "otro", raiz="enc-x")
        self.assertEqual(len(self._lineas()), 2)

    def test_canal_nulo_no_envia_y_lo_dice(self):
        canal = avisos.CanalNulo()
        self.assertFalse(canal.disponible())
        self.assertFalse(canal.enviar({"tipo": "x"}))
        # Con el canal en la config, emitir no falla y el aviso queda
        # solo en el registro.
        (self.base / "avisos-config.json").write_text(
            json.dumps({"destinos": ["registro", "canal"],
                        "canal": "nulo"}), encoding="utf-8")
        av = avisos.emitir(self.base, "bloqueo_dueno", "algo pasa")
        self.assertIsNotNone(av)
        self.assertEqual(len(self._lineas()), 1)

    def test_registrar_canal_fija_el_contrato(self):
        class CanalFalso:
            nombre = "canal"
            enviados = []

            def disponible(self):
                return True

            def enviar(self, aviso):
                self.enviados.append(aviso)
                return True

        avisos.registrar_canal("falso", CanalFalso)
        try:
            (self.base / "avisos-config.json").write_text(
                json.dumps({"destinos": ["registro", "canal"],
                            "canal": "falso"}), encoding="utf-8")
            avisos.emitir(self.base, "encargo_recibido", "hola")
            self.assertEqual(len(CanalFalso.enviados), 1)
        finally:
            avisos._CANALES.pop("falso", None)

    def test_rotacion(self):
        tope = avisos.TOPE_BYTES
        avisos.TOPE_BYTES = 200
        try:
            for i in range(6):
                avisos.emitir(self.base, "encargo_terminado",
                              f"cierre número {i} con texto de relleno "
                              "para hacer crecer el registro")
        finally:
            avisos.TOPE_BYTES = tope
        self.assertTrue((self.base / "avisos.jsonl.1").exists())
        self.assertTrue((self.base / "avisos.jsonl").exists())

    def test_leer_recientes(self):
        for i in range(5):
            avisos.emitir(self.base, "encargo_terminado", f"cierre {i}")
        recientes = avisos.leer_recientes(self.base, 3)
        self.assertEqual(len(recientes), 3)
        self.assertEqual(recientes[0]["texto"], "cierre 4")
        self.assertEqual(avisos.leer_recientes(self.base / "nada"), [])


if __name__ == "__main__":
    unittest.main()

"""Pruebas del vigilante externo (Fase 4): stdlib pura, relanza carriles
muertos con tope de 3 por hora y jamás mata un proceso vivo.

Ejecutar: python3 -m unittest test_vigilante
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

import vigilante


class TestEvaluar(unittest.TestCase):
    def setUp(self):
        self.ahora = time.time()

    def _status(self, pid=1234, edad=400):
        return {"pid": pid, "last_poll": time.strftime(
            "%Y-%m-%dT%H:%M:%S%z",
            time.localtime(self.ahora - edad))}

    def test_pid_muerto_y_poll_viejo_relanza(self):
        self.assertEqual(
            vigilante.evaluar_carril(self._status(), self.ahora,
                                     lambda pid: False),
            "relanzar")

    def test_pid_vivo_y_poll_viejo_solo_avisa(self):
        self.assertEqual(
            vigilante.evaluar_carril(self._status(), self.ahora,
                                     lambda pid: True),
            "avisar")

    def test_poll_fresco_nada(self):
        self.assertEqual(
            vigilante.evaluar_carril(self._status(edad=10), self.ahora,
                                     lambda pid: False),
            "nada")

    def test_sin_estado_legible_no_se_actua(self):
        self.assertEqual(vigilante.evaluar_carril(
            None, self.ahora, lambda pid: False), "nada")
        self.assertEqual(vigilante.evaluar_carril(
            {"pid": 1, "last_poll": "basura"}, self.ahora,
            lambda pid: False), "nada")


class TestTope(unittest.TestCase):
    def test_tope_tres_por_hora(self):
        ahora = time.time()
        estado = {"relanzamientos": {"a": [ahora - 10, ahora - 20,
                                           ahora - 30]}}
        self.assertFalse(vigilante.puede_relanzar(estado, "a", ahora))
        estado2 = {"relanzamientos": {"a": [ahora - 3700, ahora - 3800,
                                            ahora - 3900]}}
        self.assertTrue(vigilante.puede_relanzar(estado2, "a", ahora))


class TestInspeccionar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.app = self.base / "app-a"
        self.app.mkdir()
        self.ahora = time.time()
        (self.app / "runner-status.json").write_text(json.dumps({
            "pid": 4321,
            "last_poll": time.strftime("%Y-%m-%dT%H:%M:%S%z",
                                       time.localtime(self.ahora - 500)),
        }), encoding="utf-8")
        self.config = {"base": str(self.base),
                       "carriles": [{"nombre": "a", "dir": str(self.app),
                                     "arranque": ["python3", "x.py"]}]}
        self.relanzados = []
        self.avisos = []

    def tearDown(self):
        self.tmp.cleanup()

    def _inspeccionar(self, estado):
        return vigilante.inspeccionar(
            self.config, estado, ahora=self.ahora,
            pid_vivo=lambda pid: False,
            relanzar=lambda c: self.relanzados.append(c["nombre"]),
            avisar=lambda t: self.avisos.append(t))

    def test_relanza_el_carril_muerto(self):
        estado = self._inspeccionar({})
        self.assertEqual(self.relanzados, ["a"])
        self.assertEqual(len(estado["relanzamientos"]["a"]), 1)

    def test_superado_el_tope_avisa_una_vez_y_no_relanza(self):
        estado = {"relanzamientos": {"a": [self.ahora - 1,
                                           self.ahora - 2,
                                           self.ahora - 3]},
                  "bloqueo_avisado": {}}
        estado = self._inspeccionar(estado)
        self.assertEqual(self.relanzados, [])
        self.assertEqual(len(self.avisos), 1)
        estado = self._inspeccionar(estado)
        self.assertEqual(len(self.avisos), 1)  # no repite el aviso

    def test_aviso_minimo_en_el_registro_compartido(self):
        self.assertTrue(vigilante.escribir_aviso(
            self.base, "bloqueo_dueno", "el carril a sigue caído"))
        lineas = (self.base / "avisos.jsonl").read_text(
            encoding="utf-8").splitlines()
        datos = json.loads(lineas[0])
        self.assertEqual(datos["tipo"], "bloqueo_dueno")
        self.assertEqual(datos["origen"], "vigilante")
        self.assertTrue(datos["id"].startswith("av-"))


if __name__ == "__main__":
    unittest.main()

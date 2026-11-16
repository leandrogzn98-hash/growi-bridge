"""Pruebas de las pruebas físicas (Fase 4): el clasificador marca las
no marcadas, en presente van al circuito de aprobaciones y solo corren
con un permiso de un solo uso consumido al recoger, «aplazar» es una
aprobación programada que no arranca ni un segundo antes y no vuelve a
preguntar, sin respuesta vencen sin ejecutarse, y en ausente corren
avisando antes con la foto de recursos en el resultado.

El monolito se importa con el entorno aislado. Ejecutar:
python3 -m unittest test_pruebas_fisicas
"""
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="gb-pruebas-")
os.environ["GROWI_BRIDGE_SHARE"] = str(Path(_TMP) / "share")
os.environ["GROWI_BRIDGE_COLA"] = str(Path(_TMP) / "cola.db")
os.environ["XDG_DATA_HOME"] = str(Path(_TMP) / "xdg")

_spec = importlib.util.spec_from_file_location(
    "gb_pruebas", str(Path(__file__).with_name("growi-bridge.py")))
gb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gb)

import presencia  # noqa: E402

CUENTAS = {
    "version": 1, "revision": 1, "borradas": [],
    "cuentas": [
        {"id": "principal", "nombre": "Principal", "carril": "a",
         "conexion": "ambas", "habilitada": True},
        {"id": "segunda", "nombre": "Segunda", "carril": "b",
         "conexion": "ambas", "habilitada": True},
    ],
}
PRUEBA = {"clase": "medicion", "detalle": "medir el rendimiento de "
          "todo el equipo", "duracion_est_min": 15,
          "impacto": "carga la PC entera"}


class Base(unittest.TestCase):
    def setUp(self):
        os.environ["XDG_DATA_HOME"] = str(Path(_TMP) / "xdg")
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.app = raiz / "app"
        self.app.mkdir()
        (self.app / "accounts.json").write_text(
            json.dumps(CUENTAS), encoding="utf-8")
        gb.APP_DIR = self.app
        gb.LOG_FILE = raiz / "gb.log"
        gb.COLA_DB = raiz / "cola.db"
        gb._CUENTAS_CACHE.update(clave=None, reg=None)
        for d in (gb.TASKS, gb.PROCESSING, gb.DONE, gb.RESULTS, gb.WAITING,
                  gb.APR_PEDIDOS):
            d.mkdir(parents=True, exist_ok=True)
            for p in d.glob("*"):
                if p.is_file():
                    p.unlink()
        base = gb._base_tablero()
        for p in base.glob("*"):
            if p.is_file():
                p.unlink()
        gb.cola_init()
        gb._TABLERO["estado"] = "activa"
        gb._F4_PRUEBAS_AUSENTE.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def _tarea(self, tid="t-fisica-1", **extra):
        datos = {"id": tid, "prompt": PRUEBA["detalle"],
                 "cwd": str(Path.home()), "motor": "claude",
                 "tipo": "prueba_fisica", "prueba": dict(PRUEBA)}
        datos.update(extra)
        p = gb.TASKS / f"{tid}.task.json"
        p.write_text(json.dumps(datos), encoding="utf-8")
        return p, datos

    def _aparcar(self, tid="t-fisica-1"):
        p, datos = self._tarea(tid)
        self.assertEqual(gb._f4_modo(), "presente")
        self.assertEqual(gb._f4_prueba_puerta(p, datos, dict(PRUEBA)),
                         "aparcada")
        rows = gb._cola("SELECT * FROM aprobaciones WHERE tarea=?",
                        (tid,), fetch=True)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _avisos(self):
        ruta = gb._base_tablero() / "avisos.jsonl"
        return ruta.read_text(encoding="utf-8") if ruta.exists() else ""


class TestClasificador(unittest.TestCase):
    def test_marca_la_no_marcada(self):
        b = gb._f4_prueba_de({"prompt": "mide el rendimiento de todo "
                                        "el equipo, por favor"})
        self.assertEqual(b["clase"], "medicion")
        b2 = gb._f4_prueba_de({"prompt": "abre el juego para probar "
                                         "el nivel nuevo"})
        self.assertEqual(b2["clase"], "ejecutar_proyecto")

    def test_la_declarada_manda(self):
        b = gb._f4_prueba_de({"tipo": "prueba_fisica",
                              "prueba": dict(PRUEBA),
                              "prompt": "otra cosa"})
        self.assertEqual(b["clase"], "medicion")
        self.assertEqual(b["duracion_est_min"], 15)

    def test_una_tarea_normal_no_es_prueba(self):
        self.assertIsNone(gb._f4_prueba_de(
            {"prompt": "escribe un informe sobre el nivel 2"}))


class TestPresente(Base):
    def test_se_aparca_con_su_bloque_en_el_pedido(self):
        row = self._aparcar()
        self.assertEqual(row["estado"], "pendiente")
        self.assertIn("prueba_fisica", row["acciones"])
        self.assertIn("PRUEBA FÍSICA", row["motivo"])
        pedido = json.loads((gb.APR_PEDIDOS
                             / f"{row['approval_id']}.pedido.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(pedido["prueba"]["clase"], "medicion")
        self.assertFalse((gb.TASKS / "t-fisica-1.task.json").exists())
        self.assertTrue((gb.WAITING / "t-fisica-1.task.json").exists())
        self.assertIn("prueba_fisica_pendiente", self._avisos())

    def test_aplazar_es_una_aprobacion_programada(self):
        row = self._aparcar()
        antes = time.time()
        hecho, msg = gb.decidir_aprobacion(
            row["approval_id"], "aplazar", minutos=30)
        self.assertTrue(hecho, msg)
        row2 = gb.apr_get(row["approval_id"])
        self.assertEqual(row2["estado"], "aprobada")
        self.assertIn("aplazada 30 min", row2["resultado"])
        cola = gb.cola_get("t-fisica-1")
        self.assertIsNotNone(cola["proximo_intento"])
        self.assertAlmostEqual(cola["proximo_intento"], antes + 1800,
                               delta=10)
        # No arranca ni un segundo antes: sigue en la espera de la cola.
        self.assertIn("t-fisica-1.task.json", gb.cola_en_espera())
        # La aprobada-aplazada NO vence por el barrido de vencimientos.
        gb.aprobaciones_vencer(time.time() + 7200)
        self.assertEqual(gb.apr_get(row["approval_id"])["estado"],
                         "aprobada")
        # Al recogerla, el permiso se consume (B7) y corre sin que se
        # vuelva a preguntar.
        p = gb.TASKS / "t-fisica-1.task.json"
        datos = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(
            gb._f4_prueba_puerta(p, datos, dict(PRUEBA)), "correr")
        self.assertEqual(gb.apr_get(row["approval_id"])["estado"],
                         "consumida")

    def test_aprobar_y_correr_consume_el_permiso(self):
        row = self._aparcar()
        hecho, msg = gb.decidir_aprobacion(row["approval_id"], "aprobar")
        self.assertTrue(hecho, msg)
        p = gb.TASKS / "t-fisica-1.task.json"
        self.assertTrue(p.exists())
        datos = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(
            gb._f4_prueba_puerta(p, datos, dict(PRUEBA)), "correr")
        self.assertEqual(gb.apr_get(row["approval_id"])["estado"],
                         "consumida")

    def test_sin_respuesta_vence_sin_ejecutarse(self):
        row = self._aparcar()
        gb.aprobaciones_vencer(time.time() + 100000)
        row2 = gb.apr_get(row["approval_id"])
        self.assertEqual(row2["estado"], "vencida")
        self.assertIn("no se ejecutó nada", row2["resultado"])
        cola = gb.cola_get("t-fisica-1")
        self.assertIn(cola["estado"], gb.COLA_FINALES)
        self.assertFalse((gb.TASKS / "t-fisica-1.task.json").exists())


class TestAusente(Base):
    def test_en_ausente_corre_avisando_y_con_foto_de_recursos(self):
        presencia.poner_override(gb._base_tablero(), "ausente")
        self.assertEqual(gb._f4_modo(), "ausente")
        p, datos = self._tarea()
        self.assertEqual(
            gb._f4_prueba_puerta(p, datos, dict(PRUEBA)), "correr")
        self.assertIn("prueba_fisica_inicio", self._avisos())
        self.assertIn("t-fisica-1", gb._F4_PRUEBAS_AUSENTE)
        resultado = {"id": "t-fisica-1", "raiz": "t-fisica-1",
                     "status": "ok"}
        gb._f4_resultado_a_buzon(resultado)
        self.assertIn("recursos_periodo", resultado)


if __name__ == "__main__":
    unittest.main()

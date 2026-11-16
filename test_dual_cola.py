"""Pruebas del modo dual contra la cola real (Fase 4): el marcador
por_confirmar va ANTES que el envío, lo marcado no se ejecuta nunca en
local, la reconciliación cierra sin ejecutar lo que el servidor ya hizo,
lo no hecho se ejecuta exactamente una vez en local, el indeterminado
×3 lo decide el dueño, y un reinicio reconstruye el estado desde la
tabla dual_en_vuelo.

El monolito se importa con el entorno aislado (share, cola y XDG en un
temporal). Ejecutar: python3 -m unittest test_dual_cola
"""
import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="gb-dual-")
os.environ["GROWI_BRIDGE_SHARE"] = str(Path(_TMP) / "share")
os.environ["GROWI_BRIDGE_COLA"] = str(Path(_TMP) / "cola.db")
os.environ["XDG_DATA_HOME"] = str(Path(_TMP) / "xdg")

_spec = importlib.util.spec_from_file_location(
    "gb_dual", str(Path(__file__).with_name("growi-bridge.py")))
gb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gb)

import dual  # noqa: E402

CUENTAS = {
    "version": 1, "revision": 1, "borradas": [],
    "cuentas": [
        {"id": "principal", "nombre": "Principal", "carril": "a",
         "conexion": "ambas", "habilitada": True},
        {"id": "segunda", "nombre": "Segunda", "carril": "b",
         "conexion": "ambas", "habilitada": True},
    ],
}


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
        for d in (gb.TASKS, gb.PROCESSING, gb.DONE, gb.RESULTS, gb.WAITING):
            d.mkdir(parents=True, exist_ok=True)
            for p in d.glob("*"):
                if p.is_file():
                    p.unlink()
        base = gb._base_tablero()
        for p in base.glob("*"):
            if p.is_file():
                p.unlink()
        gb.cola_init()
        self.sonda = {"ok": True}
        self.vigia = dual.VigiaDual(lambda: self.sonda["ok"])
        gb._VIGIA_DUAL.update(vigia=self.vigia, parar=None)
        gb._TABLERO["estado"] = "activa"

    def tearDown(self):
        gb._VIGIA_DUAL.update(vigia=None, parar=None)
        self.tmp.cleanup()

    def _tarea(self, tid="t-dual-1"):
        datos = {"id": tid, "prompt": "haz algo útil",
                 "cwd": str(self.app), "motor": "claude"}
        p = gb.TASKS / f"{tid}.task.json"
        p.write_text(json.dumps(datos), encoding="utf-8")
        return p

    def _marcar(self, tid="t-dual-1"):
        p = self._tarea(tid)
        self.assertEqual(gb._puerta_tablero(p), "saltar")
        return p

    def _a_reconciliando(self):
        self.sonda["ok"] = False
        for _ in range(3):
            self.vigia.tick()
        self.assertEqual(self.vigia.estado, dual.LOCAL)
        self.sonda["ok"] = True
        for _ in range(2):
            self.vigia.tick()
        self.assertEqual(self.vigia.estado, dual.RECONCILIANDO)


class TestMarcador(Base):
    def test_marcador_antes_que_el_envio(self):
        p = self._marcar()
        fila = gb._dual_fila("t-dual-1")
        self.assertIsNotNone(fila)
        self.assertEqual(fila["estado"], "por_confirmar")
        row = gb.cola_get("t-dual-1")
        self.assertEqual(row["estado"], "enviada_servidor")
        self.assertEqual(row["cuenta"], "principal")  # la fila manda (B2)
        self.assertIn("t-dual-1", self.vigia.por_confirmar)
        # El archivo sigue visible en TASKS para la sesión del servidor.
        self.assertTrue(p.exists())

    def test_si_el_insert_falla_no_hay_envio(self):
        gb._cola("DROP TABLE dual_en_vuelo")
        try:
            p = self._tarea()
            self.assertEqual(gb._puerta_tablero(p), "saltar")
            # Sin marcador no hay envío: la fila nunca pasó a
            # enviada_servidor (ni siquiera se creó).
            self.assertIsNone(gb.cola_get("t-dual-1"))
        finally:
            gb.cola_init()

    def test_por_confirmar_no_se_ejecuta_en_local(self):
        p = self._marcar()
        self.sonda["ok"] = False
        for _ in range(3):
            self.vigia.tick()
        self.assertEqual(self.vigia.estado, dual.LOCAL)
        self.assertEqual(gb._puerta_tablero(p), "saltar")
        # Ni la recuperación del arranque lo devuelve a la cola local.
        gb.cola_set("t-dual-1", estado="en_curso")
        gb.cola_recuperar()
        self.assertEqual(gb.cola_get("t-dual-1")["estado"], "en_curso")


class TestReconciliacion(Base):
    def test_con_resultado_se_cierra_sin_ejecutar(self):
        p = self._marcar()
        (gb.RESULTS / "t-dual-1.result.json").write_text(
            json.dumps({"id": "t-dual-1", "status": "ok"}),
            encoding="utf-8")
        gb._f4_barrido("principal")
        self.assertIsNone(gb._dual_fila("t-dual-1"))
        self.assertEqual(gb.cola_get("t-dual-1")["estado"], "terminada")
        self.assertNotIn("t-dual-1", self.vigia.por_confirmar)
        self.assertFalse(p.exists())  # archivado, no ejecutado

    def test_sin_resultado_se_ejecuta_exactamente_una_vez(self):
        p = self._marcar()
        self._a_reconciliando()
        gb._cola("UPDATE dual_en_vuelo SET enviada_ts=? WHERE tarea=?",
                 (time.time() - 200, "t-dual-1"))
        gb._f4_barrido("principal")
        self.assertIsNone(gb._dual_fila("t-dual-1"))
        row = gb.cola_get("t-dual-1")
        self.assertEqual(row["estado"], "en_cola")
        self.assertTrue(any(e.get("dual_resuelta_local")
                            for e in gb._cola_hist(row)))
        # La puerta ya la deja pasar (se ejecutará una vez)...
        self.assertEqual(gb._puerta_tablero(p), "ok")
        # ...y ni volviendo el vigía a SERVIDOR se reenvía: la marca de
        # la fila manda. (RECONCILIANDO → SERVIDOR ocurre al completar
        # una reconciliación sin nada por confirmar.)
        self.vigia.reconciliar(lambda t: False, lambda t: None)
        self.assertEqual(self.vigia.estado, dual.SERVIDOR)
        self.assertEqual(gb._puerta_tablero(p), "ok")
        self.assertIsNone(gb._dual_fila("t-dual-1"))

    def test_indeterminado_tres_veces_lo_decide_el_dueno(self):
        p = self._marcar()
        self._a_reconciliando()
        (gb.RESULTS / "t-dual-1.result.json").write_text(
            "esto no es json {{{", encoding="utf-8")
        for _ in range(2):
            gb._f4_barrido("principal")
            self.assertEqual(gb._dual_fila("t-dual-1")["estado"],
                             "por_confirmar")
        gb._f4_barrido("principal")
        self.assertEqual(gb._dual_fila("t-dual-1")["estado"],
                         "resuelta_dueno")
        self.assertEqual(gb.cola_get("t-dual-1")["estado"],
                         "resuelta_dueno")
        # No se ejecuta con duda: la puerta lo sigue saltando.
        self.assertEqual(gb._puerta_tablero(p), "saltar")
        avisos = (gb._base_tablero() / "avisos.jsonl").read_text(
            encoding="utf-8")
        self.assertIn("dual_sin_resolver", avisos)

    def test_reinicio_reconstruye_el_estado_desde_la_tabla(self):
        self._marcar()
        vigia2 = dual.VigiaDual(lambda: True)
        self.assertNotIn("t-dual-1", vigia2.por_confirmar)
        gb._VIGIA_DUAL.update(vigia=vigia2)
        gb._f4_dual_asegurar()
        self.assertIn("t-dual-1", vigia2.por_confirmar)


class TestDecisionDelDueno(Base):
    def _resuelta(self):
        self._marcar()
        gb._cola("UPDATE dual_en_vuelo SET estado='resuelta_dueno' "
                 "WHERE tarea='t-dual-1'")
        gb.cola_set("t-dual-1", estado="resuelta_dueno")

    def test_se_hizo_en_el_servidor(self):
        self._resuelta()
        gb._dual_resolver_dueno("t-dual-1", hecha=True)
        self.assertIsNone(gb._dual_fila("t-dual-1"))
        self.assertEqual(gb.cola_get("t-dual-1")["estado"], "terminada")

    def test_ejecutarla_aqui(self):
        self._resuelta()
        p = gb.TASKS / "t-dual-1.task.json"
        gb._dual_resolver_dueno("t-dual-1", hecha=False)
        self.assertIsNone(gb._dual_fila("t-dual-1"))
        row = gb.cola_get("t-dual-1")
        self.assertEqual(row["estado"], "en_cola")
        self.assertTrue(any(e.get("dual_resuelta_local")
                            for e in gb._cola_hist(row)))
        # Y la puerta no la reenvía aunque el vigía esté en SERVIDOR.
        self.assertEqual(gb._puerta_tablero(p), "ok")


if __name__ == "__main__":
    unittest.main()

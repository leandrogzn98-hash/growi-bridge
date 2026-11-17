# -*- coding: utf-8 -*-
"""Pruebas de la P6 de la bifurcación: la lectura de disco en
POSIX (antes pedía «C:» y siempre fallaba) y la vista «Tareas por
cuenta» (encargos vivos con avance + cola por carril)."""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def _cargar_monolito(tmp):
    os.environ.update({
        "GROWI_BRIDGE_APP_DIR": str(tmp),
        "GROWI_BRIDGE_INBOX": str(tmp / "share" / "inbox"),
        "GROWI_BRIDGE_SCREENS": str(tmp / "share" / "screens"),
        "GROWI_BRIDGE_SKILLS": str(tmp / "skills"),
        "GROWI_BRIDGE_SECRET": "x",
        "HOME": str(tmp),
    })
    for mod in ("cuentas", "relevo", "sala"):
        spec = importlib.util.spec_from_file_location(
            mod, RAIZ / f"{mod}.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules[mod] = m
        spec.loader.exec_module(m)
    spec = importlib.util.spec_from_file_location(
        "gb_p6", RAIZ / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    sys.modules["gb_p6"] = gb
    spec.loader.exec_module(gb)
    return gb


class TestDiscoPosix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gb-p6-"))
        cls.gb = _cargar_monolito(cls.tmp)

    def test_disco_en_posix(self):
        if os.name == "nt":
            self.skipTest("la rama POSIX no aplica en Windows")
        gb = self.gb
        gb._RES["install_tried"] = True
        gb._res_psutil = lambda: None
        gb._res_gpu_kick = lambda: None
        gb._res_cpu_fallback = lambda: 3.0
        gb._res_mem_fallback = lambda: (1 << 30, 4 << 30)
        gb._res_procs_tasklist = lambda: {}
        d = gb._res_sample()
        self.assertIsNotNone(d["disk"], "el disco debe leerse en POSIX")
        etiqueta, libre, total = d["disk"]
        self.assertEqual(etiqueta, "/")
        self.assertGreater(total, 0)
        self.assertGreaterEqual(libre, 0)


class TestTareasPorCuenta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gb-p6b-"))
        cls.gb = _cargar_monolito(cls.tmp)
        import cuentas as cm
        import relevo as rv
        cls.cm, cls.rv = cm, rv

    def setUp(self):
        gb = self.gb
        self.base = Path(tempfile.mkdtemp(prefix="gb-p6-base-"))
        self.lane_a = Path(tempfile.mkdtemp(prefix="gb-p6-a-"))
        self.lane_b = Path(tempfile.mkdtemp(prefix="gb-p6-b-"))
        gb._base_tablero = lambda: self.base
        gb._CUENTAS_CACHE = {"reg": None, "clave": "forzar"}
        gb.APP_DIR = self.lane_a
        cm = self.cm
        reg = cm.cargar(self.lane_a)
        reg["cuentas"] = [
            {"id": "principal", "nombre": "Principal", "asistente": None,
             "carril": "a", "conexion": "servidor", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "hereda",
                          "clases_extra_denegadas": []}},
            {"id": "segunda", "nombre": "Segunda", "asistente": None,
             "carril": "b", "conexion": "servidor", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "hereda",
                          "clases_extra_denegadas": []}}]
        cm.guardar(self.lane_a, reg)
        gb._CUENTAS_CACHE = {"reg": None, "clave": "forzar"}
        gb._dir_carril = lambda c: self.lane_a if c == "a" else self.lane_b
        # Encargo vivo: 2 subtareas de segunda, 1 terminada.
        datos = {"version": 1, "revision": 1, "encargos": {
            "enc-x": {"raiz": "enc-x", "estado": "en_curso",
                      "receptora": "principal",
                      "subtareas": {
                          "s1": {"cuenta": "segunda",
                                 "estado": "terminada",
                                 "titulo": "parte uno"},
                          "s2": {"cuenta": "segunda",
                                 "estado": "en_curso",
                                 "titulo": "parte dos"}}}}}
        (self.base / "encargos.json").write_text(
            json.dumps(datos), encoding="utf-8")
        # Cola del carril B: 1 en curso y 2 en cola de segunda.
        con = sqlite3.connect(self.lane_b / "cola.db")
        con.execute("CREATE TABLE tareas (id TEXT, cuenta TEXT, "
                    "estado TEXT)")
        con.executemany("INSERT INTO tareas VALUES (?, ?, ?)", [
            ("t1", "segunda", "en_curso"),
            ("t2", "segunda", "en_cola"),
            ("t3", "segunda", "en_cola"),
            ("t4", "principal", "terminada")])
        con.commit()
        con.close()

    def test_lineas_por_cuenta(self):
        lineas = self.gb._tareas_cuentas_lineas()
        texto = "\n".join(lineas)
        self.assertIn("Principal — carril A", texto)
        self.assertIn("Segunda — carril B", texto)
        self.assertIn("avance 1/2 (50 %)", texto)
        self.assertIn("parte dos: en_curso", texto)
        self.assertIn("en su cola: 1 en curso, 2 en espera", texto)
        self.assertIn("sin trabajo ahora", texto)  # principal

    def test_sin_encargos_no_rompe(self):
        (self.base / "encargos.json").write_text(
            json.dumps({"version": 1, "revision": 0, "encargos": {}}),
            encoding="utf-8")
        lineas = self.gb._tareas_cuentas_lineas()
        self.assertTrue(any("Segunda" in l for l in lineas))


if __name__ == "__main__":
    unittest.main()

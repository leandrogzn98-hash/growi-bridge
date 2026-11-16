# -*- coding: utf-8 -*-
"""Pruebas de alquileres.py (Fase 3, §4 del diseño).

Alquileres por (repo, ruta) con TTL: exclusión archivo↔archivo y
archivo↔proyecto, todo-o-nada, caducidad con robo auditado, y la
carrera entre dos procesos reales sin doble concesión.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alquileres


class Reloj:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


class CasoBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.reloj = Reloj()

    def tearDown(self):
        self.tmp.cleanup()


class TestTomar(CasoBase):
    def test_tomar_y_vigentes(self):
        r = alquileres.tomar(self.base, "repo1", ["src/a.py"], "principal",
                             "t1", reloj=self.reloj)
        self.assertTrue(r["ok"])
        self.assertEqual(r["robados"], [])
        v = alquileres.vigentes(self.base, "repo1", reloj=self.reloj)
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["cuenta"], "principal")

    def test_conflicto_mismo_archivo_otra_cuenta(self):
        alquileres.tomar(self.base, "repo1", ["src/a.py"], "principal", "t1",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo1", ["src/a.py"], "segunda",
                             "t2", reloj=self.reloj)
        self.assertFalse(r["ok"])
        self.assertEqual(r["conflictos"][0]["cuenta"], "principal")

    def test_conflicto_proyecto_contra_archivo(self):
        alquileres.tomar(self.base, "repo1", ["*"], "principal", "t1",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo1", ["src/a.py"], "segunda",
                             "t2", reloj=self.reloj)
        self.assertFalse(r["ok"])

    def test_conflicto_archivo_contra_proyecto(self):
        alquileres.tomar(self.base, "repo1", ["src/a.py"], "principal", "t1",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo1", ["*"], "segunda", "t2",
                             reloj=self.reloj)
        self.assertFalse(r["ok"])

    def test_misma_cuenta_otra_tarea_conflicto(self):
        alquileres.tomar(self.base, "repo1", ["src/a.py"], "principal", "t1",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo1", ["src/a.py"], "principal",
                             "t2", reloj=self.reloj)
        self.assertFalse(r["ok"])

    def test_misma_cuenta_misma_tarea_amplia(self):
        alquileres.tomar(self.base, "repo1", ["src/a.py"], "principal", "t1",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo1", ["src/a.py", "src/b.py"],
                             "principal", "t1", reloj=self.reloj)
        self.assertTrue(r["ok"])
        self.assertEqual(len(alquileres.vigentes(self.base, "repo1",
                                                 reloj=self.reloj)), 2)

    def test_todo_o_nada(self):
        alquileres.tomar(self.base, "repo1", ["b.py"], "segunda", "t9",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo1", ["a.py", "b.py"],
                             "principal", "t1", reloj=self.reloj)
        self.assertFalse(r["ok"])
        v = alquileres.vigentes(self.base, "repo1", reloj=self.reloj)
        self.assertEqual([x["ruta"] for x in v], ["b.py"])  # a.py no quedó

    def test_rutas_invalidas(self):
        for ruta in ("../fuera.py", "/absoluta.py", "", "a/../../b.py"):
            with self.assertRaises(alquileres.ErrorAlquileres, msg=ruta):
                alquileres.tomar(self.base, "repo1", [ruta], "principal",
                                 "t1", reloj=self.reloj)

    def test_repos_distintos_no_conflicto(self):
        alquileres.tomar(self.base, "repo1", ["a.py"], "principal", "t1",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo2", ["a.py"], "segunda", "t2",
                             reloj=self.reloj)
        self.assertTrue(r["ok"])

    def test_clave_mezcla_solo_conflicto_consigo(self):
        # @mezcla (B9): no bloquea archivos ni la bloquean los archivos.
        alquileres.tomar(self.base, "repo1", ["a.py"], "principal", "t1",
                         reloj=self.reloj)
        r = alquileres.tomar(self.base, "repo1", ["@mezcla"], "segunda",
                             "mezcla-x", reloj=self.reloj)
        self.assertTrue(r["ok"])
        r = alquileres.tomar(self.base, "repo1", ["@mezcla"], "principal",
                             "mezcla-y", reloj=self.reloj)
        self.assertFalse(r["ok"])


class TestCaducidadYRenovar(CasoBase):
    def test_caducado_se_puede_robar_con_aviso(self):
        alquileres.tomar(self.base, "repo1", ["a.py"], "principal", "t1",
                         ttl_s=100, reloj=self.reloj)
        self.reloj.avanzar(101)
        r = alquileres.tomar(self.base, "repo1", ["a.py"], "segunda", "t2",
                             reloj=self.reloj)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["robados"]), 1)
        self.assertEqual(r["robados"][0]["cuenta_anterior"], "principal")
        self.assertEqual(r["robados"][0]["tarea_anterior"], "t1")

    def test_renovar_ok(self):
        alquileres.tomar(self.base, "repo1", ["a.py"], "principal", "t1",
                         ttl_s=100, reloj=self.reloj)
        self.reloj.avanzar(50)
        r = alquileres.renovar(self.base, "principal", "t1", ttl_s=100,
                               reloj=self.reloj)
        self.assertTrue(r["ok"])
        self.assertEqual(r["renovados"], 1)

    def test_renovar_tras_robo_no_ok(self):
        alquileres.tomar(self.base, "repo1", ["a.py"], "principal", "t1",
                         ttl_s=100, reloj=self.reloj)
        self.reloj.avanzar(101)
        alquileres.tomar(self.base, "repo1", ["a.py"], "segunda", "t2",
                         reloj=self.reloj)
        r = alquileres.renovar(self.base, "principal", "t1", reloj=self.reloj)
        self.assertFalse(r["ok"])  # la dueña muerta se entera (I1)

    def test_soltar(self):
        alquileres.tomar(self.base, "repo1", ["a.py"], "principal", "t1",
                         reloj=self.reloj)
        # Soltar lo ajeno no libera nada.
        self.assertEqual(alquileres.soltar(self.base, "segunda", "t2"), 0)
        self.assertEqual(alquileres.soltar(self.base, "principal", "t1"), 1)
        r = alquileres.tomar(self.base, "repo1", ["a.py"], "segunda", "t2",
                             reloj=self.reloj)
        self.assertTrue(r["ok"])

    def test_reasignar(self):
        alquileres.tomar(self.base, "repo1", ["a.py", "b.py"], "principal",
                         "t1", reloj=self.reloj)
        n = alquileres.reasignar(self.base, "repo1", "t1", "principal",
                                 "segunda", reloj=self.reloj)
        self.assertEqual(n, 2)
        v = alquileres.vigentes(self.base, "repo1", reloj=self.reloj)
        self.assertTrue(all(x["cuenta"] == "segunda" for x in v))


class TestConcurrenciaReal(CasoBase):
    def test_dos_procesos_sin_doble_concesion(self):
        repo_dir = Path(__file__).resolve().parent
        salida = self.base / "salidas"
        salida.mkdir()
        go = self.base / "go"
        guion = (
            "import sys, json, time\n"
            f"sys.path.insert(0, {str(repo_dir)!r})\n"
            "from pathlib import Path\n"
            "import alquileres\n"
            f"base = Path({str(self.base)!r})\n"
            "while not (base / 'go').exists():\n"
            "    time.sleep(0.005)\n"
            "r = alquileres.tomar(base, 'repo1', ['a.py'], sys.argv[1], 't')\n"
            f"(Path({str(salida)!r}) / (sys.argv[1] + '.json'))"
            ".write_text(json.dumps(r))\n"
        )
        procs = [subprocess.Popen([sys.executable, "-c", guion, nombre],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
                 for nombre in ("principal", "segunda")]
        go.write_text("ya")
        for p in procs:
            p.wait(timeout=30)
        resultados = [json.loads((salida / f"{n}.json").read_text())
                      for n in ("principal", "segunda")]
        self.assertEqual(sum(1 for r in resultados if r["ok"]), 1,
                         f"exactamente una concesión: {resultados}")


if __name__ == "__main__":
    unittest.main()

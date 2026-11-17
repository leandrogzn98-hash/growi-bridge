"""Pruebas de los recursos por % (Fase 4): el mismo % produce límites
proporcionales en hardware distinto (sin cifras absolutas compartidas),
traducción a systemd y a Job Objects, suelos de cordura, admisión de
GPU y reparto sobre la suma de ambos carriles.

Ejecutar: python3 -m unittest test_recursos
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import recursos

GIB = 1024 ** 3
MIB = 1024 ** 2

XEON = {"cpu": {"fisicos": 14, "logicos": 28, "nombre": "Xeon E5-2680 v4"},
        "ram_total": 32 * GIB,
        "gpu": {"nombre": "GTX 1070", "vram_total": 8 * GIB},
        "disco": {"ruta": "/tmp", "total": 500 * GIB, "libre": 200 * GIB}}
MODESTA = {"cpu": {"fisicos": 2, "logicos": 4, "nombre": "PC modesta"},
           "ram_total": 8 * GIB,
           "gpu": {"nombre": "Integrada", "vram_total": 2 * GIB},
           "disco": {"ruta": "/tmp", "total": 128 * GIB, "libre": 40 * GIB}}


class TestLimites(unittest.TestCase):
    def test_xeon_ausente_pleno(self):
        lim = recursos.limites(XEON, {"cpu": 100, "ram": 100, "gpu": 100}, 1)
        self.assertEqual(lim["cpu"]["cpuquota_pct"], 2800)  # 28 núcleos
        self.assertEqual(lim["ram"]["bytes_por_tarea"], 32 * GIB)
        self.assertEqual(lim["gpu"]["vram_presupuesto"], 8 * GIB)
        self.assertEqual(lim["suelos"], [])

    def test_presente_repartido_entre_dos(self):
        lim = recursos.limites(XEON, {"cpu": 50, "ram": 50, "gpu": 50}, 2)
        self.assertEqual(lim["cpu"]["cpuquota_pct"], 700)   # 50 % × 28 / 2
        self.assertEqual(lim["cpu"]["cpu_rate_job"], 2500)  # 25 % del total
        self.assertEqual(lim["ram"]["bytes_por_tarea"], 8 * GIB)

    def test_proporcional_sin_cifras_compartidas(self):
        a = recursos.limites(XEON, {"cpu": 50, "ram": 50, "gpu": 50}, 1)
        b = recursos.limites(MODESTA, {"cpu": 50, "ram": 50, "gpu": 50}, 1)
        self.assertEqual(a["cpu"]["cpuquota_pct"], 1400)
        self.assertEqual(b["cpu"]["cpuquota_pct"], 200)
        self.assertEqual(a["ram"]["bytes_por_tarea"], 16 * GIB)
        self.assertEqual(b["ram"]["bytes_por_tarea"], 4 * GIB)
        # El mismo % en las dos máquinas: ningún límite absoluto coincide.
        self.assertNotEqual(a["cpu"]["cpuquota_pct"],
                            b["cpu"]["cpuquota_pct"])
        self.assertNotEqual(a["ram"]["bytes_por_tarea"],
                            b["ram"]["bytes_por_tarea"])

    def test_suelos_de_cordura(self):
        mini = {"cpu": {"fisicos": 1, "logicos": 1, "nombre": "mini"},
                "ram_total": 128 * MIB, "gpu": None,
                "disco": {"ruta": "/tmp", "total": GIB, "libre": GIB}}
        lim = recursos.limites(mini, {"cpu": 1, "ram": 50, "gpu": 50}, 1)
        self.assertEqual(lim["ram"]["bytes_por_tarea"],
                         recursos.SUELO_RAM_BYTES)
        self.assertEqual(lim["cpu"]["cpuquota_pct"], 5)  # 5 % de un núcleo
        self.assertEqual(len(lim["suelos"]), 2)


class TestAsignacion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_por_defecto(self):
        asig = recursos.asignacion_de(self.base)
        self.assertEqual(asig["ausente"], {"cpu": 100, "ram": 100,
                                           "gpu": 100})
        self.assertEqual(asig["presente"], {"cpu": 50, "ram": 50,
                                            "gpu": 50})

    def test_guardar_y_releer(self):
        recursos.guardar_asignacion(self.base,
                                    {"presente": {"cpu": 25}})
        asig = recursos.asignacion_de(self.base)
        self.assertEqual(asig["presente"]["cpu"], 25)
        self.assertEqual(asig["presente"]["ram"], 50)  # el resto, intacto

    def test_invalida_rechazada(self):
        for mala in ({"presente": {"cpu": 0}}, {"presente": {"cpu": 101}},
                     {"presente": {"cpu": "50"}}, {"presente": {"cpu": True}},
                     {"noche": {"cpu": 50}}, {"presente": {"disco": 50}}):
            with self.assertRaises(recursos.ErrorRecursos):
                recursos.guardar_asignacion(self.base, mala)


class TestAsegurar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_specs_inyectadas_y_firma(self):
        specs = recursos.asegurar(self.base, inyectadas= XEON)
        self.assertEqual(specs["cpu"]["logicos"], 28)
        recursos.guardar_asignacion(self.base, {"presente": {"cpu": 30}})
        # Misma firma: no se pisa la asignación.
        specs2 = recursos.asegurar(self.base, inyectadas= XEON)
        self.assertEqual(specs2["ram_total"], 32 * GIB)
        self.assertEqual(recursos.asignacion_de(self.base)
                         ["presente"]["cpu"], 30)
        # Firma nueva (otra RAM): specs nuevos, asignación conservada.
        otras = dict(XEON, ram_total=16 * GIB)
        specs3 = recursos.asegurar(self.base, inyectadas=otras)
        self.assertEqual(specs3["ram_total"], 16 * GIB)
        self.assertEqual(recursos.asignacion_de(self.base)
                         ["presente"]["cpu"], 30)


class TestGpu(unittest.TestCase):
    ASIG = {"cpu": 100, "ram": 100, "gpu": 50}  # presupuesto: 4096 MiB

    def test_cabe(self):
        m = recursos.hay_margen_gpu(XEON, self.ASIG, 1000, 2000)
        self.assertTrue(m["ok"])
        self.assertTrue(m["gobernada"])

    def test_no_cabe(self):
        m = recursos.hay_margen_gpu(XEON, self.ASIG, 3000, 2000)
        self.assertFalse(m["ok"])

    def test_sin_estimacion_suelo_del_25_de_la_libre(self):
        # Libre = 8192-3000 = 5192; supuesta = 1298; 3000+1298 > 4096.
        m = recursos.hay_margen_gpu(XEON, self.ASIG, 3000, None)
        self.assertFalse(m["ok"])
        self.assertTrue(m["supuesta"])
        self.assertAlmostEqual(m["necesidad_mib"], 1298, delta=1)
        m2 = recursos.hay_margen_gpu(XEON, self.ASIG, 0, None)
        self.assertTrue(m2["ok"])  # supuesta 2048 <= 4096

    def test_sin_gpu_no_se_gobierna(self):
        sin = dict(XEON, gpu=None)
        m = recursos.hay_margen_gpu(sin, self.ASIG, 0, 100)
        self.assertTrue(m["ok"])
        self.assertFalse(m["gobernada"])


class TestEstadoCompartido(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reparto_sobre_la_suma_de_ambos_carriles(self):
        recursos.escribir_seccion_estado(self.base, "a", {
            "tareas": {"t1": {"cuenta": "principal", "cpu_pct": 30,
                              "rss": 100 * MIB, "vram_mib": 500}}})
        recursos.escribir_seccion_estado(self.base, "b", {
            "tareas": {"t2": {"cuenta": "segunda", "cpu_pct": 50,
                              "rss": 300 * MIB, "vram_mib": 700}}})
        agreg = recursos.agregado(recursos.leer_estado(self.base))
        self.assertEqual(agreg["n_tareas"], 2)
        self.assertEqual(agreg["cpu_pct"], 80)
        self.assertEqual(agreg["rss"], 400 * MIB)
        self.assertEqual(agreg["por_cuenta"]["segunda"]["tareas"], 1)
        # Escribir la sección de A no pisa la de B.
        recursos.escribir_seccion_estado(self.base, "a", {"tareas": {}})
        estado = recursos.leer_estado(self.base)
        self.assertIn("t2", estado["carriles"]["b"]["tareas"])

    def test_sobre_presupuesto(self):
        agreg = {"cpu_pct": 60, "rss": 20 * GIB}
        sobre = recursos.sobre_presupuesto(
            agreg, XEON, {"cpu": 50, "ram": 50, "gpu": 50})
        self.assertTrue(sobre["cpu"])
        self.assertTrue(sobre["ram"])  # 20 > 16 GiB


class TestSonda(unittest.TestCase):
    def test_sonda_exige_exito_real(self):
        class R:
            def __init__(self, rc):
                self.returncode = rc

        if not shutil.which("systemd-run"):
            self.assertFalse(recursos.sonda_systemd())
            return
        self.assertTrue(recursos.sonda_systemd(
            ejecutar=lambda cmd, **kw: R(0)))
        self.assertFalse(recursos.sonda_systemd(
            ejecutar=lambda cmd, **kw: R(1)))

        def roto(cmd, **kw):
            raise OSError("no está")

        self.assertFalse(recursos.sonda_systemd(ejecutar=roto))


class TestAbsolutos(unittest.TestCase):
    """Topes absolutos opcionales por modo (corrección de la prueba
    real): el tope efectivo es el MENOR entre el de % y el absoluto, y
    «topes» declara cuál mandó en cada recurso."""

    def test_sin_absolutos_manda_el_pct(self):
        lim = recursos.limites(XEON, {"cpu": 50, "ram": 50, "gpu": 50}, 1)
        self.assertEqual(lim["topes"],
                         {"cpu": "pct", "ram": "pct", "gpu": "pct"})
        self.assertEqual(lim["cpu"]["cpuquota_pct"], 1400)

    def test_absoluto_menor_acota(self):
        asig = {"cpu": 100, "ram": 100, "gpu": 100,
                "absolutos": {"cpu_nucleos": 4, "ram_gb": 5, "gpu_gb": 2}}
        lim = recursos.limites(XEON, asig, 1)
        self.assertEqual(lim["cpu"]["cpuquota_pct"], 400)   # 4 núcleos
        self.assertEqual(lim["cpu"]["cpu_rate_job"], 1429)  # 4/28 del total
        self.assertEqual(lim["ram"]["bytes_por_tarea"], 5 * GIB)
        self.assertEqual(lim["gpu"]["vram_presupuesto"], 2 * GIB)
        self.assertEqual(lim["topes"], {"cpu": "absoluto",
                                        "ram": "absoluto",
                                        "gpu": "absoluto"})

    def test_absoluto_mayor_no_acota(self):
        asig = {"cpu": 50, "ram": 50, "gpu": 50,
                "absolutos": {"cpu_nucleos": 28, "ram_gb": 64,
                              "gpu_gb": 16}}
        lim = recursos.limites(XEON, asig, 1)
        self.assertEqual(lim["cpu"]["cpuquota_pct"], 1400)
        self.assertEqual(lim["ram"]["bytes_por_tarea"], 16 * GIB)
        self.assertEqual(lim["gpu"]["vram_presupuesto"], 4 * GIB)
        self.assertEqual(lim["topes"],
                         {"cpu": "pct", "ram": "pct", "gpu": "pct"})

    def test_absolutos_se_reparten_entre_tareas(self):
        asig = {"cpu": 100, "ram": 100, "gpu": 100,
                "absolutos": {"cpu_nucleos": 4, "ram_gb": 8}}
        lim = recursos.limites(XEON, asig, 2)
        self.assertEqual(lim["cpu"]["cpuquota_pct"], 200)  # 4/2 núcleos
        self.assertEqual(lim["ram"]["bytes_por_tarea"], 4 * GIB)

    def test_absoluto_parcial_solo_acota_su_recurso(self):
        asig = {"cpu": 100, "ram": 100, "gpu": 100,
                "absolutos": {"ram_gb": 3}}
        lim = recursos.limites(XEON, asig, 1)
        self.assertEqual(lim["ram"]["bytes_por_tarea"], 3 * GIB)
        self.assertEqual(lim["topes"]["ram"], "absoluto")
        self.assertEqual(lim["topes"]["cpu"], "pct")
        self.assertEqual(lim["topes"]["gpu"], "pct")

    def test_guardar_y_releer_absolutos(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            recursos.guardar_asignacion(base, {"presente": {
                "absolutos": {"cpu_nucleos": 4, "ram_gb": 5,
                              "gpu_gb": None}}})
            self.assertEqual(recursos.absolutos_de(base)["presente"],
                             {"cpu_nucleos": 4, "ram_gb": 5,
                              "gpu_gb": None})
            self.assertEqual(recursos.absolutos_de(base)["ausente"],
                             {"cpu_nucleos": None, "ram_gb": None,
                              "gpu_gb": None})
            # Guardar solo absolutos no toca los %.
            self.assertEqual(
                recursos.asignacion_de(base)["presente"]["ram"], 50)

    def test_absoluto_invalido_rechazado(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for malo in ({"cpu_nucleos": 0}, {"ram_gb": -1},
                         {"gpu_gb": "2"}, {"ram_gb": True},
                         {"disco_gb": 3}):
                with self.assertRaises(recursos.ErrorRecursos):
                    recursos.guardar_asignacion(
                        base, {"presente": {"absolutos": malo}})

    def test_admision_gpu_acotada_por_el_absoluto(self):
        asig = {"cpu": 100, "ram": 100, "gpu": 100,
                "absolutos": {"gpu_gb": 2}}
        # Al 100 % cabría (8 GiB); con el tope de 2 GiB, 1+2 GiB no cabe.
        self.assertFalse(
            recursos.hay_margen_gpu(XEON, asig, 1024, 2048)["ok"])
        self.assertTrue(
            recursos.hay_margen_gpu(XEON, asig, 0, 1024)["ok"])


if __name__ == "__main__":
    unittest.main()

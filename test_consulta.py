# -*- coding: utf-8 -*-
"""Pruebas de consulta.py (Fase 2): topes duros de la cadena completa,
derivación desde el padre, entrega revalidada, reserva y caducidad."""
import importlib.util
import json
import os
import tempfile
import unittest

import consulta

REG = {"cuentas": [
    {"id": "principal", "habilitada": True, "carril": "a"},
    {"id": "segunda", "habilitada": True, "carril": "b"},
    {"id": "sincarril", "habilitada": True, "carril": None},
    {"id": "apagada", "habilitada": False, "carril": "b"},
]}
VISTA_OK = {"segunda": {"estado": "activa", "pct_efectivo": 60}}


def crear(**kw):
    args = dict(registro=REG, vista_d=VISTA_OK, origen="principal", destino="segunda",
                pregunta="¿este enfoque compila?", tarea_padre="tarea-1")
    args.update(kw)
    return consulta.crear_consulta(**args)


def tracker_en(tmp):
    spec = importlib.util.spec_from_file_location(
        "quota_tracker", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "quota-tracker.py"))
    qt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qt)
    cfg = os.path.join(tmp, "config-quota.json")
    uso = os.path.join(tmp, "quota-uso.json")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({"motores": {"claude": {"nombre": "Claude", "tipo": "cuota_mensual",
                                          "limite": 100, "unidad": "USD",
                                          "reset": "mensual"}}}, f)
    return qt.QuotaTracker(cfg, uso)


class TestCrear(unittest.TestCase):
    def test_consulta_valida(self):
        t = crear()
        self.assertEqual(t["tipo"], "consulta")
        self.assertEqual(t["lane"], "b")
        self.assertEqual(t["cuenta"], "segunda")
        self.assertEqual(t["tarea_padre"], "tarea-1")
        self.assertEqual(t["raiz"], "tarea-1")
        self.assertEqual(t["consulta"]["saltos"], 1)
        self.assertEqual(t["consulta"]["gastado"], 0)
        self.assertGreater(t["expira_ts"], 0)

    def test_saltos_derivados_del_padre(self):
        padre = crear()  # saltos 1
        hija = crear(tarea_padre=padre["id"], padre=padre)
        self.assertEqual(hija["consulta"]["saltos"], 2)
        self.assertEqual(hija["raiz"], "tarea-1")
        # La nieta ya no cabe: el llamante no puede declarar saltos a mano.
        with self.assertRaises(consulta.ErrorConsulta):
            crear(tarea_padre=hija["id"], padre=hija)
        self.assertTrue(consulta.puede_tener_hijas(padre))
        self.assertFalse(consulta.puede_tener_hijas(hija))

    def test_presupuesto_hija_limitado_por_el_padre(self):
        padre = crear(presupuesto=20)
        padre["consulta"]["gastado"] = 15  # le quedan 5
        with self.assertRaises(consulta.ErrorConsulta):
            crear(tarea_padre=padre["id"], padre=padre, presupuesto=10)
        hija = crear(tarea_padre=padre["id"], padre=padre, presupuesto=5)
        self.assertEqual(hija["consulta"]["presupuesto"], 5)

    def test_topes_de_presupuesto(self):
        crear(presupuesto=20)
        with self.assertRaises(consulta.ErrorConsulta):
            crear(presupuesto=21)
        with self.assertRaises(consulta.ErrorConsulta):
            crear(presupuesto=0)

    def test_reglas_basicas(self):
        with self.assertRaises(consulta.ErrorConsulta):
            crear(destino="principal")          # a sí misma
        with self.assertRaises(consulta.ErrorConsulta):
            crear(destino="fantasma")           # no existe
        with self.assertRaises(consulta.ErrorConsulta):
            crear(destino="apagada")            # deshabilitada
        with self.assertRaises(consulta.ErrorConsulta):
            crear(destino="sincarril")          # sin carril
        with self.assertRaises(consulta.ErrorConsulta):
            crear(pregunta="  ")                # sin pregunta
        with self.assertRaises(consulta.ErrorConsulta):
            crear(tarea_padre="")               # sin padre

    def test_destino_sin_tokens_no_se_consulta(self):
        for estado in ("restringida", "cuarentena"):
            with self.assertRaises(consulta.ErrorConsulta):
                crear(vista_d={"segunda": {"estado": estado, "pct_efectivo": 0}})

    def test_cwd_y_archivos_para_la_guardia_del_carril_b(self):
        # La guardia del carril B exige cwd y «archivos» dentro de su
        # carpeta: la consulta los trae derivados del cwd del destino.
        t = crear(cwd="/instalacion/lane2")
        self.assertEqual(t["cwd"], "/instalacion/lane2")
        self.assertEqual(len(t["archivos"]), 1)
        self.assertTrue(t["archivos"][0].startswith("/instalacion/lane2/"))
        self.assertIn(t["id"], t["archivos"][0])
        t2 = crear()  # sin cwd no se inventan campos
        self.assertNotIn("cwd", t2)
        self.assertNotIn("archivos", t2)

    def test_caducidad(self):
        t = crear(ttl_s=10, reloj=lambda: 1000.0)
        self.assertFalse(consulta.caducada(t, ahora=1005.0))
        self.assertTrue(consulta.caducada(t, ahora=1011.0))


class TestLibroRaiz(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_tope_de_hijas_por_tarea(self):
        for _ in range(consulta.MAX_HIJAS):
            crear(base_dir=self.base)
        with self.assertRaises(consulta.ErrorConsulta):
            crear(base_dir=self.base)
        # Otra tarea padre sí puede lanzar las suyas.
        crear(base_dir=self.base, tarea_padre="tarea-2")

    def test_tope_de_raiz_con_reservas(self):
        t1 = crear(base_dir=self.base, presupuesto=20)
        # Una hija de la misma cadena: misma raíz, otros 20 comprometidos.
        crear(base_dir=self.base, tarea_padre=t1["id"], padre=t1, presupuesto=20)
        # 40 comprometidos en la raíz: no cabe ni 1 más en la cadena.
        with self.assertRaises(consulta.ErrorConsulta):
            crear(base_dir=self.base, tarea_padre=t1["id"], padre=t1, presupuesto=1)
        # Al cerrar la primera, su reserva se libera y vuelve a caber.
        consulta.cerrar_consulta(self.base, t1)
        crear(base_dir=self.base, tarea_padre=t1["id"], padre=t1, presupuesto=1)
        # Otra raíz distinta no se ve afectada por el tope de esta.
        crear(base_dir=self.base, tarea_padre="raiz-ajena", presupuesto=20)


class TestEntregaYGasto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_entregar_escribe_el_archivo(self):
        t = crear()
        p = consulta.entregar(t, self.tmp.name, registro=REG, vista_d=VISTA_OK)
        self.assertTrue(p.is_file())
        with open(p, encoding="utf-8") as f:
            datos = json.load(f)
        self.assertEqual(datos["id"], t["id"])
        self.assertEqual([x for x in os.listdir(self.tmp.name) if x.endswith(".tmp")], [])

    def test_entregar_rechaza_dict_forjado(self):
        t = crear()
        t["consulta"]["saltos"] = 99  # forjado a mano, sin pasar por crear
        with self.assertRaises(consulta.ErrorConsulta):
            consulta.entregar(t, self.tmp.name)
        t2 = crear()
        t2["lane"] = "a"  # el carril no es el de la cuenta destino
        with self.assertRaises(consulta.ErrorConsulta):
            consulta.entregar(t2, self.tmp.name, registro=REG)

    def test_entregar_dir_inexistente_error(self):
        with self.assertRaises(consulta.ErrorConsulta):
            consulta.entregar(crear(), os.path.join(self.tmp.name, "no-existe"))

    def test_reserva_respeta_presupuesto(self):
        tracker = tracker_en(self.tmp.name)
        t = crear(presupuesto=2)
        self.assertEqual(consulta.reservar_gasto(t, tracker), 1)
        self.assertEqual(consulta.reservar_gasto(t, tracker), 2)
        self.assertIsNone(consulta.reservar_gasto(t, tracker))  # pasaría del tope
        self.assertEqual(tracker.obtener_estado("claude", cuenta="segunda")["usado"], 2)
        self.assertEqual(t["consulta"]["gastado"], 2)

    def test_reserva_respeta_tope_de_raiz(self):
        tracker = tracker_en(self.tmp.name)
        base = self.tmp.name
        t1 = crear(base_dir=base, presupuesto=20)
        # Gasta 20 de la raíz entre reservas de gasto.
        for _ in range(20):
            self.assertIsNotNone(consulta.reservar_gasto(t1, tracker, base_dir=base))
        t2 = crear(base_dir=base, tarea_padre="otra", presupuesto=20)
        # La raíz ya gastó 20; quedan 20 de TOPE_RAIZ: caben 20, no 21.
        for _ in range(20):
            self.assertIsNotNone(consulta.reservar_gasto(t2, tracker, base_dir=base))
        self.assertIsNone(consulta.reservar_gasto(t2, tracker, base_dir=base))


if __name__ == "__main__":
    unittest.main(verbosity=2)

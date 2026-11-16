# -*- coding: utf-8 -*-
"""Pruebas de tablero.py (Fase 2): publicación sin pisarse, % efectivo con
fuentes y caducidad, máquina de cuarentena y reparto determinista."""
import json
import multiprocessing as mp
import os
import tempfile
import threading
import unittest

import tablero

CFG = dict(tablero.CONFIG_DEF)


class RelojFalso:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class TestTablero(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.reloj = RelojFalso()

    def tearDown(self):
        self.tmp.cleanup()

    # -- publicación y lectura -------------------------------------------
    def test_publicar_y_leer_dos_cuentas(self):
        tablero.publicar(self.base, "principal", tarea="el juego", avance=40, reloj=self.reloj)
        tablero.publicar(self.base, "segunda", tarea="revisar", avance=10, reloj=self.reloj)
        t = tablero.cargar(self.base)
        self.assertEqual(t["cuentas"]["principal"]["tarea"], "el juego")
        self.assertEqual(t["cuentas"]["segunda"]["avance"], 10)
        # Publicar en una no pisa la otra.
        tablero.publicar(self.base, "principal", avance=55, reloj=self.reloj)
        t = tablero.cargar(self.base)
        self.assertEqual(t["cuentas"]["principal"]["avance"], 55)
        self.assertEqual(t["cuentas"]["segunda"]["tarea"], "revisar")

    def test_archivo_corrupto_tablero_vacio(self):
        with open(os.path.join(self.base, "tablero.json"), "w") as f:
            f.write("{roto")
        t = tablero.cargar(self.base)
        self.assertEqual(t["cuentas"], {})
        self.assertIsNotNone(tablero.problema(self.base))
        # Y publicar reconstruye.
        tablero.publicar(self.base, "principal", tarea="x", reloj=self.reloj)
        self.assertIsNone(tablero.problema(self.base))

    def test_validacion(self):
        with self.assertRaises(tablero.ErrorTablero):
            tablero.publicar(self.base, "Cuenta Mala", tarea="x")
        with self.assertRaises(tablero.ErrorTablero):
            tablero.publicar(self.base, "principal", avance=101)
        with self.assertRaises(tablero.ErrorTablero):
            tablero.declarar_pct(self.base, "principal", -1)
        with self.assertRaises(tablero.ErrorTablero):
            tablero.guardar_config(self.base, umbral_cuarentena=100)

    def test_publicaciones_concurrentes_hilos(self):
        def pub(n):
            for i in range(15):
                tablero.publicar(self.base, f"cuenta-{n}", avance=i)
        hilos = [threading.Thread(target=pub, args=(n,)) for n in range(4)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        t = tablero.cargar(self.base)
        self.assertEqual(len(t["cuentas"]), 4)
        for n in range(4):
            self.assertEqual(t["cuentas"][f"cuenta-{n}"]["avance"], 14)

    # -- % efectivo --------------------------------------------------------
    def _vista(self, estimador=None, ahora=None):
        return tablero.vista(self.base, estimador=estimador,
                             ahora=self.reloj.t if ahora is None else ahora)

    def test_declarado_fresco_manda(self):
        tablero.declarar_pct(self.base, "principal", 62, reloj=self.reloj)
        v = self._vista(estimador=lambda c, m: 10)
        self.assertEqual(v["principal"]["pct_efectivo"], 62)
        self.assertEqual(v["principal"]["pct_fuente"], "declarado")

    def test_declarado_caducado_cae_a_estimado(self):
        tablero.declarar_pct(self.base, "principal", 62, reloj=self.reloj)
        self.reloj.t += CFG["frescura_declarado_s"] + 1
        v = self._vista(estimador=lambda c, m: 30)
        self.assertEqual(v["principal"]["pct_efectivo"], 30)
        self.assertEqual(v["principal"]["pct_fuente"], "estimado")
        # El declarado viejo sigue en el archivo (último reporte).
        t = tablero.cargar(self.base)
        self.assertEqual(t["cuentas"]["principal"]["pct_declarado"], 62)

    def test_sin_dato_no_se_inventa(self):
        tablero.publicar(self.base, "principal", tarea="x", reloj=self.reloj)
        v = self._vista(estimador=lambda c, m: None)
        self.assertIsNone(v["principal"]["pct_efectivo"])
        self.assertEqual(v["principal"]["pct_fuente"], "sin_dato")

    # -- máquina de estados -------------------------------------------------
    def test_transiciones(self):
        tr = tablero.transicion
        self.assertEqual(tr("activa", 50, CFG), "activa")
        self.assertEqual(tr("activa", 9, CFG), "restringida")
        self.assertEqual(tr("activa", 0, CFG), "cuarentena")
        self.assertEqual(tr("restringida", 12, CFG), "restringida")  # margen: 10+5=15
        self.assertEqual(tr("restringida", 15, CFG), "activa")
        self.assertEqual(tr("restringida", 0, CFG), "cuarentena")
        self.assertEqual(tr("cuarentena", 20, CFG), "activa")
        self.assertEqual(tr("cuarentena", 12, CFG), "cuarentena")  # ni salida ni restringida
        self.assertEqual(tr("cuarentena", 5, CFG), "restringida")
        self.assertEqual(tr("cuarentena", 0, CFG), "cuarentena")
        for e in tablero.ESTADOS:  # sin dato conserva
            self.assertEqual(tr(e, None, CFG), e)

    def test_estado_se_persiste_con_margen(self):
        # Declarar un % bajo recalcula el estado de la cuenta al momento.
        tablero.declarar_pct(self.base, "principal", 5, reloj=self.reloj)
        self.assertEqual(tablero.cargar(self.base)["cuentas"]["principal"]["estado"], "restringida")
        # Sube a 12 (sobre el umbral pero bajo el margen): sigue restringida.
        tablero.declarar_pct(self.base, "principal", 12, reloj=self.reloj)
        self.assertEqual(tablero.cargar(self.base)["cuentas"]["principal"]["estado"], "restringida")
        # A 15 (umbral + margen) sale.
        tablero.declarar_pct(self.base, "principal", 15, reloj=self.reloj)
        self.assertEqual(tablero.cargar(self.base)["cuentas"]["principal"]["estado"], "activa")

    def test_recalcular_con_estimaciones(self):
        tablero.publicar(self.base, "principal", tarea="x", reloj=self.reloj)
        estados = tablero.recalcular(self.base, {"principal": 0}, reloj=self.reloj)
        self.assertEqual(estados["principal"], "cuarentena")
        e = tablero.cargar(self.base)["cuentas"]["principal"]
        self.assertEqual(e["estado"], "cuarentena")
        self.assertIn("estado_ts", e)
        # Idempotente: sin cambios no sube la revision.
        rev = tablero.cargar(self.base)["revision"]
        tablero.recalcular(self.base, {"principal": 0}, reloj=self.reloj)
        self.assertEqual(tablero.cargar(self.base)["revision"], rev)

    def test_declarado_caducado_se_distigue(self):
        tablero.declarar_pct(self.base, "principal", 40, reloj=self.reloj)
        self.reloj.t += CFG["frescura_declarado_s"] + 10
        v = self._vista(estimador=lambda c, m: None)
        self.assertIsNone(v["principal"]["pct_efectivo"])
        self.assertEqual(v["principal"]["pct_fuente"], "declarado_caducado")
        self.assertEqual(v["principal"]["pct_declarado"], 40)  # el reporte queda

    def test_puerta_usa_el_minimo(self):
        tablero.declarar_pct(self.base, "principal", 80, reloj=self.reloj)
        v = self._vista(estimador=lambda c, m: 30)
        self.assertEqual(v["principal"]["pct_efectivo"], 80)  # manda el declarado
        self.assertEqual(v["principal"]["pct_puerta"], 30)     # la puerta, el minimo
        self.assertEqual(v["principal"]["pct_estimado"], 30)

    def test_declarado_fresco_por_evento(self):
        # Declarado viejo por reloj, pero la cuenta sigue en la misma tarea
        # con latido fresco: el declarado sigue mandando.
        tablero.publicar(self.base, "principal", tarea="tarea larga", reloj=self.reloj)
        tablero.declarar_pct(self.base, "principal", 55, reloj=self.reloj)
        self.reloj.t += CFG["frescura_declarado_s"] + 600
        tablero.publicar(self.base, "principal", avance=70, reloj=self.reloj)  # latido
        v = self._vista(estimador=lambda c, m: None)
        self.assertEqual(v["principal"]["pct_fuente"], "declarado")
        self.assertEqual(v["principal"]["pct_efectivo"], 55)

    def test_hueco_cero_uno(self):
        # Un estimado de 0.4 se normaliza a 0: cuarentena, sin hueco (0,1).
        tablero.publicar(self.base, "principal", tarea="x", reloj=self.reloj)
        estados = tablero.recalcular(self.base, {"principal": 0.4}, reloj=self.reloj)
        self.assertEqual(estados["principal"], "cuarentena")

    def test_config_invalida_rechazada(self):
        with self.assertRaises(tablero.ErrorTablero):
            tablero.guardar_config(self.base, umbral_cuarentena=98, margen_salida=5)
        with self.assertRaises(tablero.ErrorTablero):
            tablero.guardar_config(self.base, umbral_cuarentena=0)
        # Y una config imposible escrita a mano cae a los valores por defecto.
        import json as _json
        with open(os.path.join(self.base, "tablero.json"), "w") as f:
            _json.dump({"version": 1, "revision": 0,
                        "config": {"umbral_cuarentena": 99, "margen_salida": 5,
                                   "frescura_declarado_s": 1800},
                        "cuentas": {}}, f)
        t = tablero.cargar(self.base)
        self.assertEqual(t["config"]["umbral_cuarentena"], CFG["umbral_cuarentena"])
        self.assertIsNotNone(tablero.problema(self.base))

    def test_liberar(self):
        tablero.declarar_pct(self.base, "principal", 0, reloj=self.reloj)
        self.assertEqual(tablero.cargar(self.base)["cuentas"]["principal"]["estado"], "cuarentena")
        tablero.liberar(self.base, "principal", reloj=self.reloj)
        self.assertEqual(tablero.cargar(self.base)["cuentas"]["principal"]["estado"], "activa")
        with self.assertRaises(tablero.ErrorTablero):
            tablero.liberar(self.base, "fantasma")

    # -- reparto -------------------------------------------------------------
    def _registro(self):
        return {"cuentas": [
            {"id": "principal", "habilitada": True, "carril": "a"},
            {"id": "segunda", "habilitada": True, "carril": "b"},
            {"id": "tercera", "habilitada": True, "carril": None},
            {"id": "apagada", "habilitada": False, "carril": "b"},
        ]}

    def _vista_de(self, datos):
        return {cid: {"estado": e, "pct_efectivo": p} for cid, (e, p) in datos.items()}

    def test_elegir_mayor_pct(self):
        v = self._vista_de({"principal": ("activa", 40), "segunda": ("activa", 70)})
        self.assertEqual(tablero.elegir_cuenta(v, {}, self._registro()), "segunda")

    def test_elegir_excluye_restringida_y_sin_carril(self):
        v = self._vista_de({"principal": ("restringida", 5), "segunda": ("activa", 20),
                            "tercera": ("activa", 99)})
        self.assertEqual(tablero.elegir_cuenta(v, {}, self._registro()), "segunda")
        v2 = self._vista_de({"principal": ("cuarentena", 0), "segunda": ("restringida", 3)})
        self.assertIsNone(tablero.elegir_cuenta(v2, {}, self._registro()))

    def test_elegir_desempates_deterministas(self):
        v = self._vista_de({"principal": ("activa", 50), "segunda": ("activa", 50)})
        # Mismo %: menos tareas activas.
        self.assertEqual(tablero.elegir_cuenta(v, {"principal": 2, "segunda": 1},
                                               self._registro()), "segunda")
        # Mismo % y mismas tareas: id ascendente, siempre igual.
        self.assertEqual(tablero.elegir_cuenta(v, {}, self._registro()), "principal")
        self.assertEqual(tablero.elegir_cuenta(v, {}, self._registro()), "principal")

    def test_elegir_sin_dato_va_detras(self):
        v = self._vista_de({"principal": ("activa", None), "segunda": ("activa", 15)})
        self.assertEqual(tablero.elegir_cuenta(v, {}, self._registro()), "segunda")
        v2 = self._vista_de({"principal": ("activa", None), "segunda": ("activa", None)})
        self.assertEqual(tablero.elegir_cuenta(v2, {}, self._registro()), "principal")


def _pub_proceso(base, cuenta, n):
    for i in range(n):
        tablero.publicar(base, cuenta, avance=i)


class TestTableroProcesos(unittest.TestCase):
    def test_dos_procesos_no_se_pisan(self):
        with tempfile.TemporaryDirectory() as base:
            p1 = mp.Process(target=_pub_proceso, args=(base, "principal", 12))
            p2 = mp.Process(target=_pub_proceso, args=(base, "segunda", 12))
            p1.start(); p2.start(); p1.join(30); p2.join(30)
            self.assertEqual(p1.exitcode, 0)
            self.assertEqual(p2.exitcode, 0)
            t = tablero.cargar(base)
            self.assertEqual(t["cuentas"]["principal"]["avance"], 11)
            self.assertEqual(t["cuentas"]["segunda"]["avance"], 11)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Pruebas del modo dual (Fase 1): histéresis y corte de red con contadores.

La prueba de corte NO cuenta filas de una cola: cuenta EJECUCIONES en cada
lado (servidor y local). El invariante es que cada tarea se ejecuta
exactamente una vez en total, también si estaba en vuelo cuando cayó la red.

Ejecutar: python3 test_dual.py
"""
import unittest

import dual


class RedFalsa:
    """Red con interruptor: la sonda y el ejecutor del servidor la comparten."""

    def __init__(self):
        self.arriba = True
        self.ejecuciones_servidor = {}

    def probar(self):
        return self.arriba

    def ejecutar_en_servidor(self, tarea_id):
        assert self.arriba, "el servidor no puede ejecutar sin red"
        self.ejecuciones_servidor[tarea_id] = \
            self.ejecuciones_servidor.get(tarea_id, 0) + 1


class TestHisteresis(unittest.TestCase):
    def test_un_fallo_no_cambia_nada(self):
        red = RedFalsa()
        v = dual.VigiaDual(red.probar, fallos_para_local=3,
                           exitos_para_servidor=2)
        red.arriba = False
        v.tick()
        v.tick()
        self.assertEqual(v.estado, dual.SERVIDOR)  # 2 fallos < 3
        v.tick()
        self.assertEqual(v.estado, dual.LOCAL)     # 3.er fallo seguido

    def test_volver_exige_exitos_seguidos(self):
        red = RedFalsa()
        v = dual.VigiaDual(red.probar, fallos_para_local=1,
                           exitos_para_servidor=2)
        red.arriba = False
        v.tick()
        self.assertEqual(v.estado, dual.LOCAL)
        red.arriba = True
        v.tick()
        self.assertEqual(v.estado, dual.LOCAL)     # 1 éxito no basta
        red.arriba = False
        v.tick()                                    # un fallo reinicia la racha
        red.arriba = True
        v.tick()
        self.assertEqual(v.estado, dual.LOCAL)
        v.tick()
        self.assertEqual(v.estado, dual.RECONCILIANDO)


class TestCorteDeRed(unittest.TestCase):
    def test_cada_tarea_se_ejecuta_exactamente_una_vez(self):
        red = RedFalsa()
        v = dual.VigiaDual(red.probar, fallos_para_local=2,
                           exitos_para_servidor=1)
        ejecuciones_local = {}

        def ejecutar_local(tarea_id):
            ejecuciones_local[tarea_id] = ejecuciones_local.get(tarea_id, 0) + 1

        # 1) Con red: t1 se confirma hecha en el servidor; t2 sale y queda
        #    en vuelo (sin confirmación) justo cuando cae la red.
        red.ejecutar_en_servidor("t1")
        v.registrar_en_vuelo("t1")
        v.confirmar_hecha_en_servidor("t1")
        red.ejecutar_en_servidor("t2")       # el servidor SÍ la ejecutó…
        v.registrar_en_vuelo("t2")           # …pero la confirmación se perdió
        v.registrar_en_vuelo("t3")           # t3 salió y el servidor NO la hizo

        # 2) Corte: la histéresis lleva el vigía a local.
        red.arriba = False
        v.tick(); v.tick()
        self.assertEqual(v.estado, dual.LOCAL)

        # 3) En local: t4 (nueva, nunca salió) se puede ejecutar; t2 y t3 NO
        #    (están por confirmar: ejecutarlas aquí podría duplicarlas).
        self.assertTrue(v.puede_ejecutar_en_local("t4"))
        ejecutar_local("t4")
        self.assertFalse(v.puede_ejecutar_en_local("t2"))
        self.assertFalse(v.puede_ejecutar_en_local("t3"))

        # 4) Vuelve la red: reconciliación. El servidor dice la verdad:
        #    t2 hecha, t3 no hecha -> t3 se ejecuta en local, una vez.
        red.arriba = True
        v.tick()
        self.assertEqual(v.estado, dual.RECONCILIANDO)
        res = v.reconciliar(resolver=lambda tid: tid in red.ejecuciones_servidor,
                            ejecutar_local=ejecutar_local)
        self.assertEqual(res, {"hechas_en_servidor": 1, "hechas_en_local": 1})
        self.assertEqual(v.estado, dual.SERVIDOR)
        self.assertEqual(v.por_confirmar, {})

        # 5) El invariante: ejecuciones totales por tarea == 1.
        totales = {}
        for fuente in (red.ejecuciones_servidor, ejecuciones_local):
            for tid, n in fuente.items():
                totales[tid] = totales.get(tid, 0) + n
        self.assertEqual(totales, {"t1": 1, "t2": 1, "t3": 1, "t4": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)

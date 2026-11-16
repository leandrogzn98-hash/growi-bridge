"""Pruebas de la presencia del dueño (Fase 4): tabla de verdad,
histéresis (3 confirmaciones para ausente, vuelta inmediata a presente)
y override manual que siempre manda.

Ejecutar: python3 -m unittest test_presencia
"""
import tempfile
import unittest
from pathlib import Path

import presencia

AUSENTE = {"idle_s": 5000, "pantalla_completa": False,
           "sesion_bloqueada": False, "proceso_absorbente": False,
           "gpu_ajena_cargada": False}
PRESENTE = {"idle_s": 5, "pantalla_completa": False,
            "sesion_bloqueada": False, "proceso_absorbente": False,
            "gpu_ajena_cargada": False}


class TestEvaluar(unittest.TestCase):
    def test_pelicula_pantalla_completa_con_idle_enorme(self):
        s = dict(AUSENTE, pantalla_completa=True, idle_s=99999)
        self.assertEqual(presencia.evaluar(s), "presente")

    def test_tecleando_es_presente(self):
        self.assertEqual(presencia.evaluar(PRESENTE), "presente")

    def test_lejos_y_sin_nada_es_ausente(self):
        self.assertEqual(presencia.evaluar(AUSENTE), "ausente")

    def test_idle_intermedio_no_basta(self):
        # 1000 s > umbral de ausencia (900) pero < 3600 y sin bloqueo:
        # no hay evidencia positiva de ausencia -> presente.
        s = dict(AUSENTE, idle_s=1000)
        self.assertEqual(presencia.evaluar(s), "presente")

    def test_sesion_bloqueada_sin_senales_es_ausente(self):
        # La excepción I1: bloqueada y sin ninguna señal positiva basta
        # (si no, en Wayland el presupuesto de ausente sería inalcanzable).
        s = {"idle_s": None, "pantalla_completa": None,
             "sesion_bloqueada": True, "proceso_absorbente": None,
             "gpu_ajena_cargada": None}
        self.assertEqual(presencia.evaluar(s), "ausente")

    def test_bloqueada_pero_pantalla_completa_es_presente(self):
        s = dict(AUSENTE, sesion_bloqueada=True, pantalla_completa=True)
        self.assertEqual(presencia.evaluar(s), "presente")

    def test_proceso_absorbente_desbloqueado_es_presente(self):
        s = dict(AUSENTE, proceso_absorbente=True, idle_s=300)
        self.assertEqual(presencia.evaluar(s), "presente")

    def test_proceso_absorbente_bloquea_la_ausencia(self):
        s = dict(AUSENTE, proceso_absorbente=True)
        self.assertEqual(presencia.evaluar(s), "presente")

    def test_gpu_ajena_con_idle_bajo_es_presente(self):
        s = dict(AUSENTE, gpu_ajena_cargada=True, idle_s=300)
        self.assertEqual(presencia.evaluar(s), "presente")

    def test_todo_desconocido_es_presente(self):
        self.assertEqual(presencia.evaluar({}), "presente")
        self.assertEqual(presencia.evaluar(None), "presente")
        s = {k: None for k in presencia.SENALES}
        self.assertEqual(presencia.evaluar(s), "presente")


class TestMaquina(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.t = [1000.0]
        self.reloj = lambda: self.t[0]

    def tearDown(self):
        self.tmp.cleanup()

    def _ticks(self, senales, n):
        est = None
        for _ in range(n):
            self.t[0] += 30
            est = presencia.tick(self.base, senales, reloj=self.reloj)
        return est

    def test_histeresis_tres_confirmaciones(self):
        est = self._ticks(AUSENTE, 2)
        self.assertEqual(est["modo"], "presente")  # 2 no bastan
        est = self._ticks(AUSENTE, 1)
        self.assertEqual(est["modo"], "ausente")    # la 3ª confirma

    def test_vuelta_a_presente_inmediata(self):
        self._ticks(AUSENTE, 3)
        self.assertEqual(presencia.modo_efectivo(self.base), "ausente")
        est = self._ticks(PRESENTE, 1)
        self.assertEqual(est["modo"], "presente")   # sin histéresis

    def test_racha_se_rompe_con_un_presente(self):
        self._ticks(AUSENTE, 2)
        self._ticks(PRESENTE, 1)
        est = self._ticks(AUSENTE, 2)
        self.assertEqual(est["modo"], "presente")
        est = self._ticks(AUSENTE, 1)
        self.assertEqual(est["modo"], "ausente")

    def test_override_manda_siempre(self):
        presencia.poner_override(self.base, "presente", reloj=self.reloj)
        est = self._ticks(AUSENTE, 5)
        self.assertEqual(est["modo"], "presente")
        self.assertEqual(presencia.modo_efectivo(self.base), "presente")
        presencia.poner_override(self.base, "ausente", reloj=self.reloj)
        self.assertEqual(presencia.modo_efectivo(self.base), "ausente")

    def test_override_caducado_vuelve_al_automatico(self):
        self.t[0] = 2000.0
        presencia.poner_override(self.base, "presente",
                                 hasta_ts=2100.0, reloj=self.reloj)
        self.assertEqual(presencia.modo_efectivo(self.base), "presente")
        self.t[0] = 2200.0  # el override ya caducó
        est = presencia.tick(self.base, PRESENTE, reloj=self.reloj)
        self.assertIsNone(est["override"])
        self.assertTrue(any(h["motivo"].startswith("override caducado")
                            for h in est["historial"]))

    def test_la_ultima_evaluacion_queda_guardada(self):
        est = presencia.tick(self.base, AUSENTE, reloj=self.reloj)
        self.assertEqual(est["ultima"]["veredicto"], "ausente")
        self.assertEqual(est["ultima"]["senales"]["idle_s"], 5000)

    def test_marca_de_supervision(self):
        presencia.marcar_supervision_ts(self.base, 1234.5)
        est = presencia.leer_estado(self.base)
        self.assertEqual(est["supervision_ts"], 1234.5)


if __name__ == "__main__":
    unittest.main()

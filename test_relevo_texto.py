# -*- coding: utf-8 -*-
"""Pruebas del veto de motores solo-texto (Growi Private MQTT, P5):
una cuenta cuyo motor efectivo es de chat (DeepSeek/Kimi) no recibe
fases de código (con git o archivos), sí fases de texto; si todas las
candidatas están vetadas, la fase queda sin asignar con el motivo
claro; sin los parámetros nuevos, el reparto no cambia.

Ejecutar: python3 -m unittest test_relevo_texto
"""
import tempfile
import time
import unittest
from pathlib import Path

import relevo

REGISTRO = {
    "version": 1, "revision": 1,
    "cuentas": [
        {"id": "principal", "nombre": "Principal", "carril": "a",
         "conexion": "ambas", "habilitada": True, "motor": "deepseek"},
        {"id": "segunda", "nombre": "Segunda", "carril": "b",
         "conexion": "ambas", "habilitada": True},
    ],
}
MOTORES = {"principal": "deepseek", "segunda": None}
TEXTO = {"deepseek", "kimi"}


def vista(pcts=None):
    pcts = pcts or {}
    return {cid: {"estado": "activa", "pct_puerta": pcts.get(cid, 80),
                  "motor_principal": "claude", "latido_ts": time.time(),
                  "tarea": None}
            for cid in ("principal", "segunda")}


def motor_fn(cid):
    return MOTORES.get(cid)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _raiz(self):
        return relevo.registrar_encargo(
            self.base, {"id": "t-enc-1", "prompt": "encargo",
                        "cwd": "/home/dueno/juego"}, receptora="segunda")


class TestVetoTexto(Base):
    def test_fase_de_codigo_no_va_a_la_de_texto(self):
        raiz = self._raiz()
        # principal tiene más % y el motor de texto: la fase con git
        # debe ir a segunda aunque pierda por %.
        res = relevo.asignar(
            self.base, raiz,
            [{"prompt": "escribe el nivel 2", "git": {"repo": "juego"},
              "archivos": ["nivel2.py"]}],
            vista({"principal": 95, "segunda": 40}), REGISTRO, {},
            motor_fn=motor_fn, motores_texto=TEXTO)
        self.assertEqual(res[f"{raiz}-s1"], "segunda")

    def test_fase_de_texto_si_puede_ir(self):
        raiz = self._raiz()
        res = relevo.asignar(
            self.base, raiz,
            [{"prompt": "redacta el resumen del encargo"}],
            vista({"principal": 95, "segunda": 40}), REGISTRO, {},
            motor_fn=motor_fn, motores_texto=TEXTO)
        self.assertEqual(res[f"{raiz}-s1"], "principal")

    def test_todas_vetadas_motivo_claro(self):
        raiz = self._raiz()
        reg = {"version": 1, "revision": 1, "cuentas": [
            dict(REGISTRO["cuentas"][0]),
            dict(REGISTRO["cuentas"][1], motor="kimi")]}
        res = relevo.asignar(
            self.base, raiz,
            [{"prompt": "escribe el nivel 2", "archivos": ["nivel2.py"]}],
            vista(), reg, {},
            motor_fn=lambda cid: {"principal": "deepseek",
                                  "segunda": "kimi"}.get(cid),
            motores_texto=TEXTO)
        sid = f"{raiz}-s1"
        self.assertIsNone(res[sid])
        sub = relevo.obtener(self.base, raiz)["subtareas"][sid]
        self.assertIn("solo de texto", sub["motivo"])

    def test_motor_de_la_subtarea_tambien_veta(self):
        raiz = self._raiz()
        # La subtarea pide deepseek expresamente y es de código: nadie
        # puede hacerla (el motor efectivo es el de la subtarea).
        res = relevo.asignar(
            self.base, raiz,
            [{"prompt": "escribe el nivel 2", "motor": "deepseek",
              "archivos": ["nivel2.py"]}],
            vista(), REGISTRO, {},
            motor_fn=motor_fn, motores_texto=TEXTO)
        self.assertIsNone(res[f"{raiz}-s1"])

    def test_sin_parametros_nada_cambia(self):
        raiz = self._raiz()
        res = relevo.asignar(
            self.base, raiz,
            [{"prompt": "escribe el nivel 2", "git": {"repo": "juego"},
              "archivos": ["nivel2.py"]}],
            vista({"principal": 95, "segunda": 40}), REGISTRO, {})
        self.assertEqual(res[f"{raiz}-s1"], "principal")

    def test_veto_tambien_con_fuertes(self):
        raiz = self._raiz()

        def fn(cid, spec):
            return (1.0, "loquesea") if cid == "principal" else (0.0, None)

        res = relevo.asignar(
            self.base, raiz,
            [{"prompt": "escribe el nivel 2", "archivos": ["nivel2.py"]}],
            vista({"principal": 95, "segunda": 40}), REGISTRO, {},
            fuertes_fn=fn, motor_fn=motor_fn, motores_texto=TEXTO)
        self.assertEqual(res[f"{raiz}-s1"], "segunda")


if __name__ == "__main__":
    unittest.main()

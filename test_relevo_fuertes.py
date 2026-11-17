# -*- coding: utf-8 -*-
"""Pruebas del reparto por puntos con fuertes (Growi Private MQTT, P4):
con `fuertes_fn`, la fórmula 0,4·fuerte + 0,3·peso(topado por el
fuerte) + 0,2·tokens + 0,1·(1−carga) decide la asignación y deja los
puntos guardados en la subtarea; sin ella, el reparto es el de siempre.

Ejecutar: python3 -m unittest test_relevo_fuertes
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
         "conexion": "ambas", "habilitada": True},
        {"id": "segunda", "nombre": "Segunda", "carril": "b",
         "conexion": "ambas", "habilitada": True},
    ],
}


def vista(pcts):
    return {cid: {"estado": "activa", "pct_puerta": pcts.get(cid),
                  "motor_principal": "claude", "latido_ts": time.time(),
                  "tarea": None}
            for cid in ("principal", "segunda")}


def fn_por_texto(mapa):
    """fuertes_fn de juguete: mapa {cuenta: (palabra, skill)} — factor 1
    si la palabra aparece en el prompt de la subtarea."""
    def fn(cid, spec):
        entrada = mapa.get(cid)
        if not entrada:
            return 0.0, None
        palabra, skill = entrada
        texto = str((spec or {}).get("prompt") or "")
        return (1.0, skill) if palabra in texto else (0.0, None)
    return fn


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _raiz(self):
        return relevo.registrar_encargo(
            self.base, {"id": "t-enc-1", "prompt": "encargo",
                        "cwd": "/home/dueno/juego"}, receptora="principal")


class TestRepartoConFuertes(Base):
    def test_el_fuerte_gana_al_porcentaje(self):
        raiz = self._raiz()
        # principal tiene muchos más tokens libres, pero la fase es de
        # revisión y el fuerte de revisión es de segunda.
        fn = fn_por_texto({"segunda": ("revisa", "revision-de-codigo")})
        res = relevo.asignar(
            self.base, raiz, [{"prompt": "revisa el nivel 2 a fondo"}],
            vista({"principal": 95, "segunda": 40}), REGISTRO, {},
            fuertes_fn=fn)
        sid = f"{raiz}-s1"
        self.assertEqual(res[sid], "segunda")
        sub = relevo.obtener(self.base, raiz)["subtareas"][sid]
        self.assertEqual(sub["fuerte"], 1.0)
        self.assertEqual(sub["skill_fuerte"], "revision-de-codigo")
        self.assertIsNotNone(sub["puntos"])

    def test_sin_fuertes_fn_el_reparto_es_el_de_siempre(self):
        raiz = self._raiz()
        res = relevo.asignar(
            self.base, raiz, [{"prompt": "revisa el nivel 2 a fondo"}],
            vista({"principal": 95, "segunda": 40}), REGISTRO, {})
        sid = f"{raiz}-s1"
        self.assertEqual(res[sid], "principal")
        sub = relevo.obtener(self.base, raiz)["subtareas"][sid]
        self.assertNotIn("fuerte", sub)

    def test_sin_encaje_manda_el_porcentaje(self):
        raiz = self._raiz()
        fn = fn_por_texto({"segunda": ("revisa", "revision-de-codigo")})
        res = relevo.asignar(
            self.base, raiz, [{"prompt": "dibuja el nivel 3"}],
            vista({"principal": 95, "segunda": 40}), REGISTRO, {},
            fuertes_fn=fn)
        self.assertEqual(res[f"{raiz}-s1"], "principal")

    def test_peso_declarado_topado_por_el_fuerte(self):
        # Segunda se autopide con peso 100, pero su fuerte no encaja:
        # el peso efectivo queda topado a 0 y no le roba la fase a
        # principal, cuyo fuerte sí encaja.
        raiz = self._raiz()
        fn = fn_por_texto({"principal": ("ahorra", "ahorro")})
        spec = {"prompt": "ahorra tokens en el nivel 2",
                "pesos": {"segunda": 100, "principal": 10}}
        res = relevo.asignar(self.base, raiz, [spec],
                             vista({"principal": 50, "segunda": 50}),
                             REGISTRO, {}, fuertes_fn=fn)
        self.assertEqual(res[f"{raiz}-s1"], "principal")

    def test_cuentas_no_activas_no_entran(self):
        raiz = self._raiz()
        fn = fn_por_texto({"segunda": ("revisa", "revision-de-codigo")})
        v = vista({"principal": 95, "segunda": 40})
        v["segunda"]["estado"] = "cuarentena"
        res = relevo.asignar(
            self.base, raiz, [{"prompt": "revisa el nivel 2"}],
            v, REGISTRO, {}, fuertes_fn=fn)
        self.assertEqual(res[f"{raiz}-s1"], "principal")

    def test_fuerte_parcial_cuenta_medio(self):
        raiz = self._raiz()

        def fn(cid, spec):
            if cid == "segunda":
                return 0.5, "revision-de-codigo"
            return 0.0, None

        # Con % iguales y sin carga, el 0,5 de fuerte basta para ganar
        # al 0 de la otra (0,4·0,5 + 0,3·0,5 = 0,35 contra 0,2·tokens…).
        res = relevo.asignar(
            self.base, raiz, [{"prompt": "lo que sea"}],
            vista({"principal": 10, "segunda": 10}), REGISTRO, {},
            fuertes_fn=fn)
        self.assertEqual(res[f"{raiz}-s1"], "segunda")


if __name__ == "__main__":
    unittest.main()

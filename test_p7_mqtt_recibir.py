# -*- coding: utf-8 -*-
"""Regresión de la P7: el cableado MQTT del monolito usaba
`cuentas.` sin importar el módulo. En vivo eso descartaba todo
resultado/aviso recibido («name 'cuentas' is not defined»),
impedía enviar tareas y dejaba la redacción de la sala sin los
valores de la bóveda. Estas pruebas llaman a las tres funciones
en el monolito importado en aislamiento, como corre la app."""
import importlib.util
import json
import os
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
        "gb_p7", RAIZ / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    sys.modules["gb_p7"] = gb
    spec.loader.exec_module(gb)
    return gb


class TestRecibirMQTT(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gb-p7-"))
        cls.gb = _cargar_monolito(cls.tmp)

    def setUp(self):
        # El monolito resuelve APP_DIR desde su propio archivo: se
        # apunta al temporal para no tocar el registro de verdad.
        self.gb.APP_DIR = self.tmp
        self.gb.CRED_DPAPI_FILE = self.tmp / "credenciales.dpapi.json"
        self.gb._CRED_MEM.clear()
        import cuentas as cm
        reg = cm.cargar(self.tmp)
        if not any(c["id"] == "segunda" for c in reg["cuentas"]):
            reg["cuentas"].append(
                {"id": "segunda", "nombre": "Segunda",
                 "asistente": None, "carril": "b",
                 "conexion": "mqtt", "habilitada": True,
                 "creada": None,
                 "permisos": {"modo": "hereda",
                              "clases_extra_denegadas": []}})
            cm.guardar(self.tmp, reg)
        self.gb._CUENTAS_CACHE = {"reg": None, "clave": "forzar"}
        self.gb._sec_set("muse:segunda", "CLAVE-P7-TEST")

    def test_resultado_valido_se_archiva(self):
        gb = self.gb
        sobre = {"v": 1, "id": "sobre-p7-1", "tipo": "resultado",
                 "ts": 1, "cuenta": "segunda", "clave": "CLAVE-P7-TEST",
                 "datos": {"texto": "listo"}}
        gb._fpm_al_recibir(sobre, "growi/x/segunda/resultados")
        destino = gb._token_dir() / "mqtt-resultados" / "sobre-p7-1.json"
        self.assertTrue(destino.exists(),
                        "el sobre válido debe archivarse")
        self.assertEqual(json.loads(destino.read_text(
            encoding="utf-8"))["datos"]["texto"], "listo")

    def test_resultado_clave_mala_se_descarta(self):
        gb = self.gb
        sobre = {"v": 1, "id": "sobre-p7-2", "tipo": "resultado",
                 "ts": 1, "cuenta": "segunda", "clave": "OTRA",
                 "datos": {"texto": "no"}}
        gb._fpm_al_recibir(sobre, "growi/x/segunda/resultados")
        destino = gb._token_dir() / "mqtt-resultados" / "sobre-p7-2.json"
        self.assertFalse(destino.exists())

    def test_enviar_tarea_usa_la_clave_de_la_cuenta(self):
        gb = self.gb

        class FalsoEnlace:
            def __init__(self):
                self.llamadas = []

            def publicar_tarea(self, cuenta, datos, clave):
                self.llamadas.append((cuenta, datos, clave))
                return "sobre-saliente-1"

        falso = FalsoEnlace()
        gb._FPM["enlace"] = falso
        try:
            sid = gb._mqtt_enviar_tarea("segunda", {"prompt": "hola"})
        finally:
            gb._FPM["enlace"] = None
        self.assertEqual(sid, "sobre-saliente-1")
        self.assertEqual(falso.llamadas[0][2], "CLAVE-P7-TEST")

    def test_sala_valores_incluye_las_claves(self):
        valores = self.gb._sala_valores()
        self.assertIn("CLAVE-P7-TEST", valores)


if __name__ == "__main__":
    unittest.main()

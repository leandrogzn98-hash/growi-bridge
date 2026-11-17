# -*- coding: utf-8 -*-
"""Pruebas de la P5 en el monolito: las fichas de DeepSeek/Kimi
existen y están bien formadas, el motor propio de la cuenta manda
cuando la tarea no pide otro, la clave propia de la cuenta gana a
la general, y la detección de MCP solo lee nombres.

El monolito se importa aislado como en test_skills_fuertes.

Ejecutar: python3 -m unittest test_motores_p5
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent


def _cargar_monolito():
    tmp = Path(tempfile.mkdtemp(prefix="gb-p5-"))
    env = {
        "GROWI_BRIDGE_APP_DIR": str(tmp),
        "GROWI_BRIDGE_INBOX": str(tmp / "share" / "inbox"),
        "GROWI_BRIDGE_SCREENS": str(tmp / "share" / "screens"),
        "GROWI_BRIDGE_SKILLS": str(tmp / "skills"),
        "GROWI_BRIDGE_SECRET": "secreto-de-prueba",
        "HOME": str(tmp),
    }
    viejos = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        spec = importlib.util.spec_from_file_location(
            "gb_p5", _RAIZ / "growi-bridge.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["gb_p5"] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in viejos.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


gb = _cargar_monolito()


class TestFichas(unittest.TestCase):
    def test_las_fichas_existen_y_estan_bien(self):
        ids = gb.engine_ids()
        self.assertIn("deepseek", ids)
        self.assertIn("kimi", ids)
        for mid in ("deepseek", "kimi"):
            eng = gb.get_engine(mid)
            self.assertIsNotNone(eng)
            self.assertNotEqual(eng.get("tipo"), "_mal_formado",
                                eng.get("_problemas"))
            self.assertEqual(eng.get("tipo"), "api_sincrona")

    def test_solo_texto(self):
        texto = gb._f5_motores_texto()
        self.assertIn("deepseek", texto)
        self.assertIn("kimi", texto)
        self.assertNotIn("claude", texto)
        self.assertNotIn("llama", texto)

    def test_sin_clave_no_disponible(self):
        ok, why = gb.engine_status("deepseek")
        self.assertFalse(ok)
        self.assertIn("clave", why.lower())


class TestMotorParaTarea(unittest.TestCase):
    def setUp(self):
        import cuentas as cm
        self.reg = cm.cargar(gb.APP_DIR, carril="a")
        self.reg["cuentas"] = [
            {"id": "principal", "nombre": "P", "asistente": None,
             "carril": "a", "conexion": "servidor", "habilitada": True,
             "creada": None,
             "permisos": {"modo": "hereda",
                          "clases_extra_denegadas": []}},
            {"id": "segunda", "nombre": "S", "asistente": None,
             "carril": "b", "conexion": "servidor", "habilitada": True,
             "creada": None, "motor": "deepseek",
             "permisos": {"modo": "hereda",
                          "clases_extra_denegadas": []}}]
        # El registro se escribe de verdad en el APP_DIR aislado:
        # _cuentas_reg() cachea por (mtime, tamaño) del archivo.
        cm.guardar(gb.APP_DIR, self.reg)
        gb._CUENTAS_CACHE.update({"reg": None, "clave": "forzar"})
        gb._ENV_TAREA.clear()

    def tearDown(self):
        gb._CUENTAS_CACHE.update({"reg": None, "clave": "forzar"})
        gb._ENV_TAREA.clear()

    def test_el_de_la_tarea_manda(self):
        gb._ENV_TAREA["GROWI_CUENTA_ID"] = "segunda"
        self.assertEqual(gb._motor_para_tarea({"motor": "claude"}),
                         "claude")

    def test_el_de_la_cuenta_si_no_pide(self):
        gb._ENV_TAREA["GROWI_CUENTA_ID"] = "segunda"
        self.assertEqual(gb._motor_para_tarea({}), "deepseek")

    def test_sin_motor_propio_el_del_programa(self):
        gb._ENV_TAREA["GROWI_CUENTA_ID"] = "principal"
        self.assertEqual(gb._motor_para_tarea({}), gb.default_motor())

    def test_motor_de_cuenta_para_el_reparto(self):
        self.assertEqual(gb._f5_motor_de_cuenta("segunda"), "deepseek")
        self.assertIsNone(gb._f5_motor_de_cuenta("principal"))

    def test_validate_task_aplica_el_motor_de_la_cuenta(self):
        # validate_task siempre estampa un motor: el de la cuenta de
        # ESTE carril (en la importación aislada, la principal) manda
        # en el último resorte; el de otra cuenta, no.
        import cuentas as cm
        reg = cm.cargar(gb.APP_DIR, carril="a")
        for c in reg["cuentas"]:
            if c["id"] == "principal":
                c["motor"] = "kimi"
        cm.guardar(gb.APP_DIR, reg)
        gb._CUENTAS_CACHE.update({"reg": None, "clave": "forzar"})
        casa = str(gb.HOME_DIR)
        base = {"prompt": "resume el proyecto", "cwd": casa,
                "archivos": [casa + "/archivo.txt"]}
        Path(casa, "archivo.txt").write_text("x", encoding="utf-8")
        tarea, err = gb.validate_task(dict(base, id="v1",
                                           cuenta="principal"))
        self.assertIsNone(err)
        self.assertEqual(tarea["motor"], "kimi")
        tarea, err = gb.validate_task(dict(base, id="v2",
                                           cuenta="segunda"))
        self.assertIsNone(err)
        self.assertEqual(tarea["motor"], gb.default_motor())
        tarea, err = gb.validate_task(dict(base, id="v3"))
        self.assertIsNone(err)
        self.assertEqual(tarea["motor"], gb.default_motor())
        # Y si la tarea pide su motor, el suyo manda:
        tarea, err = gb.validate_task(dict(base, id="v4",
                                           cuenta="principal",
                                           motor="claude"))
        self.assertIsNone(err)
        self.assertEqual(tarea["motor"], "claude")


class TestClavePropia(unittest.TestCase):
    def setUp(self):
        gb._ENV_TAREA.clear()
        self._get = gb._sec_get
        self.vault = {"motor:segunda:deepseek": "sk-propia-123"}
        gb._sec_get = lambda nombre: self.vault.get(nombre)

    def tearDown(self):
        gb._sec_get = self._get
        gb._ENV_TAREA.clear()

    def test_la_propia_gana(self):
        gb._ENV_TAREA["GROWI_CUENTA_ID"] = "segunda"
        eng = gb.get_engine("deepseek")
        self.assertEqual(gb._clave_motor_cuenta(eng), "sk-propia-123")
        key, base, why = gb.resolver_credencial_motor(eng)
        self.assertEqual(key, "sk-propia-123")
        self.assertEqual(base, "https://api.deepseek.com/v1")
        self.assertIn("propia", why)

    def test_sin_propia_cae_a_la_general(self):
        gb._ENV_TAREA["GROWI_CUENTA_ID"] = "principal"
        eng = gb.get_engine("deepseek")
        self.assertIsNone(gb._clave_motor_cuenta(eng))
        key, _base, why = gb.resolver_credencial_motor(eng)
        self.assertIsNone(key)  # no hay clave general en el entorno
        self.assertTrue(why)


class TestMcp(unittest.TestCase):
    def test_solo_nombres_y_sin_fichero_no_falla(self):
        # En el entorno de prueba no hay ~/.claude.json del dueño:
        # devuelve una lista (vacía o no) de cadenas, sin lanzar.
        nombres = gb._mcp_detectados()
        self.assertIsInstance(nombres, list)
        self.assertTrue(all(isinstance(n, str) for n in nombres))


if __name__ == "__main__":
    unittest.main()

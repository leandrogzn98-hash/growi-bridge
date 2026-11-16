"""Pruebas de la capa de permisos por cuenta (Fase 1).

Ejecutar: python3 test_permission_layer.py
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "permission_layer", str(Path(__file__).with_name("permission-layer.py")))
pl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pl)


class TestAuditoriaPorCuenta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self._audit = pl.AUDIT_PATH
        pl.AUDIT_PATH = str(self.base / "audit-log.json")

    def tearDown(self):
        pl.AUDIT_PATH = self._audit
        self.tmp.cleanup()

    def test_defecto_usa_el_archivo_de_siempre(self):
        pl.registrar("claude_cli", "resume esto", "ok")
        self.assertTrue((self.base / "audit-log.json").exists())
        ok, n, _ = pl.verificar_cadena()
        self.assertTrue(ok)
        self.assertEqual(n, 1)

    def test_cada_cuenta_su_archivo_y_su_cadena(self):
        pl.registrar("claude_cli", "tarea de A", "ok", cuenta="segunda")
        pl.registrar("claude_cli", "otra de A", "ok", cuenta="segunda")
        pl.registrar("claude_cli", "tarea de la principal", "ok")
        pa = self.base / "audit-log-segunda.json"
        self.assertTrue(pa.exists())
        ok, n, _ = pl.verificar_cadena(str(pa))
        self.assertTrue(ok)
        self.assertEqual(n, 2)
        entrada = json.loads(pa.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(entrada["cuenta"], "segunda")
        self.assertEqual(entrada["v"], 2)
        # La cadena de la principal no se mezcló con la de la segunda.
        ok2, n2, _ = pl.verificar_cadena()
        self.assertTrue(ok2)
        self.assertEqual(n2, 1)

    def test_cuenta_invalida_rechazada(self):
        with self.assertRaises(pl.AuditoriaError):
            pl.registrar("claude_cli", "x", "ok", cuenta="../fuera")
        with self.assertRaises(pl.AuditoriaError):
            pl.audit_path_de("Cuenta Mala")

    def test_disponible_por_cuenta(self):
        ok, _ = pl.auditoria_disponible("segunda")
        self.assertTrue(ok)

    def test_ancla_detecta_borrado_y_truncado(self):
        pl.registrar("claude_cli", "uno", "ok", cuenta="segunda")
        pl.registrar("claude_cli", "dos", "ok", cuenta="segunda")
        ok, _ = pl.verificar_ancla("segunda")
        self.assertTrue(ok)
        pa = self.base / "audit-log-segunda.json"
        lineas = pa.read_text(encoding="utf-8").splitlines()
        pa.write_text(lineas[0] + "\n", encoding="utf-8")  # truncado
        ok, _ = pl.verificar_ancla("segunda")
        self.assertFalse(ok)
        pa.unlink()  # borrado entero
        ok, _ = pl.verificar_ancla("segunda")
        self.assertFalse(ok)

    def test_cadena_mixta_v1_y_v2(self):
        # Una entrada «v1» (sin campos v/cuenta, como las de antes de la
        # Fase 1) seguida de entradas v2: la cadena verifica entera.
        e1 = {"timestamp": "2026-11-01T00:00:00-04:00", "motor": "claude",
              "tool": "claude_cli", "accion": "entrada vieja",
              "resultado": "ok", "motivo_bloqueo": None, "duracion_s": 0.0}
        e1["prev_hash"] = pl.GENESIS
        e1["hash"] = pl._hash_entrada(pl.GENESIS, dict(e1))
        p = self.base / "audit-log.json"
        p.write_text(json.dumps(e1, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        pl.registrar("claude_cli", "entrada nueva", "ok")
        ok, n, _ = pl.verificar_cadena()
        self.assertTrue(ok)
        self.assertEqual(n, 2)


class TestClasificarPorCuenta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        reg = {"version": 1, "cuentas": [
            {"id": "segunda", "permisos": {
                "modo": "restringido",
                "clases_extra_denegadas": ["analizar_o_revisar"]}},
            {"id": "libre", "permisos": {
                "modo": "hereda",
                "clases_extra_denegadas": ["analizar_o_revisar"]}},
        ]}
        p = self.base / "accounts.json"
        p.write_text(json.dumps(reg), encoding="utf-8")
        self._env = os.environ.get("GROWI_ACCOUNTS_JSON")
        os.environ["GROWI_ACCOUNTS_JSON"] = str(p)

    def tearDown(self):
        if self._env is None:
            os.environ.pop("GROWI_ACCOUNTS_JSON", None)
        else:
            os.environ["GROWI_ACCOUNTS_JSON"] = self._env
        self.tmp.cleanup()

    def test_sin_cuenta_como_siempre(self):
        clases, motivo = pl.clasificar_tarea("analiza este informe")
        self.assertEqual(motivo, "")
        self.assertIn("analizar_o_revisar", clases)

    def test_cuenta_restringida_bloquea_su_clase(self):
        clases, motivo = pl.clasificar_tarea("analiza este informe",
                                             cuenta="segunda")
        self.assertIn("analizar_o_revisar", clases)
        self.assertIn("denegada para la cuenta segunda", motivo)

    def test_cuenta_que_hereda_no_bloquea(self):
        _clases, motivo = pl.clasificar_tarea("analiza este informe",
                                              cuenta="libre")
        self.assertEqual(motivo, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

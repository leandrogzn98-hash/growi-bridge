"""Pruebas del harness multi-cuenta (Fase 4): GROWI_CUENTA_ID validada
contra el registro (salida 4 sin ejecutar si no cuadra), estado por
ejecución con pasos y marcas, y la capa de permisos recibiendo la cuenta
desde el harness. Sin GROWI_CUENTA_ID, el comportamiento histórico.

smolagents no está en este entorno: se inyecta un paquete de pega con la
superficie que harness.py usa al importar y al construir el agente. El
CodeAgent de pega deja una marca al construirse: si la marca no existe,
el harness no ejecutó nada.

Ejecutar: python3 -m unittest test_harness_multi
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent
ARCHIVOS = ("harness.py", "growi-bridge-harness.py", "quota-tracker.py",
            "permission-layer.py", "cuentas.py")

CUENTAS = {
    "version": 1, "revision": 1, "borradas": [],
    "cuentas": [
        {"id": "principal", "nombre": "Principal", "carril": "a",
         "conexion": "ambas", "habilitada": True},
        {"id": "segunda", "nombre": "Segunda", "carril": "b",
         "conexion": "ambas", "habilitada": True,
         "permisos": {"modo": "restringido",
                      "clases_extra_denegadas": ["analizar_o_revisar"]}},
        {"id": "apagada", "nombre": "Apagada", "carril": None,
         "conexion": "local", "habilitada": False},
    ],
}

STUB_INIT = '''
import os


class ChatMessage:
    def __init__(self, role=None, content=None):
        self.role = role
        self.content = content


class MessageRole:
    ASSISTANT = "assistant"
    USER = "user"
    SYSTEM = "system"


class Model:
    def __init__(self, model_id=None, **kw):
        self.model_id = model_id


class Tool:
    pass


class CodeAgent:
    def __init__(self, **kw):
        marca = os.environ.get("STUB_MARKER")
        if marca:
            with open(marca, "w", encoding="utf-8") as f:
                f.write("agente construido")

    def run(self, tarea):
        return "respuesta de prueba"
'''

STUB_MEMORY = '''
class ActionStep:
    def __init__(self, step_number=1):
        self.step_number = step_number
        self.observations = ""
        self.action_output = None
        self.error = None
'''


def _escribir_stub(raiz):
    paquete = raiz / "smolagents"
    (paquete / "prompts").mkdir(parents=True)
    (paquete / "__init__.py").write_text(STUB_INIT, encoding="utf-8")
    (paquete / "memory.py").write_text(STUB_MEMORY, encoding="utf-8")
    (paquete / "prompts" / "__init__.py").write_text("", encoding="utf-8")
    (paquete / "prompts" / "code_agent.yaml").write_text(
        "system_prompt: de pega\n", encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for nombre in ARCHIVOS:
            shutil.copy(REPO / nombre, self.dir / nombre)
        (self.dir / "accounts.json").write_text(
            json.dumps(CUENTAS), encoding="utf-8")
        self.stub = self.dir / "stub"
        _escribir_stub(self.stub)
        self._env_guardado = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_guardado)
        for nombre in ("harness_bajo_prueba", "smolagents",
                       "smolagents.memory", "permission_layer"):
            sys.modules.pop(nombre, None)
        self.tmp.cleanup()

    def _cargar(self, env):
        for clave in ("GROWI_CUENTA_ID", "GROWI_RAIZ", "GROWI_TAREA_ID",
                      "GROWI_HARNESS_ESTADO", "GROWI_BRIDGE_LANE",
                      "GROWI_SESION", "GROWI_TIEMPO_MAX_S"):
            os.environ.pop(clave, None)
        os.environ.update(env)
        sys.path.insert(0, str(self.stub))
        try:
            for nombre in ("smolagents", "smolagents.memory"):
                spec = importlib.util.spec_from_file_location(
                    nombre, self.stub / "smolagents" /
                    ("__init__.py" if nombre == "smolagents"
                     else "memory.py"))
                mod = importlib.util.module_from_spec(spec)
                sys.modules[nombre] = mod
                spec.loader.exec_module(mod)
            spec = importlib.util.spec_from_file_location(
                "harness_bajo_prueba", self.dir / "harness.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        finally:
            sys.path.remove(str(self.stub))


class TestValidacionCuenta(Base):
    def test_sin_cuenta_comportamiento_historico(self):
        h = self._cargar({})
        self.assertIsNone(h.CUENTA_HARNESS)
        self.assertIsNone(h.validar_cuenta_entorno())
        self.assertIsNone(h.CAPA.cuenta)

    def test_cuenta_valida(self):
        h = self._cargar({"GROWI_CUENTA_ID": "principal"})
        self.assertIsNone(h.validar_cuenta_entorno())
        self.assertEqual(h.CAPA.cuenta, "principal")

    def test_cuenta_inexistente(self):
        h = self._cargar({"GROWI_CUENTA_ID": "fantasma"})
        self.assertIn("no existe", h.validar_cuenta_entorno())

    def test_cuenta_deshabilitada(self):
        h = self._cargar({"GROWI_CUENTA_ID": "apagada"})
        self.assertIn("deshabilitada", h.validar_cuenta_entorno())

    def test_cuenta_de_otro_carril(self):
        h = self._cargar({"GROWI_CUENTA_ID": "segunda"})
        self.assertIn("carril", h.validar_cuenta_entorno())
        h2 = self._cargar({"GROWI_CUENTA_ID": "segunda",
                           "GROWI_BRIDGE_LANE": "b"})
        self.assertIsNone(h2.validar_cuenta_entorno())


class TestEstadoPorEjecucion(Base):
    def test_estado_con_identidad_y_pasos(self):
        estado = self.dir / "estado-x.json"
        h = self._cargar({
            "GROWI_CUENTA_ID": "principal",
            "GROWI_RAIZ": "enc-20260101-abcdef01",
            "GROWI_TAREA_ID": "t-9",
            "GROWI_HARNESS_ESTADO": str(estado)})
        est = h.Estado("una tarea")
        est.anotar_paso(1, "claude", True)
        est.anotar_paso(2, "codex", False)
        est.escribir(status="working")
        datos = json.loads(estado.read_text(encoding="utf-8"))
        self.assertEqual(datos["cuenta"], "principal")
        self.assertEqual(datos["raiz"], "enc-20260101-abcdef01")
        self.assertEqual(datos["tarea_id"], "t-9")
        self.assertEqual(len(datos["pasos"]), 2)
        self.assertEqual(datos["pasos"][0]["motor"], "claude")
        self.assertTrue(datos["pasos"][0]["ok"])
        self.assertIn("ts", datos["pasos"][0])
        self.assertFalse(datos["pasos"][1]["ok"])


class TestCapaConCuenta(Base):
    def _pl(self):
        spec = importlib.util.spec_from_file_location(
            "pl_bajo_prueba", self.dir / "permission-layer.py")
        pl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pl)
        pl.AUDIT_PATH = str(self.dir / "audit-log.json")
        return pl

    def test_clases_extra_denegadas_aplican_en_el_harness(self):
        os.environ["GROWI_ACCOUNTS_JSON"] = str(self.dir / "accounts.json")
        pl = self._pl()
        capa_libre = pl.nueva_capa("s-libre", cuenta="principal")
        d = capa_libre.verificar_permiso(
            "claude_cli", "analiza y revisa este informe")
        self.assertTrue(d.permitido)
        capa_rest = pl.nueva_capa("s-rest", cuenta="segunda")
        d2 = capa_rest.verificar_permiso(
            "claude_cli", "analiza y revisa este informe")
        self.assertFalse(d2.permitido)
        self.assertIn("segunda", d2.motivo + d2.estado)

    def test_registrar_cae_en_la_auditoria_de_la_cuenta(self):
        pl = self._pl()
        capa = pl.nueva_capa("s-x", cuenta="segunda")
        capa.registrar_bloqueo("claude_cli", "algo",
                               pl.Decision("bloquear", "motivo de prueba"))
        self.assertTrue((self.dir / "audit-log-segunda.json").exists())


class TestSubproceso(Base):
    def _correr(self, env):
        marca = self.dir / "marca.txt"
        estado = self.dir / "estado-sub.json"
        entorno = dict(os.environ)
        entorno["PYTHONPATH"] = str(self.stub)
        entorno["STUB_MARKER"] = str(marca)
        entorno["GROWI_HARNESS_ESTADO"] = str(estado)
        entorno.pop("GROWI_CUENTA_ID", None)
        entorno.pop("GROWI_BRIDGE_LANE", None)
        entorno.update(env)
        p = subprocess.run(
            [sys.executable, str(self.dir / "harness.py"),
             "explica qué es un bucle"],
            cwd=self.dir, env=entorno, capture_output=True, text=True,
            timeout=60)
        return p, marca, estado

    def test_cuenta_invalida_exit_4_sin_ejecutar(self):
        p, marca, estado = self._correr({"GROWI_CUENTA_ID": "fantasma"})
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertIn("BLOQUEADO", p.stdout)
        self.assertFalse(marca.exists())  # el agente ni se construyó
        datos = json.loads(estado.read_text(encoding="utf-8"))
        self.assertEqual(datos["status"], "error")
        self.assertEqual(datos["cuenta"], "fantasma")

    def test_cuenta_de_otro_carril_exit_4(self):
        p, marca, _ = self._correr({"GROWI_CUENTA_ID": "segunda"})
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertFalse(marca.exists())

    def test_cuenta_valida_ejecuta(self):
        p, marca, estado = self._correr(
            {"GROWI_CUENTA_ID": "segunda", "GROWI_BRIDGE_LANE": "b"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(marca.exists())
        datos = json.loads(estado.read_text(encoding="utf-8"))
        self.assertEqual(datos["status"], "done")
        self.assertEqual(datos["cuenta"], "segunda")

    def test_sin_cuenta_ejecuta_como_siempre(self):
        p, marca, _ = self._correr({})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(marca.exists())


if __name__ == "__main__":
    unittest.main()

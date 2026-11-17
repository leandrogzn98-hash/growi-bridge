# -*- coding: utf-8 -*-
"""Pruebas de la forma derivada «chats/» de la página Chat (corrección
de la primera prueba real): validate_task acepta la tarea de chat del
propio programa (carril B, cwd = la carpeta del carril, archivos dentro
de <carpeta>/chats/) con la misma estrictud que encargos/ y consultas/,
y rechaza todo lo que se salga de esa forma exacta.

El monolito se importa con el entorno aislado (share, cola y XDG en un
temporal), como en test_dual_cola. Ejecutar: python3 -m unittest
test_chat_tarea
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="gb-chat-")
os.environ["GROWI_BRIDGE_SHARE"] = str(Path(_TMP) / "share")
os.environ["GROWI_BRIDGE_COLA"] = str(Path(_TMP) / "cola.db")
os.environ["XDG_DATA_HOME"] = str(Path(_TMP) / "xdg")

_spec = importlib.util.spec_from_file_location(
    "gb_chat", str(Path(__file__).with_name("growi-bridge.py")))
gb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gb)


class TestFormaChats(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(_TMP)
        self.app = self.raiz / "app"
        self.app.mkdir(exist_ok=True)
        gb.APP_DIR = self.app
        gb.LANE = "b"

    def tarea(self, archivos, cwd=None):
        return {"id": "chat-abc123def4", "tipo": "chat", "lane": "b",
                "cuenta": "segunda", "prompt": "hola, ¿qué tal?",
                "cwd": str(cwd or self.app), "archivos": archivos}

    def test_forma_chats_aceptada(self):
        t = self.tarea([str(self.app / "chats" / "chat-abc123def4.md")])
        ok, err = gb.validate_task(t)
        self.assertIsNotNone(ok, err)

    def test_formas_previas_siguen_aceptadas(self):
        for sub in ("encargos", "consultas"):
            t = self.tarea([str(self.app / sub / "chat-abc123def4.md")])
            ok, err = gb.validate_task(t)
            self.assertIsNotNone(ok, f"{sub}: {err}")

    def test_archivo_fuera_del_carril_rechazado(self):
        t = self.tarea(["/tmp/evil.md"])
        ok, err = gb.validate_task(t)
        self.assertIsNone(ok)
        self.assertIn("fuera de la carpeta del carril B", err)

    def test_archivo_en_la_raiz_no_es_forma_derivada(self):
        # Dentro del carril pero fuera de las subcarpetas derivadas: la
        # excepción no se abre a «todo el APP_DIR».
        t = self.tarea([str(self.app / "suelto.md")])
        ok, err = gb.validate_task(t)
        self.assertIsNone(ok)
        self.assertIn("carpetas permitidas", err)

    def test_cwd_fuera_rechazado(self):
        t = self.tarea([str(self.app / "chats" / "chat-abc123def4.md")],
                       cwd=self.raiz)
        ok, err = gb.validate_task(t)
        self.assertIsNone(ok)


if __name__ == "__main__":
    unittest.main()

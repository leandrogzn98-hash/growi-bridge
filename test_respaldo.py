# -*- coding: utf-8 -*-
"""Pruebas de respaldo.py (Fase 3, §7 del diseño).

Instantáneas con manifiesto de la LISTA BLANCA y nada más: los JSON se
leen por el `cargar` de su módulo dueño, `cola.db` por la API de
respaldo de SQLite (B14), todo se valida y se escanea antes de
respaldar, y la restauración sanea los marcadores de traspaso (I10).
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alquileres
import cuentas
import respaldo
import tablero
import traspaso

AUD = lambda **k: None


class Reloj:
    def __init__(self, t=1_700_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


def _reg():
    return {"version": 1, "migrado_secret_txt": True, "cuentas": [
        {"id": "principal", "nombre": "Muse A", "asistente": "a.md",
         "carril": "a", "conexion": "ambas", "habilitada": True,
         "creada": None,
         "permisos": {"modo": "hereda", "clases_extra_denegadas": []}}]}


class CasoRespaldo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.base = raiz / "compartida"
        self.base.mkdir()
        self.lane_a = raiz / "lane_a"
        self.lane_a.mkdir()
        self.reloj = Reloj()
        # Estado compartido sembrado con los módulos dueños.
        tablero.declarar_pct(self.base, "principal", 80, reloj=self.reloj)
        alquileres.tomar(self.base, "repo1", ["a.py"], "principal", "t1",
                         reloj=self.reloj)
        (self.base / "consultas-uso.json").write_text(
            '{"version": 1, "raices": {}}', encoding="utf-8")
        # Estado del carril A.
        cuentas.guardar(self.lane_a, _reg())
        (self.lane_a / "audit-log.json").write_text(
            '{"tool": "x", "resultado": "ok"}\n', encoding="utf-8")
        (self.lane_a / "audit-log-principal.json").write_text(
            '{"tool": "y"}\n', encoding="utf-8")
        (self.lane_a / "audit-indice.json").write_text(
            '{"principal": "abc"}', encoding="utf-8")
        (self.lane_a / "settings.json").write_text('{"k": 1}',
                                                   encoding="utf-8")
        db = sqlite3.connect(self.lane_a / "cola.db")
        db.execute("CREATE TABLE tareas (id TEXT, estado TEXT)")
        db.execute("INSERT INTO tareas VALUES ('t1', 'en_curso')")
        db.commit()
        db.close()
        # Archivos ajenos que NO deben viajar jamás.
        (self.lane_a / "secret.txt").write_text("no debo salir\n")
        (self.lane_a / "otra-cosa.txt").write_text("ajeno\n")
        self.carriles = {"a": self.lane_a}

    def tearDown(self):
        self.tmp.cleanup()

    def crear(self, **kw):
        return respaldo.crear_instantanea(self.base, self.carriles,
                                          reloj=self.reloj, auditar=AUD,
                                          **kw)


class TestInstantanea(CasoRespaldo):
    def test_crea_y_verifica(self):
        r = self.crear()
        self.assertTrue(r["creada"])
        carpeta = r["carpeta"]
        self.assertTrue(respaldo.verificar(carpeta)["ok"])
        nombres = {str(p.relative_to(carpeta))
                   for p in carpeta.rglob("*") if p.is_file()}
        self.assertIn("compartida/tablero.json", nombres)
        self.assertIn("compartida/alquileres.json", nombres)
        self.assertIn("a/accounts.json", nombres)
        self.assertIn("a/cola.db", nombres)
        self.assertIn("a/audit-log.json", nombres)
        self.assertIn("a/audit-log-principal.json", nombres)
        self.assertNotIn("a/secret.txt", nombres)      # la bóveda no viaja
        self.assertNotIn("a/otra-cosa.txt", nombres)   # lista blanca cerrada
        # La cola respaldada es una base íntegra y legible.
        db = sqlite3.connect(carpeta / "a" / "cola.db")
        self.assertEqual(db.execute("SELECT estado FROM tareas").fetchone(),
                         ("en_curso",))
        db.close()

    def test_sin_cambios_no_duplica(self):
        self.crear()
        r = self.crear()
        self.assertFalse(r["creada"])
        self.assertEqual(len(respaldo.instantaneas(self.base)), 1)

    def test_rotacion_diez(self):
        for i in range(12):
            tablero.declarar_pct(self.base, "principal", 50 + i,
                                 reloj=self.reloj)
            self.reloj.avanzar(3600)
            self.crear(forzar=True)
        self.assertEqual(len(respaldo.instantaneas(self.base)), 10)

    def test_verificar_detecta_dano_y_ausencia(self):
        carpeta = self.crear()["carpeta"]
        (carpeta / "compartida" / "tablero.json").write_text("{}")
        v = respaldo.verificar(carpeta)
        self.assertFalse(v["ok"])
        self.assertIn("compartida/tablero.json", v["danados"])
        (carpeta / "a" / "settings.json").unlink()
        v = respaldo.verificar(carpeta)
        self.assertIn("a/settings.json", v["ausentes"])

    def test_cola_bajo_escritura_concurrente(self):
        db = sqlite3.connect(self.lane_a / "cola.db", check_same_thread=False)
        parar = threading.Event()

        def escribir():
            n = 0
            while not parar.is_set():
                db.execute("INSERT INTO tareas VALUES (?, 'en_curso')",
                           (f"x{n}",))
                db.commit()
                n += 1
                time.sleep(0.005)

        hilo = threading.Thread(target=escribir)
        hilo.start()
        try:
            r = self.crear()
        finally:
            parar.set()
            hilo.join()
            db.close()
        copia = sqlite3.connect(r["carpeta"] / "a" / "cola.db")
        self.assertEqual(copia.execute(
            "PRAGMA integrity_check").fetchone()[0], "ok")
        copia.close()

    def test_aborta_con_json_corrupto(self):
        (self.base / "alquileres.json").write_text("{roto", encoding="utf-8")
        with self.assertRaises(respaldo.ErrorRespaldo):
            self.crear()
        self.assertEqual(respaldo.instantaneas(self.base), [])

    def test_aborta_con_secreto_plantado(self):
        (self.lane_a / "audit-log.json").write_text(
            "clave = 'sk-1234567890abcdefghijklmnopqrstuv'\n",
            encoding="utf-8")
        with self.assertRaises(respaldo.ErrorRespaldo):
            self.crear()
        self.assertEqual(respaldo.instantaneas(self.base), [])


class TestRestaurarYEspacio(CasoRespaldo):
    def test_restaurar_sanea_traspasos(self):
        traspaso.crear(self.base, "t1", "principal", "segunda",
                       reloj=self.reloj)
        carpeta = self.crear()["carpeta"]
        destino = Path(self.tmp.name) / "restaurado"
        r = respaldo.restaurar(carpeta, destino, reloj=self.reloj,
                               auditar=AUD)
        self.assertEqual(r["traspasos_saneados"], 1)
        d = json.loads((destino / "compartida" / "traspasos.json")
                       .read_text(encoding="utf-8"))
        estados = [m["estado"] for m in d["traspasos"].values()]
        self.assertEqual(estados, ["requiere_dueno"])
        self.assertTrue((destino / "RESTAURADO.md").is_file())

    def test_restaurar_rechaza_instantanea_danada(self):
        carpeta = self.crear()["carpeta"]
        (carpeta / "compartida" / "tablero.json").write_text("{}")
        with self.assertRaises(respaldo.ErrorRespaldo):
            respaldo.restaurar(carpeta, Path(self.tmp.name) / "destino",
                               auditar=AUD)

    def test_copiar_a_espacio(self):
        self.crear()
        espacio = Path(self.tmp.name) / "espacio-a"
        r = respaldo.copiar_a_espacio(self.base, espacio, auditar=AUD)
        self.assertTrue(r["actualizada"])
        self.assertTrue((espacio / "respaldo-estado" / "manifiesto.json")
                        .is_file())
        r = respaldo.copiar_a_espacio(self.base, espacio, auditar=AUD)
        self.assertFalse(r["actualizada"])  # ya es la última

    def test_exportar_fuera(self):
        self.crear()
        fuera = Path(self.tmp.name) / "usb"
        r = respaldo.exportar(self.base, fuera, auditar=AUD)
        self.assertTrue(respaldo.verificar(r["carpeta"])["ok"])


if __name__ == "__main__":
    unittest.main()

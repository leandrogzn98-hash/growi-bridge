"""Pruebas del relevo telefónico (Fase 4): raíz generada por el código,
validación entera de planes, asignación determinista con contador
simulado, entrega atómica en orden seguro, buzón compartido como
autoridad del cierre y cierre atómico.

Ejecutar: python3 -m unittest test_relevo
"""
import json
import re
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
MOTORES = {"claude", "codex", "gemini"}


def vista(estados=None, pcts=None):
    estados = estados or {}
    pcts = pcts or {}
    return {cid: {"estado": estados.get(cid, "activa"),
                  "pct_puerta": pcts.get(cid, 80),
                  "motor_principal": "claude",
                  "latido_ts": time.time(), "tarea": None}
            for cid in ("principal", "segunda")}


def sub(prompt, **kw):
    d = {"prompt": prompt}
    d.update(kw)
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.tareas_a = self.base / "lane-a-tasks"
        self.tareas_b = self.base / "lane-b-tasks"
        self.tareas_a.mkdir()
        self.tareas_b.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _encargo(self, prompt="Haz el nivel 2 y la pantalla de opciones"):
        return relevo.registrar_encargo(
            self.base, {"id": "t-enc-1", "prompt": prompt,
                        "cwd": "/home/dueno/juego", "canal": "telefono",
                        "raiz": "LO-QUE-TRAIGA-EL-PAYLOAD"},
            receptora="principal")


class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_raiz_la_genera_el_codigo_no_el_payload(self):
        raiz = relevo.registrar_encargo(
            self.base, {"id": "t1", "prompt": "hola",
                        "raiz": "enc-19990101-deadbeef"},
            receptora="principal")
        self.assertIsNotNone(
            re.fullmatch(r"enc-\d{8}-[0-9a-f]{8}", raiz))
        self.assertNotEqual(raiz, "enc-19990101-deadbeef")
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["receptora"], "principal")
        self.assertEqual(ent["estado"], "abierto")
        self.assertGreater(ent["plazo_ts"], ent["creado_ts"])


class TestValidarPlan(unittest.TestCase):
    def test_plan_valido_normaliza_dependencias(self):
        plan = relevo.validar_plan(
            {"subtareas": [sub("primero"),
                           sub("segundo", depende_de=[1], motor="claude",
                               timeout_min=30)]},
            MOTORES, raiz="enc-20260101-abcdef01")
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[1]["depende_de"], ["enc-20260101-abcdef01-s1"])
        self.assertEqual(plan[1]["motor"], "claude")

    def test_extrae_el_json_del_texto_del_planificador(self):
        texto = ('Claro, aquí va el plan:\n{"subtareas": '
                 '[{"prompt": "única"}]}\nEspero que sirva.')
        plan = relevo.validar_plan(texto, MOTORES, raiz="enc-x")
        self.assertEqual(len(plan), 1)

    def test_rechazos(self):
        casos = [
            {"subtareas": []},                                  # cero
            {"subtareas": [sub(f"s{i}") for i in range(13)]},   # trece
            {"subtareas": [sub("x", motor="motor_falso")]},     # motor
            {"subtareas": [sub("x", timeout_min=0)]},           # timeout
            {"subtareas": [sub("x", timeout_min=121)]},
            {"subtareas": [sub("x", depende_de=[2]),
                           sub("y", depende_de=[1])]},          # ciclo
            {"subtareas": [sub("x", depende_de=[7])]},          # fuera
            {"subtareas": [sub("")]},                           # prompt vacío
            {"subtareas": [sub("x", prueba_fisica={"clase": "otra",
                                                   "detalle": "d"})]},
        ]
        for caso in casos:
            with self.assertRaises(relevo.ErrorRelevo, msg=str(caso)[:60]):
                relevo.validar_plan(caso, MOTORES, raiz="enc-x")

    def test_plan_reserva_una_sola_subtarea(self):
        plan = relevo.plan_reserva("el encargo entero")
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["prompt"], "el encargo entero")
        self.assertEqual(plan[0]["depende_de"], [])


class TestAsignar(Base):
    def test_reparto_determinista_con_contador_simulado(self):
        raiz = self._encargo()
        plan = relevo.validar_plan(
            {"subtareas": [sub("una"), sub("dos"), sub("tres")]},
            MOTORES, raiz=raiz)
        asig = relevo.asignar(self.base, raiz, plan, vista(), REGISTRO, {})
        sids = [f"{raiz}-s{i}" for i in (1, 2, 3)]
        # Empate de %: gana principal (id menor); el contador simulado
        # manda la segunda a segunda y la tercera vuelve a principal.
        self.assertEqual([asig[s] for s in sids],
                         ["principal", "segunda", "principal"])

    def test_cuarentena_no_recibe_nada(self):
        raiz = self._encargo()
        plan = relevo.validar_plan({"subtareas": [sub("una"), sub("dos")]},
                                   MOTORES, raiz=raiz)
        asig = relevo.asignar(
            self.base, raiz, plan,
            vista(estados={"segunda": "cuarentena"}), REGISTRO, {})
        self.assertEqual(set(asig.values()), {"principal"})

    def test_nadie_activo_queda_pendiente_con_motivo(self):
        raiz = self._encargo()
        plan = relevo.validar_plan({"subtareas": [sub("una")]},
                                   MOTORES, raiz=raiz)
        asig = relevo.asignar(
            self.base, raiz, plan,
            vista(estados={"principal": "cuarentena",
                           "segunda": "cuarentena"}), REGISTRO, {})
        self.assertEqual(list(asig.values()), [None])
        ent = relevo.obtener(self.base, raiz)
        sub_ = ent["subtareas"][f"{raiz}-s1"]
        self.assertEqual(sub_["estado"], "pendiente_entrega")
        self.assertTrue(sub_["motivo"])

    def test_asignacion_escrita_antes_de_entregar(self):
        raiz = self._encargo()
        plan = relevo.validar_plan({"subtareas": [sub("una")]},
                                   MOTORES, raiz=raiz)
        relevo.asignar(self.base, raiz, plan, vista(), REGISTRO, {})
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["estado"], "trabajando")
        self.assertEqual(ent["plan_tipo"], None)  # sin tipo si no se pasa
        self.assertIsNotNone(ent["dividido_ts"])
        # Nada entregado todavía: no hay archivos de tarea en ningún lado.
        self.assertEqual(list(self.tareas_a.glob("*.task.json")), [])
        self.assertEqual(list(self.tareas_b.glob("*.task.json")), [])


class TestEntregar(Base):
    def _asignado(self, subtareas, estados=None):
        raiz = self._encargo()
        plan = relevo.validar_plan({"subtareas": subtareas},
                                   MOTORES, raiz=raiz)
        relevo.asignar(self.base, raiz, plan, vista(estados=estados),
                       REGISTRO, {})
        return raiz

    def test_entrega_con_cabecera_y_herencia(self):
        raiz = self._asignado([sub("haz A"), sub("haz B")])
        sid = f"{raiz}-s2"  # la segunda va a la cuenta segunda (carril b)
        res = relevo.entregar(self.base, raiz, sid, self.tareas_b,
                              base_carril=self.base / "lane-b")
        self.assertTrue(res["ok"])
        ruta = self.tareas_b / f"{sid}.task.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(datos["raiz"], raiz)
        self.assertEqual(datos["tarea_padre"], "t-enc-1")
        self.assertEqual(datos["cuenta"], "segunda")
        self.assertIn(raiz, datos["prompt"])
        self.assertIn("haz B", datos["prompt"])
        # Sin contexto git en el carril B: cwd y archivos derivados.
        self.assertEqual(datos["cwd"], str(self.base / "lane-b"))
        self.assertEqual(datos["archivos"],
                         [str(self.base / "lane-b" / "encargos"
                              / f"{sid}.md")])
        self.assertFalse((self.tareas_b / f"{sid}.task.json.tmp").exists())
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["subtareas"][sid]["estado"], "entregada")

    def test_entrega_con_git_usa_el_cwd_del_encargo(self):
        raiz = self._asignado([sub("toca el nivel", git="requerido",
                                   archivos=["src/nivel.py"])])
        sid = f"{raiz}-s1"
        res = relevo.entregar(self.base, raiz, sid, self.tareas_a)
        self.assertTrue(res["ok"])
        datos = json.loads((self.tareas_a / f"{sid}.task.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(datos["cwd"], "/home/dueno/juego")
        self.assertEqual(datos["archivos"], ["src/nivel.py"])

    def test_carpeta_inexistente_queda_pendiente_con_motivo(self):
        raiz = self._asignado([sub("haz A")])
        sid = f"{raiz}-s1"
        res = relevo.entregar(self.base, raiz, sid,
                              self.base / "no-existe")
        self.assertFalse(res["ok"])
        ent = relevo.obtener(self.base, raiz)
        sub_ = ent["subtareas"][sid]
        self.assertEqual(sub_["estado"], "asignada")
        self.assertIn("no existe", sub_["motivo"])

    def test_subtarea_de_prueba_fisica_nace_marcada(self):
        raiz = self._asignado([sub("mide todo", prueba_fisica={
            "clase": "medicion", "detalle": "medir el equipo",
            "duracion_est_min": 20, "impacto": "carga la PC"})])
        sid = f"{raiz}-s1"
        relevo.entregar(self.base, raiz, sid, self.tareas_a)
        datos = json.loads((self.tareas_a / f"{sid}.task.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(datos["tipo"], "prueba_fisica")
        self.assertEqual(datos["prueba"]["clase"], "medicion")


class TestBuzonYCierre(Base):
    def test_buzon_solo_acepta_subtareas_registradas(self):
        raiz = self._encargo()
        plan = relevo.validar_plan({"subtareas": [sub("una")]},
                                   MOTORES, raiz=raiz)
        relevo.asignar(self.base, raiz, plan, vista(), REGISTRO, {})
        sid = f"{raiz}-s1"
        ok = relevo.escribir_en_buzon(
            self.base, {"id": sid, "raiz": raiz, "status": "ok"})
        self.assertTrue(ok)
        self.assertEqual(
            relevo.leer_de_buzon(self.base, raiz, sid)["status"], "ok")
        self.assertFalse(relevo.escribir_en_buzon(
            self.base, {"id": "enc-x-s9", "raiz": raiz, "status": "ok"}))
        self.assertFalse(relevo.escribir_en_buzon(
            self.base, {"id": sid, "status": "ok"}))  # sin raíz

    def test_cierre_atomico_solo_uno_gana(self):
        raiz = self._encargo()
        self.assertTrue(relevo.cerrar(self.base, raiz, "terminado"))
        self.assertFalse(relevo.cerrar(self.base, raiz, "terminado"))
        ent = relevo.obtener(self.base, raiz)
        self.assertIsNotNone(ent["cerrado_ts"])

    def test_reasignar_lo_no_entregado_de_cuenta_caida(self):
        raiz = self._encargo()
        plan = relevo.validar_plan({"subtareas": [sub("una"), sub("dos")]},
                                   MOTORES, raiz=raiz)
        relevo.asignar(self.base, raiz, plan, vista(), REGISTRO, {})
        sid2 = f"{raiz}-s2"  # asignada a segunda
        cambios = relevo.reasignar(
            self.base, raiz, vista(estados={"segunda": "cuarentena"}),
            REGISTRO, {})
        self.assertIn((sid2, "segunda", "principal"), cambios)
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["subtareas"][sid2]["cuenta"], "principal")

    def test_lo_entregado_no_se_reasigna(self):
        raiz = self._encargo()
        plan = relevo.validar_plan({"subtareas": [sub("una"), sub("dos")]},
                                   MOTORES, raiz=raiz)
        relevo.asignar(self.base, raiz, plan, vista(), REGISTRO, {})
        sid2 = f"{raiz}-s2"
        relevo.entregar(self.base, raiz, sid2, self.tareas_b,
                        base_carril=self.base / "lane-b")
        cambios = relevo.reasignar(
            self.base, raiz, vista(estados={"segunda": "cuarentena"}),
            REGISTRO, {})
        self.assertEqual(cambios, [])


if __name__ == "__main__":
    unittest.main()

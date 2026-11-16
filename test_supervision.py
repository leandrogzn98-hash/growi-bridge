"""Pruebas de la supervisión (Fase 4): fail-open por fuente, duración
máxima sobre el inicio real, cuelgue del harness, cierre de encargos
desde el buzón, entrega diferida por dependencias, entrega perdida que
vuelve a pendiente, y la política dual (gracia e indeterminado).

Ejecutar: python3 -m unittest test_supervision
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

import avisos
import relevo
import supervision

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


def vista():
    return {cid: {"estado": "activa", "pct_puerta": 80,
                  "motor_principal": "claude", "latido_ts": time.time(),
                  "tarea": None}
            for cid in ("principal", "segunda")}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.ahora = time.time()
        self.muertes = []
        self.anotaciones = []
        self.resumenes = {}
        self.tareas = {"a": self.base / "ta", "b": self.base / "tb"}
        self.tareas["a"].mkdir()
        self.tareas["b"].mkdir()
        self.filas = {"a": [], "b": []}
        self.status = {}
        self.harness = {}

    def tearDown(self):
        self.tmp.cleanup()

    def _matar(self, pid, creado):
        self.muertes.append((pid, creado))
        return True, "árbol detenido"

    def _anotar(self, fila, entrada):
        self.anotaciones.append((fila.get("id"), entrada))

    def ctx(self, **extra):
        ctx = {
            "base_dir": self.base,
            "ahora": self.ahora,
            "carril_propio": "a",
            "carriles": ("a", "b"),
            "cuentas": [{"id": "principal", "carril": "a",
                         "habilitada": True},
                        {"id": "segunda", "carril": "b",
                         "habilitada": True}],
            "vista": vista(),
            "registro": REGISTRO,
            "activas": {},
            "leer_status": lambda c: self.status.get(c),
            "pid_vivo": lambda pid: False,
            "filas": lambda c: self.filas.get(c, []),
            "estado_harness": lambda fila: self.harness.get(fila["id"]),
            "matar": self._matar,
            "anotar": self._anotar,
            "dir_tareas": lambda c: self.tareas[c],
            "base_carril": lambda c: self.base / f"lane-{c}",
            "archivo_en_tareas": lambda c, sid: (
                self.tareas[c] / f"{sid}.task.json").exists(),
            "escribir_resumen": lambda raiz, res:
                self.resumenes.setdefault(raiz, res) or True,
            "log": None,
        }
        ctx.update(extra)
        return ctx

    def _avisos(self, tipo=None):
        salida = []
        ruta = self.base / "avisos.jsonl"
        if ruta.exists():
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                if linea.strip():
                    d = json.loads(linea)
                    if tipo is None or d["tipo"] == tipo:
                        salida.append(d)
        return salida


class TestCuentasYDURacion(Base):
    def test_cuenta_sin_latido_con_trabajo_en_curso(self):
        self.status["a"] = {"pid": 987654, "last_poll_ts": self.ahora - 400,
                            "current": "t-1"}
        supervision.barrer(self.ctx())
        av = self._avisos("cuenta_sin_latido")
        self.assertEqual(len(av), 1)
        self.assertEqual(av[0]["nivel"], "accion")
        self.assertIn("t-1", av[0]["texto"])

    def test_status_ausente_no_autoriza_nada(self):
        self.status["a"] = None
        resumen = supervision.barrer(self.ctx())
        self.assertEqual(self._avisos(), [])
        self.assertEqual(resumen["paradas"], [])

    def test_duracion_maxima_mata_con_identidad(self):
        self.filas["a"] = [{
            "id": "t-1", "cuenta": "principal", "estado": "en_curso",
            "raiz": "t-1",
            "historial": [{"inicio_ts": self.ahora - 121 * 60,
                           "pid": 4242, "create_time": 111.5}]}]
        resumen = supervision.barrer(self.ctx(pid_vivo=lambda pid: True))
        self.assertEqual(self.muertes, [(4242, 111.5)])
        self.assertEqual(len(resumen["paradas"]), 1)

    def test_sin_inicio_real_no_se_toca(self):
        self.filas["a"] = [{
            "id": "t-1", "cuenta": "principal", "estado": "en_curso",
            "raiz": "t-1",
            "historial": [{"pid": 4242, "create_time": 111.5}]}]
        supervision.barrer(self.ctx())
        self.assertEqual(self.muertes, [])

    def test_otro_carril_solo_se_anota(self):
        self.filas["b"] = [{
            "id": "t-9", "cuenta": "segunda", "estado": "en_curso",
            "raiz": "t-9", "carril": "b",
            "historial": [{"inicio_ts": self.ahora - 200 * 60,
                           "pid": 777, "create_time": 1.0}]}]
        supervision.barrer(self.ctx())
        self.assertEqual(self.muertes, [])  # B9: matar es solo en casa
        self.assertTrue(any(e.get("tipo") == "supervision_ajena"
                            for _, e in self.anotaciones))

    def test_cuelgue_del_harness(self):
        self.filas["a"] = [{
            "id": "t-2", "cuenta": "principal", "estado": "en_curso",
            "raiz": "t-2",
            "historial": [{"inicio_ts": self.ahora - 60,
                           "pid": 555, "create_time": 2.0}]}]
        self.harness["t-2"] = {"status": "working",
                               "pasos": [{"n": 1, "ts": self.ahora - 700,
                                          "motor": "claude", "ok": True}]}
        resumen = supervision.barrer(self.ctx(pid_vivo=lambda pid: True))
        self.assertEqual(self.muertes, [(555, 2.0)])
        self.assertIn("harness", resumen["paradas"][0]["motivo"])

    def test_marca_supervision_ts(self):
        supervision.barrer(self.ctx())
        import presencia
        est = presencia.leer_estado(self.base)
        self.assertEqual(est["supervision_ts"], self.ahora)


class TestEncargos(Base):
    def _encargo(self, subtareas):
        raiz = relevo.registrar_encargo(
            self.base, {"id": "t-enc", "prompt": "encargo de prueba",
                        "cwd": "/home/dueno/juego", "canal": "telefono"},
            receptora="principal")
        plan = relevo.validar_plan({"subtareas": subtareas}, MOTORES,
                                   raiz=raiz)
        relevo.asignar(self.base, raiz, plan, vista(), REGISTRO, {})
        return raiz

    def _entregar(self, raiz, sid):
        ent = relevo.obtener(self.base, raiz)
        carril = ent["subtareas"][sid]["carril"]
        return relevo.entregar(self.base, raiz, sid, self.tareas[carril],
                               self.base / f"lane-{carril}")

    def test_cierre_con_una_fallida(self):
        raiz = self._encargo([{"prompt": "una"}, {"prompt": "dos"}])
        s1, s2 = f"{raiz}-s1", f"{raiz}-s2"
        self._entregar(raiz, s1)
        self._entregar(raiz, s2)
        relevo.escribir_en_buzon(self.base, {
            "id": s1, "raiz": raiz, "status": "ok", "output": "hecho"})
        relevo.escribir_en_buzon(self.base, {
            "id": s2, "raiz": raiz, "status": "error", "error": "petó"})
        resumen = supervision.barrer(self.ctx())
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["estado"], "terminado_con_fallos")
        self.assertIn(raiz, resumen["encargos_cerrados"])
        self.assertIn(raiz, self.resumenes)
        self.assertEqual(self.resumenes[raiz]["status"], "error")
        self.assertEqual(len(self._avisos("encargo_terminado")), 1)
        self.assertEqual(len(self._avisos("subtarea_fallida")), 1)
        # Segunda pasada: ya cerrado, no se reescribe el resumen.
        self.resumenes.clear()
        supervision.barrer(self.ctx())
        self.assertEqual(self.resumenes, {})

    def test_cierre_todo_bien(self):
        raiz = self._encargo([{"prompt": "una"}])
        s1 = f"{raiz}-s1"
        self._entregar(raiz, s1)
        relevo.escribir_en_buzon(self.base, {
            "id": s1, "raiz": raiz, "status": "ok", "output": "bien"})
        supervision.barrer(self.ctx())
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["estado"], "terminado")
        self.assertEqual(self.resumenes[raiz]["status"], "ok")

    def test_cierre_por_motivo_cierre_es_fallida(self):
        raiz = self._encargo([{"prompt": "una"}])
        s1 = f"{raiz}-s1"
        self._entregar(raiz, s1)
        relevo.escribir_en_buzon(self.base, {
            "id": s1, "raiz": raiz, "status": "error",
            "motivo_cierre": "cuenta_distinta", "error": "otra cuenta"})
        supervision.barrer(self.ctx())
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["subtareas"][s1]["estado"], "fallida")
        self.assertEqual(ent["estado"], "terminado_con_fallos")

    def test_entrega_diferida_al_terminar_la_dependencia(self):
        raiz = self._encargo([{"prompt": "primero"},
                              {"prompt": "después", "depende_de": [1]}])
        s1, s2 = f"{raiz}-s1", f"{raiz}-s2"
        self._entregar(raiz, s1)
        # s2 NO se entrega a mano: depende de s1.
        relevo.escribir_en_buzon(self.base, {
            "id": s1, "raiz": raiz, "status": "ok", "output": "ya"})
        resumen = supervision.barrer(self.ctx())
        self.assertIn(s2, resumen["entregas"])
        ent = relevo.obtener(self.base, raiz)
        carril2 = ent["subtareas"][s2]["carril"]
        self.assertTrue(
            (self.tareas[carril2] / f"{s2}.task.json").exists())

    def test_dependencia_fallida_cierra_sin_ejecutar(self):
        raiz = self._encargo([{"prompt": "primero"},
                              {"prompt": "después", "depende_de": [1]}])
        s1, s2 = f"{raiz}-s1", f"{raiz}-s2"
        self._entregar(raiz, s1)
        relevo.escribir_en_buzon(self.base, {
            "id": s1, "raiz": raiz, "status": "error", "error": "mal"})
        supervision.barrer(self.ctx())
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["subtareas"][s2]["estado"], "fallida")
        self.assertIn("dependencia", ent["subtareas"][s2]
                      ["resultado"]["resumen"])
        self.assertEqual(ent["estado"], "terminado_con_fallos")
        # s2 nunca se entregó: no hay archivo suyo en ningún carril.
        for c in ("a", "b"):
            self.assertFalse((self.tareas[c] / f"{s2}.task.json").exists())

    def test_entrega_perdida_vuelve_a_pendiente_tras_3_pasadas(self):
        raiz = self._encargo([{"prompt": "una"}])
        s1 = f"{raiz}-s1"
        self._entregar(raiz, s1)
        # El archivo «desaparece» (ni en tareas ni en la cola del carril).
        carril = relevo.obtener(self.base, raiz)["subtareas"][s1]["carril"]
        (self.tareas[carril] / f"{s1}.task.json").unlink()
        for _ in range(2):
            supervision.barrer(self.ctx())
            ent = relevo.obtener(self.base, raiz)
            self.assertEqual(ent["subtareas"][s1]["estado"], "entregada")
        supervision.barrer(self.ctx())
        ent = relevo.obtener(self.base, raiz)
        sub_ = ent["subtareas"][s1]
        self.assertEqual(sub_["estado"], "pendiente_entrega")
        self.assertEqual(sub_["cuenta"], "principal")  # conserva la cuenta
        # Y a la pasada siguiente el barrido la vuelve a entregar.
        resumen = supervision.barrer(self.ctx())
        self.assertIn(s1, resumen["entregas"])

    def test_plazo_vencido_cierra_con_fallos(self):
        raiz = self._encargo([{"prompt": "una"}])
        relevo.marcar_subtarea(self.base, raiz, f"{raiz}-s1",
                               estado="entregada")
        # Forzar el plazo al pasado directamente en el registro.
        datos = relevo.cargar(self.base)
        datos["encargos"][raiz]["plazo_ts"] = self.ahora - 1
        relevo._guardar(self.base, datos)
        supervision.barrer(self.ctx())
        ent = relevo.obtener(self.base, raiz)
        self.assertEqual(ent["estado"], "terminado_con_fallos")


class TestDual(Base):
    def _dual(self, estado, filas, resolver, intentos=None):
        llamadas = {"hecha": [], "ejecutar": [], "resuelta": []}
        contador = {"n": 0}

        def _indeterminado(t):
            contador["n"] += 1
            return contador["n"]

        dual = {"estado": estado, "filas": filas, "resolver": resolver,
                "hecha": lambda t: llamadas["hecha"].append(t),
                "ejecutar": lambda t: llamadas["ejecutar"].append(t),
                "indeterminado": _indeterminado,
                "resuelta_dueno": lambda t: llamadas["resuelta"].append(t)}
        return dual, llamadas

    def test_en_servidor_confirma_si_hay_resultado(self):
        dual, llamadas = self._dual(
            "servidor", [{"tarea": "t-1", "enviada_ts": self.ahora - 10}],
            resolver=lambda t: True)
        supervision.barrer(self.ctx(dual=dual))
        self.assertEqual(llamadas["hecha"], ["t-1"])
        self.assertEqual(llamadas["ejecutar"], [])

    def test_reconciliando_sin_resultado_tras_gracia_ejecuta_local(self):
        dual, llamadas = self._dual(
            "reconciliando",
            [{"tarea": "t-1", "enviada_ts": self.ahora - 200}],
            resolver=lambda t: False)
        supervision.barrer(self.ctx(dual=dual))
        self.assertEqual(llamadas["ejecutar"], ["t-1"])

    def test_reconciliando_dentro_de_gracia_espera(self):
        dual, llamadas = self._dual(
            "reconciliando",
            [{"tarea": "t-1", "enviada_ts": self.ahora - 30}],
            resolver=lambda t: False)
        supervision.barrer(self.ctx(dual=dual))
        self.assertEqual(llamadas["ejecutar"], [])

    def test_indeterminado_por_tres_lo_decide_el_dueno(self):
        dual, llamadas = self._dual(
            "reconciliando",
            [{"tarea": "t-1", "enviada_ts": self.ahora - 100}],
            resolver=lambda t: None)
        for _ in range(2):
            supervision.barrer(self.ctx(dual=dual))
            self.assertEqual(llamadas["resuelta"], [])
        supervision.barrer(self.ctx(dual=dual))
        self.assertEqual(llamadas["resuelta"], ["t-1"])
        self.assertEqual(llamadas["ejecutar"], [])  # nunca con duda
        self.assertEqual(len(self._avisos("dual_sin_resolver")), 1)


if __name__ == "__main__":
    unittest.main()

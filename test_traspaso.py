# -*- coding: utf-8 -*-
"""Pruebas de traspaso.py (Fase 3, §8 del diseño).

El protocolo completo con directorios y repos temporales: marcador
antes que efectos, parada del origen ANTES del rescate (B1), ejecutor
único (B4), rescate con commit wip, entrega derivada y reclamación
exactamente-una-vez con reasignación de alquileres (B5). Los fallos
(secreto en el rescate, merge a medias, parada no confirmada, tarea no
idempotente sin repo) caen en `requiere_dueno`, nunca en silencio.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alquileres
import git_trabajo
import traspaso


class Reloj:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True)


class CasoTraspaso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.base = raiz / "base"
        self.base.mkdir()
        self.inbox = raiz / "inbox-b"
        self.inbox.mkdir()
        self.repo = raiz / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@t.t")
        _git(self.repo, "config", "user.name", "T")
        (self.repo / "a.txt").write_text("base\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "inicial")
        self.proyecto = git_trabajo.registrar_proyecto(self.base, self.repo)
        self.repo_id = self.proyecto["repo_id"]
        self.reloj = Reloj()
        self.tarea = {"id": "t1", "prompt": "haz la cosa", "cuenta": "principal"}

    def tearDown(self):
        self.tmp.cleanup()

    def worktree_sucio(self, contenido="trabajo a medias\n", nombre="w.txt"):
        wt = git_trabajo.preparar_worktree(self.base, self.repo, "principal",
                                           "t1", "main")
        (wt / nombre).write_text(contenido)
        return wt

    def ganchos(self, **cambios):
        g = {"detener": lambda tid: True,
             "dict_tarea": lambda tid: self.tarea,
             "dir_tareas": self.inbox,
             "carril_destino": "b",
             "destino": "segunda",
             "ejecutor": "a:app"}
        g.update(cambios)
        return g

    def crear(self, **kw):
        args = dict(repo_id=self.repo_id, rama="muse/principal/t1",
                    reloj=self.reloj)
        args.update(kw)
        return traspaso.crear(self.base, "t1", "principal", "segunda", **args)


class TestProtocoloFeliz(CasoTraspaso):
    def test_protocolo_completo(self):
        wt = self.worktree_sucio()
        alquileres.tomar(self.base, self.repo_id, ["a.txt"], "principal",
                         "t1", reloj=self.reloj)
        m, creado = self.crear()
        self.assertTrue(creado)
        self.assertEqual(m["estado"], "ofrecido")
        m = traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                     reloj=self.reloj)
        self.assertEqual(m["estado"], "entregado")
        self.assertTrue(m["commit_rescate"])
        self.assertTrue(m["origen_detenido_ts"])
        # El trabajo sucio quedó confirmado en la rama y el worktree liberado.
        log = _git(self.repo, "log", "-1", "--format=%s",
                   "muse/principal/t1").stdout
        self.assertIn("wip: rescate", log)
        self.assertFalse(wt.exists())
        # La tarea derivada está en la bandeja del destino, bien formada.
        import json
        derivada = json.loads((self.inbox / f"{m['id']}.task.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(derivada["id"], m["id"])
        self.assertEqual(derivada["traspaso"]["de"], "principal")
        self.assertEqual(derivada["cuenta"], "segunda")
        self.assertIn("no repitas lo ya hecho", derivada["prompt"])
        # Reclamación: aceptada una sola vez y con los alquileres movidos.
        r = traspaso.reclamar(self.base, m["id"], "segunda", carril="b",
                              instancia="b:app", reloj=self.reloj)
        self.assertEqual(r["resultado"], "aceptado")
        self.assertEqual(r["reasignados"], 1)
        v = alquileres.vigentes(self.base, self.repo_id, reloj=self.reloj)
        self.assertEqual(v[0]["cuenta"], "segunda")
        # El mismo reclamante tras un cierre: reanudar, no duplicado (B3).
        r = traspaso.reclamar(self.base, m["id"], "segunda", carril="b",
                              instancia="b:app", reloj=self.reloj)
        self.assertEqual(r["resultado"], "reanudar")
        # Otra cuenta: duplicado, sin ejecutar nada.
        r = traspaso.reclamar(self.base, m["id"], "tercera", carril="b",
                              instancia="b:app2", reloj=self.reloj)
        self.assertEqual(r["resultado"], "duplicado")
        # Aceptada ⇒ el origen ya no puede recuperarla (B2).
        self.assertIsNotNone(traspaso.marcador_vivo_de(self.base, "t1"))

    def test_crear_es_idempotente(self):
        m1, c1 = self.crear()
        m2, c2 = self.crear()
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(m1["id"], m2["id"])

    def test_reclamar_antes_de_entregar_espera(self):
        m, _ = self.crear()
        r = traspaso.reclamar(self.base, m["id"], "segunda", carril="b",
                              reloj=self.reloj)
        self.assertEqual(r["resultado"], "esperar")


class TestCaidasAlDueno(CasoTraspaso):
    def test_parada_no_confirmada(self):
        self.worktree_sucio()
        m, _ = self.crear()
        m = traspaso.ejecutar_origen(
            self.base, m["id"], self.ganchos(detener=lambda tid: False),
            reloj=self.reloj)
        self.assertEqual(m["estado"], "requiere_dueno")
        self.assertIsNone(m["commit_rescate"])

    def test_rescate_con_secreto_no_confirma(self):
        wt = self.worktree_sucio("clave = 'sk-1234567890abcdefghij'\n",
                                 "s.txt")
        m, _ = self.crear()
        m = traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                     reloj=self.reloj)
        self.assertEqual(m["estado"], "requiere_dueno")
        self.assertIsNone(m["commit_rescate"])
        self.assertTrue(wt.exists())  # el worktree queda para el dueño

    def test_rescate_a_mitad_de_merge(self):
        wt = self.worktree_sucio()
        gitdir = Path((wt / ".git").read_text().split(":", 1)[1].strip())
        (gitdir / "MERGE_HEAD").write_text("0" * 40 + "\n")
        m, _ = self.crear()
        m = traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                     reloj=self.reloj)
        self.assertEqual(m["estado"], "requiere_dueno")
        self.assertIsNone(m["commit_rescate"])

    def test_sin_repo_y_sin_idempotente(self):
        m, _ = traspaso.crear(self.base, "t1", "principal", "segunda",
                              reloj=self.reloj)
        m = traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                     reloj=self.reloj)
        self.assertEqual(m["estado"], "requiere_dueno")

    def test_sin_repo_con_idempotente_entrega(self):
        self.tarea = {"id": "t1", "prompt": "p", "idempotente": True}
        m, _ = traspaso.crear(self.base, "t1", "principal", "segunda",
                              reloj=self.reloj)
        m = traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                     reloj=self.reloj)
        self.assertEqual(m["estado"], "entregado")


class TestEntregaFallida(CasoTraspaso):
    def test_fallo_en_la_entrega_deja_el_marcador_ofrecido(self):
        # El marcador se escribió ANTES que cualquier efecto (paso 0):
        # si la entrega falla, el estado queda reanudable, no perdido.
        self.worktree_sucio()
        m, _ = self.crear()
        ganchos = self.ganchos(dir_tareas=self.base / "no-existe")
        with self.assertRaises(traspaso.ErrorTraspaso):
            traspaso.ejecutar_origen(self.base, m["id"], ganchos,
                                     reloj=self.reloj)
        m = traspaso.obtener(self.base, m["id"])
        self.assertEqual(m["estado"], "ofrecido")
        self.assertTrue(m["origen_detenido_ts"])   # la parada sí ocurrió
        self.assertTrue(m["commit_rescate"])       # y el rescate también
        # Reintentando con la bandeja bien, el protocolo se completa.
        m = traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                     reloj=self.reloj)
        self.assertEqual(m["estado"], "entregado")


class TestCaducidades(CasoTraspaso):
    def test_entrega_caducada_se_devuelve(self):
        self.worktree_sucio()
        m, _ = self.crear()
        m = traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                     reloj=self.reloj)
        self.assertEqual(m["estado"], "entregado")
        self.reloj.avanzar(traspaso.TTL_OFRECIDO_S + 1)
        r = traspaso.reclamar(self.base, m["id"], "segunda", carril="b",
                              reloj=self.reloj)
        self.assertEqual(r["resultado"], "no_valido")
        self.assertEqual(traspaso.obtener(self.base, m["id"])["estado"],
                         "devuelto")
        # Devuelta ⇒ el origen SÍ puede recuperarla (ya no retiene).
        self.assertIsNone(traspaso.marcador_vivo_de(self.base, "t1"))

    def test_devuelto_no_se_reofrece_al_mismo_destino(self):
        m, _ = self.crear()
        traspaso._transicion(self.base, m["id"], estado="devuelto")
        m2, creado = self.crear()
        self.assertFalse(creado)
        self.assertIsNone(m2)
        # A un destino DISTINTO sí se puede ofrecer de nuevo.
        m3, creado3 = traspaso.crear(self.base, "t1", "principal", "tercera",
                                     reloj=self.reloj)
        self.assertTrue(creado3)

    def test_barrido_confirmado_sin_latido(self):
        self.worktree_sucio()
        m, _ = self.crear()
        traspaso.ejecutar_origen(self.base, m["id"], self.ganchos(),
                                 reloj=self.reloj)
        traspaso.reclamar(self.base, m["id"], "segunda", carril="b",
                          reloj=self.reloj)
        self.reloj.avanzar(traspaso.TTL_SUPERVISION_S + 1)
        cambios = traspaso.barrido(self.base, reloj=self.reloj,
                                   destino_sin_latido=lambda c: True)
        self.assertIn((m["id"], "requiere_dueno"), cambios)

    def test_ejecutor_no_se_roba_con_latido_fresco(self):
        m, _ = self.crear()
        self.assertTrue(traspaso.tomar_ejecutor(self.base, m["id"], "a:app",
                                                reloj=self.reloj))
        self.assertFalse(traspaso.tomar_ejecutor(self.base, m["id"], "b:app",
                                                 reloj=self.reloj))
        self.reloj.avanzar(traspaso.TTL_EJECUTOR_S + 1)
        self.assertTrue(traspaso.tomar_ejecutor(self.base, m["id"], "b:app",
                                                reloj=self.reloj))


if __name__ == "__main__":
    unittest.main()

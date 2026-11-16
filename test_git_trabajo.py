# -*- coding: utf-8 -*-
"""Pruebas de git_trabajo.py (Fase 3, §2/§3/§5/§6 del diseño).

Con repos git temporales REALES (incluido un remoto «bare» local):
registro de proyectos, worktrees por (cuenta, tarea), propuestas con
veredicto firmado sobre un sha, aprobación del dueño por el circuito
de permission-layer.py y mezcla en HEAD separado que no toca el árbol
del dueño ni su `main` local.
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


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check,
                          capture_output=True, text=True)


def _sha(repo, ref):
    return _git(repo, "rev-parse", ref).stdout.strip()


class CasoRepo(unittest.TestCase):
    """Repo con remoto bare local y main ya subido."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.base = raiz / "base"
        self.base.mkdir()
        self.remoto = raiz / "remoto.git"
        _git(raiz, "init", "-q", "--bare", "-b", "main", str(self.remoto))
        self.repo = raiz / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@t.t")
        _git(self.repo, "config", "user.name", "T")
        (self.repo / "a.txt").write_text("base\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "inicial")
        _git(self.repo, "remote", "add", "origin", str(self.remoto))
        _git(self.repo, "push", "-q", "origin", "main")
        _git(self.repo, "remote", "set-head", "origin", "main")
        # El circuito de confirmaciones y la auditoría, a temporal.
        self.pl = git_trabajo._cargar_permission_layer()
        pl_dir = raiz / "pl"
        pl_dir.mkdir()
        self._pl_viejo = (self.pl.AUDIT_PATH, self.pl.CONFIRM_PATH,
                          self.pl.SECRET_PATH)
        self.pl.AUDIT_PATH = str(pl_dir / "audit-log.json")
        self.pl.CONFIRM_PATH = str(pl_dir / "confirmaciones.json")
        self.pl.SECRET_PATH = str(pl_dir / "permission-secret.key")
        # secretos.py carga su PROPIA copia de permission-layer para la
        # clave HMAC: que la lea del temporal, no de la ruta por defecto
        # (que es la carpeta del repo).
        self._env_viejo = os.environ.get("GROWI_PERM_SECRET")
        os.environ["GROWI_PERM_SECRET"] = str(pl_dir / "permission-secret.key")
        self.proyecto = git_trabajo.registrar_proyecto(self.base, self.repo)
        self.repo_id = self.proyecto["repo_id"]

    def tearDown(self):
        (self.pl.AUDIT_PATH, self.pl.CONFIRM_PATH,
         self.pl.SECRET_PATH) = self._pl_viejo
        if self._env_viejo is None:
            os.environ.pop("GROWI_PERM_SECRET", None)
        else:
            os.environ["GROWI_PERM_SECRET"] = self._env_viejo
        self.tmp.cleanup()

    # -- utilidades ------------------------------------------------------
    def worktree_con_commit(self, cuenta="principal", tarea="t1",
                            archivo="b.txt", contenido="trabajo\n"):
        wt = git_trabajo.preparar_worktree(self.base, self.repo, cuenta,
                                           tarea, "main")
        (wt / archivo).write_text(contenido)
        _git(wt, "add", "-A")
        _git(wt, "commit", "-qm", f"trabajo de {tarea}")
        return wt

    def proponer(self, cuenta="principal", tarea="t1", **kw):
        wt = self.worktree_con_commit(cuenta, tarea, **kw)
        rama = git_trabajo.nombre_rama(cuenta, tarea)
        _git(self.repo, "push", "-q", "origin", rama)
        return git_trabajo.crear_propuesta(
            self.base, self.repo_id, rama, cuenta, tarea, "main",
            _sha(self.repo, "origin/main"), _sha(self.repo, f"origin/{rama}"),
            auditar=lambda **k: None)

    def aprobar(self, prop):
        git_trabajo.registrar_veredicto(self.base, prop["id"], "segunda",
                                        "ok", prop["sha_rama"],
                                        auditar=lambda **k: None)
        prop = git_trabajo.obtener_propuesta(self.base, prop["id"])
        self.pl.resolver_confirmacion(prop["confirmacion_id"], True,
                                      "consola-humano")
        return prop


class TestRegistro(CasoRepo):
    def test_registro_idempotente_e_id_estable(self):
        otro = git_trabajo.registrar_proyecto(self.base, self.repo)
        self.assertEqual(otro["repo_id"], self.repo_id)
        self.assertEqual(len(git_trabajo.proyectos(self.base)), 1)
        self.assertEqual(self.proyecto["rama_base"], "main")

    def test_hook_instalado_con_marcador(self):
        hook = self.repo / ".git" / "hooks" / "pre-push"
        self.assertTrue(hook.is_file())
        self.assertIn("growi-bridge: pre-push", hook.read_text())

    def test_hook_ajeno_es_conflicto_y_no_se_toca(self):
        repo2 = Path(self.tmp.name) / "repo2"
        repo2.mkdir()
        _git(repo2, "init", "-q", "-b", "main")
        _git(repo2, "config", "user.email", "t@t.t")
        _git(repo2, "config", "user.name", "T")
        (repo2 / "x.txt").write_text("x\n")
        _git(repo2, "add", "-A")
        _git(repo2, "commit", "-qm", "x")
        hook = repo2 / ".git" / "hooks" / "pre-push"
        hook.write_text("#!/bin/sh\necho mio\n")
        p = git_trabajo.registrar_proyecto(self.base, repo2)
        self.assertEqual(p["hook"], "conflicto")
        self.assertEqual(hook.read_text(), "#!/bin/sh\necho mio\n")


class TestWorktrees(CasoRepo):
    def test_crear_y_reutilizar(self):
        wt = git_trabajo.preparar_worktree(self.base, self.repo, "principal",
                                           "t1", "main")
        self.assertTrue(wt.is_dir())
        self.assertEqual(git_trabajo.estado_worktree(wt)["rama"],
                         "muse/principal/t1")
        wt2 = git_trabajo.preparar_worktree(self.base, self.repo, "principal",
                                            "t1", "main")
        self.assertEqual(wt, wt2)

    def test_rama_ocupada_en_otro_worktree_error(self):
        git_trabajo.preparar_worktree(self.base, self.repo, "principal",
                                      "t1", "main")
        # Otra tarea que pide la MISMA rama: está ocupada en el worktree
        # de t1 y no puede abrirse en dos sitios.
        with self.assertRaises(git_trabajo.ErrorGit):
            git_trabajo.preparar_worktree(self.base, self.repo, "principal",
                                          "t2", "main",
                                          rama="muse/principal/t1")

    def test_rama_explicita_reusa_la_del_origen(self):
        # B6: la continuidad manda — la rama del traspaso se reusa tal cual.
        wt = self.worktree_con_commit("principal", "t1")
        rama = "muse/principal/t1"
        git_trabajo.liberar_worktree(self.repo, "principal", "t1")
        wt2 = git_trabajo.preparar_worktree(self.base, self.repo, "segunda",
                                            "t9", "main", rama=rama)
        self.assertEqual(git_trabajo.estado_worktree(wt2)["rama"], rama)

    def test_liberar_sucio_sin_forzar_error_y_rama_queda(self):
        wt = self.worktree_con_commit()
        (wt / "sucio.txt").write_text("sin confirmar\n")
        with self.assertRaises(git_trabajo.ErrorGit):
            git_trabajo.liberar_worktree(self.repo, "principal", "t1")
        self.assertTrue(git_trabajo.liberar_worktree(
            self.repo, "principal", "t1", forzar=True))
        self.assertIsNotNone(git_trabajo._sha_de(self.repo,
                                                 "muse/principal/t1"))


class TestPropuestas(CasoRepo):
    def test_propuesta_vacia_rechazada(self):
        git_trabajo.preparar_worktree(self.base, self.repo, "principal",
                                      "t1", "main")
        sha = _sha(self.repo, "main")
        with self.assertRaises(git_trabajo.ErrorGit):
            git_trabajo.crear_propuesta(self.base, self.repo_id,
                                        "muse/principal/t1", "principal",
                                        "t1", "main", sha, sha)

    def test_repropuesta_actualiza_y_limpia_veredicto(self):
        prop = self.proponer()
        git_trabajo.registrar_veredicto(self.base, prop["id"], "segunda",
                                        "cambios", prop["sha_rama"],
                                        auditar=lambda **k: None)
        wt = git_trabajo.ruta_worktree(self.repo, "principal", "t1")
        (wt / "c.txt").write_text("corrección\n")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-qm", "corrección")
        _git(self.repo, "push", "-q", "origin", "muse/principal/t1")
        prop2 = git_trabajo.crear_propuesta(
            self.base, self.repo_id, "muse/principal/t1", "principal", "t1",
            "main", _sha(self.repo, "origin/main"),
            _sha(self.repo, "origin/muse/principal/t1"),
            auditar=lambda **k: None)
        self.assertEqual(prop2["id"], prop["id"])
        self.assertEqual(prop2["estado"], "propuesta")
        self.assertIsNone(prop2["veredicto"])

    def test_veredicto_ok_pide_aprobacion(self):
        prop = self.proponer()
        git_trabajo.registrar_veredicto(self.base, prop["id"], "segunda",
                                        "ok", prop["sha_rama"],
                                        auditar=lambda **k: None)
        prop = git_trabajo.obtener_propuesta(self.base, prop["id"])
        self.assertEqual(prop["estado"], "esperando_dueno")
        self.assertTrue(prop["confirmacion_id"])

    def test_mezclar_sin_aprobacion_no(self):
        prop = self.proponer()
        git_trabajo.registrar_veredicto(self.base, prop["id"], "segunda",
                                        "ok", prop["sha_rama"],
                                        auditar=lambda **k: None)
        r = git_trabajo.mezclar(self.base, prop["id"], "segunda",
                                auditar=lambda **k: None)
        self.assertFalse(r["ok"])
        self.assertEqual(_sha(self.remoto, "main"),
                         _sha(self.repo, "origin/main"))


class TestMezcla(CasoRepo):
    def test_mezcla_aprobada_con_main_local_ocupada(self):
        # El dueño tiene main abierta en su árbol, con cambios sin guardar.
        (self.repo / "a.txt").write_text("edición del dueño sin guardar\n")
        main_local_antes = _sha(self.repo, "main")
        prop = self.aprobar(self.proponer())
        r = git_trabajo.mezclar(self.base, prop["id"], "segunda",
                                auditar=lambda **k: None)
        self.assertTrue(r["ok"], r)
        # El remoto avanzó con el trabajo; el main LOCAL no se movió y el
        # árbol del dueño conserva su edición.
        self.assertNotEqual(_sha(self.remoto, "main"), main_local_antes)
        self.assertEqual(_sha(self.repo, "main"), main_local_antes)
        self.assertEqual((self.repo / "a.txt").read_text(),
                         "edición del dueño sin guardar\n")
        self.assertEqual(git_trabajo.obtener_propuesta(
            self.base, prop["id"])["estado"], "mezclada")

    def test_rama_movida_tras_aprobacion_vuelve_a_revision(self):
        prop = self.aprobar(self.proponer())
        wt = git_trabajo.ruta_worktree(self.repo, "principal", "t1")
        (wt / "tarde.txt").write_text("sin revisar\n")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-qm", "commit tardío")
        _git(self.repo, "push", "-q", "origin", "muse/principal/t1")
        remoto_antes = _sha(self.remoto, "main")
        r = git_trabajo.mezclar(self.base, prop["id"], "segunda",
                                auditar=lambda **k: None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["estado"], "en_revision")
        self.assertEqual(_sha(self.remoto, "main"), remoto_antes)
        self.assertEqual(git_trabajo.obtener_propuesta(
            self.base, prop["id"])["estado"], "en_revision")

    def test_conflicto_no_toca_la_base(self):
        prop = self.proponer(contenido="versión de la rama\n",
                             archivo="a.txt")
        # Mientras tanto, main cambia la misma línea por otro camino.
        (self.repo / "a.txt").write_text("versión de main\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "main cambia a.txt")
        _git(self.repo, "push", "-q", "origin", "main")
        prop = self.aprobar(prop)
        remoto_antes = _sha(self.remoto, "main")
        r = git_trabajo.mezclar(self.base, prop["id"], "segunda",
                                auditar=lambda **k: None)
        self.assertFalse(r["ok"])
        self.assertEqual(r["estado"], "conflicto")
        self.assertIn("a.txt", r["conflictos"])
        self.assertEqual(_sha(self.remoto, "main"), remoto_antes)


class TestSubir(CasoRepo):
    def test_subir_limpio(self):
        self.worktree_con_commit()
        r = git_trabajo.subir(self.base, self.repo, "muse/principal/t1",
                              "principal", "t1", auditar=lambda **k: None)
        self.assertTrue(r["ok"], r)
        self.assertEqual(_sha(self.remoto, "muse/principal/t1"),
                         _sha(self.repo, "muse/principal/t1"))

    def test_subir_con_secreto_bloqueado(self):
        wt = self.worktree_con_commit(
            archivo="s.txt",
            contenido="clave = 'sk-1234567890abcdefghijklmnopqrstuv'\n")
        r = git_trabajo.subir(self.base, self.repo, "muse/principal/t1",
                              "principal", "t1", auditar=lambda **k: None)
        self.assertFalse(r["ok"])
        self.assertTrue(r["hallazgos"])
        rc = _git(self.remoto, "rev-parse", "--verify", "--quiet",
                  "muse/principal/t1", check=False).returncode
        self.assertNotEqual(rc, 0)  # la rama nunca llegó al remoto

    def test_subir_sin_alquiler_avisa_pero_sube(self):
        self.worktree_con_commit()
        r = git_trabajo.subir(self.base, self.repo, "muse/principal/t1",
                              "principal", "t1", auditar=lambda **k: None)
        self.assertTrue(r["ok"])
        self.assertTrue(r["sin_alquiler"])

    def test_subir_bloqueado_si_otra_cuenta_tiene_la_tarea(self):
        self.worktree_con_commit()
        alquileres.tomar(self.base, self.repo_id, ["b.txt"], "segunda", "t1")
        r = git_trabajo.subir(self.base, self.repo, "muse/principal/t1",
                              "principal", "t1", auditar=lambda **k: None)
        self.assertFalse(r["ok"])


class TestLimpieza(CasoRepo):
    def _envejecer(self, pid, estado):
        d = git_trabajo.cargar_propuestas(self.base)
        d["propuestas"][pid]["estado"] = estado
        d["propuestas"][pid]["actualizada_ts"] = 1_000_000.0
        git_trabajo._guardar_json(self.base, git_trabajo.ARCHIVO_PROPUESTAS, d)

    def test_limpieza_respeta_sucios_y_vivas(self):
        wt_vieja = self.worktree_con_commit(tarea="vieja")
        prop = git_trabajo.crear_propuesta(
            self.base, self.repo_id, "muse/principal/vieja", "principal",
            "vieja", "main", _sha(self.repo, "main"),
            _sha(self.repo, "muse/principal/vieja"),
            auditar=lambda **k: None)
        self._envejecer(prop["id"], "mezclada")
        wt_sucia = self.worktree_con_commit(tarea="sucia")
        prop2 = git_trabajo.crear_propuesta(
            self.base, self.repo_id, "muse/principal/sucia", "principal",
            "sucia", "main", _sha(self.repo, "main"),
            _sha(self.repo, "muse/principal/sucia"),
            auditar=lambda **k: None)
        self._envejecer(prop2["id"], "rechazada")
        (wt_sucia / "sin_confirmar.txt").write_text("trabajo vivo\n")
        r = git_trabajo.limpieza(self.base, self.repo_id, dias=7,
                                 reloj=lambda: 1_000_000.0 + 8 * 86400,
                                 auditar=lambda **k: None)
        self.assertIn(str(wt_vieja), r["worktrees"])
        self.assertIn(str(wt_sucia), r["saltados"])
        self.assertTrue(wt_sucia.exists())  # sucia: intocable


if __name__ == "__main__":
    unittest.main()

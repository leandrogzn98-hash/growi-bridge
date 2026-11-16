# -*- coding: utf-8 -*-
"""Pruebas de secretos.py (Fase 3, §6 del diseño).

El escáner trabaja sobre OBJETOS git (lo que el push enviaría y el
remoto no tiene), no sobre diffs: un secreto en un commit intermedio,
en un merge o en un archivo ya borrado sigue bloqueando. Los
permitidos solo valen con firma HMAC del dueño y viven fuera del repo.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secretos

SECRETO_SK = "sk-1234567890abcdefghijklmnopqrstuv"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def _commit(repo, mensaje="c"):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", mensaje)


class CasoRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@t.t")
        _git(self.repo, "config", "user.name", "T")
        (self.repo / "a.txt").write_text("hola\n")
        _commit(self.repo, "inicial")

    def tearDown(self):
        self.tmp.cleanup()

    def head(self):
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo,
                              capture_output=True, text=True,
                              check=True).stdout.strip()

    def escanear(self, **kw):
        return secretos.escanear_objetos(self.repo, self.head(), **kw)


class TestPatronesTexto(unittest.TestCase):
    def test_patrones_de_contenido(self):
        casos = [
            f"clave = '{SECRETO_SK}'",
            "token = 'ghp_1234567890abcdefghijklmnopqrstuv'",
            "token = 'github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz'",
            "slack = 'xoxb-123456789012-abcdefghijkl'",
            "google = 'AIzaSyA1234567890abcdefghijklmnopqrstuv'",
            "aws = 'AKIAIOSFODNN7EXAMPLE'",
            "-----BEGIN RSA PRIVATE KEY-----",
            "auth = 'tsk_1234567890abcdefghij'",
            "MI_API_TOKEN = 'valor-super-secreto-123'",
            'jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.'
            'SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c"',
        ]
        for linea in casos:
            hall = secretos.escanear_texto(linea + "\n", ruta="x.py")
            self.assertTrue(hall, f"no detectado: {linea[:40]}")

    def test_marcadores_no_son_secretos(self):
        for linea in ("TOKEN = 'changeme'", "password = 'xxxxxxxxxxxx'",
                      "api_key = '${MI_API_KEY}'", "secret = '<tu-secreto>'",
                      "token = '...'"):
            hall = secretos.escanear_texto(linea + "\n", ruta="x.py")
            self.assertFalse(hall, f"falso positivo: {linea}")

    def test_evidencia_siempre_redactada(self):
        hall = secretos.escanear_texto(f"clave = '{SECRETO_SK}'\n", ruta="x.py")
        self.assertTrue(hall)
        self.assertNotIn(SECRETO_SK, str(hall))


class TestNombres(unittest.TestCase):
    def test_nombres_bloqueados(self):
        for ruta in ("secret.txt", ".env", ".env.local", "prod/.ENV",
                     "Secret.TXT", "clave.pem", "id_rsa", "id_ed25519.pub",
                     "credenciales.dpapi.json", "audit-log.json",
                     "tablero.json", "cola.db", "x/cola.db-wal",
                     "respaldo/tablero.json", ".growi/x.json",
                     "settings.json", "accounts.json"):
            self.assertTrue(secretos.nombre_bloqueado(ruta), ruta)

    def test_nombres_libres(self):
        for ruta in (".env.example", ".env.sample", "src/main.py",
                     "docs/secretos.md", "env.py"):
            self.assertFalse(secretos.nombre_bloqueado(ruta), ruta)


class TestObjetos(CasoRepo):
    def test_secreto_en_commit_intermedio(self):
        (self.repo / "s.txt").write_text(f"clave = '{SECRETO_SK}'\n")
        _commit(self.repo, "con secreto")
        (self.repo / "s.txt").write_text("ya no hay nada\n")
        _commit(self.repo, "limpieza aparente")
        hall = self.escanear()
        self.assertTrue(any(h["tipo"] == "contenido" or h["huella"]
                            for h in hall), hall)
        self.assertNotIn(SECRETO_SK, str(hall))

    def test_secreto_en_commit_de_merge(self):
        _git(self.repo, "checkout", "-qb", "rama")
        (self.repo / "s.txt").write_text(f"clave = '{SECRETO_SK}'\n")
        _commit(self.repo, "con secreto")
        _git(self.repo, "checkout", "-q", "main")
        (self.repo / "b.txt").write_text("otra cosa\n")
        _commit(self.repo, "en main")
        _git(self.repo, "merge", "-q", "--no-ff", "-m", "merge", "rama")
        hall = self.escanear()
        self.assertTrue(hall)

    def test_nombre_bloqueado_sin_excepcion(self):
        (self.repo / ".env").write_text("TODO_INOCUO=1\n")
        _commit(self.repo, "env inocuo")
        hall = self.escanear()
        self.assertTrue(any(h["tipo"] == "nombre_bloqueado" for h in hall))

    def test_env_example_limpio_pasa_y_con_clave_no(self):
        (self.repo / ".env.example").write_text("TOKEN=\nOTRA=${TOKEN}\n")
        _commit(self.repo, "ejemplo")
        self.assertEqual(self.escanear(), [])
        (self.repo / ".env.example").write_text(f"TOKEN={SECRETO_SK}\n")
        _commit(self.repo, "ejemplo con clave real")
        self.assertTrue(self.escanear())

    def test_utf16_detectado(self):
        (self.repo / "u.txt").write_bytes(
            f"clave = '{SECRETO_SK}'\n".encode("utf-16"))
        _commit(self.repo, "utf16")
        self.assertTrue(self.escanear())

    def test_binario_es_no_escaneable_y_bloquea(self):
        (self.repo / "b.bin").write_bytes(bytes(range(256)) * 4)
        _commit(self.repo, "binario")
        hall = self.escanear()
        self.assertTrue(any(h["tipo"] == "no_escaneable" for h in hall))

    def test_lfs_bloqueado(self):
        (self.repo / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs -text\n")
        (self.repo / "g.bin").write_text(
            "version https://git-lfs.github.com/spec/v1\noid sha256:abc\n")
        _commit(self.repo, "lfs")
        hall = self.escanear()
        self.assertTrue(any(h["tipo"] == "git_lfs" for h in hall))

    def test_repo_limpio_sin_hallazgos(self):
        (self.repo / "b.txt").write_text("nada que ver\n")
        _commit(self.repo, "limpio")
        self.assertEqual(self.escanear(), [])


class TestPermitidos(CasoRepo):
    def setUp(self):
        super().setUp()
        self.base = Path(self.tmp.name) / "base"
        self.base.mkdir()
        self.clave = Path(self.tmp.name) / "clave.key"
        self.clave.write_bytes(b"clave-de-prueba-del-dueno")
        os.environ["GROWI_PERM_SECRET"] = str(self.clave)
        (self.repo / "s.txt").write_text(f"clave = '{SECRETO_SK}'\n")
        _commit(self.repo, "con secreto")
        self.repo_id = "repo-prueba"

    def tearDown(self):
        os.environ.pop("GROWI_PERM_SECRET", None)
        super().tearDown()

    def test_sin_permitido_bloquea(self):
        hall = self.escanear(base_dir=self.base, repo_id=self.repo_id)
        self.assertTrue(hall)

    def test_permitido_firmado_perdona_solo_esa_linea(self):
        hall = self.escanear(base_dir=self.base, repo_id=self.repo_id)
        h = hall[0]
        secretos.agregar_permitido(self.base, self.repo_id, h["archivo"],
                                   h["huella"], h["tipo"])
        self.assertEqual(self.escanear(base_dir=self.base,
                                       repo_id=self.repo_id), [])
        # Otra línea con otro secreto NO queda perdonada.
        (self.repo / "s2.txt").write_text("token = 'ghp_1234567890abcdefghijklmnopqrstuv'\n")
        _commit(self.repo, "otro secreto")
        self.assertTrue(self.escanear(base_dir=self.base,
                                      repo_id=self.repo_id))

    def test_permitido_falsificado_no_vale(self):
        hall = self.escanear(base_dir=self.base, repo_id=self.repo_id)
        h = hall[0]
        ruta = secretos._ruta_permitidos(self.base, self.repo_id)
        ruta.write_text(
            '[{"ruta": "%s", "huella": "%s", "tipo": "%s", "firma": "00"}]'
            % (h["archivo"], h["huella"], h["tipo"]), encoding="utf-8")
        self.assertTrue(self.escanear(base_dir=self.base,
                                      repo_id=self.repo_id))

    def test_nombre_bloqueado_nunca_se_perdona(self):
        (self.repo / ".env").write_text(f"TOKEN={SECRETO_SK}\n")
        _commit(self.repo, "env con clave")
        hall = self.escanear(base_dir=self.base, repo_id=self.repo_id)
        nombres = [h for h in hall if h["tipo"] == "nombre_bloqueado"]
        self.assertTrue(nombres)


class TestHook(unittest.TestCase):
    def test_texto_hook_con_marcador_y_despliegue(self):
        with tempfile.TemporaryDirectory() as td:
            destino = secretos.desplegar(Path(td))
            self.assertTrue(destino.is_file())
            texto = secretos.texto_hook("/usr/bin/python3", str(destino),
                                        Path(td))
            self.assertIn("growi-bridge: pre-push", texto)
            self.assertIn("--escanear-push", texto)


class TestStaged(CasoRepo):
    def test_staged_con_secreto(self):
        (self.repo / "s.txt").write_text(f"clave = '{SECRETO_SK}'\n")
        _git(self.repo, "add", "s.txt")
        hall = secretos.escanear_staged(self.repo)
        self.assertTrue(hall)
        self.assertNotIn(SECRETO_SK, str(hall))

    def test_staged_limpio(self):
        (self.repo / "s.txt").write_text("nada\n")
        _git(self.repo, "add", "s.txt")
        self.assertEqual(secretos.escanear_staged(self.repo), [])


if __name__ == "__main__":
    unittest.main()

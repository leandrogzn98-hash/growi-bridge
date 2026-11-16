"""Pruebas de la Fase 6: contenedores.py con ejecutor falso."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import contenedores
import git_trabajo
import recursos


def limites_ejemplo():
    specs = {"cpu": {"logicos": 8, "fisicos": 4}, "ram_total": 16 << 30,
             "gpu": None}
    return recursos.limites(specs, {"cpu": 50, "ram": 50, "gpu": 50}, 1)


class EjecutorFalso:
    """Simula un runtime: info ok, inspect de contenedor según el
    estado que el test declare, image inspect falla (hay que pull).
    """

    def __init__(self, existe=False, en_marcha=False):
        self.llamadas = []
        self.existe = existe
        self.en_marcha = en_marcha

    def __call__(self, argv, timeout_s=10):
        self.llamadas.append(list(argv))
        if argv[1] == "info":
            return 0, "{}", ""
        if argv[1] == "inspect" and "--format" in argv:
            if not self.existe:
                return 1, "", "no existe"
            return 0, "true" if self.en_marcha else "false", ""
        if argv[1] == "image":
            return 1, "", "sin imagen local"
        return 0, "", ""

    def de(self, verbo):
        return [a for a in self.llamadas if a[1] == verbo]


def proyecto(repo="/repos/juego", **kw):
    p = {"repo_id": "abc123", "ruta": repo, "nombre": "juego",
         "contenedores": "proyecto", "contenedor_modo": "opcional",
         "contenedor_imagen": "python:3.12-slim",
         "contenedor_red": "saliente", "contenedor": None}
    p.update(kw)
    return p


class TestDeteccion(unittest.TestCase):
    def setUp(self):
        contenedores._CACHE.update({"ts": 0.0, "valor": None})

    def test_podman_preferente(self):
        def ejecutar(argv, timeout_s=10):
            return 0, "{}", ""
        det = contenedores.detectar_runtime(
            ejecutar=ejecutar, cual=lambda n: f"/usr/bin/{n}")
        self.assertEqual(det["runtime"], "podman")

    def test_podman_mudo_cae_a_docker(self):
        def ejecutar(argv, timeout_s=10):
            return (1, "", "sin respuesta") if argv[0] == "podman" \
                else (0, "{}", "")
        det = contenedores.detectar_runtime(
            ejecutar=ejecutar, cual=lambda n: f"/usr/bin/{n}")
        self.assertEqual(det["runtime"], "docker")
        self.assertIn("root", det["matiz"])

    def test_ninguno(self):
        det = contenedores.detectar_runtime(
            ejecutar=lambda a, timeout_s=10: (0, "", ""),
            cual=lambda n: None)
        self.assertIsNone(det["runtime"])


class TestArgvCrear(unittest.TestCase):
    def test_montajes_espejo_exactos_y_solo_esos(self):
        p = proyecto()
        argv, montajes, _u = contenedores.argv_crear(
            "podman", "growi-abc123", "/base", p,
            limites_dict=limites_ejemplo(), uid=1000, gid=1000)
        vols = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
        self.assertEqual(vols, [
            "/repos/juego.worktrees:/repos/juego.worktrees",
            "/repos/juego/.git:/repos/juego/.git"])
        self.assertNotIn("--user", argv)  # podman rootless: sin --user

    def test_docker_lleva_user_y_limites(self):
        p = proyecto()
        argv, _m, usuario = contenedores.argv_crear(
            "docker", "growi-abc123", "/base", p,
            limites_dict=limites_ejemplo(), uid=1000, gid=1001)
        self.assertEqual(usuario, "1000:1001")
        i = argv.index("--user")
        self.assertEqual(argv[i + 1], "1000:1001")
        self.assertIn("--cpus", argv)
        self.assertIn("--memory", argv)
        self.assertEqual(argv[-3:], ["python:3.12-slim", "sleep",
                                     "infinity"])

    def test_red_ninguna_y_sin_banderas_prohibidas(self):
        p = proyecto(contenedor_red="ninguna")
        argv, _m, _u = contenedores.argv_crear(
            "podman", "growi-abc123", "/base", p)
        i = argv.index("--network")
        self.assertEqual(argv[i + 1], "none")
        for prohibida in ("--publish", "-p", "--privileged",
                          "--device"):
            self.assertNotIn(prohibida, argv)
        p2 = proyecto(contenedor_red="saliente")
        argv2, _m2, _u2 = contenedores.argv_crear(
            "podman", "growi-abc123", "/base", p2)
        self.assertNotIn("--network", argv2)

    def test_por_cuenta_estrecha_montajes_y_git_ro(self):
        p = proyecto(contenedores="por_cuenta")
        argv, montajes, _u = contenedores.argv_crear(
            "podman", "growi-abc123-segunda", "/base", p,
            cuenta="segunda")
        vols = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
        self.assertEqual(vols, [
            "/repos/juego.worktrees/segunda:"
            "/repos/juego.worktrees/segunda",
            "/repos/juego/.git:/repos/juego/.git:ro"])


class TestExecYEntorno(unittest.TestCase):
    def test_exec_con_filtro_de_credenciales(self):
        env = {"PATH": "/usr/bin", "HOME": "/home/x",
               "GITHUB_TOKEN": "canario-secreto",
               "MI_API_KEY": "canario-2", "EDITOR": "vi"}
        argv = contenedores.argv_exec("podman", "growi-abc123",
                                      "/repos/juego.worktrees/p/t",
                                      env, ["/bin/echo", "hola"])
        plano = " ".join(argv)
        self.assertNotIn("canario-secreto", plano)
        self.assertNotIn("canario-2", plano)
        self.assertNotIn("GITHUB_TOKEN", plano)
        self.assertIn("GROWI_EN_CONTENEDOR=1", plano)
        self.assertNotIn("GIT_OPTIONAL_LOCKS", plano)
        self.assertEqual(argv[-2:], ["/bin/echo", "hola"])
        self.assertEqual(argv[:4], ["podman", "exec", "-i", "-w"])

    def test_exec_por_cuenta_marca_git_sin_cierres(self):
        argv = contenedores.argv_exec("podman", "c", "/w", {},
                                      ["/bin/true"], por_cuenta=True)
        self.assertIn("GIT_OPTIONAL_LOCKS=0", " ".join(argv))

    def test_update_limites(self):
        argv = contenedores.argv_update_limites(
            "docker", "growi-abc123", limites_ejemplo())
        self.assertEqual(argv[0:2], ["docker", "update"])
        self.assertEqual(argv[-1], "growi-abc123")
        self.assertIn("--cpus", argv)


class TestHuellaYCredenciales(unittest.TestCase):
    def test_huella_cambia_con_imagen_y_red(self):
        m = [("/a", False)]
        h1 = contenedores.huella_config("podman", "img:1", m,
                                        "saliente", None)
        h2 = contenedores.huella_config("podman", "img:2", m,
                                        "saliente", None)
        h3 = contenedores.huella_config("podman", "img:1", m,
                                        "ninguna", None)
        h4 = contenedores.huella_config("podman", "img:1", m,
                                        "saliente", None)
        self.assertNotEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(h1, h4)

    def test_token_en_url_del_remoto(self):
        with tempfile.TemporaryDirectory() as td:
            git = Path(td) / ".git"
            git.mkdir()
            (git / "config").write_text(
                '[remote "origin"]\n\turl = '
                "https://tokensecreto@github.com/x/y.git\n",
                encoding="utf-8")
            self.assertTrue(
                contenedores.credenciales_en_config_git(td))
            (git / "config").write_text(
                '[remote "origin"]\n\turl = '
                "git@github.com:x/y.git\n", encoding="utf-8")
            self.assertFalse(
                contenedores.credenciales_en_config_git(td))
            (git / "config").write_text(
                '[remote "origin"]\n\turl = '
                "https://github.com/x/y.git\n", encoding="utf-8")
            self.assertFalse(
                contenedores.credenciales_en_config_git(td))


CUAL = lambda n: f"/usr/bin/{n}"  # noqa: E731


class TestAsegurar(unittest.TestCase):
    def setUp(self):
        contenedores._CACHE.update({"ts": 0.0, "valor": None})
        self.td = tempfile.TemporaryDirectory()
        self.base = Path(self.td.name)
        self.repo = self.base / "juego"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / ".git" / "config").write_text(
            '[remote "origin"]\n\turl = git@github.com:x/y.git\n',
            encoding="utf-8")
        self.proy = proyecto(repo=str(self.repo))
        datos = {"version": 1, "revision": 0,
                 "proyectos": {"abc123": self.proy}}
        (self.base / "proyectos.json").write_text(
            json.dumps(datos), encoding="utf-8")

    def tearDown(self):
        self.td.cleanup()

    def test_modo_no_no_toca_nada(self):
        def prohibido(argv, timeout_s=10):
            raise AssertionError("con modo «no» no se llama a nada")
        r = contenedores.asegurar(
            self.base, proyecto(contenedor_modo="no"),
            ejecutar=prohibido)
        self.assertEqual(r["estado"], "sin_contenedor")

    def test_sin_runtime_opcional_degrada_requerido_espera(self):
        def sin_runtime(argv, timeout_s=10):
            return 1, "", ""
        r = contenedores.asegurar(self.base, self.proy,
                                  ejecutar=sin_runtime)
        self.assertEqual(r["estado"], "degradado")
        r = contenedores.asegurar(
            self.base, proyecto(repo=str(self.repo),
                                contenedor_modo="requerido"),
            ejecutar=sin_runtime)
        self.assertEqual(r["estado"], "esperar")

    def test_crea_con_pull_y_guarda_estado(self):
        ej = EjecutorFalso()
        r = contenedores.asegurar(self.base, self.proy, ejecutar=ej,
                                  limites_dict=limites_ejemplo(),
                                  cual=CUAL)
        self.assertEqual(r["estado"], "listo")
        self.assertFalse(r["reutilizado"])
        self.assertEqual(len(ej.de("pull")), 1)
        self.assertEqual(len(ej.de("create")), 1)
        self.assertEqual(len(ej.de("start")), 1)
        guardado = git_trabajo.proyecto(self.base, "abc123")
        self.assertEqual(guardado["contenedor"]["nombre"],
                         "growi-abc123")
        self.assertEqual(guardado["contenedor"]["runtime"], "podman")

    def test_reutiliza_si_huella_coincide(self):
        ej = EjecutorFalso()
        r1 = contenedores.asegurar(self.base, self.proy, ejecutar=ej,
                                   limites_dict=limites_ejemplo(),
                                   cual=CUAL)
        self.proy = git_trabajo.proyecto(self.base, "abc123")
        ej2 = EjecutorFalso(existe=True, en_marcha=True)
        r2 = contenedores.asegurar(self.base, self.proy, ejecutar=ej2,
                                   limites_dict=limites_ejemplo(),
                                   cual=CUAL)
        self.assertEqual(r2["estado"], "listo")
        self.assertTrue(r2["reutilizado"])
        self.assertEqual(ej2.de("create"), [])

    def test_recreacion_pospuesta_con_tareas_dentro(self):
        ej = EjecutorFalso()
        contenedores.asegurar(self.base, self.proy, ejecutar=ej,
                              limites_dict=limites_ejemplo(), cual=CUAL)
        self.proy = git_trabajo.proyecto(self.base, "abc123")
        self.proy["contenedor_imagen"] = "otra:2"
        ej2 = EjecutorFalso(existe=True, en_marcha=True)
        r = contenedores.asegurar(self.base, self.proy, ejecutar=ej2,
                                  limites_dict=limites_ejemplo(),
                                  en_curso=lambda: 1, cual=CUAL)
        self.assertEqual(r["estado"], "listo")
        self.assertTrue(r["recreacion_pospuesta"])
        self.assertEqual(ej2.de("rm"), [])
        self.assertEqual(ej2.de("create"), [])

    def test_token_en_remoto_bloquea_la_creacion(self):
        (self.repo / ".git" / "config").write_text(
            '[remote "origin"]\n\turl = '
            "https://token@github.com/x/y.git\n", encoding="utf-8")
        ej = EjecutorFalso()
        r = contenedores.asegurar(self.base, self.proy, ejecutar=ej,
                                  cual=CUAL)
        self.assertEqual(r["estado"], "degradado")
        self.assertIn("credenciales embebidas", r["motivo"])
        self.assertEqual(ej.de("create"), [])

    def test_sin_imagen_no_se_inventa(self):
        ej = EjecutorFalso()
        r = contenedores.asegurar(
            self.base, proyecto(repo=str(self.repo),
                                contenedor_imagen=None),
            ejecutar=ej, cual=CUAL)
        self.assertEqual(r["estado"], "degradado")
        self.assertIn("no declara imagen", r["motivo"])

    def test_destruir(self):
        ej = EjecutorFalso(existe=True, en_marcha=True)
        r = contenedores.destruir(self.base, self.proy, ejecutar=ej,
                                  cual=CUAL)
        self.assertEqual(r["nombre"], "growi-abc123")
        rm = ej.de("rm")
        self.assertEqual(len(rm), 1)
        self.assertIn("-f", rm[0])


if __name__ == "__main__":
    unittest.main()

"""Pruebas de la Fase 6: raiz.py (registro cerrado, dominios, huella,
ritmo, detección de vía, ejecución con lanzador falso, reglas)."""

import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import raiz


def cargar_ayudante():
    spec = importlib.util.spec_from_file_location(
        "growi_ayudante", str(Path(__file__).parent / "growi-ayudante.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONFIG = {"unidades": {"juego.service": {"nivel": None},
                       "critica.service": {"nivel": "R3"}},
          "degradada": False}


class TestValidacion(unittest.TestCase):
    def test_argv_exacto_servicio(self):
        v = raiz.validar_peticion("servicio-reiniciar",
                                  {"unidad": "juego.service"}, CONFIG)
        self.assertEqual(v["argv"], ["/usr/bin/systemctl", "restart",
                                     "juego.service"])
        self.assertEqual(v["nivel"], "R2")
        self.assertIn("juego.service", v["descripcion"])

    def test_estado_es_r1(self):
        v = raiz.validar_peticion("servicio-estado",
                                  {"unidad": "juego.service"}, CONFIG)
        self.assertEqual(v["argv"], ["/usr/bin/systemctl", "status",
                                     "juego.service", "--no-pager"])
        self.assertEqual(v["nivel"], "R1")

    def test_unidad_critica_sube_a_r3(self):
        v = raiz.validar_peticion("servicio-reiniciar",
                                  {"unidad": "critica.service"}, CONFIG)
        self.assertEqual(v["nivel"], "R3")

    def test_unidad_fuera_de_la_lista(self):
        with self.assertRaises(raiz.ErrorRaiz):
            raiz.validar_peticion("servicio-parar",
                                  {"unidad": "otra.service"}, CONFIG)

    def test_unidades_manipuladas(self):
        malas = ["juego.service; rm -rf /", "$(reboot)", "juego service",
                 "-rf", "--force", "juego.service\nreboot", "JUEGO",
                 "juego.service ", " juego.service", "a" * 90,
                 "juego.service|cat", "juego`id`.service"]
        for mala in malas:
            cfg = {"unidades": {mala: {"nivel": None}},
                   "degradada": False}
            with self.assertRaises(raiz.ErrorRaiz, msg=mala):
                raiz.validar_peticion("servicio-arrancar",
                                      {"unidad": mala}, cfg)

    def test_paquete_valido_e_invalidos(self):
        v = raiz.validar_peticion("apt-instalar",
                                  {"paquete": "ffmpeg"}, CONFIG)
        self.assertEqual(v["argv"], ["/usr/bin/apt-get", "install",
                                     "-y", "ffmpeg"])
        for malo in ["-y", "--force-yes", "FFmpeg", "ff mpeg",
                     "ffmpeg;rm", "ffmpeg$(id)", "f", "ffmpeg_1.0"]:
            with self.assertRaises(raiz.ErrorRaiz, msg=malo):
                raiz.validar_peticion("apt-instalar",
                                      {"paquete": malo}, CONFIG)

    def test_apt_actualizar_sin_params(self):
        v = raiz.validar_peticion("apt-actualizar", {}, CONFIG)
        self.assertEqual(v["argv"], ["/usr/bin/apt-get", "update"])

    def test_accion_desconocida_y_clases_no_registradas(self):
        for accion in ["borrar-todo", "shell", "servicio",
                       "apt-actualizar;rm"]:
            with self.assertRaises(raiz.ErrorRaiz, msg=accion):
                raiz.validar_peticion(accion, {}, CONFIG)

    def test_parametros_extra_o_ausentes(self):
        with self.assertRaises(raiz.ErrorRaiz):
            raiz.validar_peticion("apt-actualizar",
                                  {"paquete": "ffmpeg"}, CONFIG)
        with self.assertRaises(raiz.ErrorRaiz):
            raiz.validar_peticion("servicio-parar", {}, CONFIG)
        with self.assertRaises(raiz.ErrorRaiz):
            raiz.validar_peticion(
                "servicio-parar",
                {"unidad": "juego.service", "extra": "x"}, CONFIG)

    def test_nivel_de_tarea(self):
        nivel, det = raiz.nivel_de(
            [{"accion": "servicio-estado",
              "params": {"unidad": "juego.service"}},
             {"accion": "apt-instalar", "params": {"paquete": "ffmpeg"}}],
            CONFIG)
        self.assertEqual(nivel, "R2")
        self.assertEqual(len(det), 2)
        nivel, motivo = raiz.nivel_de(
            [{"accion": "no-existe", "params": {}}], CONFIG)
        self.assertIsNone(nivel)
        self.assertIn("desconocida", motivo)
        nivel, _motivo = raiz.nivel_de([], CONFIG)
        self.assertIsNone(nivel)


class TestHuella(unittest.TestCase):
    def test_estable_ante_reordenacion(self):
        a = raiz.huella_params({"b": 1, "a": 2})
        b = raiz.huella_params({"a": 2, "b": 1})
        self.assertEqual(a, b)

    def test_distinta_al_cambiar_un_valor(self):
        a = raiz.huella_params({"unidad": "juego.service"})
        b = raiz.huella_params({"unidad": "otra.service"})
        self.assertNotEqual(a, b)

    def test_coincide_con_el_ayudante(self):
        ayudante = cargar_ayudante()
        for params in [{"unidad": "juego.service"}, {"paquete": "ffmpeg"},
                       {}, {"a": "ñandú"}]:
            self.assertEqual(raiz.huella_params(params),
                             ayudante.huella_params(params))


class TestConfig(unittest.TestCase):
    def test_lectura_con_degradadas(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "raiz-config.json").write_text(json.dumps(
                {"unidades": ["buena.service",
                              {"nombre": "con-nivel.service",
                               "nivel": "R3"},
                              {"nombre": "nivel-malo.service",
                               "nivel": "R9"},
                              "MALA CON ESPACIOS", 42]}),
                encoding="utf-8")
            cfg = raiz.cargar_config(td)
        self.assertIn("buena.service", cfg["unidades"])
        self.assertEqual(
            cfg["unidades"]["con-nivel.service"]["nivel"], "R3")
        self.assertIsNone(
            cfg["unidades"]["nivel-malo.service"]["nivel"])
        self.assertNotIn("MALA CON ESPACIOS", cfg["unidades"])
        self.assertTrue(cfg["degradada"])

    def test_sin_archivo_ninguna_unidad(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = raiz.cargar_config(td)
        self.assertEqual(cfg["unidades"], {})
        self.assertFalse(cfg["degradada"])


class TestRitmo(unittest.TestCase):
    def test_tope_por_cuenta_y_total(self):
        with tempfile.TemporaryDirectory() as td:
            t = [1000.0]
            reloj = lambda: t[0]
            for _ in range(raiz.MAX_POR_CUENTA_HORA):
                raiz.anotar_ejecucion(td, "principal", "apt-actualizar",
                                      reloj=reloj)
            with self.assertRaises(raiz.ErrorRaiz):
                raiz.comprobar_ritmo(td, "principal", reloj=reloj)
            # otra cuenta sí, hasta el tope global
            raiz.comprobar_ritmo(td, "segunda", reloj=reloj)
            for _ in range(raiz.MAX_TOTAL_HORA
                           - raiz.MAX_POR_CUENTA_HORA):
                raiz.anotar_ejecucion(td, "segunda", "apt-actualizar",
                                      reloj=reloj)
            with self.assertRaises(raiz.ErrorRaiz):
                raiz.comprobar_ritmo(td, "tercera", reloj=reloj)
            # pasada la hora, el ritmo se libera
            t[0] += 3601
            raiz.comprobar_ritmo(td, "principal", reloj=reloj)


class TestReglas(unittest.TestCase):
    def test_componer_ok(self):
        texto = raiz.componer_sudoers("dueno", CONFIG)
        self.assertIn("dueno ALL=(root) NOPASSWD: "
                      "/usr/local/libexec/growi-ayudante.py", texto)
        self.assertNotIn("*", texto)
        self.assertNotIn("ALL=(root) NOPASSWD: ALL", texto)

    def test_nombre_invalido_no_compone_nada(self):
        cfg = {"unidades": {"bien.service": {"nivel": None}},
               "degradada": True}
        with self.assertRaises(raiz.ErrorRaiz):
            raiz.componer_sudoers("dueno", cfg)
        with self.assertRaises(raiz.ErrorRaiz):
            raiz.componer_sudoers("dueno; rm -rf /", CONFIG)
        with self.assertRaises(raiz.ErrorRaiz):
            raiz.componer_sudoers("ALL", CONFIG)

    def test_validar_sudoers_con_visudo_falso(self):
        def bien(argv, entrada=None, timeout_s=10):
            return 0, "ok", ""

        def mal(argv, entrada=None, timeout_s=10):
            return 1, "", "error de sintaxis"
        ok, _ = raiz.validar_sudoers("texto", ejecutar=bien,
                                     cual=lambda n: "/usr/sbin/visudo")
        self.assertTrue(ok)
        ok, _ = raiz.validar_sudoers("texto", ejecutar=mal,
                                     cual=lambda n: "/usr/sbin/visudo")
        self.assertFalse(ok)
        ok, motivo = raiz.validar_sudoers("texto", cual=lambda n: None)
        self.assertIsNone(ok)
        self.assertIn("visudo no está", motivo)


class TestDeteccion(unittest.TestCase):
    def _ejecutor_sonda(self, ok=True):
        def ejecutar(argv, entrada=None, timeout_s=10):
            if argv[-1] == "sonda":
                if ok:
                    return 0, json.dumps(
                        {"ok": True, "version": "1",
                         "acciones": raiz.acciones()}), ""
                return 1, "", "sudo: sin regla"
            return 1, "", ""
        return ejecutar

    def setUp(self):
        raiz._CACHE_VIA.update({"ts": 0.0, "valor": None})

    def test_via_sudoers_verificada(self):
        with tempfile.TemporaryDirectory() as td:
            reglas = Path(td, "reglas")
            reglas.write_text("x", encoding="utf-8")
            via = raiz.detectar_via(
                td, ejecutar=self._ejecutor_sonda(True),
                ruta_sudoers=str(reglas), cual=lambda n: None)
        self.assertEqual(via["via"], "sudoers")
        self.assertTrue(via["verificada"])

    def test_regla_sin_sonda_no_es_via(self):
        with tempfile.TemporaryDirectory() as td:
            reglas = Path(td, "reglas")
            reglas.write_text("x", encoding="utf-8")
            via = raiz.detectar_via(
                td, ejecutar=self._ejecutor_sonda(False),
                ruta_sudoers=str(reglas), cual=lambda n: None)
        self.assertEqual(via["via"], "ninguna")
        self.assertIn("no respondió", via["motivo"])

    def test_pkexec_presente_sin_verificar(self):
        with tempfile.TemporaryDirectory() as td:
            via = raiz.detectar_via(
                td, ejecutar=self._ejecutor_sonda(False),
                ruta_sudoers=str(Path(td, "no-existe")),
                cual=lambda n: "/usr/bin/pkexec")
        self.assertEqual(via["via"], "pkexec")
        self.assertFalse(via["verificada"])

    def test_ninguna(self):
        with tempfile.TemporaryDirectory() as td:
            via = raiz.detectar_via(
                td, ejecutar=self._ejecutor_sonda(False),
                ruta_sudoers=str(Path(td, "no-existe")),
                cual=lambda n: None)
        self.assertEqual(via["via"], "ninguna")


class TestEjecutar(unittest.TestCase):
    def setUp(self):
        raiz._CACHE_VIA.update({"ts": 0.0, "valor": None})

    def _via_sudoers(self):
        return {"via": "sudoers", "verificada": True, "motivo": "",
                "ayudante": "/ruta/growi-ayudante.py",
                "acciones": raiz.acciones()}

    def test_ejecuta_y_parsea(self):
        llamadas = []
        asientos = []

        def ejecutar(argv, entrada=None, timeout_s=10):
            llamadas.append((argv, entrada))
            return 0, json.dumps({"ok": True, "rc": 0, "salida": "activo",
                                  "motivo": "", "duracion_s": 0.5}), ""
        with tempfile.TemporaryDirectory() as td:
            Path(td, "raiz-config.json").write_text(json.dumps(
                {"unidades": ["juego.service"]}), encoding="utf-8")
            r = raiz.ejecutar(
                td, "principal", "raiz-1", "servicio-estado",
                {"unidad": "juego.service"}, ejecutar=ejecutar,
                detectar=self._via_sudoers,
                auditar=lambda a, h, res, **kw: asientos.append(
                    (a, h, res)))
        self.assertTrue(r["ok"])
        self.assertEqual(r["salida"], "activo")
        argv, entrada = llamadas[0]
        self.assertEqual(argv[:3], ["sudo", "-n", "--"])
        self.assertEqual(argv[-1], "ejecutar")
        peticion = json.loads(entrada)
        self.assertEqual(peticion["accion"], "servicio-estado")
        self.assertEqual(peticion["huella"],
                         raiz.huella_params({"unidad": "juego.service"}))
        self.assertEqual(asientos[0][2], "ok")

    def test_sin_via_lanza_y_no_llama(self):
        def ejecutar(argv, entrada=None, timeout_s=10):
            raise AssertionError("no debía llamarse al lanzador")
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(raiz.ErrorRaiz):
                raiz.ejecutar(
                    td, "principal", "r", "apt-actualizar", {},
                    ejecutar=ejecutar,
                    detectar=lambda: {"via": "ninguna",
                                      "verificada": False,
                                      "motivo": "no instalado",
                                      "ayudante": "x", "acciones": []})

    def test_respuesta_rota_es_resultado_no_excepcion(self):
        def ejecutar(argv, entrada=None, timeout_s=10):
            return 1, "esto no es json", "sudo: fallo"
        with tempfile.TemporaryDirectory() as td:
            r = raiz.ejecutar(td, "principal", "r", "apt-actualizar",
                              {}, ejecutar=ejecutar,
                              detectar=self._via_sudoers)
        self.assertFalse(r["ok"])
        self.assertIn("no respondió", r["motivo"])

    def test_orden_se_crea_y_vence(self):
        with tempfile.TemporaryDirectory() as td:
            t = [5000.0]
            ruta = raiz.crear_orden(td, "principal", "apt-actualizar",
                                    "abcd", "apr-1", reloj=lambda: t[0])
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        self.assertEqual(datos["cuenta"], "principal")
        self.assertEqual(datos["vence_ts"] - datos["ts"],
                         raiz.VENTANA_ORDEN_S)


if __name__ == "__main__":
    unittest.main()

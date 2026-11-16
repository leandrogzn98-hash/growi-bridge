"""Pruebas de la Fase 6: growi-ayudante.py con ejecutor falso.

El ayudante no importa nada del proyecto: se carga desde su archivo
y se prueba su corazón (procesar_peticion) con base temporal,
entorno falso y reloj falso."""

import importlib.util
import json
import sys
import tempfile
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


ayudante = cargar_ayudante()
ENV = {"SUDO_UID": "1000"}


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.base = Path(self.td.name)
        (self.base / "raiz-config.json").write_text(json.dumps(
            {"unidades": ["juego.service"]}), encoding="utf-8")
        self.t = [10000.0]
        self.reloj = lambda: self.t[0]
        self.llamadas = []

    def tearDown(self):
        self.td.cleanup()

    def ejecutor_ok(self, argv, timeout_s):
        self.llamadas.append((argv, timeout_s))
        return 0, "hecho", ""

    def peticion(self, accion="servicio-reiniciar", params=None,
                 cuenta="principal", huella=None, con_orden=True):
        params = {"unidad": "juego.service"} if params is None \
            else params
        if huella is None:
            huella = ayudante.huella_params(params)
        if con_orden:
            raiz.crear_orden(self.base, cuenta, accion, huella,
                             "apr-test", reloj=self.reloj)
        return {"v": 1, "accion": accion, "params": params,
                "huella": huella, "cuenta": cuenta, "raiz": "r-1"}

    def procesar(self, peticion, env=ENV, ejecutar=None):
        return ayudante.procesar_peticion(
            peticion, self.base, env,
            ejecutar=ejecutar or self.ejecutor_ok, reloj=self.reloj)


class TestAceptaYRechaza(Base):
    def test_valida_ejecuta_argv_exacto(self):
        r = self.procesar(self.peticion())
        self.assertTrue(r["ok"], r)
        argv, timeout_s = self.llamadas[0]
        self.assertEqual(argv, ["/usr/bin/systemctl", "restart",
                                "juego.service"])
        self.assertEqual(timeout_s, 180)

    def test_sin_circuito_de_elevacion_rechaza(self):
        r = self.procesar(self.peticion(), env={})
        self.assertFalse(r["ok"])
        self.assertIn("SUDO_UID", r["motivo"])
        self.assertEqual(self.llamadas, [])

    def test_sin_orden_rechaza(self):
        r = self.procesar(self.peticion(con_orden=False))
        self.assertFalse(r["ok"])
        self.assertIn("orden", r["motivo"])
        self.assertEqual(self.llamadas, [])

    def test_orden_de_otra_cuenta_rechaza(self):
        p = self.peticion()
        raiz.crear_orden(self.base, "segunda", p["accion"], p["huella"],
                         "apr-x", reloj=self.reloj)
        # la orden buena es de «principal»; se crea también la de otra
        # cuenta para la misma huella: manda el archivo (una sola) —
        # la de principal ya la creó peticion(); la sobrescribe la de
        # segunda y debe rechazar por cuenta.
        r = self.procesar(p)
        self.assertFalse(r["ok"])
        self.assertEqual(self.llamadas, [])

    def test_orden_caducada_rechaza(self):
        p = self.peticion()
        self.t[0] += ayudante.VENTANA_ORDEN_S + 1
        r = self.procesar(p)
        self.assertFalse(r["ok"])
        self.assertIn("caducó", r["motivo"])
        self.assertEqual(self.llamadas, [])

    def test_orden_de_un_solo_uso(self):
        p = self.peticion()
        r1 = self.procesar(p)
        self.assertTrue(r1["ok"])
        r2 = self.procesar(p)
        self.assertFalse(r2["ok"])
        self.assertEqual(len(self.llamadas), 1)

    def test_huella_manipulada_rechaza(self):
        p = self.peticion(huella="0" * 16, con_orden=False)
        r = self.procesar(p)
        self.assertFalse(r["ok"])
        self.assertIn("huella", r["motivo"])
        self.assertEqual(self.llamadas, [])

    def test_parametro_fuera_de_dominio_no_llega(self):
        for params in [{"unidad": "otra.service"},
                       {"unidad": "juego.service; rm -rf /"},
                       {"unidad": "$(reboot)"},
                       {"unidad": "../juego.service"}]:
            p = self.peticion(params=params, con_orden=False)
            r = self.procesar(p)
            self.assertFalse(r["ok"], params)
        p = self.peticion(accion="apt-instalar",
                          params={"paquete": "--force"}, con_orden=False)
        self.assertFalse(self.procesar(p)["ok"])
        p = self.peticion(accion="apt-instalar",
                          params={"paquete": "ffmpeg$(id)"},
                          con_orden=False)
        self.assertFalse(self.procesar(p)["ok"])
        self.assertEqual(self.llamadas, [])

    def test_accion_desconocida_rechaza(self):
        p = self.peticion(accion="shell-libre", params={},
                          con_orden=False)
        r = self.procesar(p)
        self.assertFalse(r["ok"])
        self.assertEqual(self.llamadas, [])

    def test_parametro_literal_nunca_interpretado(self):
        # Un valor con forma válida viaja como UN elemento de argv.
        p = self.peticion(accion="apt-instalar",
                          params={"paquete": "ffmpeg"})
        r = self.procesar(p)
        self.assertTrue(r["ok"])
        argv, _ = self.llamadas[0]
        self.assertEqual(argv, ["/usr/bin/apt-get", "install", "-y",
                                "ffmpeg"])

    def test_timeout_del_ejecutor(self):
        # El ejecutor real convierte el timeout en rc 124; aquí se
        # simula ese contrato:
        def rc124(argv, timeout_s):
            return 124, "", "[tiempo agotado]"
        r = self.procesar(self.peticion(), ejecutar=rc124)
        self.assertFalse(r["ok"])
        self.assertIn("tiempo", r["motivo"])

    def test_rc_distinto_de_cero_es_resultado(self):
        def falla(argv, timeout_s):
            return 3, "", "unidad enmascarada"
        r = self.procesar(self.peticion(), ejecutar=falla)
        self.assertFalse(r["ok"])
        self.assertEqual(r["rc"], 3)
        self.assertIn("unidad enmascarada", r["salida"])


class TestLogYRitmo(Base):
    def test_log_encadenado_verifica_y_detecta_manipulacion(self):
        self.procesar(self.peticion())
        self.procesar(self.peticion(accion="apt-actualizar",
                                    params={}))
        entradas = ayudante._leer_log(self.base)
        self.assertGreaterEqual(len(entradas), 2)
        self.assertTrue(ayudante.verificar_cadena(entradas))
        entradas[0]["motivo"] = "manipulado"
        self.assertFalse(ayudante.verificar_cadena(entradas))

    def test_ritmo_propio_del_ayudante(self):
        for _ in range(ayudante.MAX_POR_CUENTA_HORA):
            r = self.procesar(self.peticion(accion="apt-actualizar",
                                            params={}))
            self.assertTrue(r["ok"])
        r = self.procesar(self.peticion(accion="apt-actualizar",
                                        params={}))
        self.assertFalse(r["ok"])
        self.assertIn("ritmo", r["motivo"])

    def test_salida_truncada(self):
        def verboso(argv, timeout_s):
            return 0, "x" * (ayudante.SALIDA_MAX + 5000), ""
        r = self.procesar(self.peticion(), ejecutar=verboso)
        self.assertTrue(r["ok"])
        self.assertIn("truncada", r["salida"])
        self.assertLess(len(r["salida"]),
                        ayudante.SALIDA_MAX + 100)


class TestEspejoDelRegistro(unittest.TestCase):
    def test_mismos_ids_argv_y_timeouts_que_raiz(self):
        self.assertEqual(sorted(ayudante.REGISTRO),
                         raiz.acciones())
        casos = [("servicio-estado", {"unidad": "juego.service"}),
                 ("servicio-arrancar", {"unidad": "juego.service"}),
                 ("servicio-parar", {"unidad": "juego.service"}),
                 ("servicio-reiniciar", {"unidad": "juego.service"}),
                 ("apt-actualizar", {}),
                 ("apt-instalar", {"paquete": "ffmpeg"})]
        config = {"unidades": {"juego.service": {"nivel": None}},
                  "degradada": False}
        for accion, params in casos:
            v = raiz.validar_peticion(accion, params, config)
            argv, motivo = ayudante.validar(
                accion, params, {"juego.service"})
            self.assertIsNone(motivo, accion)
            self.assertEqual(argv, v["argv"], accion)
            self.assertEqual(ayudante.REGISTRO[accion]["timeout_s"],
                             raiz.REGISTRO[accion]["timeout_s"],
                             accion)

    def test_sonda(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ayudante.main(["growi-ayudante.py", "sonda"])
        self.assertEqual(rc, 0)
        datos = json.loads(buf.getvalue())
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["acciones"], raiz.acciones())


if __name__ == "__main__":
    unittest.main()

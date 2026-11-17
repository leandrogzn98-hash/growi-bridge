#!/usr/bin/env python3
"""Pruebas de mqtt_enlace (P1 de Growi Private MQTT) y del modo de
conexión «mqtt» en el registro de cuentas. Sin broker ni paho: el
cliente MQTT es una falsificación con la misma superficie."""
import json
import os
import unittest

import cuentas
import mqtt_enlace as m


class InfoPub:
    def __init__(self):
        self.esperado = False

    def wait_for_publish(self, timeout=None):
        self.esperado = True


class ClienteFalso:
    def __init__(self):
        self.publicados = []
        self.suscripciones = []
        self.voluntad = None
        self.conexion = None
        self.on_connect = None
        self.on_message = None
        self.on_disconnect = None

    def username_pw_set(self, u, p):
        self.credencial = (u, p)

    def tls_set(self, **kw):
        self.tls = True

    def tls_insecure_set(self, v):
        self.inseguro = v

    def ws_set_options(self, path=None):
        self.ws_path = path

    def will_set(self, tema, payload=None, qos=0, retain=False):
        self.voluntad = (tema, payload, qos, retain)

    def connect(self, host, puerto, keepalive=60):
        self.conexion = (host, puerto, keepalive)

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def subscribe(self, tema, qos=0):
        self.suscripciones.append((tema, qos))

    def publish(self, tema, payload=None, qos=0, retain=False):
        self.publicados.append((tema, payload, qos, retain))
        return InfoPub()


def enlace(recibidos, **kw):
    falso = ClienteFalso()
    e = m.EnlaceMQTT("wss://broker.ejemplo.com:443/mqtt", "prog", "secreto",
                     "growi/pc-1", lambda s, t: recibidos.append((s, t)),
                     fabrica=lambda: falso, **kw)
    return e, falso


class TestURL(unittest.TestCase):
    def test_wss_por_defecto_443(self):
        info = m.parse_broker_url("wss://broker.ejemplo.com/mqtt")
        self.assertEqual((info["puerto"], info["tls"], info["websockets"]),
                         (443, True, True))

    def test_mqtts_por_defecto_8883(self):
        info = m.parse_broker_url("mqtts://broker.ejemplo.com")
        self.assertEqual(info["puerto"], 8883)
        self.assertFalse(info["websockets"])

    def test_texto_plano_a_internet_rechazado(self):
        with self.assertRaises(m.ErrorEnlace):
            m.parse_broker_url("ws://broker.ejemplo.com:8083/mqtt")

    def test_texto_plano_local_permitido(self):
        info = m.parse_broker_url("ws://127.0.0.1:18084")
        self.assertTrue(info["es_local"])
        self.assertFalse(info["tls"])

    def test_esquema_raro_y_sin_host(self):
        with self.assertRaises(m.ErrorEnlace):
            m.parse_broker_url("http://broker.ejemplo.com")
        with self.assertRaises(m.ErrorEnlace):
            m.parse_broker_url("wss://")


class TestSobre(unittest.TestCase):
    def test_forma_y_clave(self):
        s = m.crear_sobre("tarea", "rayo", {"prompt": "hola"}, "CLAVE")
        self.assertEqual(s["v"], 1)
        self.assertEqual(s["clave"], "CLAVE")
        self.assertTrue(m.validar_sobre(s))

    def test_tope_64k(self):
        s = m.crear_sobre("resultado", "rayo", {"texto": "x" * 70000})
        with self.assertRaises(m.ErrorEnlace):
            m.serializar(s)

    def test_validar_rechaza(self):
        self.assertIsNone(m.validar_sobre({"v": 2, "id": "a",
                                           "tipo": "tarea", "cuenta": "x",
                                           "datos": {}}))
        self.assertIsNone(m.validar_sobre({"v": 1, "id": "a",
                                           "tipo": "inventado",
                                           "cuenta": "x", "datos": {}}))
        self.assertIsNone(m.validar_sobre("no dict"))

    def test_vistos_acotado(self):
        v = m.Vistos(maximo=3)
        for i in ("a", "b", "c", "d"):
            self.assertTrue(v.es_nuevo(i))
        self.assertFalse(v.es_nuevo("d"))
        self.assertTrue(v.es_nuevo("a"))  # «a» ya salió de la ventana


class TestEnlace(unittest.TestCase):
    def test_no_verificar_solo_local(self):
        with self.assertRaises(m.ErrorEnlace):
            enlace([], tls_verificar=False)

    def test_conectar_deja_lwt_y_presencia(self):
        recibidos = []
        e, falso = enlace(recibidos)
        e.conectar()
        self.assertEqual(falso.conexion[0], "broker.ejemplo.com")
        tema_lwt, _carga, _qos, retain = falso.voluntad
        self.assertEqual(tema_lwt, "growi/pc-1/programa/presencia")
        self.assertTrue(retain)
        falso.on_connect(falso, None, None, 0)
        temas = [t for t, _q in falso.suscripciones]
        self.assertEqual(temas, ["growi/pc-1/+/resultados",
                                 "growi/pc-1/+/avisos",
                                 "growi/pc-1/+/presencia"])
        self.assertTrue(e.estado()["conectado"])
        pres = [p for p in falso.publicados
                if p[0] == "growi/pc-1/programa/presencia"]
        self.assertTrue(pres and pres[0][3])  # retenida

    def test_publicar_tarea_con_clave_dentro(self):
        recibidos = []
        e, falso = enlace(recibidos)
        e.conectar()
        mid = e.publicar_tarea("rayo", {"prompt": "haz X"}, "CLAVE-RAYO")
        tema_t, carga, qos, _r = falso.publicados[-1]
        self.assertEqual(tema_t, "growi/pc-1/rayo/tareas")
        sobre = json.loads(carga.decode("utf-8"))
        self.assertEqual((sobre["id"], sobre["tipo"], sobre["clave"]),
                         (mid, "tarea", "CLAVE-RAYO"))
        self.assertEqual(qos, 1)

    def test_recepcion_idempotente_y_presencia(self):
        recibidos = []
        e, falso = enlace(recibidos)
        e.conectar()

        class Msg:
            pass
        sobre = m.crear_sobre("resultado", "rayo", {"ok": True}, "CLAVE")
        msg = Msg()
        msg.topic = "growi/pc-1/rayo/resultados"
        msg.payload = json.dumps(sobre).encode("utf-8")
        falso.on_message(falso, None, msg)
        falso.on_message(falso, None, msg)  # duplicado QoS 1
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0]["cuenta"], "rayo")
        msg.payload = b"{roto"
        falso.on_message(falso, None, msg)
        self.assertEqual(len(recibidos), 1)
        pres = m.crear_sobre("presencia", "rayo", {"estado": "en_linea",
                                                   "ts": 5})
        msg.payload = json.dumps(pres).encode("utf-8")
        msg.topic = "growi/pc-1/rayo/presencia"
        falso.on_message(falso, None, msg)
        self.assertEqual(e.presencia_cuentas["rayo"]["estado"], "en_linea")


class TestCuentaMQTT(unittest.TestCase):
    def test_conexion_mqtt_valida(self):
        reg = cuentas.registro_compatibilidad()
        reg["cuentas"][0]["conexion"] = "mqtt"
        self.assertEqual(cuentas.validar(reg), [])

    def test_conexion_inventada_no_valida(self):
        reg = cuentas.registro_compatibilidad()
        reg["cuentas"][0]["conexion"] = "paloma-mensajera"
        errores = cuentas.validar(reg)
        self.assertTrue(any("conexion" in e for e in errores), errores)


if __name__ == "__main__":
    unittest.main()

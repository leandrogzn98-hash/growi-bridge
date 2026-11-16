# -*- coding: utf-8 -*-
"""Pruebas de la Fase 5: el adaptador de Telegram (canal_telegram.py)
contra un servidor HTTP falso local con la forma real de la Bot API.

Sin tocar la API real: getMe, getUpdates (long polling) y sendMessage
se sirven desde 127.0.0.1. Se verifica la normalización (solo chats
privados, I1; ids siempre str, I3), el avance del offset, el envío al
chat emparejado y solo a él, y que el token canario no aparece en
ningún error (I15/I16).
"""

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import canal_telegram
import canales

TOKEN = "123456789:AAHcanaryTOKENfalsoDePruebas123456"
CHAT = "424242"


def upd(uid, texto="hola", chat_id=424242, tipo="private", mid=None,
        cita=None, fecha=1_760_000_100):
    msg = {"message_id": mid if mid is not None else uid,
           "date": fecha,
           "chat": {"id": chat_id, "type": tipo},
           "from": {"id": chat_id}}
    if texto is not None:
        msg["text"] = texto
    if cita is not None:
        msg["reply_to_message"] = {"message_id": cita}
    return {"update_id": uid, "message": msg}


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _resp(self, code, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        srv = self.server
        largo = int(self.headers.get("Content-Length") or 0)
        crudo = self.rfile.read(largo) if largo else b"{}"
        try:
            body = json.loads(crudo or b"{}")
        except ValueError:
            body = {}
        partes = self.path.strip("/").split("/")
        metodo = partes[-1] if partes else ""
        token = partes[-2][3:] if len(partes) >= 2 \
            and partes[-2].startswith("bot") else ""
        srv.peticiones.append((metodo, body))
        if token != srv.token_bueno:
            self._resp(401, {"ok": False,
                             "description": "Unauthorized"})
            return
        if metodo == "getMe":
            self._resp(200, {"ok": True, "result": {
                "id": srv.bot_id, "username": "growi_bot",
                "first_name": "Growi"}})
        elif metodo == "getUpdates":
            srv.offsets.append(body.get("offset"))
            ups = srv.updates
            srv.updates = []
            self._resp(200, {"ok": True, "result": ups})
        elif metodo == "sendMessage":
            srv.enviados.append(body)
            self._resp(200, {"ok": True, "result": {
                "message_id": 900 + len(srv.enviados),
                "chat": {"id": body.get("chat_id")}}})
        else:
            self._resp(404, {"ok": False,
                             "description": "Not Found"})


class TestTelegram(unittest.TestCase):
    def setUp(self):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.srv.token_bueno = TOKEN
        self.srv.bot_id = 777001
        self.srv.updates = []
        self.srv.enviados = []
        self.srv.offsets = []
        self.srv.peticiones = []
        self.hilo = threading.Thread(target=self.srv.serve_forever,
                                     daemon=True)
        self.hilo.start()
        puerto = self.srv.server_address[1]
        self.base_url = f"http://127.0.0.1:{puerto}"
        self.secreto = TOKEN
        self.ad = canal_telegram.AdaptadorTelegram(
            lambda nombre: self.secreto, lambda: CHAT,
            base_url=self.base_url)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    # -- identidad del bot y disponibilidad ------------------------------

    def test_bot_info_y_disponible(self):
        info = self.ad.bot_info()
        self.assertEqual(info["id"], "777001")
        self.assertEqual(info["username"], "growi_bot")
        self.assertTrue(self.ad.disponible())

    def test_token_rechazado_no_disponible_y_sin_bucle(self):
        self.secreto = "999999999:AAHtokenmalotokenmalotokenmalo12"
        self.assertFalse(self.ad.disponible())
        self.assertEqual(self.ad.estado(),
                         "token rechazado por Telegram")

    def test_sin_token_no_disponible(self):
        self.secreto = None
        self.assertFalse(self.ad.disponible())
        self.assertEqual(self.ad.estado(), "sin token")

    # -- recepción --------------------------------------------------------

    def test_recibir_normaliza_privado(self):
        self.srv.updates = [upd(41, "revisa el informe", mid=7,
                                cita=6)]
        mensajes, cursor = self.ad.recibir({"offset": 41})
        self.assertEqual(self.srv.offsets, [41])
        self.assertEqual(cursor["offset"], 42)
        self.assertEqual(len(mensajes), 1)
        m = mensajes[0]
        self.assertEqual(m["transporte"], "telegram")
        self.assertEqual(m["id_mensaje"], "41")       # str siempre (I3)
        self.assertIsInstance(m["id_mensaje"], str)
        self.assertEqual(m["remitente"], "424242")    # str siempre
        self.assertEqual(m["texto"], "revisa el informe")
        self.assertEqual(m["cita_id"], "6")
        self.assertEqual(m["ts_transporte"], 1_760_000_100)
        self.assertEqual(m["_offset_siguiente"], 42)

    def test_grupo_se_descarta_entero_pero_el_offset_avanza(self):
        self.srv.updates = [
            upd(50, "hola grupo", chat_id=-100123, tipo="group"),
            upd(51, "hola privado"),
        ]
        mensajes, cursor = self.ad.recibir({})
        self.assertEqual([m["id_mensaje"] for m in mensajes], ["51"])
        self.assertEqual(cursor["offset"], 52)

    def test_mensaje_sin_texto_llega_como_none(self):
        self.srv.updates = [upd(60, None)]  # una foto, p. ej.
        mensajes, _ = self.ad.recibir({})
        self.assertEqual(len(mensajes), 1)
        self.assertIsNone(mensajes[0]["texto"])

    def test_sin_offset_no_se_envia_offset(self):
        self.srv.updates = []
        mensajes, cursor = self.ad.recibir({})
        self.assertEqual(mensajes, [])
        self.assertEqual(self.srv.offsets, [None])
        self.assertNotIn("offset", cursor)

    def test_long_poll_acotado(self):
        self.srv.updates = []
        self.ad.recibir({})
        metodo, body = self.srv.peticiones[-1]
        self.assertEqual(metodo, "getUpdates")
        self.assertLessEqual(body["timeout"],
                             canal_telegram.POLL_S)
        self.assertEqual(body["allowed_updates"], ["message"])

    # -- envío --------------------------------------------------------------

    def test_transmitir_al_chat_emparejado_texto_plano(self):
        r = self.ad.transmitir("Encargo recibido ✓")
        self.assertEqual(r["mensaje_id"], "901")
        self.assertEqual(len(self.srv.enviados), 1)
        body = self.srv.enviados[0]
        self.assertEqual(str(body["chat_id"]), CHAT)
        self.assertEqual(body["text"], "Encargo recibido ✓")
        self.assertNotIn("parse_mode", body)

    def test_transmitir_sin_destino_falla(self):
        ad = canal_telegram.AdaptadorTelegram(
            lambda nombre: TOKEN, lambda: None,
            base_url=self.base_url)
        with self.assertRaises(canal_telegram.ErrorTelegram):
            ad.transmitir("hola")
        self.assertEqual(self.srv.enviados, [])

    # -- el token no sale jamás ----------------------------------------------

    def test_el_token_no_aparece_en_los_errores(self):
        def http_roto(url, datos, timeout):
            raise urllib.error.URLError(f"sin salida hacia {url}")

        ad = canal_telegram.AdaptadorTelegram(
            lambda nombre: TOKEN, lambda: CHAT,
            base_url=self.base_url, http=http_roto)
        with self.assertRaises(canal_telegram.ErrorTelegram) as cm:
            ad.bot_info()
        self.assertNotIn(TOKEN, str(cm.exception))
        self.assertNotIn(TOKEN, canales.resumen_error(cm.exception))
        self.assertNotIn("canary", canales.resumen_error(cm.exception))

    def test_error_http_no_filtra_el_token(self):
        self.secreto = "111111111:AAHcanaryTOKENfalsoDePruebas123456"
        with self.assertRaises(canal_telegram.ErrorTelegram) as cm:
            self.ad.transmitir("hola")
        self.assertNotIn("canary", str(cm.exception))
        self.assertEqual(cm.exception.http_code, 401)


class TestCambioDeBot(unittest.TestCase):
    """I3 a nivel de capa común: invalidar el emparejamiento."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="f5-bot-")
        self.base = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_invalidar_por_cambio_bot(self):
        codigo = canales.generar_codigo(self.base, "telegram")
        r = canales.intentar_emparejar(self.base, "telegram", CHAT,
                                       codigo)
        self.assertEqual(r["resultado"], "emparejado")
        canales.invalidar_por_cambio_bot(self.base, "telegram")
        cfg = canales.cargar_config(self.base)
        self.assertIsNone(canales.identidad_de(cfg, "telegram"))
        eventos = [e.get("evento")
                   for e in canales.leer_registro(self.base, 50)]
        self.assertIn("bot_cambiado", eventos)


if __name__ == "__main__":
    unittest.main()

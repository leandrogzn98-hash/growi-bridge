# -*- coding: utf-8 -*-
"""Adaptador de Telegram (Fase 5): el transporte real del canal.

Habla con la Bot API por HTTPS con long polling acotado (20 s, B3).
El token se pide a la bóveda EN EL MOMENTO de cada llamada (nunca se
guarda en el objeto ni en el adaptador): rotarlo en la app surte
efecto en el ciclo siguiente, sin reiniciar. Ningún error que salga
de aquí lleva la URL ni el texto crudo de la excepción: la URL de la
Bot API CONTIENE el token, así que todo error es solo «tipo + código
HTTP» y pasa por canales.resumen_error (I15/I16).

La base de la API es inyectable (``base_url``) y el transporte HTTP
también (``http``): las pruebas corren contra un servidor falso local
con la misma forma de respuestas, sin tocar la API real.

Contrato con la capa común (canales.py):
- recibir(cursor) -> (mensajes, cursor'): mensajes normalizados
  {transporte, id_mensaje (str, I3), remitente, texto|None,
  cita_id|None, ts_transporte} y el cursor nuevo SOLO avanza con lo
  devuelto; el llamador persiste el offset mensaje a mensaje tras
  procesar (cada mensaje lleva su «_offset_siguiente»).
- transmitir(texto, meta) -> {"mensaje_id": str}: envía al chat
  emparejado y a ningún otro sitio: el destino se lee en el momento
  (leer_destino) y no es un parámetro libre (principio 6).
- Solo chats privados: un grupo jamás empareja ni crea tareas (I1);
  sus updates se descartan enteros en la normalización.
"""

import json
import time
import urllib.error
import urllib.request

import canales

NOMBRE = "telegram"
BASE_URL_DEF = "https://api.telegram.org"
POLL_S = 20          # long polling acotado (B3): ningún paso sin cota
TIMEOUT_HTTP_S = 30  # > POLL_S: el poll largo no debe cortarse antes


class ErrorTelegram(canales.ErrorCanal):
    """Error del adaptador, ya saneado: tipo y código, nunca la URL.
    Hereda de canales.ErrorCanal para que resumen_error conserve su
    texto (ya saneado al construirse) en los logs del monolito."""

    def __init__(self, texto, http_code=None):
        super().__init__(texto)
        self.http_code = http_code


def _http_urllib(url, datos, timeout):
    """Transporte por defecto (urllib de la stdlib): POST JSON.
    Devuelve (status, cuerpo_dict). Las excepciones suben tal cual: el
    llamador las sanea antes de que toquen un log."""
    cuerpo = json.dumps(datos).encode("utf-8") if datos is not None \
        else None
    req = urllib.request.Request(
        url, data=cuerpo, method="POST" if cuerpo is not None else "GET",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(
                resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, {}


class AdaptadorTelegram:
    nombre = NOMBRE

    def __init__(self, leer_secreto, leer_destino, base_url=BASE_URL_DEF,
                 reloj=None, http=None):
        """leer_secreto(nombre) -> str|None: la bóveda, en el momento.
        leer_destino() -> str|None: la identidad emparejada vigente."""
        self._leer_secreto = leer_secreto
        self._leer_destino = leer_destino
        self.base_url = (base_url or BASE_URL_DEF).rstrip("/")
        self._reloj = reloj or time.time
        self._http = http or _http_urllib
        self._estado = "sin configurar"
        self._bot = None

    # -- la llamada cruda -------------------------------------------------

    def _llamar(self, metodo, params=None, timeout=TIMEOUT_HTTP_S):
        token = self._leer_secreto("canal:telegram")
        if not token:
            self._estado = "sin token"
            raise ErrorTelegram("sin token en la bóveda")
        url = f"{self.base_url}/bot{token}/{metodo}"
        try:
            status, cuerpo = self._http(url, params or {}, timeout)
        except ErrorTelegram:
            raise
        except Exception as e:
            self._estado = "error de red"
            raise ErrorTelegram(
                canales.resumen_error(e, secretos_conocidos=(token,)))
        if status == 401 or status == 404:
            self._estado = "token rechazado por Telegram"
            raise ErrorTelegram("token rechazado por Telegram",
                                http_code=status)
        if status != 200 or not isinstance(cuerpo, dict) \
                or not cuerpo.get("ok"):
            desc = ""
            if isinstance(cuerpo, dict):
                desc = str(cuerpo.get("description") or "")[:80]
            self._estado = f"error de Telegram ({status})"
            raise ErrorTelegram(
                canales.resumen_error(
                    f"Telegram respondió {status} {desc}",
                    secretos_conocidos=(token,)), http_code=status)
        return cuerpo.get("result")

    # -- contrato ----------------------------------------------------------

    def estado(self):
        """Texto corto y seguro para la UI y los logs."""
        return self._estado

    def bot_info(self):
        """getMe: {id (str), username} del bot del token vigente."""
        r = self._llamar("getMe")
        if not isinstance(r, dict) or r.get("id") is None:
            raise ErrorTelegram("getMe sin id")
        self._bot = {"id": str(r["id"]),
                     "username": r.get("username")}
        self._estado = "conectado"
        return dict(self._bot)

    def disponible(self):
        """¿Se puede hablar con Telegram ahora? Token presente y getMe
        correcto. Un token inválido NO entra en bucle de reintentos: se
        dice una vez («token rechazado por Telegram») y disponible()
        devuelve False hasta que el token cambie."""
        try:
            self.bot_info()
            return True
        except ErrorTelegram:
            return False

    def recibir(self, cursor):
        """Un long poll. El cursor es {"offset": int}: se pide desde
        ahí y cada mensaje devuelto trae «_offset_siguiente» para que
        el llamador persista el avance mensaje a mensaje, solo tras
        procesarlo y anotarlo (principio 5)."""
        cursor = dict(cursor or {})
        offset = cursor.get("offset")
        params = {"timeout": POLL_S, "allowed_updates": ["message"]}
        if isinstance(offset, int):
            params["offset"] = offset
        updates = self._llamar("getUpdates", params,
                               timeout=TIMEOUT_HTTP_S + POLL_S)
        mensajes = []
        nuevo = offset
        for u in updates or []:
            if not isinstance(u, dict):
                continue
            uid = u.get("update_id")
            if not isinstance(uid, int):
                continue
            nuevo = uid + 1
            msg = u.get("message")
            if not isinstance(msg, dict):
                continue  # edited_message, callback...: no es un mensaje
            chat = msg.get("chat") or {}
            if chat.get("type") != "private":
                continue  # grupos: jamás (I1), se descartan enteros
            if chat.get("id") is None or msg.get("message_id") is None:
                continue
            cita = None
            rt = msg.get("reply_to_message")
            if isinstance(rt, dict) and rt.get("message_id") is not None:
                cita = str(rt["message_id"])
            mensajes.append({
                "transporte": NOMBRE,
                "id_mensaje": str(uid),
                "remitente": str(chat["id"]),
                "texto": msg.get("text") if isinstance(
                    msg.get("text"), str) else None,
                "cita_id": cita,
                "ts_transporte": msg.get("date"),
                "_offset_siguiente": uid + 1,
            })
        if nuevo is not None:
            cursor["offset"] = nuevo
        return mensajes, cursor

    def transmitir(self, texto, meta=None):
        """sendMessage al chat emparejado, texto plano (sin
        parse_mode: ningún Markdown del contenido puede romper el
        formato ni inyectar enlaces)."""
        destino = self._leer_destino()
        if not destino:
            raise ErrorTelegram("sin chat emparejado")
        r = self._llamar("sendMessage",
                         {"chat_id": destino, "text": str(texto)})
        if not isinstance(r, dict) or r.get("message_id") is None:
            raise ErrorTelegram("sendMessage sin message_id")
        return {"mensaje_id": str(r["message_id"])}

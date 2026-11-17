#!/usr/bin/env python3
"""mqtt_enlace.py — Enlace MQTT de Growi Private MQTT (P1).

El transporte de la bifurcación: el programa se conecta a un broker
MQTT (siempre con TLS) y por ahí habla con las cuentas Muse, que se
conectan al mismo broker desde sus espacios. El broker es transporte,
no autoridad: la clave Growi de cada cuenta viaja DENTRO de la carga
y autentica de extremo a extremo, como con el puente HTTP.

Temas (raíz configurable, por defecto «growi/<id-pc>»):

    <raiz>/<cuenta>/tareas      programa -> Muse (órdenes, texto)
    <raiz>/<cuenta>/resultados  Muse -> programa (entregas, texto)
    <raiz>/<cuenta>/avisos      Muse -> programa (avisos, texto)
    <raiz>/<cuenta>/presencia   retenido + LWT de cada cuenta
    <raiz>/programa/presencia   retenido + LWT del programa
    <raiz>/programa/tablero     retenido: última foto del tablero

Reglas (diseño MQTT §5–§7):
- QoS 1 con sesión persistente; idempotencia por `id` de sobre: el
  receptor descarta duplicados (QoS 1 puede entregar dos veces).
- Tope de 64 KB por mensaje, sin trocear: lo que no cabe no viaja
  por MQTT (va por GitHub, como siempre).
- TLS obligatorio. Solo se permite texto plano o «no verificar el
  certificado» cuando el host es local (127.0.0.1/localhost): es el
  caso del túnel CONNECT local que usan los espacios Muse, donde el
  TLS sigue siendo extremo a extremo con el broker pero el nombre
  del certificado no coincide con el extremo local.
- Sin paho-mqtt instalado, el módulo carga igual y `EnlaceMQTT`
  falla al conectar con un motivo claro (la app no se cae).
"""

import json
import os
import time
import uuid
from urllib.parse import urlparse

TOPE_MENSAJE = 64 * 1024
TIPOS = ("tarea", "resultado", "aviso", "presencia", "tablero")
_VISTOS_MAX = 2000


class ErrorEnlace(Exception):
    """Fallo del enlace con motivo listo para mostrar/loguear."""


def parse_broker_url(url):
    """«wss://host:puerto/ruta» -> dict. Lanza ErrorEnlace si no vale.

    Acepta wss/mqtts (TLS) y, solo para host local, ws/mqtt (el túnel
    local de los espacios Muse; ver la cabecera del módulo).
    """
    if not isinstance(url, str) or not url.strip():
        raise ErrorEnlace("broker sin dirección")
    p = urlparse(url.strip())
    esquema = (p.scheme or "").lower()
    if esquema not in ("wss", "mqtts", "ws", "mqtt"):
        raise ErrorEnlace(f"esquema de broker no soportado: {esquema or '—'}")
    host = p.hostname or ""
    if not host:
        raise ErrorEnlace("broker sin host")
    es_local = host in ("127.0.0.1", "localhost", "::1")
    tls = esquema in ("wss", "mqtts")
    if not tls and not es_local:
        raise ErrorEnlace("broker sin TLS: solo se permite texto plano "
                          "hacia un host local (túnel)")
    puerto = p.port or (443 if esquema == "wss" else 8883 if esquema == "mqtts"
                        else 8083 if esquema == "ws" else 1883)
    return {"esquema": esquema, "host": host, "puerto": puerto,
            "ruta": p.path or "", "tls": tls, "es_local": es_local,
            "websockets": esquema in ("wss", "ws")}


def tema(raiz, *partes):
    return "/".join([raiz.strip("/")] + [str(x).strip("/") for x in partes])


def crear_sobre(tipo, cuenta, datos, clave_growi=None, sobre_id=None):
    """Sobre v1. `clave_growi` autentica dentro de la carga (o None)."""
    if tipo not in TIPOS:
        raise ErrorEnlace(f"tipo de mensaje desconocido: {tipo}")
    sobre = {"v": 1, "id": sobre_id or uuid.uuid4().hex,
             "tipo": tipo, "ts": int(time.time()), "cuenta": cuenta,
             "datos": datos}
    if clave_growi:
        sobre["clave"] = clave_growi
    return sobre


def serializar(sobre):
    crudo = json.dumps(sobre, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
    if len(crudo) > TOPE_MENSAJE:
        raise ErrorEnlace(
            f"mensaje de {len(crudo)} bytes supera el tope de "
            f"{TOPE_MENSAJE}: por MQTT solo viaja texto corto; "
            "lo grande va por GitHub")
    return crudo


def validar_sobre(obj):
    """Forma mínima del sobre; devuelve el dict o None (descartar)."""
    if not isinstance(obj, dict) or obj.get("v") != 1:
        return None
    if not isinstance(obj.get("id"), str) or not obj["id"]:
        return None
    if obj.get("tipo") not in TIPOS:
        return None
    if not isinstance(obj.get("cuenta"), str) or not obj["cuenta"]:
        return None
    if "datos" not in obj:
        return None
    return obj


class Vistos:
    """Idempotencia: ids ya procesados (memoria acotada)."""

    def __init__(self, maximo=_VISTOS_MAX):
        self._orden = []
        self._set = set()
        self._max = maximo

    def es_nuevo(self, mid):
        if mid in self._set:
            return False
        self._set.add(mid)
        self._orden.append(mid)
        while len(self._orden) > self._max:
            self._set.discard(self._orden.pop(0))
        return True


class EnlaceMQTT:
    """Cliente MQTT del programa. `al_recibir(sobre, tema)` es la
    puerta de entrada: el llamador verifica la clave Growi de cada
    sobre (el módulo transporta; la autoridad es de la app)."""

    def __init__(self, broker_url, usuario, contrasena, raiz,
                 al_recibir, cliente_id=None, tls_verificar=True,
                 fabrica=None, reloj=time.time):
        info = parse_broker_url(broker_url)
        if not tls_verificar and not info["es_local"]:
            raise ErrorEnlace("no verificar el certificado solo se "
                              "permite con un broker local (túnel)")
        if not raiz or not raiz.strip("/"):
            raise ErrorEnlace("raíz de temas vacía")
        self.info = info
        self.usuario = usuario or ""
        self._contrasena = contrasena or ""
        self.raiz = raiz.strip("/")
        self.al_recibir = al_recibir
        self.cliente_id = cliente_id or f"growi-programa-{uuid.uuid4().hex[:8]}"
        self.tls_verificar = tls_verificar
        self._fabrica = fabrica
        self._reloj = reloj
        self._cliente = None
        self._conectado = False
        self._desde = None
        self._vistos = Vistos()
        self.presencia_cuentas = {}

    # -- construcción del cliente ------------------------------------
    def _crear_cliente(self):
        if self._fabrica is not None:
            return self._fabrica()
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise ErrorEnlace("falta la librería paho-mqtt: el enlace "
                              "MQTT no puede arrancar sin ella")
        kwargs = {"client_id": self.cliente_id, "clean_session": False,
                  "protocol": mqtt.MQTTv311}
        if self.info["websockets"]:
            kwargs["transport"] = "websockets"
        cliente = mqtt.Client(**kwargs)
        if self.info["websockets"] and self.info["ruta"]:
            cliente.ws_set_options(path=self.info["ruta"])
        if self.usuario:
            cliente.username_pw_set(self.usuario, self._contrasena)
        if self.info["tls"]:
            cliente.tls_set()
            if not self.tls_verificar:
                cliente.tls_insecure_set(True)
        return cliente

    # -- ciclo de vida ------------------------------------------------
    def conectar(self):
        cliente = self._crear_cliente()
        self._cliente = cliente
        lwt = serializar(crear_sobre(
            "presencia", "programa",
            {"estado": "sin_conexion", "ts": int(self._reloj())}))
        cliente.will_set(tema(self.raiz, "programa", "presencia"),
                         payload=lwt, qos=1, retain=True)
        cliente.on_connect = self._al_conectar
        cliente.on_message = self._al_mensaje
        cliente.on_disconnect = self._al_desconectar
        cliente.connect(self.info["host"], self.info["puerto"],
                        keepalive=60)
        cliente.loop_start()
        return self

    def cerrar(self):
        if self._cliente is not None:
            try:
                self.publicar_presencia_programa("sin_conexion")
                self._cliente.loop_stop()
                self._cliente.disconnect()
            except Exception:
                pass
            self._cliente = None
            self._conectado = False

    def estado(self):
        return {"conectado": self._conectado, "desde": self._desde,
                "broker": f"{self.info['esquema']}://{self.info['host']}:"
                          f"{self.info['puerto']}",
                "raiz": self.raiz,
                "presencia_cuentas": dict(self.presencia_cuentas)}

    # -- publicación --------------------------------------------------
    def _publicar(self, destino, sobre, retain=False):
        if self._cliente is None:
            raise ErrorEnlace("enlace no conectado")
        crudo = serializar(sobre)
        info = self._cliente.publish(destino, payload=crudo, qos=1,
                                     retain=retain)
        if info is not None and hasattr(info, "wait_for_publish"):
            info.wait_for_publish(timeout=10)
        return sobre["id"]

    def publicar_tarea(self, cuenta, datos, clave_growi):
        sobre = crear_sobre("tarea", cuenta, datos, clave_growi)
        return self._publicar(tema(self.raiz, cuenta, "tareas"), sobre)

    def publicar_presencia_programa(self, estado="en_linea"):
        sobre = crear_sobre("presencia", "programa",
                            {"estado": estado, "ts": int(self._reloj())})
        return self._publicar(tema(self.raiz, "programa", "presencia"),
                              sobre, retain=True)

    def publicar_tablero(self, foto):
        sobre = crear_sobre("tablero", "programa", foto)
        return self._publicar(tema(self.raiz, "programa", "tablero"),
                              sobre, retain=True)

    # -- recepción ----------------------------------------------------
    def _al_conectar(self, cliente, _ud, _flags, rc):
        if rc != 0:
            self._conectado = False
            return
        self._conectado = True
        self._desde = int(self._reloj())
        for sufijo in ("resultados", "avisos", "presencia"):
            cliente.subscribe(tema(self.raiz, "+", sufijo), qos=1)
        try:
            self.publicar_presencia_programa("en_linea")
        except Exception:
            pass

    def _al_desconectar(self, _cliente, _ud, _rc):
        self._conectado = False

    def _al_mensaje(self, _cliente, _ud, msg):
        try:
            obj = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        sobre = validar_sobre(obj)
        if sobre is None or not self._vistos.es_nuevo(sobre["id"]):
            return
        if sobre["tipo"] == "presencia":
            datos = sobre.get("datos") or {}
            self.presencia_cuentas[sobre["cuenta"]] = {
                "estado": datos.get("estado"), "ts": datos.get("ts")}
        try:
            self.al_recibir(sobre, msg.topic)
        except Exception:
            pass  # el transporte no se cae por un consumidor roto

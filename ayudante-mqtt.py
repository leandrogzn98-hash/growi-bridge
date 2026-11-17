#!/usr/bin/env python3
"""ayudante-mqtt.py — El lado Muse de Growi Private MQTT (P1).

Lo corre cada Muse en su propio espacio. Se conecta al broker,
recibe las tareas del programa como archivos y publica los
resultados que la Muse deje como archivos. Sin dependencias del
proyecto: solo necesita Python y paho-mqtt.

Configuración (un solo archivo JSON, el «paquete» que el dueño le
pasa a cada Muse junto con su clave):

    {
      "broker": "wss://<broker>:443/mqtt",
      "usuario": "<usuario del broker de esta cuenta>",
      "contrasena": "<contraseña del broker de esta cuenta>",
      "raiz": "growi/<id-pc>",
      "cuenta": "<id de su cuenta en Growi>",
      "clave_growi": "<su clave de conexión Growi>",
      "carpeta": "./mqtt-ayudante"
    }

Uso:  python3 ayudante-mqtt.py <config.json>

Carpetas de trabajo (dentro de «carpeta»):
- `entrada/`: cada tarea del programa llega como `<id>.json`
  (sobre completo; el campo `datos` es el encargo). La Muse la lee
  y trabaja; la autenticidad ya viene verificada: sin la clave
  Growi correcta dentro del sobre, el ayudante descarta el mensaje.
- `salida/`: la Muse deja archivos `*.json` con
  {"tipo": "resultado"|"aviso", "datos": {...}} y el ayudante los
  publica al programa con su clave dentro, QoS 1; al confirmarse el
  envío los mueve a `salida/enviados/`.

Presencia: al conectar publica «en_linea» retenido en su tema de
presencia y deja un LWT «sin_conexion» por si se cae sin despedirse.

Salida por proxy: los espacios Muse salen a internet por un proxy
CONNECT (variables http_proxy/https_proxy). Si están presentes y el
broker es seguro (wss/mqtts), el ayudante levanta un túnel local
CONNECT y conecta por ahí — el mismo patrón verificado en la prueba
de viabilidad. En ese caso la verificación del nombre del
certificado se desactiva (el extremo local es 127.0.0.1 y el
certificado es del broker); el TLS sigue siendo extremo a extremo
con el broker y la clave Growi dentro de la carga autentica igual.
"""

import json
import os
import socket
import ssl
import sys
import threading
import time
import uuid
from urllib.parse import urlparse

TOPE_MENSAJE = 64 * 1024


def _sobre(tipo, cuenta, datos, clave=None):
    s = {"v": 1, "id": uuid.uuid4().hex, "tipo": tipo,
         "ts": int(time.time()), "cuenta": cuenta, "datos": datos}
    if clave:
        s["clave"] = clave
    return s


def _serializar(sobre):
    crudo = json.dumps(sobre, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
    if len(crudo) > TOPE_MENSAJE:
        raise ValueError(f"mensaje de {len(crudo)} bytes supera el "
                         f"tope de {TOPE_MENSAJE}")
    return crudo


# --- túnel CONNECT local (para salir por el proxy del entorno) ------

def _tunel_local(destino_host, destino_puerto, proxy_url):
    """Escucha en 127.0.0.1:<efímero> y reenvía cada conexión al
    destino a través del proxy CONNECT. Devuelve el puerto local."""
    p = urlparse(proxy_url)
    proxy_host, proxy_puerto = p.hostname, p.port or 3128
    auth = ""
    if p.username:
        import base64
        cred = f"{p.username}:{p.password or ''}".encode()
        auth = "Proxy-Authorization: Basic " + \
            base64.b64encode(cred).decode() + "\r\n"

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    puerto_local = srv.getsockname()[1]

    def bombear(a, b):
        try:
            while True:
                datos = a.recv(65536)
                if not datos:
                    break
                b.sendall(datos)
        except OSError:
            pass
        try:
            b.shutdown(socket.SHUT_WR)
        except OSError:
            pass

    def atender(cliente):
        try:
            remoto = socket.create_connection((proxy_host, proxy_puerto),
                                              timeout=20)
            peticion = (f"CONNECT {destino_host}:{destino_puerto} "
                        f"HTTP/1.1\r\nHost: {destino_host}:{destino_puerto}"
                        f"\r\n{auth}\r\n").encode()
            remoto.sendall(peticion)
            respuesta = b""
            while b"\r\n\r\n" not in respuesta:
                trozo = remoto.recv(4096)
                if not trozo:
                    raise OSError("el proxy cerró la conexión")
                respuesta += trozo
            if b" 200" not in respuesta.split(b"\r\n")[0]:
                raise OSError("el proxy rechazó el túnel: "
                              + respuesta.split(b"\r\n")[0].decode("latin-1"))
            threading.Thread(target=bombear, args=(cliente, remoto),
                             daemon=True).start()
            bombear(remoto, cliente)
        except OSError as e:
            print(f"túnel: {e}", file=sys.stderr)
        finally:
            try:
                cliente.close()
            except OSError:
                pass

    def bucle():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=atender, args=(c,), daemon=True).start()

    threading.Thread(target=bucle, daemon=True).start()
    return puerto_local


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        cfg = json.load(f)
    for campo in ("broker", "usuario", "raiz", "cuenta", "clave_growi"):
        if not cfg.get(campo):
            print(f"config: falta «{campo}»", file=sys.stderr)
            return 2
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("falta paho-mqtt (pip install paho-mqtt)", file=sys.stderr)
        return 2

    base = cfg.get("carpeta") or "./mqtt-ayudante"
    entrada = os.path.join(base, "entrada")
    salida = os.path.join(base, "salida")
    enviados = os.path.join(salida, "enviados")
    for d in (entrada, salida, enviados):
        os.makedirs(d, exist_ok=True)

    raiz = cfg["raiz"].strip("/")
    cuenta = cfg["cuenta"]
    clave = cfg["clave_growi"]
    p = urlparse(cfg["broker"])
    esquema = (p.scheme or "").lower()
    host, puerto = p.hostname, p.port or (443 if esquema == "wss" else 8883)
    websockets = esquema in ("wss", "ws")
    tls = esquema in ("wss", "mqtts")
    inseguro = False

    proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy")
    if proxy and tls:
        puerto_local = _tunel_local(host, puerto, proxy)
        print(f"túnel local por proxy: 127.0.0.1:{puerto_local} -> "
              f"{host}:{puerto}")
        host, puerto = "127.0.0.1", puerto_local
        inseguro = True

    kwargs = {"client_id": f"growi-{cuenta}-{uuid.uuid4().hex[:8]}",
              "clean_session": False, "protocol": mqtt.MQTTv311}
    if websockets:
        kwargs["transport"] = "websockets"
    cliente = mqtt.Client(**kwargs)
    if websockets and p.path:
        cliente.ws_set_options(path=p.path)
    cliente.username_pw_set(cfg["usuario"], cfg.get("contrasena") or "")
    if tls:
        cliente.tls_set()
        if inseguro:
            cliente.tls_insecure_set(True)

    tema_presencia = f"{raiz}/{cuenta}/presencia"
    cliente.will_set(tema_presencia,
                     payload=_serializar(_sobre(
                         "presencia", cuenta,
                         {"estado": "sin_conexion",
                          "ts": int(time.time())})),
                     qos=1, retain=True)

    def al_conectar(c, _ud, _flags, rc):
        if rc != 0:
            print(f"broker: conexión rechazada (rc={rc})", file=sys.stderr)
            return
        c.subscribe(f"{raiz}/{cuenta}/tareas", qos=1)
        c.publish(tema_presencia,
                  payload=_serializar(_sobre(
                      "presencia", cuenta,
                      {"estado": "en_linea", "ts": int(time.time())})),
                  qos=1, retain=True)
        print(f"conectada como «{cuenta}»: escuchando tareas")

    def al_mensaje(_c, _ud, msg):
        try:
            sobre = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        if not isinstance(sobre, dict) or sobre.get("v") != 1:
            return
        if sobre.get("clave") != clave:
            print("mensaje descartado: clave Growi no coincide",
                  file=sys.stderr)
            return
        mid = sobre.get("id") or uuid.uuid4().hex
        destino = os.path.join(entrada, f"{mid}.json")
        if os.path.exists(destino):
            return  # duplicado de QoS 1: ya está entregado
        tmp = destino + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sobre, f, ensure_ascii=False, indent=1)
        os.replace(tmp, destino)
        print(f"tarea recibida: {mid}")

    cliente.on_connect = al_conectar
    cliente.on_message = al_mensaje
    cliente.connect(host, puerto, keepalive=60)
    cliente.loop_start()

    try:
        while True:
            for nombre in sorted(os.listdir(salida)):
                if not nombre.endswith(".json"):
                    continue
                ruta = os.path.join(salida, nombre)
                try:
                    with open(ruta, encoding="utf-8") as f:
                        envio = json.load(f)
                    tipo = envio.get("tipo")
                    if tipo not in ("resultado", "aviso"):
                        raise ValueError("tipo debe ser resultado|aviso")
                    sobre = _sobre(tipo, cuenta, envio.get("datos"),
                                   clave=clave)
                    info = cliente.publish(
                        f"{raiz}/{cuenta}/{tipo}s",
                        payload=_serializar(sobre), qos=1)
                    info.wait_for_publish(timeout=10)
                    os.replace(ruta, os.path.join(enviados, nombre))
                    print(f"{tipo} publicado: {sobre['id']}")
                except Exception as e:
                    print(f"salida {nombre}: {e}", file=sys.stderr)
                    os.replace(ruta, os.path.join(
                        enviados, nombre + ".error"))
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            cliente.publish(tema_presencia,
                            payload=_serializar(_sobre(
                                "presencia", cuenta,
                                {"estado": "sin_conexion",
                                 "ts": int(time.time())})),
                            qos=1, retain=True).wait_for_publish(timeout=5)
        except Exception:
            pass
        cliente.loop_stop()
        cliente.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Emulador de gadget por serie (PROTOCOLO-GADGET.md, protocolo 1).

No hay hardware: escucha en tcp://127.0.0.1:<puerto> (la «línea serie» que la
app acepta para el emulador) y contesta como lo haría el gadget. Con --pedir
«texto» manda, tras el HOLA, una línea PEDIR (el gadget pide un encargo).

  python pruebas/emulador_gadget.py 8830 [--pedir "Borra el archivo C:\\x.txt"]
"""

import socket
import sys


def atender(con, pedidos):
    estado = {"led": "OFF", "pantalla": ""}
    buf = b""
    while True:
        d = con.recv(256)
        if not d:
            return
        buf += d
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            linea = raw.decode("utf-8", errors="replace").strip()
            cmd, _sp, arg = linea.partition(" ")
            if cmd == "HOLA":
                resp = [f"OK HOLA emulador-gadget {arg or '?'}", "EVENTO ARRANQUE emulador listo"]
                resp += [f"PEDIR {p}" for p in pedidos]
            elif cmd == "PING":
                resp = ["OK PONG"]
            elif cmd == "ESTADO":
                resp = [f"OK ESTADO led={estado['led']} pantalla={estado['pantalla'] or '-'}"]
            elif cmd == "MOSTRAR":
                estado["pantalla"] = arg[:32]
                resp = ["OK MOSTRAR"]
            elif cmd == "LED" and arg in ("ON", "OFF"):
                estado["led"] = arg
                resp = [f"OK LED {arg}"]
            elif cmd == "OK":  # la app confirma un PEDIR: no se contesta
                resp = []
            else:
                resp = [f"ERR DESCONOCIDO {cmd}"]
            for r in resp:
                con.sendall((r + "\n").encode("utf-8"))


def main():
    puerto = int(sys.argv[1])
    pedidos = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--pedir"]
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", puerto))
    srv.listen(1)
    print(f"emulador en tcp://127.0.0.1:{puerto}", flush=True)
    while True:
        con, _a = srv.accept()
        try:
            atender(con, pedidos)
        except OSError:
            pass
        finally:
            con.close()


if __name__ == "__main__":
    main()

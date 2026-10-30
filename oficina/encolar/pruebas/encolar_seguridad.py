"""(e) Que escucha y quien: todos los sockets LISTEN del PC con su proceso; los
procesos de esta prueba (runner aislado, encolador, llama-server que lance) se
marcan, y se dice si alguno escucha fuera de 127.0.0.1/::1.
Uso: python encolar_seguridad.py [pid ...]"""
import sys
import psutil

pids = {int(x) for x in sys.argv[1:]}
# hijos de los pids de la prueba (llama-server lanzado por el runner aislado)
for pid in list(pids):
    try:
        pids |= {c.pid for c in psutil.Process(pid).children(recursive=True)}
    except psutil.Error:
        pass
fuera, nuestros = [], []
for c in psutil.net_connections(kind="inet"):
    if c.status != psutil.CONN_LISTEN:
        continue
    try:
        nombre = psutil.Process(c.pid).name() if c.pid else "?"
    except psutil.Error:
        nombre = "?"
    ip, port = c.laddr.ip, c.laddr.port
    loop = ip in ("127.0.0.1", "::1")
    marca = "PRUEBA" if c.pid in pids else ""
    if c.pid in pids:
        nuestros.append((ip, port, c.pid, nombre))
    if not loop:
        fuera.append((ip, port, c.pid, nombre, marca))
print("procesos de la prueba:", sorted(pids))
print("LISTEN de la prueba:", nuestros or "ninguno")
print("de la prueba fuera de loopback:", [x for x in fuera if x[4]] or "NINGUNO")
print("otros procesos del PC que escuchan fuera de loopback (preexistentes, no de esta prueba):")
for x in sorted(set(fuera)):
    if not x[4]:
        print("   ", x[:4])

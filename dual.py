"""Growi Bridge — Fase 1 Multi-Muse: modo dual (servidor + local).

La lógica pura de la conmutación de una cuenta con conexion «ambas»:
latido con histéresis, estados servidor/local/reconciliando y el protocolo
de tareas «por confirmar». No conoce el monolito: la sonda de red y los
ejecutores se inyectan, así que la prueba de corte de red es automática y
reproducible (nada de desenchufar cables a mano).

La regla que hace seguro el modo dual (revisión de diseño de la Fase 1):

    Una tarea se ejecuta UNA vez: en el servidor o en local, nunca en los
    dos. La que ya salió al servidor cuando cae la red NO se completa en
    local: queda «por_confirmar» y solo se resuelve al reconciliar,
    preguntando al servidor si la ejecutó. Si dice que no, se ejecuta en
    local una vez; si dice que sí, se marca hecha sin ejecutarla.

Histéresis del latido: hacen falta N fallos seguidos para pasar a local y
M éxitos seguidos para volver; un solo fallo no cambia nada (una red
inestable no hace oscilar el estado). Un latido fallido tampoco equivale a
una tarea fallida: son cosas distintas.
"""

import threading
import time

SERVIDOR = "servidor"
LOCAL = "local"
RECONCILIANDO = "reconciliando"

POR_CONFIRMAR = "por_confirmar"
HECHA_EN_SERVIDOR = "hecha_en_servidor"
HECHA_EN_LOCAL = "hecha_en_local"


class VigiaDual:
    """Vigía de una cuenta dual: sonda, estado y tareas por confirmar.

    - probar(): -> bool, ¿el servidor responde?
    - al_cambiar(estado_nuevo, estado_viejo): callback opcional (log/UI).
    """

    def __init__(self, probar, fallos_para_local=3, exitos_para_servidor=2,
                 al_cambiar=None):
        self._probar = probar
        self.fallos_para_local = max(1, int(fallos_para_local))
        self.exitos_para_servidor = max(1, int(exitos_para_servidor))
        self._al_cambiar = al_cambiar
        self.estado = SERVIDOR
        self._fallos = 0
        self._exitos = 0
        self._lock = threading.Lock()
        # id -> {"estado": POR_CONFIRMAR|HECHA_*, "tarea": obj}
        self.por_confirmar = {}

    # -- latido ---------------------------------------------------------
    def tick(self):
        """Una sonda. Devuelve el estado tras aplicarla."""
        try:
            ok = bool(self._probar())
        except Exception:
            ok = False
        with self._lock:
            if ok:
                self._fallos = 0
                self._exitos += 1
            else:
                self._exitos = 0
                self._fallos += 1
            nuevo = self.estado
            if self.estado == SERVIDOR and self._fallos >= self.fallos_para_local:
                nuevo = LOCAL
            elif self.estado == LOCAL and self._exitos >= self.exitos_para_servidor:
                nuevo = RECONCILIANDO
            elif self.estado == RECONCILIANDO and not ok:
                nuevo = LOCAL
            if nuevo != self.estado:
                viejo, self.estado = self.estado, nuevo
                self._fallos = self._exitos = 0
                if self._al_cambiar:
                    self._al_cambiar(nuevo, viejo)
            return self.estado

    # -- tareas ---------------------------------------------------------
    def registrar_en_vuelo(self, tarea_id, tarea=None):
        """Marca una tarea como «salió al servidor, sin confirmar».

        Se llama cuando la tarea se envía al servidor. Si luego hay corte,
        esa tarea NO se ejecuta en local (ver al_cortar). Sin `tarea`, el
        propio id hace de carga útil al reconciliar."""
        with self._lock:
            self.por_confirmar[tarea_id] = {
                "estado": POR_CONFIRMAR,
                "tarea": tarea if tarea is not None else tarea_id}

    def confirmar_hecha_en_servidor(self, tarea_id):
        """El servidor confirmó la ejecución normal (sin corte de por medio)."""
        with self._lock:
            self.por_confirmar.pop(tarea_id, None)

    def puede_ejecutar_en_local(self, tarea_id):
        """False si la tarea ya salió al servidor y está por confirmar."""
        with self._lock:
            return tarea_id not in self.por_confirmar

    def reconciliar(self, resolver, ejecutar_local):
        """Al volver la red: resuelve cada tarea por confirmar.

        - resolver(tarea_id) -> True si el servidor la ejecutó.
        - ejecutar_local(tarea) -> ejecuta en local (una sola vez) las que
          el servidor no ejecutó.
        Devuelve {"hechas_en_servidor": n, "hechas_en_local": m}.
        Solo tiene sentido en estado RECONCILIANDO; al terminar sin
        errores, el vigía pasa a SERVIDOR.
        """
        with self._lock:
            pendientes = list(self.por_confirmar.items())
        hechas_srv = hechas_loc = 0
        for tarea_id, datos in pendientes:
            if resolver(tarea_id):
                with self._lock:
                    self.por_confirmar[tarea_id]["estado"] = HECHA_EN_SERVIDOR
                    del self.por_confirmar[tarea_id]
                hechas_srv += 1
            else:
                ejecutar_local(datos["tarea"])
                with self._lock:
                    self.por_confirmar.pop(tarea_id, None)
                hechas_loc += 1
        with self._lock:
            if self.estado == RECONCILIANDO and not self.por_confirmar:
                viejo, self.estado = self.estado, SERVIDOR
                self._fallos = self._exitos = 0
                if self._al_cambiar:
                    self._al_cambiar(SERVIDOR, viejo)
        return {"hechas_en_servidor": hechas_srv, "hechas_en_local": hechas_loc}

    # -- bucle ----------------------------------------------------------
    def correr(self, parar, intervalo=15.0):
        """Bucle del latido hasta que el evento `parar` se active."""
        while not parar.is_set():
            self.tick()
            parar.wait(intervalo)

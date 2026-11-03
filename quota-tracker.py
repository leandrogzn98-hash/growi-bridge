# -*- coding: utf-8 -*-
"""Tracker de cuotas multi-motor (Growi Bridge 0.6.0).

Lee config-quota.json en CADA llamada (anadir un motor = editar el JSON, sin reiniciar ni tocar codigo)
y persiste el uso en quota-uso.json: {"claude": {"usado": 12.5, "periodo": "2026-11"}, ...}.

Campos de un motor en config-quota.json: nombre, tipo, limite (numero o null), unidad,
reset ("diario" | "mensual" | "nunca"). Opcional: "costo_por_llamada" (default 1): lo que suma una
llamada en la unidad del motor; si no se pone, una llamada suma 1.

Uso:
    python quota-tracker.py                      (estado de todos)
    python quota-tracker.py --registrar claude 1
"""
import json
import os
import sys
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG_DEF = os.path.join(AQUI, "config-quota.json")
USO_DEF = os.path.join(AQUI, "quota-uso.json")


def _periodo(reset, ahora):
    r = str(reset or "nunca").lower()
    if r == "diario":
        return ahora.strftime("%Y-%m-%d")
    if r == "mensual":
        return ahora.strftime("%Y-%m")
    return "siempre"


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


class QuotaTracker:
    def __init__(self, config_path=None, uso_path=None, reloj=None):
        self.config_path = config_path or CONFIG_DEF
        self.uso_path = uso_path or USO_DEF
        self._reloj = reloj or datetime.now

    # -- config (recargada en cada lectura)
    def motores(self):
        m = _leer_json(self.config_path).get("motores", {})
        return {k: v for k, v in m.items() if isinstance(v, dict)} if isinstance(m, dict) else {}

    def resolver_motor(self, nombre):
        """'claude' -> 'claude'; 'claude_cli' -> 'claude' (la clave de config es prefijo del nombre del motor)."""
        mot = self.motores()
        n = str(nombre).lower()
        if n in mot:
            return n
        for k in sorted(mot, key=len, reverse=True):
            if n.startswith(k.lower()):
                return k
        return None

    def _uso(self):
        return _leer_json(self.uso_path)

    def _guardar(self, uso):
        tmp = self.uso_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(uso, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.uso_path)

    # -- escritura
    def registrar_uso(self, motor, cantidad=1, tipo="llamada"):
        """Suma uso. tipo='llamada': cantidad * costo_por_llamada (default 1). tipo='unidad': cantidad tal cual
        (p.ej. USD reales). Devuelve el estado nuevo, o None si el motor no esta en la config (no se inventa)."""
        clave = self.resolver_motor(motor)
        if clave is None:
            return None
        cfg = self.motores()[clave]
        per = _periodo(cfg.get("reset"), self._reloj())
        mult = 1.0
        if tipo == "llamada":
            try:
                mult = float(cfg.get("costo_por_llamada", 1))
            except (TypeError, ValueError):
                mult = 1.0
        uso = self._uso()
        reg = uso.get(clave) if isinstance(uso.get(clave), dict) else {}
        usado = float(reg.get("usado", 0)) if reg.get("periodo") == per else 0.0  # periodo nuevo = reset
        usado += float(cantidad) * mult
        uso[clave] = {"usado": round(usado, 6), "periodo": per}
        self._guardar(uso)
        return self.obtener_estado(clave)

    # -- lectura
    def obtener_estado(self, motor):
        clave = self.resolver_motor(motor)
        if clave is None:
            return None
        cfg = self.motores()[clave]
        per = _periodo(cfg.get("reset"), self._reloj())
        reg = self._uso().get(clave)
        usado = 0.0
        if isinstance(reg, dict) and reg.get("periodo") == per:  # periodo distinto = reset automatico
            try:
                usado = float(reg.get("usado", 0))
            except (TypeError, ValueError):
                usado = 0.0
        limite = cfg.get("limite")
        if not isinstance(limite, (int, float)) or isinstance(limite, bool) or limite <= 0:
            limite = None
        ilimitado = str(cfg.get("tipo", "")).lower() == "ilimitado"
        if ilimitado:
            limite = None
        pct = None if limite is None else round(usado / limite * 100)
        unidad = cfg.get("unidad", "")
        if "usd" in str(unidad).lower() and "costo_por_llamada" not in cfg:
            # el harness suma llamadas, no dolares: no se muestra 'USD' si no hay costo por llamada configurado
            unidad = "llamadas (USD pendiente)"
        return {"motor": clave, "nombre": cfg.get("nombre", clave), "tipo": cfg.get("tipo", ""),
                "usado": int(usado) if usado == int(usado) else round(usado, 4),
                "limite": limite, "unidad": unidad, "reset": cfg.get("reset", "nunca"),
                "periodo": per, "ilimitado": ilimitado, "porcentaje": pct}

    def obtener_todos(self):
        return {k: self.obtener_estado(k) for k in self.motores()}

    def para_estado(self):
        """Seccion 'quotas' de harness-state.json."""
        out = {}
        for k, e in self.obtener_todos().items():
            out[k] = {"nombre": e["nombre"], "tipo": e["tipo"], "usado": e["usado"], "limite": e["limite"],
                      "unidad": e["unidad"], "porcentaje": e["porcentaje"], "ilimitado": e["ilimitado"]}
        return out


def main(argv):
    t = QuotaTracker()
    if len(argv) >= 4 and argv[1] == "--registrar":
        print(json.dumps(t.registrar_uso(argv[2], float(argv[3])), ensure_ascii=False))
        return 0
    print(json.dumps(t.obtener_todos(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

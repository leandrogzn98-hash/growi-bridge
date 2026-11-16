#!/usr/bin/env python3
"""Growi Bridge — generador de las reglas del intermediario (Fase 6).

Lo ejecuta EL DUEÑO, en su terminal. Este script:

- Lee la lista del dueño (raiz-config.json en la carpeta compartida)
  y compone la regla de sudoers desde el registro cerrado de
  raiz.py. Si la lista trae un nombre inválido, se niega ANTES de
  componer nada.
- Verifica el texto con `visudo -cf` si visudo está disponible.
- Escribe el texto en `growi-bridge.sudoers`, junto a este script
  (un archivo normal, sin privilegios), lo MUESTRA entero y dice
  los comandos exactos que el dueño pega en su terminal para
  instalarlo todo con SU contraseña.

Lo que NUNCA hace: ejecutar sudo, pedir una contraseña, ni tocar
/etc. La app tampoco instala nada de esto: instalar el intermediario
es un acto del dueño en su terminal, para siempre.

Sin terminal interactiva (sin TTY) se niega a hacer nada (§14 bis
I9): este guion no es una tubería para que otro programa lo conduzca.
"""

import getpass
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import raiz  # noqa: E402  (módulo hermano, el registro de la app)


def _base_defecto():
    xdg = os.environ.get("XDG_DATA_HOME")
    raiz_dir = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return raiz_dir / "GrowiBridge"


def main(argv):
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("instalar-raiz: me niego a funcionar sin una terminal "
              "interactiva (sin TTY). Este guion lo ejecuta el dueño "
              "a mano, en su terminal; no es una tubería para otros "
              "programas.", file=sys.stderr)
        return 2
    base = Path(argv[1]) if len(argv) > 1 else _base_defecto()
    usuario = getpass.getuser()
    print(f"Intermediario de root de Growi Bridge — generar reglas")
    print(f"Usuario: {usuario} · Lista del dueño: "
          f"{base / raiz.ARCHIVO_CONFIG}")
    config = raiz.cargar_config(base)
    if config["unidades"]:
        print("Unidades que el intermediario podrá tocar: "
              + ", ".join(sorted(config["unidades"])))
    else:
        print("Sin unidades en la lista del dueño: solo estarán "
              "disponibles las acciones de paquetes. Para autorizar "
              f"servicios, edita {raiz.ARCHIVO_CONFIG} en la carpeta "
              "compartida y vuelve a ejecutar este guion.")
    try:
        texto = raiz.componer_sudoers(usuario, config)
    except raiz.ErrorRaiz as e:
        print(f"\nNO se generó nada: {e}", file=sys.stderr)
        return 1
    ok, detalle = raiz.validar_sudoers(texto)
    if ok is False:
        print(f"\nvisudo rechazó el texto generado ({detalle}): "
              "NO se escribió nada.", file=sys.stderr)
        return 1
    destino = AQUI / "growi-bridge.sudoers"
    destino.write_text(texto, encoding="utf-8")
    print("\n--- growi-bridge.sudoers (esto es TODO lo que se "
          "autoriza) ---")
    print(texto, end="")
    print("--- fin ---")
    if ok is None:
        print(f"Aviso: {detalle}. Revisa el texto a ojo con más "
              "cuidado antes de instalarlo.")
    else:
        print(f"Verificado con visudo: {detalle or 'correcto'}.")
    print("\nPara instalarlo, pega estos comandos en ESTA terminal "
          "(te pedirán TU contraseña; ni este guion ni la app la "
          "ven nunca):")
    for comando in raiz.comandos_instalacion(
            ruta_reglas=str(destino),
            ruta_ayudante=str(AQUI / "growi-ayudante.py")):
        print(f"  {comando}")
    print("\nDespués, abre Growi Bridge → Cuentas → Seguridad "
          "avanzada y pulsa «Probar sonda»: debe decir «sudoers».")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

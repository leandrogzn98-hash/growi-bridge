#!/usr/bin/env sh
# Instala el vigilante de Growi Bridge (Fase 4) en Linux como servicio de
# usuario de systemd. El vigilante es biblioteca estándar pura: no
# necesita venv ni root. Vigila el runner-status.json de cada carril y
# relanza el que muera (tope 3 por hora); nunca mata un proceso vivo.
#
#   sh instalar-vigilante.sh [--desinstalar]
#
# La configuración vive en vigilante.json junto a vigilante.py: la base
# compartida y los carriles con su carpeta y su comando de arranque. Si
# el carril B vive en otra copia del programa, añade su entrada a
# "carriles" en ese archivo (nombre "b", su "dir" y su "arranque").
set -eu
AQUI=$(cd "$(dirname "$0")" && pwd)
RAIZ=$(dirname "$AQUI")
DESINSTALAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --desinstalar) DESINSTALAR=1; shift ;;
    *) echo "opción desconocida: $1" >&2; exit 2 ;;
  esac
done
UNIDADES="$HOME/.config/systemd/user"
SERVICIO="$UNIDADES/growi-vigilante.service"
BASE="${XDG_DATA_HOME:-$HOME/.local/share}/GrowiBridge"

if [ "$DESINSTALAR" = 1 ]; then
  systemctl --user disable --now growi-vigilante.service 2>/dev/null || true
  rm -f "$SERVICIO"
  systemctl --user daemon-reload 2>/dev/null || true
  echo "Vigilante desinstalado (vigilante.json se conserva)."
  exit 0
fi

if [ ! -f "$RAIZ/vigilante.json" ]; then
  mkdir -p "$BASE"
  cat > "$RAIZ/vigilante.json" <<EOF
{
  "base": "$BASE",
  "carriles": [
    {"nombre": "a", "dir": "$RAIZ",
     "arranque": ["python3", "$RAIZ/growi-bridge.py"]}
  ]
}
EOF
  echo "Creado $RAIZ/vigilante.json (edítalo si el carril B vive en otra copia)."
fi

if systemctl --user show-environment >/dev/null 2>&1; then
  mkdir -p "$UNIDADES"
  PYTHON=$(command -v python3)
  sed -e "s|@RAIZ@|$RAIZ|g" -e "s|@PYTHON@|$PYTHON|g" \
      "$AQUI/growi-vigilante.service" > "$SERVICIO"
  systemctl --user daemon-reload
  systemctl --user enable --now growi-vigilante.service
  echo "Vigilante activo como servicio de usuario (growi-vigilante.service)."
else
  echo "Sin systemd de usuario: deja el vigilante corriendo con" >&2
  echo "  python3 $RAIZ/vigilante.py" >&2
  echo "o añádelo a tu arranque de sesión." >&2
  exit 1
fi

#!/usr/bin/env sh
# Instala el supervisor local de Growi Bridge en macOS: entorno de Python propio (.venv junto a este script) y un
# agente de launchd (~/Library/LaunchAgents/local.<nombre>.plist, desde la plantilla supervisor.plist.plantilla)
# que lo corre cada N minutos (N = subgerente.intervalo_minutos del YAML). No necesita administrador.
#
#   sh instalar-supervisor-macos.sh [--config otra.yaml] [--desinstalar]
set -eu
AQUI=$(cd "$(dirname "$0")" && pwd)
CONFIG="$AQUI/supervisor-config.yaml"
DESINSTALAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --config) CONFIG=$(cd "$(dirname "$2")" && pwd)/$(basename "$2"); shift 2 ;;
    --desinstalar) DESINSTALAR=1; shift ;;
    *) echo "opción desconocida: $1" >&2; exit 2 ;;
  esac
done
PY="$AQUI/.venv/bin/python"
if [ ! -x "$PY" ]; then
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || { echo "Hace falta Python 3.10 o superior (https://www.python.org/downloads/macos/)." >&2; exit 1; }
  python3 -m venv "$AQUI/.venv"
fi
"$PY" -m pip install -q -r "$AQUI/requirements.txt"
set -- $("$PY" "$AQUI/supervisor.py" --config "$CONFIG" --programacion)
MIN=$1; NOMBRE=$2
ETIQUETA="local.$NOMBRE"
PLIST="$HOME/Library/LaunchAgents/$ETIQUETA.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
if [ "$DESINSTALAR" = 1 ]; then rm -f "$PLIST"; echo "Agente $ETIQUETA quitado."; exit 0; fi
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.growi-supervisor"
sed -e "s|@ETIQUETA@|$ETIQUETA|g" -e "s|@PYTHON@|$PY|g" -e "s|@SCRIPT@|$AQUI/supervisor.py|g" \
    -e "s|@CONFIG@|$CONFIG|g" -e "s|@AQUI@|$AQUI|g" -e "s|@SEGUNDOS@|$((MIN * 60))|g" \
    -e "s|@DATOS@|$HOME/.growi-supervisor|g" "$AQUI/supervisor.plist.plantilla" > "$PLIST"
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Agente $ETIQUETA activo cada $MIN min. Comprueba todo con: $PY $AQUI/supervisor.py --config $CONFIG --verificar"

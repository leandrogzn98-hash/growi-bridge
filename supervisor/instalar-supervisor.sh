#!/usr/bin/env sh
# Instala el supervisor local de Growi Bridge en Linux: entorno de Python propio (.venv junto a este script) y un
# temporizador de systemd de usuario cada N minutos (N = subgerente.intervalo_minutos del YAML). Sin systemd de
# usuario, usa cron. No necesita root.
#
#   sh instalar-supervisor.sh [--config otra.yaml] [--desinstalar]
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
    || { echo "Hace falta Python 3.10 o superior (y python3-venv)." >&2; exit 1; }
  python3 -m venv "$AQUI/.venv"
fi
"$PY" -m pip install -q -r "$AQUI/requirements.txt"
set -- $("$PY" "$AQUI/supervisor.py" --config "$CONFIG" --programacion)
MIN=$1; NOMBRE=$2
CMD="$PY $AQUI/supervisor.py --config $CONFIG"
UNIDADES="$HOME/.config/systemd/user"

if systemctl --user show-environment >/dev/null 2>&1; then
  if [ "$DESINSTALAR" = 1 ]; then
    systemctl --user disable --now "$NOMBRE.timer" 2>/dev/null || true
    rm -f "$UNIDADES/$NOMBRE.service" "$UNIDADES/$NOMBRE.timer"
    systemctl --user daemon-reload; echo "Temporizador $NOMBRE quitado."; exit 0
  fi
  mkdir -p "$UNIDADES"
  cat > "$UNIDADES/$NOMBRE.service" <<EOF
[Unit]
Description=Supervisor local de Growi Bridge (subgerente): lee, juzga e informa

[Service]
Type=oneshot
WorkingDirectory=$AQUI
ExecStart=$CMD
EOF
  cat > "$UNIDADES/$NOMBRE.timer" <<EOF
[Unit]
Description=Supervisor de Growi Bridge cada $MIN min

[Timer]
OnBootSec=5min
OnUnitActiveSec=${MIN}min
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now "$NOMBRE.timer"
  echo "Temporizador $NOMBRE.timer activo cada $MIN min (systemd de usuario)."
else
  ACTUAL=$(crontab -l 2>/dev/null | grep -v "# $NOMBRE\$" || true)
  if [ "$DESINSTALAR" = 1 ]; then
    printf '%s\n' "$ACTUAL" | crontab -; echo "Línea de cron $NOMBRE quitada."; exit 0
  fi
  if [ "$MIN" -lt 60 ]; then CUANDO="*/$MIN * * * *"; else CUANDO="0 */$((MIN / 60)) * * *"; fi
  printf '%s\n%s\n' "$ACTUAL" "$CUANDO $CMD # $NOMBRE" | sed '/^$/d' | crontab -
  echo "cron: $NOMBRE cada $MIN min."
fi
echo "Comprueba todo con: $CMD --verificar"

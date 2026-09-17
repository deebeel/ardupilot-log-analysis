#!/usr/bin/env bash
# Експериментальний скрипт (гілка experiment/flightgear-viz, не для здачі —
# MAVProxy --map/--console/horizon уже закриває GCS+візуалізацію, CLAUDE.md).
# Піднімає FlightGear на Mac, готовий приймати FGNetFDM-дані напряму від SITL
# (ArduPilot, --enable-fgview — див. FLIGHTGEAR_HOST у local/run-sitl.sh), не
# через MAVProxy-модуль (такого модуля fgout у встановленій MAVProxy немає —
# перевірено живцем).
#
# Порти/прапорці скопійовані з офіційного ardupilot/Tools/autotest/fg_plane_view.sh
# (те, що реально викликає ArduPilot CI для перевірки FlightGear-виводу):
# --fdm=external (SITL сам рахує фізику, FlightGear лише візуалізує), rate=10,
# модель Rascal110-JSBSim з бандленої Tools/autotest/aircraft/ у самому ArduPilot.
#
# Ця тека (~17МБ, апстрім ArduPilot) НЕ копіюється в цей репозиторій — одноразово
# перенести з хоста, де вже клоновано .sitl/ (SITL_HOST=user@host):
#   scp -r "$SITL_HOST:~/ardupilot-log-analysis/.sitl/Tools/autotest/aircraft" \
#     "$HOME/.fg-aircraft-ardupilot"
set -euo pipefail

PORT="${FG_PORT:-5503}"
AIRCRAFT="${FG_AIRCRAFT:-Rascal110-JSBSim}"
FG_AIRCRAFT_DIR="${FG_AIRCRAFT_DIR:-$HOME/.fg-aircraft-ardupilot}"
FGFS_BIN="${FGFS_BIN:-/Applications/FlightGear.app/Contents/MacOS/FlightGear}"
FG_ROOT="${FG_ROOT:-$HOME/Library/Application Support/FlightGear/fgdata_2024_1}"

if [ ! -d "$FG_AIRCRAFT_DIR" ]; then
  echo "FG_AIRCRAFT_DIR ($FG_AIRCRAFT_DIR) не знайдено — перенести Tools/autotest/aircraft" >&2
  echo "з хоста з клонованим .sitl/ (див. коментар на початку файлу)." >&2
  exit 1
fi

echo "== FlightGear: приймаю FGNetFDM (external FDM) на UDP $PORT, модель $AIRCRAFT =="
echo "   На стороні SITL: FLIGHTGEAR_HOST=\$(ipconfig getifaddr en0) ./local/run-sitl.sh"

"$FGFS_BIN" \
  --fg-root="$FG_ROOT" \
  --native-fdm=socket,in,10,,"$PORT",udp \
  --fdm=external \
  --aircraft="$AIRCRAFT" \
  --fg-aircraft="$FG_AIRCRAFT_DIR" \
  --airport=KSFO \
  --geometry=650x550 \
  --bpp=32 \
  --disable-hud-3d \
  --disable-horizon-effect \
  --timeofday=noon \
  --disable-sound \
  --disable-fullscreen \
  --disable-random-objects \
  --disable-ai-models \
  --fog-disable \
  --disable-specular-highlight \
  --disable-anti-alias-hud \
  --wind=0@0

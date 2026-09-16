#!/usr/bin/env bash
# Піднімає SITL ArduPlane + MAVProxy (--console --map — GCS і 2D-візуалізатор
# одним рішенням, CLAUDE.md). keyboard-adapter НЕ окремий процес — MAVProxy-
# модуль (mavproxy_keyboard_adapter.py), що вантажиться в сам процес MAVProxy
# через --mavproxy-args "--load-module keyboard_adapter" (CLAUDE.md: свідомий
# компроміс — упаде MAVProxy, впаде й керування; падіння ОКРЕМОГО модуля,
# напр. map, керування клавіатурою не чіпає). Модуль шукається за іменем
# файлу на PYTHONPATH, не через pip install — звідси експорт нижче.
# Клавіатурний бекенд — лише evdev (kernel /dev/input, однаково на Xorg і
# Wayland, потребує групи `input` — ./tools/prereqs.sh); KEYBOARD_DEVICE=
# /dev/input/eventN, якщо автовизначення обрало не той пристрій.
# Без sudo, повторюваний — викликати перед кожним польотом, після одноразового
# ./tools/prereqs.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITL_DIR="$REPO_ROOT/.sitl"

if [ ! -d "$SITL_DIR/ArduPlane" ]; then
  echo "$SITL_DIR не знайдено — спочатку ./tools/prereqs.sh" >&2
  exit 1
fi

export PYTHONPATH="$REPO_ROOT/tools/keyboard_adapter/src${PYTHONPATH:+:$PYTHONPATH}"

# speech/graph/horizon — штатні MAVProxy-модулі, не наші: живий фідбек під час
# клавіатурного пілотування (озвучка режиму/арм/failsafe, графік attitude,
# намальований авіагоризонт). `horizon` — wxPython (python3-wxgtk4.0, вже в
# tools/prereqs.sh), решта без додаткових залежностей.
echo "== SITL ArduPlane + MAVProxy (keyboard_adapter + speech/graph/horizon модулями) =="
cd "$SITL_DIR/ArduPlane"
sim_vehicle.py -v ArduPlane --frame plane -M plane --console --map \
  --mavproxy-args "--load-module keyboard_adapter --load-module speech --load-module graph --load-module horizon"

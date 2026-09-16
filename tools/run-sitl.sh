#!/usr/bin/env bash
# Піднімає SITL ArduPlane + MAVProxy (--console --map — GCS і 2D-візуалізатор
# одним рішенням, CLAUDE.md). keyboard-adapter НЕ окремий процес — MAVProxy-
# модуль (`init()` у keyboard_adapter/__init__.py), що вантажиться в сам
# процес MAVProxy через --mavproxy-args "--load-module keyboard_adapter"
# (CLAUDE.md: свідомий компроміс — упаде MAVProxy, впаде й керування; падіння
# ОКРЕМОГО модуля, напр. map, керування клавіатурою не чіпає). MAVProxy для
# сторонніх модулів імпортує голе ім'я `keyboard_adapter` (наш пакет) — не
# `mavproxy_keyboard_adapter.py`, звідси PYTHONPATH нижче саме на src/, а не
# pip install.
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

# install-prereqs-ubuntu.sh ставить MAVProxy/pymavlink у venv (`~/venv-ardupilot`,
# `--system-site-packages`), не системно, і НЕ дописує `source .../activate` в
# `.bashrc` за замовчуванням (інтерактивний "Make ArduPilot venv default? [N/y]",
# наш non-interactive прогін лишає N) — тож активуємо тут явно. `sim_vehicle.py`
# теж не на PATH за замовчуванням — він у Tools/autotest, не встановлюється.
VENV_ACTIVATE="$HOME/venv-ardupilot/bin/activate"
if [ -f "$VENV_ACTIVATE" ]; then
  # shellcheck disable=SC1090
  source "$VENV_ACTIVATE"
fi
export PATH="$SITL_DIR/Tools/autotest:$PATH"

export PYTHONPATH="$REPO_ROOT/tools/keyboard_adapter/src${PYTHONPATH:+:$PYTHONPATH}"

echo "== SITL ArduPlane + MAVProxy (keyboard_adapter модулем) =="
cd "$SITL_DIR/ArduPlane"
sim_vehicle.py -v ArduPlane --frame plane -M plane --console --map \
  --mavproxy-args "--load-module keyboard_adapter"

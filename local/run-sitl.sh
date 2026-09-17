#!/usr/bin/env bash
# Піднімає SITL ArduPlane + MAVProxy (--console --map — GCS і 2D-візуалізатор
# одним рішенням, CLAUDE.md). keyboard-adapter НЕ окремий процес — MAVProxy-
# модуль (`init()` у keyboard_adapter/__init__.py), що вантажиться в сам
# процес MAVProxy через --mavproxy-args "--load-module keyboard_adapter
# --load-module horizon" (CLAUDE.md: свідомий компроміс — упаде MAVProxy,
# впаде й керування; падіння ОКРЕМОГО модуля, напр. map, керування
# клавіатурою не чіпає). MAVProxy для сторонніх модулів імпортує голе ім'я
# `keyboard_adapter` (наш пакет) — не `mavproxy_keyboard_adapter.py`, звідси
# PYTHONPATH нижче саме на src/, а не pip install. `horizon` — штатний
# MAVProxy-модуль (wx-авіагоризонт), живий фідбек під час ручного пілотування
# без потреби дивитись на --map/--console.
# Клавіатурний бекенд — лише evdev (kernel /dev/input, однаково на Xorg і
# Wayland, потребує групи `input` — ./local/provision.sh); KEYBOARD_DEVICE=
# /dev/input/eventN, якщо автовизначення обрало не той пристрій.
# keyboard_adapter НЕ керує сам по собі — треба `kb on` у консолі MAV> (окрім
# FBWA + armed, README.md крок 4).
# Без sudo, повторюваний — викликати перед кожним польотом, після одноразового
# ./local/provision.sh.
#
# FlightGear (опційно, лише для ефектнішого запису — CLAUDE.md, MAVProxy сам
# закриває роль GCS+візуалізації): якщо задано FLIGHTGEAR_HOST, SITL сам шле
# FGNetFDM (--enable-fgview -A "--fg=$FLIGHTGEAR_HOST") на порт 5503 (дефолт
# ArduPilot) тому хосту — там має вже бути піднятий FlightGear, який приймає
# --native-fdm=socket,in,10,,5503,udp (local/run-flightgear-mac.sh на Mac).
# Без FLIGHTGEAR_HOST — прапорець не додається, поведінка не змінюється.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITL_DIR="$REPO_ROOT/.sitl"

if [ ! -d "$SITL_DIR/ArduPlane" ]; then
  echo "$SITL_DIR не знайдено — спочатку ./local/provision.sh" >&2
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

export PYTHONPATH="$REPO_ROOT/local/keyboard_adapter/src${PYTHONPATH:+:$PYTHONPATH}"

LOGDIR="$SITL_DIR/ArduPlane/logs"
TLOG="$LOGDIR/mav.tlog"
mkdir -p "$LOGDIR"

# SSH host key VPS приймається окремим одноразовим кроком, НЕ тут (інакше
# перший rsync/ssh у push-logs.sh застряг би на інтерактивному "are you sure
# you want to continue connecting?" посеред виводу MAVProxy) — перед першим
# запуском run-sitl.sh виконати вручну: `ssh root@10.10.0.1 exit`.

# Автоматична доставка логів на VPS (RND-254, критерій приймання — не dev-
# зручність) — окремий фоновий процес (local/push-logs.sh), не частина самого
# MAVProxy/SITL; живе, поки живий цей скрипт, вимикається разом з ним (trap).
"$REPO_ROOT/local/push-logs.sh" &
PUSH_LOGS_PID=$!
trap 'kill "$PUSH_LOGS_PID" 2>/dev/null || true' EXIT

SIM_VEHICLE_ARGS=(-v ArduPlane --frame plane -M plane --console --map)
if [ -n "${FLIGHTGEAR_HOST:-}" ]; then
  echo "== FlightGear: FDM-вивід на $FLIGHTGEAR_HOST:5503 (--enable-fgview) =="
  SIM_VEHICLE_ARGS+=(--enable-fgview -A "--fg=$FLIGHTGEAR_HOST")
fi

echo "== SITL ArduPlane + MAVProxy (keyboard_adapter + horizon модулями) =="
echo "   .BIN та .tlog: $LOGDIR (push-logs.sh у фоні, pid $PUSH_LOGS_PID)"
cd "$SITL_DIR/ArduPlane"
sim_vehicle.py "${SIM_VEHICLE_ARGS[@]}" \
  --mavproxy-args "--load-module keyboard_adapter --load-module horizon --logfile $TLOG"

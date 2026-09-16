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
# FBWA + armed, docs/host-prerequisites.md крок 3).
# Без sudo, повторюваний — викликати перед кожним польотом, після одноразового
# ./local/provision.sh.
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

# Прийняти SSH host key VPS ДО старту push-logs.sh у фоні — інакше перший
# rsync/ssh застрягає на інтерактивному "are you sure you want to continue
# connecting?" просто посеред виводу MAVProxy в тому ж терміналі. Best-effort
# (не валимо запуск польоту, якщо VPS/WireGuard зараз недоступні — push-logs.sh
# сам ретраїть при кожному новому файлі).
VPS_WG_HOST="${VPS_WG_HOST:-10.10.0.1}"
VPS_USER="${VPS_USER:-root}"
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=3 \
  "$VPS_USER@$VPS_WG_HOST" true 2>/dev/null || true

# Автоматична доставка логів на VPS (RND-254, критерій приймання — не dev-
# зручність) — окремий фоновий процес (local/push-logs.sh), не частина самого
# MAVProxy/SITL; живе, поки живий цей скрипт, вимикається разом з ним (trap).
"$REPO_ROOT/local/push-logs.sh" &
PUSH_LOGS_PID=$!
trap 'kill "$PUSH_LOGS_PID" 2>/dev/null || true' EXIT

echo "== SITL ArduPlane + MAVProxy (keyboard_adapter + horizon модулями) =="
echo "   .BIN та .tlog: $LOGDIR (push-logs.sh у фоні, pid $PUSH_LOGS_PID)"
cd "$SITL_DIR/ArduPlane"
sim_vehicle.py -v ArduPlane --frame plane -M plane --console --map \
  --mavproxy-args "--load-module keyboard_adapter --load-module horizon --logfile $TLOG"

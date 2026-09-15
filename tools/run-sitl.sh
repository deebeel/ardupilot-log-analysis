#!/usr/bin/env bash
# Піднімає SITL ArduPlane (MAVProxy --console --map — GCS і 2D-візуалізатор одним
# рішенням, CLAUDE.md) разом з keyboard-adapter. Без sudo, повторюваний — викликати
# перед кожним польотом, після одноразового ./tools/prereqs.sh.
#
# Ctrl+C (або вихід із SITL) зупиняє keyboard-adapter теж — trap на EXIT.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITL_DIR="$REPO_ROOT/.sitl"
# pynput — X11 global-grab (дефолт); evdev — Xorg і Wayland однаково, потребує
# групи input (./tools/prereqs.sh). Див. docs/host-prerequisites.md.
KEYBOARD_BACKEND="${KEYBOARD_BACKEND:-pynput}"

if [ ! -d "$SITL_DIR/ArduPlane" ]; then
  echo "$SITL_DIR не знайдено — спочатку ./tools/prereqs.sh" >&2
  exit 1
fi

KEYBOARD_PID=""
cleanup() {
  if [ -n "$KEYBOARD_PID" ] && kill -0 "$KEYBOARD_PID" 2>/dev/null; then
    echo "Зупиняю keyboard-adapter..."
    kill "$KEYBOARD_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "== keyboard-adapter (фон, backend=${KEYBOARD_BACKEND}) =="
(
  cd "$REPO_ROOT/tools/keyboard_adapter"
  uv sync >/dev/null
  exec uv run keyboard-adapter --connect udp:127.0.0.1:14550 --input-backend "$KEYBOARD_BACKEND"
) &
KEYBOARD_PID=$!

echo "== SITL ArduPlane (передній план — Ctrl+C зупиняє обидва процеси) =="
cd "$SITL_DIR/ArduPlane"
sim_vehicle.py -v ArduPlane --frame plane -M plane --console --map

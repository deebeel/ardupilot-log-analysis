#!/usr/bin/env bash
# Одноразовий провіжн SITL-хоста (Ubuntu VM/bare-metal). Клонує ОФІЦІЙНИЙ апстрім
# ArduPilot (не форк) у `.sitl/` — гітignored локальна тека, той самий патерн, що
# `assets/`/`data/`/`worktrees/` — і ставить усі системні залежності одним прогоном.
#
# Один sudo-пароль замість розкиданих кроків: `install-prereqs-ubuntu.sh` (сам
# ArduPilot-скрипт) викликає sudo ВСЕРЕДИНІ себе, без обгортки — тому кешуємо
# credentials (`sudo -v`) на самому початку, щоб він і решта кроків нижче не
# перепитували пароль кожен окремо.
#
# Ідемпотентний: повторний прогін безпечний (клон/checkout/apt install/групу
# перевіряють стан перед дією).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITL_DIR="$REPO_ROOT/.sitl"
# Серія тегів Plane-4.6, не гілка — звірити актуальний останній 4.6.x:
#   git -C .sitl tag -l "Plane-4.6.*" --sort=-v:refname | head -1
ARDUPILOT_TAG="${ARDUPILOT_TAG:-Plane-4.6.3}"

sudo -v

echo "== ArduPilot (.sitl/): клон офіційного апстріму + тег ${ARDUPILOT_TAG} =="
if [ ! -d "$SITL_DIR/.git" ]; then
  git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$SITL_DIR"
else
  echo ".sitl/ вже клоновано — пропускаю clone, лише fetch/checkout."
fi
git -C "$SITL_DIR" fetch --tags
git -C "$SITL_DIR" checkout "$ARDUPILOT_TAG"
git -C "$SITL_DIR" submodule update --init --recursive

echo "== ArduPilot install-prereqs (важкий, sudo викликає сам усередині) =="
"$SITL_DIR/Tools/environment_install/install-prereqs-ubuntu.sh" -y

# python3-wxgtk4.0 — для MAVProxy-модуля `horizon` (авіагоризонт, run-sitl.sh).
# Саме apt-пакет (не `pip3 install wxPython`): PyPI не публікує прекомпільовані
# wheel-и wxPython під linux/aarch64 (наша VM — arm64), тож pip зібрав би його з
# джерела — довго й ще одна залежність на компілятор поза тим, що вже тягне
# ArduPilot. apt ставить готовий бінарний пакет у system dist-packages, який
# MAVProxy (без venv, --user pip) бачить нарівні з --user-пакетами нижче.
echo "== Додаткові системні пакети (не ArduPilot-специфіка): WireGuard-клієнт, доставка логів, =="
echo "== GUI-тулкіт для MAVProxy-модуля horizon =="
sudo apt-get update
sudo apt-get install -y wireguard-tools rsync openssh-client git-lfs python3-wxgtk4.0

echo "== Група input (keyboard-adapter --input-backend evdev) =="
if id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  echo "$USER вже в групі input"
else
  sudo usermod -aG input "$USER"
  echo "Додано $USER до групи input — потрібен релогін (вийти й зайти знову), щоб застосувалось."
fi

# keyboard-adapter вантажиться MAVProxy-модулем (mavproxy_keyboard_adapter.py, у
# процесі MAVProxy — CLAUDE.md), не окремим процесом з власним uv-venv. Тому
# evdev має стояти в ТОМУ Ж Python-оточенні, де install-prereqs-ubuntu.sh щойно
# поставив саму MAVProxy (--user, без venv) — інакше `--load-module
# keyboard_adapter` впаде на ImportError. Лише evdev (не pynput — той вимагав би
# Xorg-сесії, а evdev працює однаково на Xorg і Wayland, тож для єдиного
# продакшн-шляху сенсу тримати другий бекенд нема). Сам пакет keyboard_adapter/
# і шим mavproxy_keyboard_adapter.py окремо не встановлюються — run-sitl.sh
# додає tools/keyboard_adapter/src у PYTHONPATH MAVProxy напряму.
echo "== evdev в оточення MAVProxy (для keyboard-adapter-модуля) =="
pip3 install --user --upgrade evdev

cat <<EOF

Готово. .sitl/ на тезі ${ARDUPILOT_TAG}, системні залежності встановлені.
Якщо групу input щойно додано — релогін, тоді:
  ./tools/run-sitl.sh
EOF

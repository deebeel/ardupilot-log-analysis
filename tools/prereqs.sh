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

echo "== Додаткові системні пакети (не ArduPilot-специфіка): WireGuard-клієнт, доставка логів =="
sudo apt-get update
sudo apt-get install -y wireguard-tools rsync openssh-client git-lfs

echo "== Група input (keyboard-adapter --input-backend evdev) =="
if id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  echo "$USER вже в групі input"
else
  sudo usermod -aG input "$USER"
  echo "Додано $USER до групи input — потрібен релогін (вийти й зайти знову), щоб застосувалось."
fi

cat <<EOF

Готово. .sitl/ на тезі ${ARDUPILOT_TAG}, системні залежності встановлені.
Якщо групу input щойно додано — релогін, тоді:
  ./tools/run-sitl.sh
EOF

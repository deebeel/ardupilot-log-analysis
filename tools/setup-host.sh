#!/usr/bin/env bash
# Один прогін на свіжій Ubuntu VM/bare-metal перед SITL — усі кроки, що потребують
# sudo, зібрані тут, щоб `sudo`-пароль питався один раз, а не розкидано по README.
# Не покриває `Tools/environment_install/install-prereqs-ubuntu.sh` (крок 3
# docs/host-prerequisites.md) — це власний скрипт ArduPilot, запускається окремо
# після клону репозиторію ardupilot.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== apt: системні залежності =="
sudo apt update
sudo apt install -y git python3-pip python3-dev python3-venv \
  build-essential libtool libxml2-dev libxslt1-dev python3-matplotlib \
  wireguard-tools rsync openssh-client git-lfs

echo "== група input (для keyboard-адаптера, --input-backend evdev) =="
make -C "$REPO_ROOT" setup-input-group

echo "Готово. Якщо група input щойно додана — вийти з сесії й зайти знову."

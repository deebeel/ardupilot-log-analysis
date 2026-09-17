#!/usr/bin/env bash
# Одноразовий провіжн SITL-хоста (Ubuntu VM/bare-metal). Той самий скрипт-патерн
# і та сама назва файлу, що на VPS (vps/provision.sh) — обидва провіжни
# запускаються з клона репозиторія на своєму хості, жодних кроків з робочої
# машини. Клонує ОФІЦІЙНИЙ апстрім ArduPilot (не форк) у `.sitl/` — гітignored
# локальна тека, той самий патерн, що `assets/`/`data/`/`worktrees/` — і ставить
# усі системні залежності одним прогоном.
#
# Один sudo-пароль замість розкиданих кроків: `install-prereqs-ubuntu.sh` (сам
# ArduPilot-скрипт) викликає sudo ВСЕРЕДИНІ себе, без обгортки — тому кешуємо
# credentials (`sudo -v`) на самому початку, щоб він і решта кроків нижче не
# перепитували пароль кожен окремо.
#
# WireGuard тут НЕ налаштовується — окремий крок, `local/setup-wireguard.sh`
# (дивись цей файл): цей скрипт лише ставить `wireguard-tools` як пакет,
# піднімати сам тунель — робота іншого скрипта.
#
# Ідемпотентний: повторний прогін безпечний (клон/checkout/apt install/групу
# перевіряють стан перед дією).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITL_DIR="$REPO_ROOT/.sitl"
# Серія тегів Plane-4.6, не гілка — звірити актуальний останній 4.6.x (без
# повного клону, лише список тегів з віддаленого репозиторія):
#   git ls-remote --tags https://github.com/ArduPilot/ardupilot.git 'refs/tags/Plane-4.6.*' | sort -V | tail -1
ARDUPILOT_TAG="${ARDUPILOT_TAG:-Plane-4.6.3}"

sudo -v

# Shallow-клон САМЕ потрібного тега (--depth 1 --branch), не всієї історії
# репозиторія (в ArduPilot вона величезна — десятки тисяч комітів, сотні
# тегів) і не всіх submodule-ів на повну глибину (--shallow-submodules).
# Економить і час, і диск; для збірки SITL повна історія не потрібна взагалі.
echo "== ArduPilot (.sitl/): shallow-клон офіційного апстріму на тег ${ARDUPILOT_TAG} =="
if [ ! -d "$SITL_DIR/.git" ]; then
  git clone --recurse-submodules --shallow-submodules --depth 1 \
    --branch "$ARDUPILOT_TAG" \
    https://github.com/ArduPilot/ardupilot.git "$SITL_DIR"
else
  CURRENT_TAG="$(git -C "$SITL_DIR" describe --tags --exact-match 2>/dev/null || true)"
  if [ "$CURRENT_TAG" = "$ARDUPILOT_TAG" ]; then
    echo ".sitl/ вже на тезі ${ARDUPILOT_TAG} — пропускаю."
  else
    echo ".sitl/ на іншому тезі (${CURRENT_TAG:-невідомо}) — перетягую ${ARDUPILOT_TAG} (shallow)."
    git -C "$SITL_DIR" fetch --depth 1 origin tag "$ARDUPILOT_TAG"
    git -C "$SITL_DIR" checkout "$ARDUPILOT_TAG"
    git -C "$SITL_DIR" submodule update --init --recursive --depth 1
  fi
fi

echo "== ArduPilot install-prereqs (важкий, sudo викликає сам усередині) =="
"$SITL_DIR/Tools/environment_install/install-prereqs-ubuntu.sh" -y

echo "== Додаткові системні пакети (не ArduPilot-специфіка): WireGuard-клієнт, доставка логів =="
sudo apt-get update
# inotify-tools — local/push-logs.sh стежить за закриттям .BIN (той самий принцип,
# що й watcher на боці парсера: реагувати на "закрито", не на частково записаний
# файл), щоб
# штовхати на VPS лише завершені файли, не частково записані.
sudo apt-get install -y wireguard-tools rsync openssh-client git-lfs inotify-tools

echo "== Група input (keyboard-adapter --input-backend evdev) =="
if id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  echo "$USER вже в групі input"
else
  sudo usermod -aG input "$USER"
  echo "Додано $USER до групи input — потрібен релогін (вийти й зайти знову), щоб застосувалось."
fi

# keyboard-adapter вантажиться MAVProxy-модулем (mavproxy_keyboard_adapter.py, у
# процесі MAVProxy — CLAUDE.md), не окремим процесом з власним uv-venv. Тому
# evdev має стояти в ТОМУ Ж Python-оточенні, де сама MAVProxy — а це
# `~/venv-ardupilot` (install-prereqs-ubuntu.sh: `python3 -m venv
# --system-site-packages`), не системний/`--user` pip3. Живцем перевірено: на
# Ubuntu 24.04 системного pip3 навіть немає (PEP 668), лише venv-івський. Лише
# evdev (не pynput — той вимагав би Xorg-сесії, а evdev працює однаково на Xorg
# і Wayland, тож для єдиного продакшн-шляху сенсу тримати другий бекенд нема).
# Сам пакет keyboard_adapter/ і шим mavproxy_keyboard_adapter.py окремо не
# встановлюються — run-sitl.sh додає local/keyboard_adapter/src у PYTHONPATH.
echo "== evdev у venv-ardupilot (те саме Python-оточення, де сам MAVProxy) =="
VENV_PIP="$HOME/venv-ardupilot/bin/pip3"
if [ -x "$VENV_PIP" ]; then
  "$VENV_PIP" install --upgrade evdev
else
  echo "$VENV_PIP не знайдено — install-prereqs-ubuntu.sh не створив venv-ardupilot? Ставлю --user як запасний варіант." >&2
  pip3 install --user --upgrade evdev
fi

echo "== Перевірка: чи застосувалась група input (без цього evdev не працюватиме) =="
if id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  echo "OK: $USER у групі input — relogin (якщо був потрібен) уже застосувався."
else
  echo "УВАГА: $USER ще НЕ в групі input у поточній сесії — вийти й зайти знову (або 'newgrp input'), інакше keyboard_adapter впаде на правах доступу до /dev/input." >&2
fi

cat <<EOF

Готово. .sitl/ на тезі ${ARDUPILOT_TAG}, системні залежності встановлені.
Наступний крок — WireGuard-тунель (README.md, крок 3):
  ./local/setup-wireguard.sh
EOF

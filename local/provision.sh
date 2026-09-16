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
# WireGuard-клієнт налаштовується автоматично настільки, наскільки це можливо
# без ручного кроку: якщо передано SERVER_WG_PUBKEY (+опційно VPS_ENDPOINT) —
# скрипт сам згенерує клієнтський ключ (якщо ще нема) і підніме `wg0`, без
# ручного редагування wg0.conf. Обмін самими публічними ключами між двома
# окремими машинами — той єдиний крок, який фізично не можна автоматизувати
# одним скриптом (немає спільного каналу): SITL-хост має власний, деплой на VPS
# запускається окремо (vps/provision.sh) з ключем звідси.
#
# Ідемпотентний: повторний прогін безпечний (клон/checkout/apt install/групу/
# wg0.conf перевіряють стан перед дією).
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
# inotify-tools — local/push-logs.sh стежить за закриттям .BIN (watchdog on_closed,
# той самий принцип, що й на боці парсера, docs/implementation-plan.md §3), щоб
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

echo "== WireGuard-клієнт: ключі (якщо ще нема) =="
WG_PRIVATE_KEY_FILE="$HOME/.wg-privatekey"
WG_PUBLIC_KEY_FILE="$HOME/.wg-publickey"
if [ ! -f "$WG_PRIVATE_KEY_FILE" ]; then
  wg genkey | tee "$WG_PRIVATE_KEY_FILE" | wg pubkey > "$WG_PUBLIC_KEY_FILE"
  chmod 600 "$WG_PRIVATE_KEY_FILE"
  echo "Згенеровано новий ключ клієнта."
else
  echo "Ключ клієнта вже є (повторний прогін) — лишаю як є."
fi
echo "Публічний ключ клієнта (передати на VPS-провіжн, vps/provision.sh):"
cat "$WG_PUBLIC_KEY_FILE"

# SERVER_WG_PUBKEY — публічний ключ, який виводить vps/provision.sh на VPS.
# Без нього неможливо скласти [Peer] — тож без цієї змінної просто виводимо
# свій ключ вище і пропускаємо власне піднімання інтерфейсу, не падаємо: цей
# скрипт мусить лишатись прогонним і тоді, коли VPS-ключа ще нема.
if [ -n "${SERVER_WG_PUBKEY:-}" ]; then
  VPS_ENDPOINT="${VPS_ENDPOINT:?потрібен VPS_ENDPOINT=<ip_або_домен_vps>:51820 разом із SERVER_WG_PUBKEY}"
  echo "== WireGuard-клієнт: wg0.conf (SERVER_WG_PUBKEY передано) =="
  sudo mkdir -p /etc/wireguard
  sudo tee /etc/wireguard/wg0.conf >/dev/null <<EOF
[Interface]
Address = 10.10.0.2/24
PrivateKey = $(cat "$WG_PRIVATE_KEY_FILE")

[Peer]
PublicKey = ${SERVER_WG_PUBKEY}
Endpoint = ${VPS_ENDPOINT}
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
EOF
  sudo chmod 600 /etc/wireguard/wg0.conf
  sudo systemctl enable wg-quick@wg0
  # restart, не start — той самий мотив, що на VPS: повторний прогін з іншим
  # SERVER_WG_PUBKEY/VPS_ENDPOINT (переліт VPS) теж підхопиться.
  sudo systemctl restart wg-quick@wg0
  sudo wg show wg0
else
  echo "SERVER_WG_PUBKEY не передано — інтерфейс wg0 НЕ піднімаю. Прогнати ще раз:"
  echo "  SERVER_WG_PUBKEY=<з vps/provision.sh> VPS_ENDPOINT=<ip_або_домен>:51820 ./local/provision.sh"
fi

cat <<EOF

Готово. .sitl/ на тезі ${ARDUPILOT_TAG}, системні залежності встановлені.
Якщо групу input щойно додано — релогін, тоді:
  ./local/run-sitl.sh
EOF

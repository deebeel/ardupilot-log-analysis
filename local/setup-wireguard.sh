#!/usr/bin/env bash
# SITL-хост: піднімає клієнтську частину WireGuard-тунелю до VPS. Симетричний
# файл до vps/setup-wireguard.sh (сервер) — та сама назва з обох боків.
#
# Два режими:
#
# 1) Автоматичний (є SSH з SITL-хоста на VPS):
#      VPS_HOST=root@<vps> ./local/setup-wireguard.sh
#    Сам генерує ключ тут, ходить по SSH і викликає той самий
#    vps/setup-wireguard.sh з клона репозиторія на VPS (без дублювання логіки
#    в цьому файлі), забирає звідти публічний ключ сервера і сам піднімає wg0
#    тут. Заодно ставить SSH-ключ (~/.ssh/id_ed25519) в authorized_keys на
#    VPS і приймає host key 10.10.0.1 — щоб push-logs.sh (local/run-sitl.sh)
#    потім конектився на root@10.10.0.1 без пароля/prompt'ів. Жодного ручного
#    кроку.
#
# 2) Ручний (SSH до VPS нема — інша мережа, фаєрвол, VPS адмінить хтось
#    інший): той самий тунель усе одно потрібен (критерій приймання тікета),
#    просто обмін публічними ключами відбувається людиною, не скриптом:
#      а) тут:    ./local/setup-wireguard.sh
#                  -> друкує публічний ключ клієнта, wg0 ще НЕ піднятий
#      б) на VPS (яким завгодно доступом): CLIENT_WG_PUBKEY=<з а> ./vps/setup-wireguard.sh
#                  -> друкує публічний ключ сервера
#      в) тут:    SERVER_WG_PUBKEY=<з б> VPS_ENDPOINT=<ip_або_домен>:51820 ./local/setup-wireguard.sh
#                  -> тепер піднімає wg0
#    У цьому режимі немає SSH-доступу для автоматизації push-logs.sh — SSH-
#    ключ (`~/.ssh/id_ed25519.pub`) для root@10.10.0.1 треба додати в
#    authorized_keys на VPS вручну (яким завгодно доступом), інакше перший
#    rsync у push-logs.sh питатиме пароль.
#
# VPS_REPO_DIR (лише для автоматичного режиму) — назва теки клона репозиторія
# в $HOME на VPS; за замовчуванням береться назва локальної теки (той самий
# `git clone <URL>` дає ту саму назву на обох хостах, якщо не перейменовували).
#
# Ідемпотентний в обох режимах.
set -euo pipefail

WG_PRIVATE_KEY_FILE="$HOME/.wg-privatekey"
WG_PUBLIC_KEY_FILE="$HOME/.wg-publickey"

echo "== Локальний (SITL) ключ клієнта: якщо ще нема — генерую =="
if [ ! -f "$WG_PRIVATE_KEY_FILE" ]; then
  wg genkey | tee "$WG_PRIVATE_KEY_FILE" | wg pubkey > "$WG_PUBLIC_KEY_FILE"
  chmod 600 "$WG_PRIVATE_KEY_FILE"
else
  echo "Ключ клієнта вже є — лишаю як є."
fi
CLIENT_PUBKEY="$(cat "$WG_PUBLIC_KEY_FILE")"
echo "Публічний ключ клієнта: $CLIENT_PUBKEY"

if [ -n "${VPS_HOST:-}" ]; then
  # Автоматичний режим: SSH є, ганяти ключі копіпастою між терміналами нема сенсу.
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  VPS_ENDPOINT="${VPS_ENDPOINT:-${VPS_HOST#*@}:51820}"
  VPS_REPO_DIR="${VPS_REPO_DIR:-$(basename "$REPO_ROOT")}"
  echo "== VPS_HOST передано — піднімаю сервер по SSH (~/${VPS_REPO_DIR}/vps/setup-wireguard.sh) =="
  SERVER_PUBKEY="$(ssh "$VPS_HOST" "CLIENT_WG_PUBKEY='${CLIENT_PUBKEY}' ~/${VPS_REPO_DIR}/vps/setup-wireguard.sh")"
elif [ -n "${SERVER_WG_PUBKEY:-}" ]; then
  # Ручний режим: ключ сервера вже отримано десь інакше (крок "б" вище).
  SERVER_PUBKEY="$SERVER_WG_PUBKEY"
  VPS_ENDPOINT="${VPS_ENDPOINT:?потрібен VPS_ENDPOINT=<ip_або_домен_vps>:51820 разом із SERVER_WG_PUBKEY}"
else
  cat <<EOF

Ні VPS_HOST (автоматичний режим), ні SERVER_WG_PUBKEY (ручний режим) не
передано — wg0 НЕ піднімаю. Публічний ключ клієнта вище передати на VPS
(CLIENT_WG_PUBKEY=... ./vps/setup-wireguard.sh) і прогнати цей скрипт ще раз
із SERVER_WG_PUBKEY+VPS_ENDPOINT — або одразу VPS_HOST=root@<vps>, якщо є SSH.
EOF
  exit 0
fi

echo "Публічний ключ сервера: $SERVER_PUBKEY"

echo "== Локально: wg0.conf з публічним ключем сервера, Endpoint=${VPS_ENDPOINT} =="
sudo mkdir -p /etc/wireguard
sudo tee /etc/wireguard/wg0.conf >/dev/null <<EOF
[Interface]
Address = 10.10.0.2/24
PrivateKey = $(cat "$WG_PRIVATE_KEY_FILE")

[Peer]
PublicKey = ${SERVER_PUBKEY}
Endpoint = ${VPS_ENDPOINT}
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
EOF
sudo chmod 600 /etc/wireguard/wg0.conf
sudo systemctl enable wg-quick@wg0
sudo systemctl restart wg-quick@wg0
sudo wg show wg0

echo "== Перевірка тунелю =="
if ping -c3 -W2 10.10.0.1 >/dev/null 2>&1; then
  echo "OK: 10.10.0.1 (VPS) відповідає крізь тунель."
else
  echo "ПОМИЛКА: 10.10.0.1 не відповідає — 'sudo wg show wg0' тут і на VPS, ufw 51820/udp." >&2
  exit 1
fi

# push-logs.sh (local/run-sitl.sh) ходить по SSH на root@10.10.0.1 без нагляду
# людини (фоновий rsync) — без ключа перший конект або зависав би на паролі
# (успадкований термінал MAVProxy), або (при ssh-batch) просто мовчки фейлився
# б назавжди. Лише автоматичний режим: тут уже є SSH-доступ через $VPS_HOST,
# тож і ключ, і host key 10.10.0.1 можна поставити без ручного кроку.
# Ідемпотентно: ssh-keygen -N "" не перезаписує існуючий ключ без -y/force,
# authorized_keys-рядок додається лише якщо його там ще нема.
if [ -n "${VPS_HOST:-}" ]; then
  echo "== SSH-ключ для push-logs.sh (root@10.10.0.1, без пароля) =="
  SSH_KEY_FILE="$HOME/.ssh/id_ed25519"
  if [ ! -f "$SSH_KEY_FILE" ]; then
    ssh-keygen -t ed25519 -N "" -f "$SSH_KEY_FILE" -C "push-logs@$(hostname)"
  fi
  ssh-keyscan -H 10.10.0.1 >> "$HOME/.ssh/known_hosts" 2>/dev/null
  SSH_PUBKEY="$(cat "${SSH_KEY_FILE}.pub")"
  ssh "$VPS_HOST" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -qxF '${SSH_PUBKEY}' ~/.ssh/authorized_keys 2>/dev/null || echo '${SSH_PUBKEY}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
  if ssh -o BatchMode=yes -o ConnectTimeout=3 root@10.10.0.1 true 2>/dev/null; then
    echo "OK: root@10.10.0.1 доступний по SSH без пароля."
  else
    echo "ПОПЕРЕДЖЕННЯ: root@10.10.0.1 по SSH без пароля не спрацював — push-logs.sh питатиме пароль." >&2
  fi
fi

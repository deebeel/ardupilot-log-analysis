#!/usr/bin/env bash
# SITL-хост: піднімає клієнтську частину WireGuard-тунелю до VPS. Симетричний
# файл до vps/setup-wireguard.sh (сервер) — та сама назва з обох боків.
#
# Лише ручний обмін ключами — SITL-хост НІКОЛИ не ходить по SSH на публічну
# адресу VPS (лише крізь сам WireGuard-тунель, після його підняття, і то лише
# push-logs.sh на root@10.10.0.1). Раніше був ще "автоматичний" режим
# (VPS_HOST=... сам ходив по SSH на публічну адресу VPS) — прибрано: він
# порушував цей же принцип під час самого бутстрапу тунелю.
#
#   а) тут:    ./local/setup-wireguard.sh
#               -> друкує публічний ключ клієнта (WireGuard) і публічний
#                  SSH-ключ push-logs.sh, wg0 ще НЕ піднятий
#   б) на VPS (яким завгодно доступом — консоль хостера, той самий термінал,
#      де вже виконувався vps/provision.sh): CLIENT_WG_PUBKEY=<з а>
#      ./vps/setup-wireguard.sh
#               -> друкує публічний ключ сервера; вивід друкує й підказку
#                  додати SSH-ключ push-logs.sh (з "а") у authorized_keys —
#                  зробити це тут же, ще ДО (в) нижче
#   в) тут:    SERVER_WG_PUBKEY=<з б> VPS_ENDPOINT=<ip_або_домен>:51820 ./local/setup-wireguard.sh
#               -> тепер піднімає wg0 і перевіряє root@10.10.0.1 (push-logs.sh)
#
# Ідемпотентний.
set -euo pipefail

WG_PRIVATE_KEY_FILE="$HOME/.wg-privatekey"
WG_PUBLIC_KEY_FILE="$HOME/.wg-publickey"
SSH_KEY_FILE="$HOME/.ssh/id_ed25519"

echo "== Локальний (SITL) ключ клієнта WireGuard: якщо ще нема — генерую =="
if [ ! -f "$WG_PRIVATE_KEY_FILE" ]; then
  wg genkey | tee "$WG_PRIVATE_KEY_FILE" | wg pubkey > "$WG_PUBLIC_KEY_FILE"
  chmod 600 "$WG_PRIVATE_KEY_FILE"
else
  echo "Ключ клієнта вже є — лишаю як є."
fi
CLIENT_PUBKEY="$(cat "$WG_PUBLIC_KEY_FILE")"
echo "Публічний ключ клієнта (WireGuard): $CLIENT_PUBKEY"

# push-logs.sh (local/run-sitl.sh) ходить по SSH на root@10.10.0.1 (крізь
# тунель, не публічна адреса) без нагляду людини (фоновий rsync) — без ключа
# перший конект зависав би на паролі (успадкований термінал MAVProxy). Ключ
# генерується тут завжди (не лише в автоматичному режимі, якого більше нема),
# а в authorized_keys на VPS його додає людина вручну (крок "б") — SITL сюди
# по SSH на публічну адресу не ходить.
echo "== Локальний SSH-ключ для push-logs.sh: якщо ще нема — генерую =="
if [ ! -f "$SSH_KEY_FILE" ]; then
  ssh-keygen -t ed25519 -N "" -f "$SSH_KEY_FILE" -C "push-logs@$(hostname)"
else
  echo "Ключ уже є — лишаю як є."
fi
SSH_PUBKEY="$(cat "${SSH_KEY_FILE}.pub")"
echo "Публічний SSH-ключ push-logs.sh: $SSH_PUBKEY"

if [ -z "${SERVER_WG_PUBKEY:-}" ]; then
  cat <<EOF

SERVER_WG_PUBKEY не передано — wg0 НЕ піднімаю.

Наступні кроки (вручну, з будь-якого доступу до VPS — не з цього хоста):
  1. Обидва ключі вище передати на VPS одним прогоном:
       CLIENT_WG_PUBKEY='${CLIENT_PUBKEY}' \\
         CLIENT_SSH_PUBKEY='${SSH_PUBKEY}' \\
         ./vps/setup-wireguard.sh
     -> сам додає SSH-ключ у /root/.ssh/authorized_keys і друкує публічний
        ключ сервера (WireGuard).
  2. Прогнати цей скрипт ще раз:
       SERVER_WG_PUBKEY=<з кроку 1> VPS_ENDPOINT=<ip_або_домен_vps>:51820 ./local/setup-wireguard.sh
EOF
  exit 0
fi

VPS_ENDPOINT="${VPS_ENDPOINT:?потрібен VPS_ENDPOINT=<ip_або_домен_vps>:51820 разом із SERVER_WG_PUBKEY}"

echo "== Локально: wg0.conf з публічним ключем сервера, Endpoint=${VPS_ENDPOINT} =="
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
sudo systemctl restart wg-quick@wg0
sudo wg show wg0

echo "== Перевірка тунелю =="
if ping -c3 -W2 10.10.0.1 >/dev/null 2>&1; then
  echo "OK: 10.10.0.1 (VPS) відповідає крізь тунель."
else
  echo "ПОМИЛКА: 10.10.0.1 не відповідає — 'sudo wg show wg0' тут і на VPS, ufw 51820/udp." >&2
  exit 1
fi

# Тепер, коли тунель живий, root@10.10.0.1 (крізь тунель, не публічна
# адреса) — саме той конект, яким користується push-logs.sh. Лише
# інформаційна перевірка: сам ключ у authorized_keys додає людина вручну
# (крок "б" вище), цей скрипт нічого по SSH на VPS не пише.
echo "== Перевірка SSH для push-logs.sh (root@10.10.0.1, крізь тунель) =="
ssh-keyscan -H 10.10.0.1 >> "$HOME/.ssh/known_hosts" 2>/dev/null
if ssh -o BatchMode=yes -o ConnectTimeout=3 root@10.10.0.1 true 2>/dev/null; then
  echo "OK: root@10.10.0.1 доступний по SSH без пароля."
else
  echo "ПОПЕРЕДЖЕННЯ: root@10.10.0.1 по SSH без пароля не спрацював — переконайся, що публічний ключ push-logs.sh (вище) доданий у /root/.ssh/authorized_keys на VPS." >&2
fi

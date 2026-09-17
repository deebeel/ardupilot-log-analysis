#!/usr/bin/env bash
# VPS: піднімає серверну частину WireGuard. Симетричний файл до
# local/setup-wireguard.sh (SITL-хост) — та сама назва з обох боків, як і
# provision.sh.
#
# Лише ручний режим — SITL-хост НІКОЛИ не ходить по SSH на публічну адресу
# VPS (лише крізь сам тунель, після його підняття). Запускається тут будь-яким
# доступом, який є (консоль хостера, окремий адмінський SSH-ключ тощо):
#   CLIENT_WG_PUBKEY=<публічний_WireGuard-ключ_з_local/setup-wireguard.sh> \
#     CLIENT_SSH_PUBKEY=<публічний_SSH-ключ_push-logs.sh_з_local/setup-wireguard.sh> \
#     ./vps/setup-wireguard.sh
# Востаннім рядком у stdout друкує публічний ключ сервера — саме його, без
# прикрас (решта виводу — в stderr), щоб можна було забрати командою й
# передати на SITL-хост вручну (SERVER_WG_PUBKEY+VPS_ENDPOINT для
# local/setup-wireguard.sh). CLIENT_SSH_PUBKEY (опційний, але потрібен, щоб
# push-logs.sh на SITL-хості потім конектився на root@10.10.0.1 без пароля) —
# додається в /root/.ssh/authorized_keys тут же, тим самим доступом.
#
# Ідемпотентний: повторний прогін не створює нового ключа сервера, якщо вже
# є, і просто перезаписує/перезапускає wg0 (напр. з іншим CLIENT_WG_PUBKEY,
# якщо SITL-хост перелетів); CLIENT_SSH_PUBKEY додається в authorized_keys
# лише якщо його там ще нема.
set -euo pipefail

: "${CLIENT_WG_PUBKEY:?потрібен CLIENT_WG_PUBKEY=<публічний ключ SITL-хоста>}"

command -v wg >/dev/null 2>&1 || {
  echo "wg не знайдено — apt install wireguard-tools (чи спочатку ./vps/provision.sh)" >&2
  exit 1
}

# Привілейовані команди — через sudo ПОКОМАНДНО, не через запуск усього
# скрипта під sudo/root: `sudo ./vps/setup-wireguard.sh` інакше обрізає
# CLIENT_WG_PUBKEY з середовища (sudo за замовчуванням чистить env), а сам
# скрипт має лишатись запускним звичайним користувачем з sudo-правами (як і
# local/setup-wireguard.sh на іншому боці).

echo "== ufw: 51820/udp =="  >&2
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 51820/udp >&2
fi

echo "== Ключ сервера (якщо ще нема) ==" >&2
sudo mkdir -p /etc/wireguard
sudo chmod 700 /etc/wireguard
if sudo test -f /etc/wireguard/server.key; then
  echo "Ключ сервера вже є — лишаю як є." >&2
else
  wg genkey | sudo tee /etc/wireguard/server.key >/dev/null
  sudo chmod 600 /etc/wireguard/server.key
fi
sudo sh -c 'wg pubkey < /etc/wireguard/server.key > /etc/wireguard/server.pub'

echo "== wg0.conf з переданим CLIENT_WG_PUBKEY ==" >&2
SERVER_PRIVATE_KEY="$(sudo cat /etc/wireguard/server.key)"
sudo tee /etc/wireguard/wg0.conf >/dev/null <<EOF
[Interface]
Address = 10.10.0.1/24
ListenPort = 51820
PrivateKey = ${SERVER_PRIVATE_KEY}

[Peer]
PublicKey = ${CLIENT_WG_PUBKEY}
AllowedIPs = 10.10.0.2/32
EOF
sudo chmod 600 /etc/wireguard/wg0.conf
sudo systemctl enable wg-quick@wg0 >&2
# restart, не start — щоб повторний прогін з ІНШИМ CLIENT_WG_PUBKEY (переліт
# SITL-хоста) теж підхопився, а не лишив старий peer у вже запущеному інтерфейсі.
sudo systemctl restart wg-quick@wg0 >&2
sudo wg show wg0 >&2

if [ -n "${CLIENT_SSH_PUBKEY:-}" ]; then
  echo "== CLIENT_SSH_PUBKEY: додаю в /root/.ssh/authorized_keys (push-logs.sh) ==" >&2
  sudo mkdir -p /root/.ssh
  sudo chmod 700 /root/.ssh
  if ! sudo grep -qxF "$CLIENT_SSH_PUBKEY" /root/.ssh/authorized_keys 2>/dev/null; then
    echo "$CLIENT_SSH_PUBKEY" | sudo tee -a /root/.ssh/authorized_keys >/dev/null
  fi
  sudo chmod 600 /root/.ssh/authorized_keys
fi

# Востаннім рядком stdout — САМЕ ключ, нічого більше: викликач (людина вручну,
# чи local/setup-wireguard.sh по SSH) забирає його звідси командною підстановкою.
sudo cat /etc/wireguard/server.pub

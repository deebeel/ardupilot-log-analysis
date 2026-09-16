#!/usr/bin/env bash
# VPS: піднімає серверну частину WireGuard. Симетричний файл до
# local/setup-wireguard.sh (SITL-хост) — та сама назва з обох боків, як і
# provision.sh.
#
# Ручний режим (немає SSH з SITL-хоста сюди — інша мережа, фаєрвол, VPS
# адмінить хтось інший): запускається тут будь-яким доступом, який є
# (консоль хостера, окремий адмінський SSH-ключ тощо):
#   CLIENT_WG_PUBKEY=<публічний_ключ_з_local/setup-wireguard.sh> ./vps/setup-wireguard.sh
# Востаннім рядком у stdout друкує публічний ключ сервера — саме його, без
# прикрас (решта виводу — в stderr), щоб можна було забрати командою й
# передати на SITL-хост вручну (SERVER_WG_PUBKEY+VPS_ENDPOINT для
# local/setup-wireguard.sh).
#
# Автоматичний режим: коли на SITL-хості є SSH до VPS, local/setup-wireguard.sh
# сам викликає цей самий файл по SSH (з клона репозиторія на VPS) — тоді
# нічого запускати тут вручну не треба, обмін ключами відбувається сам.
#
# Ідемпотентний: повторний прогін не створює нового ключа сервера, якщо вже
# є, і просто перезаписує/перезапускає wg0 (напр. з іншим CLIENT_WG_PUBKEY,
# якщо SITL-хост перелетів).
set -euo pipefail

: "${CLIENT_WG_PUBKEY:?потрібен CLIENT_WG_PUBKEY=<публічний ключ SITL-хоста>}"

command -v wg >/dev/null 2>&1 || {
  echo "wg не знайдено — apt install wireguard-tools (чи спочатку ./vps/provision.sh)" >&2
  exit 1
}

echo "== ufw: 51820/udp =="  >&2
if command -v ufw >/dev/null 2>&1; then
  ufw allow 51820/udp >&2
fi

echo "== Ключ сервера (якщо ще нема) ==" >&2
mkdir -p /etc/wireguard
chmod 700 /etc/wireguard
if [ ! -f /etc/wireguard/server.key ]; then
  wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub
  chmod 600 /etc/wireguard/server.key
else
  echo "Ключ сервера вже є — лишаю як є." >&2
fi

echo "== wg0.conf з переданим CLIENT_WG_PUBKEY ==" >&2
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = 10.10.0.1/24
ListenPort = 51820
PrivateKey = $(cat /etc/wireguard/server.key)

[Peer]
PublicKey = ${CLIENT_WG_PUBKEY}
AllowedIPs = 10.10.0.2/32
EOF
chmod 600 /etc/wireguard/wg0.conf
systemctl enable wg-quick@wg0 >&2
# restart, не start — щоб повторний прогін з ІНШИМ CLIENT_WG_PUBKEY (переліт
# SITL-хоста) теж підхопився, а не лишив старий peer у вже запущеному інтерфейсі.
systemctl restart wg-quick@wg0 >&2
wg show wg0 >&2

# Востаннім рядком stdout — САМЕ ключ, нічого більше: викликач (людина вручну,
# чи local/setup-wireguard.sh по SSH) забирає його звідси командною підстановкою.
cat /etc/wireguard/server.pub

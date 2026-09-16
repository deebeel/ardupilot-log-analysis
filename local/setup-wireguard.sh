#!/usr/bin/env bash
# Піднімає WireGuard-тунель між SITL-хостом (Мережа A) і VPS (Мережа B) —
# ОБИДВА боки, одним запуском, з SITL-хоста.
#
# Раніше кожен бік піднімав лише себе (local/provision.sh + vps/provision.sh),
# а публічні ключі передавались одна одному вручну — цей крок фізично
# доводилось робити, бо два окремі скрипти на двох окремих машинах не мали
# спільного каналу. Тут спільний канал ЄСТЬ: VPS_HOST — той самий SSH, яким
# адмінить сам VPS (клонування репозиторія, provision.sh). Раз доступ уже є —
# немає сенсу ганяти публічні ключі копіпастою між двома терміналами: цей
# скрипт сам генерує ключі на обох боках (свій — тут, серверний — по SSH) і
# сам пише конфіги на обох боках. Ручний обмін ключами більше НЕ потрібен.
#
# Використання (з SITL-хоста, після local/provision.sh і vps/provision.sh):
#   VPS_HOST=root@<vps> ./local/setup-wireguard.sh
#
# VPS_ENDPOINT — публічна адреса VPS для клієнтського Endpoint; за замовчуванням
# беремо хост із VPS_HOST (без користувача) і порт 51820. Перевизначити, якщо
# SSH ходить через інший хост/порт, ніж сам WireGuard-ендпоінт (напр. VPS_HOST
# через bastion, а VPS_ENDPOINT — реальний публічний IP).
#
# Ідемпотентний: повторний прогін не створює нових ключів, якщо вже є, і просто
# перезаписує/перезапускає wg0 на обох боках (напр. якщо VPS_ENDPOINT змінився).
set -euo pipefail

: "${VPS_HOST:?потрібен VPS_HOST=root@<vps> ./local/setup-wireguard.sh}"
VPS_ENDPOINT="${VPS_ENDPOINT:-${VPS_HOST#*@}:51820}"

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

echo "== VPS ($VPS_HOST): ключ сервера — якщо ще нема, генерую по SSH =="
# Один SSH-виклик: генерує ключ лише за потреби (ідемпотентно) і в будь-якому
# разі друкує публічний ключ сервера в stdout — тут його й забираємо.
SERVER_PUBKEY="$(ssh "$VPS_HOST" '
  set -euo pipefail
  mkdir -p /etc/wireguard
  chmod 700 /etc/wireguard
  if [ ! -f /etc/wireguard/server.key ]; then
    wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub
    chmod 600 /etc/wireguard/server.key
  fi
  cat /etc/wireguard/server.pub
')"
echo "Публічний ключ сервера: $SERVER_PUBKEY"

echo "== VPS ($VPS_HOST): wg0.conf з публічним ключем клієнта =="
ssh "$VPS_HOST" "CLIENT_PUBKEY='${CLIENT_PUBKEY}' bash -s" <<'REMOTE'
set -euo pipefail
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = 10.10.0.1/24
ListenPort = 51820
PrivateKey = $(cat /etc/wireguard/server.key)

[Peer]
PublicKey = ${CLIENT_PUBKEY}
AllowedIPs = 10.10.0.2/32
EOF
chmod 600 /etc/wireguard/wg0.conf
systemctl enable wg-quick@wg0
# restart, не start — щоб повторний прогін з ІНШИМ клієнтським ключем (переліт
# SITL-хоста) теж підхопився, а не лишив старий peer у вже запущеному інтерфейсі.
systemctl restart wg-quick@wg0
wg show wg0
REMOTE

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

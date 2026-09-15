#!/usr/bin/env bash
# Одноразовий провіжн чистого VPS (Ubuntu). Запускається ВРУЧНУ один раз на самому
# сервері — не з робочої машини (на відміну від deploy.sh):
#   CLIENT_WG_PUBKEY=<публічний ключ SITL-хоста> ssh root@<vps> 'bash -s' < deploy/provision.sh
#
# CLIENT_WG_PUBKEY — ОБОВ'ЯЗКОВИЙ: без нього немислимо скласти [Peer] у wg0.conf,
# тож скрипт падає одразу, а не лишає WireGuard непіднятим мовчки.
#
# Сертифікат для HTTPS тут НЕ генерується — це свідомо: Caddy сам робить це в
# рантаймі (self-signed для DOMAIN=localhost, або Let's Encrypt для реального
# домену з outbound-доступом), а якщо Сергій дає готові файли — вони підставляються
# в Caddyfile (`tls <cert> <key>`) на кроці deploy.sh, не тут. provision.sh лише
# готує систему (Docker, WireGuard, фаєрвол), не займається сертифікатами.
#
# Ідемпотентний: повторний прогін не ламає вже налаштований сервер (apt install —
# уже сам ідемпотентний; ufw allow повторно не дублює правило; docker/wg —
# перевіряються перед встановленням).
set -euo pipefail

: "${CLIENT_WG_PUBKEY:?потрібен публічний ключ клієнта: CLIENT_WG_PUBKEY=<ключ> ssh root@vps 'bash -s' < provision.sh}"

echo "== apt: Docker Engine + compose plugin, wireguard-tools, ufw =="
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  ARCH="$(dpkg --print-architecture)"
  CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  echo "docker вже встановлено: $(docker --version)"
fi

apt-get install -y wireguard-tools ufw

echo "== ufw: 22 (SSH), 80/443 (HTTP/HTTPS), 51820/udp (WireGuard) =="
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 51820/udp
ufw --force enable

echo "== WireGuard: ключі сервера (якщо ще нема) =="
mkdir -p /etc/wireguard
chmod 700 /etc/wireguard
if [ ! -f /etc/wireguard/server.key ]; then
  wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub
  chmod 600 /etc/wireguard/server.key
  echo "Згенеровано новий ключ сервера."
else
  echo "Ключ сервера вже є (повторний прогін) — лишаю як є."
fi
echo "Публічний ключ сервера (віддати на SITL-хост для Endpoint-конфіга):"
cat /etc/wireguard/server.pub

echo "== WireGuard: wg0.conf з переданим CLIENT_WG_PUBKEY =="
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
systemctl enable wg-quick@wg0
# restart, не start — щоб повторний прогін з ІНШИМ CLIENT_WG_PUBKEY (переліт SITL-хоста)
# теж підхопився, а не лишив старий peer з уже запущеного інтерфейсу.
systemctl restart wg-quick@wg0
wg show wg0

echo "== /srv/app: теки під bind-mount (parser пише, web читає) =="
mkdir -p /srv/app/data/inbox /srv/app/data/results
chown -R 1000:1000 /srv/app/data

cat <<'EOF'

Готово. WireGuard уже піднятий з переданим CLIENT_WG_PUBKEY. Далі:
1. На SITL-хості — Endpoint у клієнтському wg0.conf = публічний ключ сервера
   (вище) + реальна IP/домен цього VPS (deploy/wireguard/wg0-client.conf.example).
2. Скопіювати deploy/compose/* на сервер (deploy.sh зробить це) і DOMAIN у .env.
3. Сертифікат — файлами від Сергія (підставити в Caddyfile) АБО нічого не робити:
   Caddy сам видасть self-signed/Let's Encrypt залежно від DOMAIN. provision.sh
   цим свідомо не займається.
EOF

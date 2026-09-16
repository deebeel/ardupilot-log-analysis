#!/usr/bin/env bash
# Одноразовий провіжн чистого VPS (Ubuntu). Той самий скрипт-патерн і та сама
# назва файлу, що на SITL-хості (local/provision.sh) — запускається ВРУЧНУ з
# клона репозиторія на самому VPS (не з робочої машини):
#   git clone <репозиторій> && cd <репозиторій>
#   CLIENT_WG_PUBKEY=<публічний ключ SITL-хоста> ./vps/provision.sh
#
# CLIENT_WG_PUBKEY — ОБОВ'ЯЗКОВИЙ: без нього немислимо скласти [Peer] у wg0.conf,
# тож скрипт падає одразу, а не лишає WireGuard непіднятим мовчки.
#
# Без сертифікатів: HTTPS/ACME/Let's Encrypt свідомо не піднімаються — Caddy тут
# лише reverse-proxy на звичайному HTTP (80). Сертифікат — коли й якщо
# знадобиться пізніше, окреме питання, не частина цього провіжну.
#
# Образи `parser`/`web` збираються ТУТ ЖЕ, під час провіжну (docker compose
# build прямо з клона репозиторія на VPS) — окремого кроку "зібрати десь і
# перенести" нема: VPS сам amd64, тож ніякого buildx/--platform/крос-збірки не
# треба, а тягнути образ з робочої машини сюди (tar.gz/registry) — зайва
# складність без вигоди, коли можна зібрати прямо там, де він і запускається.
#
# Ідемпотентний: повторний прогін не ламає вже налаштований сервер (apt install —
# уже сам ідемпотентний; ufw allow повторно не дублює правило; docker/wg —
# перевіряються перед встановленням; `docker compose up -d` без змін просто
# підтверджує, що все вже підняте).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${CLIENT_WG_PUBKEY:?потрібен публічний ключ клієнта: CLIENT_WG_PUBKEY=<ключ> ./vps/provision.sh}"

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

echo "== ufw: 22 (SSH), 80 (HTTP, без сертифікатів), 51820/udp (WireGuard) =="
ufw allow 22/tcp
ufw allow 80/tcp
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

echo "== /srv/app/data: теки під bind-mount (parser пише, web читає) =="
mkdir -p /srv/app/data/inbox /srv/app/data/results
chown -R 1000:1000 /srv/app/data

echo "== docker compose: збірка образів (тут, на VPS — той самий amd64) + up -d =="
COMPOSE_DIR="$REPO_ROOT/vps/compose"
DATA_DIR=/srv/app/data docker compose --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" build
DATA_DIR=/srv/app/data docker compose --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" up -d

echo "== Health-check =="
if curl -sf -o /dev/null http://localhost/; then
  echo "OK: http://localhost/ відповідає (Caddy -> web)."
else
  echo "ПОМИЛКА: http://localhost/ не відповідає — 'docker compose ps'/'docker compose logs' у $COMPOSE_DIR." >&2
  exit 1
fi

cat <<'EOF'

Готово. WireGuard піднятий з переданим CLIENT_WG_PUBKEY, parser+web+caddy зібрані
й запущені прямо тут. Далі — на SITL-хості (local/provision.sh з SERVER_WG_PUBKEY
+ VPS_ENDPOINT, публічний ключ сервера виведено вище).

Повторний прогін цього ж скрипта (напр. після зміни коду — git pull) сам
пересобере образи й перезапустить контейнери.
EOF

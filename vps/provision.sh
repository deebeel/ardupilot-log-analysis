#!/usr/bin/env bash
# Одноразовий провіжн чистого VPS (Ubuntu). Той самий скрипт-патерн і та сама
# назва файлу, що на SITL-хості (local/provision.sh) — запускається ВРУЧНУ з
# клона репозиторія на самому VPS (не з робочої машини):
#   git clone <репозиторій> && cd <репозиторій>
#   ./vps/provision.sh
#
# WireGuard тут НЕ налаштовується — окремий скрипт, `local/setup-wireguard.sh`,
# запускається з SITL-хоста (там уже є SSH-доступ до VPS, тож немає сенсу
# ходити в інший бік): ставить лише пакет `wireguard-tools`, сам тунель —
# після цього провіжну.
#
# Сертифікат: реального (домен+SSL від замовника) ще нема, тож генеруємо
# self-signed у /srv/app/certs/{server.crt,server.key} — лише якщо там ще
# нічого немає. Коли замовник дасть реальний сертифікат — покласти файли з
# тими самими іменами в ту саму теку (перезаписати self-signed), Caddyfile і
# цей скрипт міняти не треба: цей блок просто нічого не згенерує повторно.
#
# Образи `parser`/`web` збираються ТУТ ЖЕ, під час провіжну (docker compose
# build прямо з клона репозиторія на VPS) — окремого кроку "зібрати десь і
# перенести" нема: VPS сам amd64, тож ніякого buildx/--platform/крос-збірки не
# треба, а тягнути образ з робочої машини сюди (tar.gz/registry) — зайва
# складність без вигоди, коли можна зібрати прямо там, де він і запускається.
#
# Ідемпотентний: повторний прогін не ламає вже налаштований сервер (apt install —
# уже сам ідемпотентний; ufw allow повторно не дублює правило; docker —
# перевіряється перед встановленням; `docker compose up -d` без змін просто
# підтверджує, що все вже підняте).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

apt-get install -y wireguard-tools ufw openssl

echo "== ufw: 22 (SSH), 80+443 (HTTP/HTTPS), 51820/udp (WireGuard) =="
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 51820/udp
ufw --force enable

echo "== /srv/app/data: теки під bind-mount (parser пише, web читає) =="
mkdir -p /srv/app/data/inbox /srv/app/data/results
chown -R 1000:1000 /srv/app/data

echo "== TLS: self-signed сертифікат, якщо реального (від замовника) ще нема =="
CERT_DIR=/srv/app/certs
mkdir -p "$CERT_DIR"
if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
  echo "Сертифікат уже є в $CERT_DIR — не чіпаю (реальний від замовника чи раніше згенерований self-signed)."
else
  PUBLIC_HOST="${VPS_PUBLIC_HOST:-$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -f)}"
  if [[ "$PUBLIC_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    SAN="IP:${PUBLIC_HOST}"
  else
    SAN="DNS:${PUBLIC_HOST}"
  fi
  openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout "$CERT_DIR/server.key" -out "$CERT_DIR/server.crt" \
    -subj "/CN=${PUBLIC_HOST}" -addext "subjectAltName=${SAN}"
  echo "Згенеровано self-signed для ${PUBLIC_HOST} (перевизначити хост: VPS_PUBLIC_HOST=<ip_або_домен>)."
fi
chown -R 1000:1000 "$CERT_DIR"

echo "== docker compose: збірка образів (тут, на VPS — той самий amd64) + up -d =="
COMPOSE_DIR="$REPO_ROOT/vps/compose"
DATA_DIR=/srv/app/data CERT_DIR=/srv/app/certs docker compose --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" build
DATA_DIR=/srv/app/data CERT_DIR=/srv/app/certs docker compose --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" up -d

echo "== Health-check (з ретраями — Node/Caddy холодний старт триває кілька секунд) =="
HEALTHY=false
for _ in $(seq 1 15); do
  if curl -sf -o /dev/null http://localhost/; then
    HEALTHY=true
    break
  fi
  sleep 2
done
if [ "$HEALTHY" = true ]; then
  echo "OK: http://localhost/ відповідає (Caddy -> web)."
else
  echo "ПОМИЛКА: http://localhost/ не відповідає навіть після 30с — 'docker compose ps'/'docker compose logs' у $COMPOSE_DIR." >&2
  exit 1
fi

if curl -sfk -o /dev/null https://localhost/; then
  echo "OK: https://localhost/ відповідає (self-signed чи реальний сертифікат — браузер сам покаже, який саме)."
else
  echo "ПОПЕРЕДЖЕННЯ: https://localhost/ не відповідає — 'docker compose logs caddy' у $COMPOSE_DIR." >&2
fi

cat <<'EOF'

Готово. parser+web+caddy зібрані й запущені прямо тут. HTTPS (:443) працює з
self-signed сертифікатом, доки замовник не дасть реальний (покласти
server.crt/server.key в /srv/app/certs, повторно прогнати цей скрипт).
WireGuard ще НЕ піднятий — обмін ключами ручний, SITL-хост на публічну
адресу цього VPS по SSH не ходить (README.md, крок 3):
  CLIENT_WG_PUBKEY=<з local/setup-wireguard.sh> CLIENT_SSH_PUBKEY=<звідти ж> \
    ./vps/setup-wireguard.sh

Повторний прогін цього ж скрипта (напр. після зміни коду — git pull) сам
пересобере образи й перезапустить контейнери.
EOF

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

apt-get install -y wireguard-tools ufw

echo "== ufw: 22 (SSH), 80 (HTTP, без сертифікатів), 51820/udp (WireGuard) =="
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 51820/udp
ufw --force enable

echo "== /srv/app/data: теки під bind-mount (parser пише, web читає) =="
mkdir -p /srv/app/data/inbox /srv/app/data/results
chown -R 1000:1000 /srv/app/data

echo "== docker compose: збірка образів (тут, на VPS — той самий amd64) + up -d =="
COMPOSE_DIR="$REPO_ROOT/vps/compose"
DATA_DIR=/srv/app/data docker compose --project-directory "$COMPOSE_DIR" \
  -f "$COMPOSE_DIR/docker-compose.yml" build
DATA_DIR=/srv/app/data docker compose --project-directory "$COMPOSE_DIR" \
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

cat <<'EOF'

Готово. parser+web+caddy зібрані й запущені прямо тут. WireGuard ще НЕ піднятий —
з SITL-хоста (там є SSH-доступ сюди):
  VPS_HOST=root@<ця_машина> ./local/setup-wireguard.sh

Повторний прогін цього ж скрипта (напр. після зміни коду — git pull) сам
пересобере образи й перезапустить контейнери.
EOF

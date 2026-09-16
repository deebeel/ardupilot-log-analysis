#!/usr/bin/env bash
# Розгортання parser+web+caddy на вже провіжненому VPS (deploy/provision.sh).
# Запускається З РОБОЧОЇ МАШИНИ (на відміну від provision.sh, що ВРУЧНУ на самому
# VPS) — за реальним публічним SSH (VPS_HOST), не через WireGuard: тунель за
# тікетом призначений для телеметрії й логів SITL, не для самого розгортання.
#
# Ідемпотентний: повторний прогін безпечний — sha256 образів звіряється перед
# копіюванням (не заливає повторно, якщо той самий tar.gz), docker compose up -d
# без змін просто підтверджує, що все вже підняте.
#
# Порядок (docs/implementation-plan.md §7):
#   1. make save (тут, якщо образів ще нема/застарілі)
#   2. mkdir -p /srv/app/data/{inbox,results} на VPS
#   3. rsync dist/images.tar.gz + deploy/compose/* на VPS
#   4. ssh vps docker load -i images.tar.gz (офлайн, без Docker Hub)
#   5. ssh vps docker compose up -d (без --build — образи вже в daemon)
#   6. health-check
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${VPS_HOST:?потрібен VPS_HOST=root@<vps>, напр. root@1.zdc.space}"
DOMAIN="${DOMAIN:-localhost}"
TAG="${TAG:-local}"
REMOTE_DIR="${REMOTE_DIR:-/srv/app}"
IMAGES_TAR="$REPO_ROOT/dist/images.tar.gz"

if [ ! -f "$IMAGES_TAR" ]; then
  echo "== $IMAGES_TAR не знайдено — білджу образи (make save) =="
  make -C "$REPO_ROOT" save
fi

echo "== VPS ($VPS_HOST): теки під bind-mount =="
ssh "$VPS_HOST" "mkdir -p $REMOTE_DIR/data/inbox $REMOTE_DIR/data/results && chown -R 1000:1000 $REMOTE_DIR/data"

echo "== Копіюю образи (sha256-звірка — не заливаю повторно, якщо збіглося) =="
LOCAL_SHA="$(shasum -a 256 "$IMAGES_TAR" | cut -d' ' -f1)"
REMOTE_SHA="$(ssh "$VPS_HOST" "sha256sum $REMOTE_DIR/images.tar.gz 2>/dev/null | cut -d' ' -f1" || true)"
if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
  echo "   збіглося ($LOCAL_SHA) — пропускаю копіювання."
else
  rsync -avz --partial "$IMAGES_TAR" "$VPS_HOST:$REMOTE_DIR/images.tar.gz"
fi

echo "== Копіюю compose/Caddyfile, генерую .env =="
rsync -avz "$REPO_ROOT/deploy/compose/docker-compose.yml" "$REPO_ROOT/deploy/compose/Caddyfile" \
  "$VPS_HOST:$REMOTE_DIR/"
ssh "$VPS_HOST" "cat > $REMOTE_DIR/.env" <<EOF
TAG=$TAG
DOMAIN=$DOMAIN
DATA_DIR=$REMOTE_DIR/data
EOF

echo "== docker load (офлайн) =="
ssh "$VPS_HOST" "docker load -i $REMOTE_DIR/images.tar.gz"

echo "== docker compose up -d =="
ssh "$VPS_HOST" "docker compose --project-directory $REMOTE_DIR -f $REMOTE_DIR/docker-compose.yml up -d"

echo "== Health-check =="
if ssh "$VPS_HOST" "curl -sf -k -o /dev/null https://localhost/"; then
  echo "OK: https://localhost/ на VPS відповідає (Caddy -> web)."
else
  echo "ПОМИЛКА: https://localhost/ на VPS не відповідає — перевір 'docker compose ps'/'docker compose logs' на VPS." >&2
  exit 1
fi

cat <<EOF

Готово. Зовнішня перевірка: https://$DOMAIN/ (self-signed сертифікат для
DOMAIN=localhost — браузер попередить, це очікувано; реальний домен від
замовника матиме дійсний сертифікат).
EOF

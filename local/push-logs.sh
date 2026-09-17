#!/usr/bin/env bash
# Автоматична доставка логів SITL -> VPS через WireGuard (RND-254: "Логи з SITL
# автоматично потрапляють на VPS і з'являються у списку" — критерій приймання,
# не просто dev-зручність; на відміну від `make fetch-logs`, який тягне логи
# з VM на Mac для локальної перевірки пайплайна).
#
# Стежить за `.sitl/ArduPlane/logs/` через inotifywait (`close_write` — той
# самий принцип "не парсити недовантажене", що й watcher на боці парсера,
# `vps/services/parser/src/parser/watcher.py`): щойно ArduPilot закриває `.BIN` (кінець
# польоту/дизарм), файл негайно rsync'ається на VPS. `.tlog` увесь час
# відкритий протягом сесії MAVProxy (не закривається між польотами), тож його
# штовхаємо окремо, періодично (за замовчуванням раз на 10с) — best-effort,
# "і/або" з тікета (п.2: ".bin DataFlash і/або .tlog") виконується вже одним
# `.BIN`.
#
# Живе в фоні, поки живий run-sitl.sh (той запускає це у background і вбиває
# через trap on EXIT) — не окремий сервіс/systemd-таймер, свідомо: логи мають
# сенс штовхати лише поки триває сесія SITL, окремий daemon поза цим не додає
# нічого.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="$REPO_ROOT/.sitl/ArduPlane/logs"

# WireGuard-адреси фіксовані у vps/setup-wireguard.sh + local/setup-wireguard.sh (сервер
# 10.10.0.1, клієнт/SITL-хост 10.10.0.2) — VPS_WG_HOST перевизначити, якщо
# тунель піднятий інакше. VPS_USER=root — provision.sh не створює окремого
# deploy-користувача, /srv/app/data ставиться chown 1000:1000 (parser у
# контейнері), але сам rsync по SSH іде як root (єдиний акаунт на свіжому VPS).
VPS_WG_HOST="${VPS_WG_HOST:-10.10.0.1}"
VPS_USER="${VPS_USER:-root}"
VPS_INBOX="${VPS_INBOX:-/srv/app/data/inbox}"
TLOG_PUSH_INTERVAL="${TLOG_PUSH_INTERVAL:-10}"

mkdir -p "$LOGDIR"

if ! command -v inotifywait >/dev/null 2>&1; then
  echo "push-logs.sh: inotifywait не знайдено — ./local/provision.sh (inotify-tools)" >&2
  exit 1
fi

DEST="$VPS_USER@$VPS_WG_HOST:$VPS_INBOX/"

push_file() {
  # `if !` навмисно — під `set -e`/`pipefail` невдалий rsync (VPS/WireGuard
  # тимчасово недоступний) інакше вбив би увесь цикл спостереження, а не
  # лише цю одну спробу; наступний закритий .BIN чи наступний тик tlog-пушера
  # все одно спробує знову.
  if ! rsync -az --partial "$1" "$DEST" 2>&1 | sed 's/^/push-logs.sh: /'; then
    echo "push-logs.sh: rsync не вдався для $1 (VPS/WireGuard недоступний?)" >&2
  fi
}

echo "push-logs.sh: стежу за $LOGDIR -> $DEST"

# Періодичний push .tlog у фоновому підпроцесі — окремо від основного
# inotify-циклу нижче (той реагує лише на .BIN).
(
  while true; do
    sleep "$TLOG_PUSH_INTERVAL"
    if [ -f "$LOGDIR/mav.tlog" ]; then
      push_file "$LOGDIR/mav.tlog"
    fi
  done
) &
TLOG_PUSHER_PID=$!

# `inotifywait -m` — окремий фоновий процес (не foreground у пайплайні), щоб
# мати його PID для явного kill: пайплайн `inotifywait | while read` інакше
# лишив би inotifywait сиротою (reparented до init) при вбивстві цього
# скрипту через SIGTERM — воно не є "job" під job control неінтерактивного
# bash, тож саме по собі не отримало б сигнал.
FIFO="${TMPDIR:-/tmp}/push-logs-events.$$"
mkfifo -m 600 "$FIFO"
inotifywait -m -e close_write --format '%w%f' "$LOGDIR" > "$FIFO" &
INOTIFY_PID=$!

trap 'kill "$TLOG_PUSHER_PID" "$INOTIFY_PID" 2>/dev/null || true; rm -f "$FIFO"' EXIT

while read -r closed_file; do
  case "$closed_file" in
    *.BIN) push_file "$closed_file" ;;
  esac
done < "$FIFO"

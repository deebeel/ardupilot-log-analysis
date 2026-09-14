# План реалізації

Порядок робіт — знизу вгору: спочатку те, що можна перевірити без VPS (парсер на наявному
`flight-01`), потім обв'язка (SITL, keyboard), потім транспорт (WireGuard), потім деплой.

## 0. Скелет репозиторію

```
ardupilot_log_analysis/
├── Makefile                     # локальні команди (див. §6)
├── README.md                    # канонічний, Ubuntu-only
├── README.mac.md                # опційний, для власного dev-циклу
├── assets/                      # логи, тікет, demo-flight-task.md
├── docs/                        # scoring-algorithm.md, цей файл
├── services/
│   ├── parser/                  # Python-сервіс (§1)
│   └── web/                     # Astro-сервіс (§2)
├── tools/
│   └── keyboard_adapter/        # Python, клавіатура → MANUAL_CONTROL (§4)
├── deploy/
│   ├── compose/                 # docker-compose.yml + .env.example + Caddyfile (§5)
│   ├── wireguard/               # конфіги peer-ів (§3)
│   └── deploy.sh, provision.sh  # shell-скрипти деплою (§7)
└── data/                        # gitignored: inbox/, results/ для локального запуску
```

---

## 1. Сервіс `parser` (Python)

### 1.1 Структура

```
services/parser/
├── pyproject.toml               # uv, deps: pymavlink, numpy, pyyaml, watchdog
├── uv.lock
├── Dockerfile
├── thresholds.yaml              # дефолтні пороги (placeholder до шаблонів замовника)
└── src/parser/
    ├── watcher.py               # entrypoint: стежить за inbox/, спавнить воркер
    ├── worker.py                # entrypoint воркера: один файл → один JSON
    ├── reader.py                # DFReader/mavlink → нормалізовані series
    ├── metrics.py               # чисті функції метрик (п.3 тікета)
    └── models.py                # dataclass-и + серіалізація JSON
```

### 1.2 Потік даних

```
data/inbox/flight-NN.bin  --(watchdog on_closed)-->  watcher.py
   └─ subprocess: python -m parser.worker <file>
         ├─ reader: RCIN, ATT, MODE, GPS → numpy-серії з таймстемпами
         ├─ metrics: 5 метрик тікета
         └─ write data/results/flight-NN.json.tmp → os.rename(.json)
```

Ключові рішення:
- **watchdog на `on_closed`**, не `on_created` — інакше rsync/scp дає частковий файл.
  Fallback для FS без inotify-close: `on_created` + чекати стабілізації розміру 2 с.
- **subprocess з таймаутом** (напр. 120 с) і `returncode != 0` → писати
  `flight-NN.error.json` зі stderr, щоб веб показав "парсинг впав", а не мовчав.
- Ідемпотентність: якщо `results/flight-NN.json` вже є і mtime новіший за вхідний — skip.

### 1.3 Нормалізація (те, що ще не було зафіксовано)

- Нейтраль/хід стіка брати з параметрів логу (`PARM`: `RC1_MIN/TRIM/MAX` … `RC4_*`),
  з фолбеком 1000/1500/2000. Нормалізувати в `[-1, +1]` окремо для half-range нижче й вище trim.
- Deadband: ±0.02 від нейтралі — все всередині вважати нейтраллю (інакше шум RC дає фантомні
  "корекції" і роздуває `corrections_per_min`).
- Ресемплінг ATT і RCIN на спільну сітку (10 Гц, лінійна інтерполяція) — RCIN і ATT пишуться
  з різною частотою, а метрика латентності потребує спільної осі часу.
- Аналізувати лише ручні режими (`FBWA`/`FBWB`/`MANUAL`/`STABILIZE`), відкидати `AUTO`/`RTL` —
  інакше автопілот "пілотує" за оператора і метрики брехливі. Межі фаз — з `MODE`.

### 1.4 Метрики (`metrics.py`, кожна — чиста функція над серіями)

| Метрика | Визначення |
|---|---|
| `corrections_per_min` | кількість перетинів deadband назовні (по кожній осі) / тривалість аналізованих фаз у хв |
| `mean_amplitude` | середнє \|value\| по семплах поза deadband |
| `mean_jerk` | середнє \|d(value)/dt\| (після ресемплінгу, з ковзним згладжуванням 3 семпли) |
| `oscillation_time_pct` | частка часу, де знак відхилення змінюється ≥ N разів за вікно (N=3, вікно 2 с) |
| `reaction_latency_ms` | для кожної події «attitude-помилка перевищила поріг» — час до першого руху відповідного стіка поза deadband; медіана по подіях |

Кожна повертає `{axis: value}` (крім латентності — скаляр). Юніт-тести на синтетичних
серіях (прямокутник, синус, шум) + smoke-тест на `flight-01`.

### 1.5 Вихідний JSON

Як у `docs/scoring-algorithm.md` (`metrics` + `default_thresholds`), плюс метадані для UI:
`flight_id`, `duration_s`, `phases[]` (з MODE), і **самі серії для графіків** —
downsampled до ~2000 точок на канал (`series: {t[], roll[], pitch[], att_roll[], att_pitch[]}`)
і гістограма амплітуд (bins). Без цього веб не побудує "графік стіків поверх attitude".

### 1.6 Dockerfile (multi-stage)

```dockerfile
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev          # → /app/.venv
COPY src/ ./src/

FROM python:3.12-slim AS runtime       # без uv
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY thresholds.yaml .
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
USER 1000:1000
CMD ["python", "-m", "parser.watcher"]
```

Білд: `docker buildx build --platform linux/amd64` (pymavlink має C-розширення).

---

## 2. Сервіс `web` (TypeScript / Astro)

Рішення: **Astro в SSR-режимі, окремий контейнер.** Свідомо платимо одним зайвим образом
за звичний людяний UI-стек (компоненти, роутинг, Tailwind) замість статики, що роздається Caddy.

### 2.1 Структура

```
services/web/
├── package.json / package-lock.json
├── astro.config.mjs             # output: 'server', adapter: @astrojs/node (mode 'standalone')
├── tailwind.config.mjs
├── Dockerfile
└── src/
    ├── styles/global.css        # @tailwind base/components/utilities
    ├── lib/results.ts           # readdir/readFile RESULTS_DIR + валідація id
    ├── lib/verdict.ts           # порт §Алгоритм на TS — чиста функція
    ├── pages/index.astro        # список польотів (SSR-скан теки)
    ├── pages/flight/[id].astro  # сторінка звіту (SSR: віддає JSON у острів)
    └── components/
        ├── StickOverlayChart    # RCIN поверх ATT у часі
        ├── AmplitudeHistogram
        └── VerdictPanel         # слайдери порогів + миттєвий перерахунок
```

- **SSR, не static** — теку результатів сканувати на кожен запит, щоб новий політ з'являвся
  без ребілду. `getStaticPaths` не використовується: `id` береться з `Astro.params` у рантаймі.
- **`readdir` — лише в тілі сторінки**, не на верхньому рівні модуля (той виконається раз при
  старті процесу і заморозить список).
- **`export const prerender = false`** явно на обох сторінках — страховка на випадок зміни
  `output` у конфізі.
- **Валідація `id`**: `/^[A-Za-z0-9_-]+$/` перед склеюванням шляху, інакше path traversal
  (`:ro`-маунт читання чужих файлів не зупиняє). Невідповідність або відсутній файл → 404.
- Індексна сторінка читає з кожного JSON лише шапку (`flight_id`, дата, тривалість, зведені
  метрики); важкі `series` тягнути в список не треба.
- **Оновлення списку — React-поллінг раз на секунду**, а не push/SSE (стійкіший: не треба
  тримати з'єднання живим і переперепідключати). **Було htmx** (`hx-trigger="every 1s"` +
  `hx-swap="outerHTML"` через окремий partial-роут) — **замінено на React** (`FlightList.tsx`,
  `client:load`, `fetch('/api/flights')` у `setInterval`), коли з'ясувалось, що в проєкті вже
  є React-острови (`VerdictPanel`) для того самого списку (бейджі вердикту, перейменування) —
  тримати паралельно дві різні клієнтські моделі (htmx-DOM-свапи + React-стейт) для сусідніх
  елементів одного компонента виявилось зайвою складністю. JSON-джерело для поллінгу —
  `src/pages/api/flights.ts` (той самий `listFlights()`, просто `Response.json` замість HTML).
- Tailwind — через `@astrojs/tailwind`; жодних CDN-стилів (VPS без інтернету), все в бандлі.
- Графіки — uPlot, вендорений у бандл, теж без CDN.
- Інтерактив (слайдери порогів, перерахунок вердикту) — один React-острів
  (`client:load`) на сторінці польоту; решта сторінки — статичний Astro-рендер.
- `verdict.ts` — дзеркало алгоритму з `docs/scoring-algorithm.md`; юніт-тест, що звіряє
  його вивід з еталонним набором кейсів (щоб TS і опис не розійшлись).

### 2.2 Dockerfile

```dockerfile
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build                       # → /app/dist

FROM node:22-slim AS runtime            # без devDependencies
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist
ENV RESULTS_DIR=/data/results HOST=0.0.0.0 PORT=4321
USER 1000:1000
CMD ["node", "./dist/server/entry.mjs"]
```

---

## 3. WireGuard (транспорт логів)

**Локальна перевірка виконана** (2026-09-14) — без другої фізичної VM, двома ізольованими
docker-мережами без спільної мережі одна з одною (саме та альтернатива, яку допускає план
нижче), UDP-порт сервера опубліковано на хості, щоб імітувати "інтернет" між ними:
handshake встановився, `ping` крізь `10.10.0.0/24` пройшов, `rsync` реального `.BIN`
(11 МБ) через тунель доставив файл побайтово ідентичним, і `parser.worker` на ньому
відпрацював без помилок. Приклади конфігів — `deploy/wireguard/wg0-{server,client}.conf.example`.
Реальний VPS замінить сервер-контейнер 1:1 — конфіг клієнта (SITL-хост) той самий, лише
`Endpoint` міняється з тестового на публічний IP VPS.

- VPS = сервер (`10.10.0.1/24`, UDP 51820, публічний IP), SITL-хост = клієнт (`10.10.0.2/24`).
- `AllowedIPs = 10.10.0.0/24` на клієнті — тунелюємо лише службову мережу, не весь трафік.
- WireGuard на VPS ставиться `provision.sh` **на хост**, не в контейнер — простіше з ключами
  й ip-forward, і стек у compose від нього не залежить.
- Локальна перевірка до отримання VPS: дві Ubuntu-VM (або два docker-нетворки) з тими ж
  конфігами — підтвердити, що `rsync` через тунель кладе файл у `inbox/` і парсер спрацьовує.
- Ключі — поза git; у репо лише `*.conf.example` з плейсхолдерами.

Доставка логів: `rsync -az --partial ... /sitl/logs/ 10.10.0.1:/srv/app/data/inbox/`
(`--partial` + watcher на `on_closed` — щоб не парсити недовантажене).

---

## 4. `tools/keyboard_adapter`

- Окремий `pyproject.toml` (`pymavlink`, `pynput`) — не тягнути `pynput` у серверний образ.
- Запускається **на хості**, не в контейнері (доступ до клавіатури), конект до SITL
  `udp:127.0.0.1:14550`.
- Модель осі: `value += k*dt` поки клавіша натиснута, `value -> 0` з тим же `k` коли
  відпущена (spring-return); кліп у `[-1000, 1000]`; відправка `MANUAL_CONTROL` на 20 Гц
  незалежно від подій клавіатури.
- Розкладка: `W/S` pitch, `A/D` roll, `Q/E` yaw, `Shift/Ctrl` throttle (throttle — без
  spring-return, він утримується). Зафіксувати в README.

---

## 5. docker-compose

**Реалізовано** — `deploy/compose/docker-compose.yml`/`Caddyfile`/`.env.example`, перевірено
живцем (`make stack-up`): `curl https://localhost/` → 200 через self-signed Caddy, парсер
підхопив реальні `.BIN` з `data/inbox`, `make stack-down` прибирає все чисто.

Один файл `deploy/compose/docker-compose.yml`, різниця локально/VPS — лише `.env`.

```yaml
services:
  parser:
    image: ardupilot-la/parser:${TAG}
    volumes: [ "${DATA_DIR}:/data" ]        # /data/inbox, /data/results
    restart: unless-stopped
  web:
    image: ardupilot-la/web:${TAG}
    volumes: [ "${DATA_DIR}/results:/data/results:ro" ]   # web не пише
    restart: unless-stopped
  caddy:
    image: caddy:2-alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data                     # сертифікати переживають рестарт
    restart: unless-stopped
volumes: { caddy_data: }
```

`Caddyfile`: `{$DOMAIN} { reverse_proxy web:4321 }` — авто-HTTPS.
Локально — `DOMAIN=localhost` (Caddy дає self-signed) або взагалі профіль без caddy.
SITL не контейнеризується (тікет: "у ВМ або на bare-metal" — Docker не згаданий, а VM уже дає
ізоляцію). Піднімається нативно в Ubuntu VM через `sim_vehicle.py` (компілює й запускає
`arduplane`, сам стартує MAVProxy з `--console --map`, роздає UDP `14550`); `.BIN`-логи —
`ArduPlane/logs/`, `.tlog` — там, де запущено MAVProxy. Дивись `docs/host-prerequisites.md`.

---

## 6. Makefile (локально)

**Реалізовано** (крім `sitl-up`/`keyboard`/`deploy` — ті йдуть окремо: SITL/keyboard-адаптер
запускаються нативно на Ubuntu-хості за `docs/host-prerequisites.md`, не з Mac; `deploy` —
разом із `deploy/deploy.sh`, §7).

```
setup-input-group        # sudo usermod -aG input — делегується з tools/setup-host.sh
fetch-logs                # dev-зручність: .BIN/.tlog з UTM VM у data/ через ssh/rsync
stack-up / stack-down    # docker compose -f deploy/compose/docker-compose.yml (parser+web+caddy)
build                    # buildx, обидва образи (--platform linux/amd64 для VPS-цілі)
save                     # build + docker save | gzip → dist/images.tar.gz
test                     # mypy+pytest (parser) + lint/vitest/playwright (web)
parse FILE=...           # разовий прогін воркера на файлі, без watcher
deploy                   # ще не реалізовано — deploy/deploy.sh
```

---

## 7. Деплой на VPS — shell, не Ansible

Тікет дозволяє "docker-compose / Ansible / shell — на вибір". Для одного VPS і
одноразового прогону (без continuous config drift, без багатьох хостів) Ansible —
оверінженірінг: його головна цінність (ідемпотентність, керування станом флоту машин)
тут не окупається, а рев'юєру довелось би читати YAML/Jinja замість лінійного bash.

```
deploy/
├── deploy.sh                 # головний скрипт (нижче)
├── provision.sh              # одноразово: apt, ufw, WireGuard-сервер на хості VPS
├── compose/
│   ├── docker-compose.yml
│   ├── .env.example
│   └── Caddyfile
└── wireguard/
    └── wg0.conf.example
```

`provision.sh` (запускається вручну один раз на чистому VPS, `ssh vps 'bash -s' < provision.sh`):
1. `apt install` — Docker Engine + compose plugin, `wireguard-tools`, `ufw`.
2. `ufw allow 22,80,443,51820/udp` — далі `ufw enable`.
3. Згенерувати ключі WireGuard, покласти `/etc/wireguard/wg0.conf` (з шаблону + підставленим публічним ключем клієнта), `systemctl enable --now wg-quick@wg0`.

`deploy.sh` (запускається з робочої машини, ідемпотентний — повторний запуск безпечний):
1. `mkdir -p /srv/app/{data/inbox,data/results}` на VPS через `ssh` (права під UID 1000).
2. `scp`/`rsync` `dist/images.tar.gz` (з `sha256sum`-порівнянням — не заливати повторно, якщо збіглося) + `deploy/compose/*` на VPS.
3. `ssh vps 'docker load -i /srv/app/images.tar.gz'` — офлайн, без Docker Hub.
4. `ssh vps 'docker compose -f /srv/app/docker-compose.yml up -d'` (**без `--build`**, образи вже в daemon).
5. `curl -sf https://$DOMAIN/` — health-check, ненульовий вихід зупиняє скрипт (`set -euo pipefail`).

Логи `.bin`/`.tlog` штовхає `rsync` із SITL-хоста напряму — окремого скрипту-фетчера не треба
(§3 вище).

---

## 8. Ризики, що впливають на план

- **Docker на VPS.** Роль `docker/` качає пакети з інтернету. Якщо outbound на VPS закритий —
  Docker має бути передвстановлений (тікет каже "умовний докер" ⇒ ймовірно так), і роль
  зводиться до перевірки `docker --version`. Уточнити в замовника.
- **ACME.** Без outbound на Let's Encrypt справжній сертифікат неможливий — тоді Caddy на
  `tls internal` + це прямо зафіксувати в README як обмеження середовища.
- **Пороги.** Весь §1.4 працює на placeholder-ах; після отримання шаблонів змінюється
  **лише** `thresholds.yaml`, коду не чіпаємо.

## 9. Порядок виконання

1. `parser` (§1) на наявному `flight-01` — єдиний крок, що не залежить ні від чого зовнішнього.
2. `web` (§2) на JSON з кроку 1, локально.
3. SITL нативно у Ubuntu VM (`sim_vehicle.py`) + `keyboard_adapter` (§4), перші ручні польоти.
4. compose + Caddy локально (§5), Makefile (§6).
5. WireGuard між двома локальними VM (§3).
6. `deploy.sh`/`provision.sh` на реальний VPS (§7), фінальний прогін строго за README.
7. 3+ залікових польоти за єдиною програмою + екранні записи.

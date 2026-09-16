# Підготовка хоста (чернетка для README)

Джерело для секції «підготовка хоста» майбутнього `README.md` (Ubuntu) і `README.mac.md`.
Стенд — **одна Ubuntu VM**: SITL нативно (`sim_vehicle.py`, без контейнера), MAVProxy як
GCS + 2D-візуалізатор в одному процесі, keyboard-адаптер нативно на тому самому хості.
Docker у цій VM не потрібен взагалі — він потрібен лише окремо, для збірки образів
`parser`/`web` під VPS. Пункти, позначені **[не перевірено]**, пройти живцем до здачі.

## Ролі програм на стенді (не плутати)

| Роль | Що робить | Чим закривається |
|---|---|---|
| **SITL** | рахує фізику апарата, віддає MAVLink | нативно `sim_vehicle.py` (ArduPlane 4.6, без контейнера) |
| **GCS + візуалізатор** | телеметрія, HUD, режими, arm/disarm, 2D-мапа | MAVProxy (`--map --console`) — одне рішення на обидві ролі |
| **keyboard-адаптер** | клавіатура → `MANUAL_CONTROL` | `tools/keyboard_adapter` |

**Тікет 3D не вимагає.** Дослівно: «Візуалізація польоту — на твій розсуд: FlightGear,
Mission Planner/QGC з картою чи інше; допускається запуск візуалізатора на хості поза ВМ».
MAVProxy закриває GCS і візуалізацію одночасно, без QGC/AppImage/`libfuse2`/FlightGear і без
вимоги до 3D-прискорення у VM. FlightGear лишається опційним — лише заради ефектнішого запису.

## Ubuntu (канонічний README) — команди по кроках

Сесія (Xorg/Wayland, `$XDG_SESSION_TYPE`) не важлива — клавіатурний бекенд один
(`evdev`, kernel `/dev/input`), працює однаково на обох (докладніше — крок 4).

### 1. `uv` (потрібен для dev-debug `cli.py --dry`, не для самого стенду)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.profile
```

### 2. Одноразовий провіжн: `tools/prereqs.sh`

Один скрипт, один запит `sudo`-пароля, ідемпотентний (повторний прогін безпечний):
клонує **офіційний апстрім** ArduPilot у гітignored `.sitl/` (не форк, не submodule —
просто ще одна локальна тека поза git, як `assets/`/`data/`), виставляє пінований тег
(`Plane-4.6.3` — серія тегів релізів, не гілка; звірити реальний останній `4.6.x`:
`git -C .sitl tag -l "Plane-4.6.*" --sort=-v:refname | head -1`, перевизначити через
`ARDUPILOT_TAG=...`), запускає ArduPilot-івський `install-prereqs-ubuntu.sh` (сам ставить
MAVProxy й Python-залежності), і додає те, що той не покриває — `wireguard-tools`/`rsync`/
`git-lfs` (доставка логів на VPS) і групу `input` (`evdev`-бекенд клавіатури, крок 4):

```bash
./tools/prereqs.sh
```

Якщо групу `input` щойно додано — релогін (вийти й зайти знову), інакше `evdev` не
запрацює до наступної сесії.

### 3. `run-sitl`: SITL + MAVProxy з keyboard-адаптером-модулем

```bash
./tools/run-sitl.sh
```

Піднімає SITL ArduPlane (`sim_vehicle.py`, компілює лише перший раз) і сам стартує
MAVProxy з `--console --map`, роздає UDP `14550`. keyboard-адаптер — **не окремий
процес**, а MAVProxy-модуль (`init()` у `keyboard_adapter/__init__.py`), що
вантажиться разом з MAVProxy через `--mavproxy-args` — ідіоматичний спосіб
розширювати MAVProxy (так само map/console), без власного UDP-конекту й очікування
heartbeat.

Клавіатурний бекенд — `evdev` (kernel `/dev/input`, однаково на Xorg і Wayland —
дивись розділ нижче), автовизначення пристрою; `Ctrl+C` зупиняє MAVProxy, а разом з
ним і всі модулі (`unload()` кожного, зокрема клавіатурний тред `keyboard_adapter`).

Тестовий політ у консолі MAVProxy:

```
STABILIZE
arm throttle
mode TAKEOFF
```

Завершення: `disarm`, потім `Ctrl+C`.

`.BIN` (DataFlash) пише сам SITL у `.sitl/ArduPlane/logs/`; `.tlog` пише MAVProxy там, де
запущено `run-sitl.sh` (корінь репозиторію). **[не перевірено]** мапі MAVProxy для тайлів
потрібен інтернет при першому запуску (кешує в `~/.tilecache`) — без мережі буде порожня
сітка замість мапи; `--console` працює офлайн.

#### keyboard-адаптер і Wayland

Ubuntu 22.04+ типово Wayland, де X11 global-grab (`pynput`) не працював би — архітектурне
рішення Wayland про ізоляцію застосунків, не недогляд бібліотеки. Саме тому єдиний
бекенд тут — `evdev`: читає клавіші напряму з ядра (`/dev/input/eventN`), нижче будь-якого
дисплейного сервера, тож однаково на Xorg і Wayland без вибору сесії логіну. Ціна —
користувач у групі `input` (додається кроком 2, `./tools/prereqs.sh`; релогін після
першого запуску). Автовизначення бере перший пристрій із `KEY_A`; якщо обрало не той —
`ls /dev/input/by-id/` або `sudo libinput list-devices`, тоді `KEYBOARD_DEVICE=/dev/input/eventN
./tools/run-sitl.sh`. Це не «фокус вікна», а сирі коди з пристрою — спрацює навіть без
фокуса на потрібному вікні (ближче до поведінки реального джойстика).

### Доставка логів і решта

- `wireguard-tools`, `rsync`, `openssh-client`, `git-lfs` — уже в кроці 2 (`tools/prereqs.sh`).

## macOS (README.mac.md, не оцінюється)

Стенд на Mac не запускається — SITL/MAVProxy/адаптер живуть лише в Ubuntu VM. Mac лишається
для розробки `parser`/`web`:

- `uv` через brew, Node.
- Docker (Desktop) — лише для збірки образів `parser`/`web` під VPS (`--platform linux/amd64`).
- WireGuard — не потрібен на Mac у фінальній схемі (тунель між VM і VPS).

## Порядок перевірки на реальному стенді

1. `evdev` реально бачить клавіатуру (група `input`, правильний `/dev/input/eventN`) —
   реальний ризик зламати сценарій, що оцінюється.
2. MAVProxy бачить SITL по TCP `5760`, `--map` показує рух апарата.
3. Модуль `keyboard_adapter` реально рухає стіки в SITL (spring-return видно на графіку
   RCIN) — `module list` у консолі MAVProxy показує його завантаженим.
4. Решта — рутинна установка пакетів.
5. Лише якщо вирішено брати FlightGear: 3D-картинка реально рухається з прийнятним fps.

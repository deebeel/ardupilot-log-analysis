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

### 1. Перевірити сесію (перше, до всього іншого)

```bash
echo $XDG_SESSION_TYPE
```

Якщо `wayland` — дивись розділ «keyboard-адаптер під Wayland» нижче. Це не блокер (є `evdev`),
але впливає на вибір бібліотеки клавіатури.

### 2. Системні залежності

```bash
sudo apt update
sudo apt install -y git python3-pip python3-dev python3-venv \
  build-essential libtool libxml2-dev libxslt1-dev python3-matplotlib \
  wireguard-tools rsync openssh-client git-lfs
```

### 3. SITL: клон і збірка

`Plane-4.6` — це не гілка, а серія тегів релізів (`Plane-4.6.0`, `Plane-4.6.1`, …). Клонувати
й перейти на останній `4.6.x`:

```bash
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
git checkout Plane-4.6.3   # звірити реальний останній тег: git tag -l "Plane-4.6.*" --sort=-v:refname | head -1
git submodule update --init --recursive
Tools/environment_install/install-prereqs-ubuntu.sh -y
source ~/.profile
```

`install-prereqs-ubuntu.sh` сам ставить `MAVProxy` і Python-залежності — окремо не потрібно.

### 4. Перший запуск SITL + MAVProxy (генерація `.bin`/`.tlog`)

```bash
cd ~/ardupilot/ArduPlane
sim_vehicle.py -v ArduPlane --frame plane -M plane --console --map
```

`sim_vehicle.py` компілює (лише перший раз) і піднімає `arduplane`, сам стартує MAVProxy
з `--console --map`, роздає UDP `14550`. Тестовий політ у консолі MAVProxy:

```
STABILIZE
arm throttle
mode TAKEOFF
```

Завершення: `disarm`, потім `Ctrl+C` у терміналі `sim_vehicle.py`.

`.BIN` (DataFlash) пише сам SITL у `ArduPlane/logs/`; `.tlog` пише MAVProxy там, де його
запущено. **[не перевірено]** мапі MAVProxy для тайлів потрібен інтернет при першому
запуску (кешує в `~/.tilecache`) — без мережі буде порожня сітка замість мапи; `--console`
працює офлайн.

### 5. `uv` і keyboard-адаптер

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.profile
cd tools/keyboard_adapter
uv sync
# Xorg-сесія:
uv run keyboard-adapter --connect udp:127.0.0.1:14550 --input-backend pynput
# Wayland-сесія (рекомендовано за підтвердженого Wayland, група `input` потрібна):
cd .. && make setup-input-group && cd tools/keyboard_adapter   # один раз, тоді релогін
uv run keyboard-adapter --connect udp:127.0.0.1:14550 --input-backend evdev
```

#### keyboard-адаптер під Wayland

Ubuntu 22.04+ типово Wayland, де `pynput` (X11 global-grab) не працює — це архітектурне
рішення Wayland про ізоляцію застосунків, не недогляд бібліотеки. Два варіанти без зміни
логіки осей (`AxisState` від бібліотеки клавіатури не залежить):

- **Найпростіше — сесія Xorg.** На екрані логіну (шестерня біля кнопки Sign In) обрати
  «Ubuntu on Xorg». Нуль коду, `pynput` працює як задумано.
- **`evdev` — працює на Xorg і Wayland однаково**, бо читає клавіші напряму з ядра
  (`/dev/input/eventN`), нижче будь-якого дисплейного сервера. Ціна: користувач у групі
  `input` (`make setup-input-group`, ідемпотентно; релогін після першого запуску), і треба
  знайти пристрій клавіатури (`ls /dev/input/by-id/` або `sudo libinput list-devices`). Це не «фокус вікна», а сирі
  коди з пристрою — спрацює навіть без фокуса на потрібному вікні (для нашого сценарію це
  плюс, ближче до поведінки реального джойстика).

  **Рекомендація за підтвердженого Wayland: `evdev`**, щоб не змінювати сесію логіну
  щоразу. Реалізовано: `uv run keyboard-adapter --input-backend evdev` (автовизначення
  пристрою, або `--device /dev/input/eventN` явно) — див. `tools/keyboard_adapter/README.md`.

- **[не перевірено]** Може знадобитись доступ до `/dev/input` навіть для `pynput`, якщо
  бібліотека сама піде evdev-шляхом на Wayland (деякі збірки так роблять).

### Доставка логів і решта

- `wireguard-tools`, `rsync`, `openssh-client` — уже в кроці 2.
- `git-lfs` — у репо вже налаштований; без нього `.bin`-логи не витягнуться з клону.

## macOS (README.mac.md, не оцінюється)

Стенд на Mac не запускається — SITL/MAVProxy/адаптер живуть лише в Ubuntu VM. Mac лишається
для розробки `parser`/`web`:

- `uv` через brew, Node.
- Docker (Desktop) — лише для збірки образів `parser`/`web` під VPS (`--platform linux/amd64`).
- WireGuard — не потрібен на Mac у фінальній схемі (тунель між VM і VPS).

## Порядок перевірки на реальному стенді

1. `$XDG_SESSION_TYPE` → вибір `pynput`+Xorg чи `evdev` для адаптера (реальний ризик зламати
   сценарій, що оцінюється).
2. MAVProxy бачить SITL по TCP `5760`, `--map` показує рух апарата.
3. Адаптер реально рухає стіки в SITL (spring-return видно на графіку RCIN).
4. Решта — рутинна установка пакетів.
5. Лише якщо вирішено брати FlightGear: 3D-картинка реально рухається з прийнятним fps.

# keyboard_adapter — клавіатура замість джойстика

Шле `MANUAL_CONTROL` у SITL ArduPlane з клавіатури, замінюючи фізичний джойстик для
ручного пілотування. **Вантажиться MAVProxy-модулем** (`init()` у
`keyboard_adapter/__init__.py`, `--load-module keyboard_adapter` — див.
`tools/run-sitl.sh`), не окремим процесом: ідіоматично для MAVProxy (так само
розширюються map/console/antenna-tracker), без власного UDP-конекту й очікування
heartbeat — `self.master` вже підключений. `cli.py` лишається окремо, лише як
dev-утиліта для debug (`--dry`) поза MAVProxy — не шлях керування польотом
(детальніше нижче).

## Чому клавіатура, а не джойстик

Апаратного джойстика/RC-передавача в стенді немає, а критерій тікета — **ручне** керування
з людською динамікою вводу (саме її міряють метрики: корекції/хв, амплітуда, різкість,
осциляції, латентність). Заміна клавіатурою погоджена із замовником напряму.

Щоб клавіатура не спотворювала метрики «квадратним» вводом (миттєвий стрибок 0 → максимум
і назад дав би нескінченний jerk), реалізовано **spring-return**-модель осі, яка імітує
підпружинений стік: значення плавно наростає, поки клавіша натиснута, і плавно повертається
до нейтралі після відпускання.

## Розкладка

| Клавіші | Вісь | MANUAL_CONTROL | Поведінка |
|---|---|---|---|
| `W` / `S` | pitch | `x` | spring-return до 0 |
| `A` / `D` | roll | `y` | spring-return до 0 |
| `Q` / `E` | yaw | `r` | spring-return до 0 |
| `Shift` / `Ctrl` | throttle | `z` | **утримується** (без spring-return) |

- Діапазон кожної осі — `[-1000, 1000]` (діапазон MAVLink `MANUAL_CONTROL`).
- Темп `k` (дефолт 2000 одиниць/с ⇒ 0 → 1000 за 0.5 с) — і на наростання, і на повернення.
- Повернення до нуля не перестрибує нуль навіть при великому кроці часу.
- Протилежні клавіші (`A`+`D`) гасять одна одну: для пружинних осей це spring-return,
  для throttle — утримання.
- Пакети йдуть на фіксованих **20 Гц незалежно від подій клавіатури** — рівномірна
  часова сітка потрібна парсеру.

## Запуск (продакшн-шлях — MAVProxy-модуль)

```bash
./tools/run-sitl.sh
```

Піднімає SITL + MAVProxy (`sim_vehicle.py --mavproxy-args "--load-module
keyboard_adapter"`). **Живцем виявлено**: MAVProxy для стороннього модуля імпортує
голе ім'я `keyboard_adapter` (не `mavproxy_keyboard_adapter`) — тобто саме цей пакет,
з `init()` у його `__init__.py`; `PYTHONPATH` (`run-sitl.sh` виставляє на
`tools/keyboard_adapter/src`) потрібен, щоб пакет узагалі був видимий. Ні `uv sync`,
ні окремий процес не потрібні — модуль виконується в тому Python-оточенні, де вже
живе сама MAVProxy (`~/venv-ardupilot`, `tools/prereqs.sh` ставить туди `evdev`).

### Клавіатурний бекенд: лише `evdev`

Читає `/dev/input` напряму (kernel input layer) — однаково на Xorg і Wayland, без
залежності від дисплейного сервера. `pynput` (X11 global-grab) свідомо не використовується:
той вимагав би саме Xorg-сесії й ламався б на Wayland (типова Ubuntu 22.04+), а оскільки
продакшн-шлях один (MAVProxy-модуль, не вибір користувача під час запуску) — тримати
другий бекенд заради Xorg-варіанту сенсу нема, лише зайва гілка коду й тестів.

Потребує групи `input` (`./tools/prereqs.sh`, ідемпотентно; релогін після першого
додавання). Автовизначення бере перший пристрій із `KEY_A`; якщо обрало не той —
`KEYBOARD_DEVICE=/dev/input/event3 ./tools/run-sitl.sh` (`ls /dev/input/by-id/` або
`sudo libinput list-devices`, щоб знайти правильний).

`evdev` не встановлюється на macOS (лінукс-специфічне C-розширення, env-маркер у
`pyproject.toml`) — це не проблема, бо стенд там і не запускається (`README.mac.md`).
Не впливає на тести: логіка осей і дешифрування подій ізольовані від реального I/O й
тестуються без реального `evdev` (`tests/evdev_fakes.py`).

## `cli.py` — окремо, лише dev-debug

`cli.py` (`uv run keyboard-adapter`) лишається як окремий процес, але **не** для
пілотування — для перевірки перехоплення клавіш/мапінгу осей у ізоляції, без MAVProxy:

```bash
uv sync
uv run keyboard-adapter --dry   # без SITL/MAVLink — лише клавіші й осі в консоль
uv run keyboard-adapter --connect udp:127.0.0.1:14550   # ad hoc, повз MAVProxy-модуль
```

Другий варіант відкриває ВЛАСНИЙ UDP-конект до SITL паралельно з MAVProxy-модулем —
навмисно не використовується `run-sitl.sh` (саме такого дублювання й уникає перехід на
модуль, CLAUDE.md), корисний лише для точкового ручного дебагу.

## Структура

```
src/keyboard_adapter/
├── __init__.py         # init(mpstate) — MAVProxy-конвенція завантаження модуля
│                       # (лінива імпортація MAVProxy.modules.lib.mp_module,
│                       # MPModule-підклас визначено ЛОКАЛЬНО всередині init(),
│                       # щоб решта пакета лишалась імпортовною без MAVProxy)
├── axes.py             # чиста логіка осей (AxisState.step) — тестується без I/O
├── loop.py             # цикл 20 Гц + формування MANUAL_CONTROL (duck-typed залежності)
├── mavproxy_glue.py     # ТЕСТОВАНА логіка модуля: тред, адаптація self.master,
│                        # кооперативна зупинка — без залежності від пакета MAVProxy
├── evdev_source.py      # клавіатурний бекенд (kernel /dev/input; Xorg і Wayland однаково)
└── cli.py               # dev-debug entrypoint (--dry), НЕ шлях пілотування
```

**Живцем виявлено:** MAVProxy шукає сторонні модулі не за файлом `mavproxy_<name>.py`
на `PYTHONPATH` (це працює лише для модулів усередині самого пакета MAVProxy) — для
`--load-module keyboard_adapter` фолбек-шлях імпортує голе ім'я `keyboard_adapter`.
Перша спроба (окремий top-level `mavproxy_keyboard_adapter.py` поряд із пакетом)
падала: `import keyboard_adapter` знаходив сам пакет, не той файл — `ERROR ... has no
attribute 'init'`. Тому `init()` живе прямо в `__init__.py`, а не в окремому shim-файлі.

Тести: `uv run pytest`. Сценарії та граничні значення — `TEST-PLAN.md`.

Типи: `uv run mypy` — strict-режим на `src/keyboard_adapter/` і `tests/`. `mav`/`clock`/
`keys_source`/`link` описані протоколами (`ManualControlSender`, `Clock`, `KeysSource`,
`MavlinkLink`), а не `Any`; тестові фейки структурно їм відповідають, що mypy перевіряє
статично. `ignore_missing_imports` увімкнено точково лише для `pymavlink.*`, `evdev.*` і
`MAVProxy.*` (жоден не постачає stubs; `MAVProxy` і зовсім не встановлений у
dev-оточенні — лише в ArduPilot-оточенні на Ubuntu-хості). Тести `evdev_source.py`
підміняють увесь модуль `evdev` у `sys.modules` фейком (`tests/evdev_fakes.py`) —
реальний пакет для прогону тестів не потрібен, тож усе працює й на macOS, де `evdev`
узагалі не встановлюється. `__init__.py`'s `init()` лишається неперевіреним
mypy/pytest (той самий принцип, що раніше — MAVProxy-залежна частина мінімальна й
лінива), уся тестована логіка — в `mavproxy_glue.py`.

# Кореневий Makefile. Розгортання на VPS — vps/provision.sh (сам себе клонує,
# сам собі будує образи), не через цілі тут.

DATA_DIR ?= $(CURDIR)/data
INBOX_DIR := $(DATA_DIR)/inbox
RESULTS_DIR := $(DATA_DIR)/results

COMPOSE_DIR := vps/compose
COMPOSE := docker compose --project-directory $(COMPOSE_DIR) -f $(COMPOSE_DIR)/docker-compose.yml

# Дефолт відповідає local/provision.sh (клонує .sitl/ у корені репозиторію на VM);
# перевизначити можна через .envrc (VM_ARDUPILOT_DIR), якщо клон на VM лежить деінде.
VM_ARDUPILOT_DIR ?= ~/ardupilot_log_analysis/.sitl

.PHONY: fetch-logs stack-up stack-down test parse

# Витягує свіжі .BIN (DataFlash) і .tlog з Ubuntu VM (UTM) на хост-машину,
# у watched-теку парсера. Це dev-зручність для локальної перевірки пайплайна
# з реального SITL-польоту — НЕ той транспорт, що йде на VPS (там WireGuard +
# rsync через local/push-logs.sh, README.md крок 5); тут звичайний SSH у
# межах локальної мережі UTM. Обидва файли — в одній теці (run-sitl.sh's
# --logfile ставить .tlog поряд із .BIN, local/run-sitl.sh), тож один rsync.
fetch-logs:
	@test -n "$(VM_HOST)" || { echo "VM_HOST не встановлено (див. .envrc)"; exit 1; }
	@test -n "$(VM_USER)" || { echo "VM_USER не встановлено (див. .envrc)"; exit 1; }
	mkdir -p $(INBOX_DIR)
	rsync -avz "$(VM_USER)@$(VM_HOST):$(VM_ARDUPILOT_DIR)/ArduPlane/logs/" $(INBOX_DIR)/

# Локальний прогін parser+web+caddy тим самим compose-файлом, що й на VPS
# (vps/compose/docker-compose.yml) — build: контекст той самий, compose сам
# збирає образи під поточну машину (тут це не проблема — на відміну від VPS,
# локальний прогін не мусить бути amd64).
stack-up:
	mkdir -p $(INBOX_DIR) $(RESULTS_DIR)
	DATA_DIR=$(DATA_DIR) $(COMPOSE) up -d --build

stack-down:
	$(COMPOSE) down

test:
	cd vps/services/parser && uv run mypy && uv run pytest -q
	cd vps/services/web && npm run lint && npm test && npx playwright test

# Разовий прогін воркера на одному файлі, без watcher-а — для локальної перевірки
# пайплайна на реальному .bin без піднятого стеку. FILE=шлях/до/flight.bin.
parse:
	@test -n "$(FILE)" || { echo "вкажи FILE=шлях/до/flight.bin"; exit 1; }
	cd vps/services/parser && uv run python -m parser.worker "$(abspath $(FILE))" --results-dir "$(RESULTS_DIR)"

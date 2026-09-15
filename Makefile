# Кореневий Makefile. Решта цілей із §6 плану (deploy) додається разом із deploy.sh.

DATA_DIR ?= $(CURDIR)/data
INBOX_DIR := $(DATA_DIR)/inbox
RESULTS_DIR := $(DATA_DIR)/results

COMPOSE_DIR := deploy/compose
COMPOSE := docker compose --project-directory $(COMPOSE_DIR) -f $(COMPOSE_DIR)/docker-compose.yml

PLATFORM ?= linux/amd64
IMAGES_TAR := dist/images.tar.gz

# Дефолт відповідає tools/prereqs.sh (клонує .sitl/ у корені репозиторію на VM);
# перевизначити можна через .envrc (VM_ARDUPILOT_DIR), якщо клон на VM лежить деінде.
VM_ARDUPILOT_DIR ?= ~/ardupilot_log_analysis/.sitl

.PHONY: fetch-logs stack-up stack-down build save test parse

# Витягує свіжі .BIN (DataFlash) і .tlog з Ubuntu VM (UTM) на хост-машину,
# у watched-теку парсера. Це dev-зручність для локальної перевірки пайплайна
# з реального SITL-польоту — НЕ той транспорт, що піде на VPS (там WireGuard +
# rsync/scp за планом, docs/implementation-plan.md §3); тут звичайний SSH у
# межах локальної мережі UTM.
fetch-logs:
	@test -n "$(VM_HOST)" || { echo "VM_HOST не встановлено (див. .envrc)"; exit 1; }
	@test -n "$(VM_USER)" || { echo "VM_USER не встановлено (див. .envrc)"; exit 1; }
	mkdir -p $(INBOX_DIR)
	rsync -avz "$(VM_USER)@$(VM_HOST):$(VM_ARDUPILOT_DIR)/ArduPlane/logs/" $(INBOX_DIR)/
	rsync -avz -m --include='*.tlog' --include='*/' --exclude='*' \
		"$(VM_USER)@$(VM_HOST):$(VM_ARDUPILOT_DIR)/ArduPlane/" $(INBOX_DIR)/

# Локальний прогін parser+web+caddy тими самими образами й compose-файлом, що й на
# VPS (deploy/compose/docker-compose.yml) — різниця лише в .env (DOMAIN/TAG/DATA_DIR).
stack-up:
	mkdir -p $(INBOX_DIR) $(RESULTS_DIR)
	DATA_DIR=$(DATA_DIR) $(COMPOSE) up -d

stack-down:
	$(COMPOSE) down

# Обидва образи під ціль VPS (типово amd64), навіть якщо білдиться на Apple Silicon —
# інакше буде "exec format error" при docker load на VPS.
build:
	docker buildx build --platform $(PLATFORM) -t ardupilot-la/parser:local --load services/parser
	docker buildx build --platform $(PLATFORM) -t ardupilot-la/web:local --load services/web

# offline docker load на VPS: образи не білдяться і не тягнуться з registry на самому
# VPS (§7 плану) — лише цей tar.gz копіюється туди deploy.sh.
save: build
	mkdir -p dist
	docker save ardupilot-la/parser:local ardupilot-la/web:local | gzip > $(IMAGES_TAR)
	@echo "-> $(IMAGES_TAR)"

test:
	cd services/parser && uv run mypy && uv run pytest -q
	cd services/web && npm run lint && npm test && npx playwright test

# Разовий прогін воркера на одному файлі, без watcher-а — для локальної перевірки
# пайплайна на реальному .bin без піднятого стеку. FILE=шлях/до/flight.bin.
parse:
	@test -n "$(FILE)" || { echo "вкажи FILE=шлях/до/flight.bin"; exit 1; }
	cd services/parser && uv run python -m parser.worker "$(abspath $(FILE))" --results-dir "$(RESULTS_DIR)"

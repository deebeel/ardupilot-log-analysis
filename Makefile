# Кореневий Makefile. Поки що лише fetch-logs — решта цілей з §6 плану
# (build/save/test/deploy) додаються разом із відповідними частинами стенду.

DATA_DIR ?= data
INBOX_DIR := $(DATA_DIR)/inbox

# Дефолт відповідає docs/host-prerequisites.md; перевизначити можна через
# .envrc (VM_ARDUPILOT_DIR), якщо клон на VM лежить деінде.
VM_ARDUPILOT_DIR ?= ~/Documents/ardupilot

.PHONY: fetch-logs setup-input-group

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

# Один раз на Ubuntu VM/bare-metal перед `--input-backend evdev` (docs/host-prerequisites.md
# §5) — /dev/input читається лише членами групи `input` або root. Ідемпотентно: якщо
# користувач вже в групі, нічого не робить і не питає sudo-пароль вдруге.
setup-input-group:
	@if id -nG "$$USER" | tr ' ' '\n' | grep -qx input; then \
		echo "$$USER вже в групі input"; \
	else \
		sudo usermod -aG input "$$USER"; \
		echo "Додано $$USER до групи input — потрібен релогін (вийти й зайти знову), щоб група застосувалась."; \
	fi

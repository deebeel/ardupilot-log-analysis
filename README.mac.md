# Розробка на macOS (не для стенду)

Цей файл — лише для розробки `parser`/`web` на Mac. Сам стенд (SITL, MAVProxy,
`keyboard_adapter`) на Mac не запускається — весь він живе в Ubuntu VM/bare-metal,
опис — у канонічному `README.md`. Рев'юєру цей файл не потрібен.

## Залежності

- **`uv`** (Python, для `vps/services/parser` і `local/keyboard_adapter`):

  ```bash
  brew install uv
  ```

- **Node.js** (для `vps/services/web`, Astro):

  ```bash
  brew install node
  ```

- **Docker Desktop** — лише для локального прогону стека (`make stack-up`) і, за
  потреби, збірки образів під VPS. VPS сам нативний `amd64`, тож образи для нього
  збираються прямо там (`vps/provision.sh`), не на Mac — крос-збірка/перенесення
  tar.gz не потрібні.

`evdev` (клавіатурний бекенд `keyboard_adapter`) — лінукс-специфічний; env-маркер у
`local/keyboard_adapter/pyproject.toml` не дає `uv sync` намагатись поставити його на
macOS.

## Типові команди

```bash
cd vps/services/parser && uv sync && uv run mypy && uv run pytest -q
cd vps/services/web && npm install && npm run lint && npm test && npx playwright test
cd local/keyboard_adapter && uv sync && uv run mypy && uv run pytest -q
```

Локальний прогін усього стека (`parser`+`web`+`caddy`, той самий
`vps/compose/docker-compose.yml`, що на VPS):

```bash
make stack-up      # docker compose up -d --build, дані в ./data/
make stack-down
```

`make fetch-logs` (`VM_HOST`/`VM_USER` — з `.envrc`) — тягне свіжі `.BIN`/`.tlog` з
Ubuntu VM (UTM) на Mac у `./data/inbox`, звичайним SSH у межах локальної мережі. Це
dev-зручність для перевірки пайплайна на реальному польоті без піднятого WireGuard —
не той транспорт, яким логи потрапляють на VPS (там `local/push-logs.sh` через
тунель, README.md крок 5).

`make parse FILE=шлях/до/flight.bin` — разовий прогін воркера-парсера на одному
файлі, без watcher-а і без піднятого стека.

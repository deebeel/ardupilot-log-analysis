# Сервіс `parser`

ArduPlane DataFlash-лог (`.bin`) → JSON із детермінованими метриками якості пілотування.
Вердикт тут **не** рахується — сервер віддає лише метрики + дефолтні пороги
(`thresholds.yaml`), категоризацію робить браузер (див. `docs/scoring-algorithm.md`).

## Команди розробника

```bash
uv sync                 # встановити залежності (runtime + dev)
uv run mypy             # статична перевірка типів, strict (src/parser + tests)
uv run pytest           # тести (unit + smoke на assets/flight-01_2026-09-11.bin)
uv run mypy && uv run pytest    # повна перевірка перед комітом
```

`uv run mypy` без аргументів перевіряє і `src/parser`, і `tests` — перелік у
`[tool.mypy] files` у `pyproject.toml`.

## Разовий прогін на файлі (без watcher-а)

```bash
uv run python -m parser.worker <log.bin> --results-dir ./out --thresholds thresholds.yaml
```

## Watcher (як у контейнері)

```bash
uv run python -m parser.watcher --inbox ./data/inbox --results-dir ./data/results
```

## Образ

```bash
docker buildx build --platform linux/amd64 -t ardupilot-la/parser:dev .
```

Multi-stage: `uv` присутній лише у build-стадії, у фінальному образі — лише `.venv` і `src`.

## Типізація

Увесь код (включно з тестами) типізований і проходить `mypy --strict`.
Послаблення — точкові й перелічені в `[[tool.mypy.overrides]]`:
`pymavlink` не має стабів, тому для нього `ignore_missing_imports = true`.

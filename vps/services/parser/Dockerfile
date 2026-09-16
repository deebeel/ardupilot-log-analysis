# Multi-stage: у фінальному образі немає uv і білд-залежностей, лише рантайм-артефакти.
# Білд під ціль: docker buildx build --platform linux/amd64 (pymavlink має C-розширення).
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY thresholds.yaml ./
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    INBOX_DIR=/data/inbox \
    RESULTS_DIR=/data/results \
    THRESHOLDS=/app/thresholds.yaml
USER 1000:1000
CMD ["python", "-m", "parser.watcher"]

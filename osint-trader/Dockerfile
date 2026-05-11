FROM python:3.12-slim AS base

# OS deps: build tools for rapidfuzz, libssl for telethon, curl for healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so the layer caches when code changes.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install --no-cache-dir \
        anthropic telethon feedparser httpx pydantic pydantic-settings pyyaml \
        tenacity rich aiosqlite structlog python-dateutil rapidfuzz \
        prometheus-client

COPY src/ ./src/
COPY config/ ./config/
COPY examples/ ./examples/
ENV PYTHONPATH=/app/src \
    LOG_FORMAT=json \
    METRICS_HOST=0.0.0.0 \
    METRICS_PORT=9108

EXPOSE 9108

# Default to dry_run; override via env in compose / production.
ENV TRADE_MODE=dry_run

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:9108/metrics > /dev/null || exit 1

CMD ["python", "-m", "osint_trader.main"]

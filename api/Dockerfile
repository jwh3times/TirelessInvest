# One image, two Railway services: the API (default CMD) and the price-sync cron job (its start
# command is set in Railway). Build from the repository root, e.g. `docker build -f api/Dockerfile .`,
# so the image carries the migrations its pre-deploy step applies (docs/adr/0001).
FROM python:3.15-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Dependencies first so code changes don't invalidate this layer.
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY api/src ./src
COPY supabase/migrations ./supabase/migrations
ENV MIGRATIONS_DIR=/app/supabase/migrations
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
# Railway injects PORT. Shell form so ${PORT} expands.
CMD uvicorn tirelessinvest.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*"

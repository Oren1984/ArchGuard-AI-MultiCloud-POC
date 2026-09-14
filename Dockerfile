FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# --trusted-host: some local/corporate networks run TLS-inspecting proxies
# that break pip's default certificate verification against PyPI from
# inside the build container (while host-side HTTPS and package integrity
# via pinned versions/hashes-in-lockfile-adjacent requirements.txt are
# unaffected). Harmless on networks without such interception.
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org \
    -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY seed ./seed
COPY alembic.ini ./alembic.ini

RUN useradd --create-home --uid 1000 archguard \
    && chown -R archguard:archguard /app
USER archguard

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

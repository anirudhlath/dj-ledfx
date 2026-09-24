# dj-ledfx: the home lighting engine and its web UIs (engine spec §6.7).
# Deploy with docker compose: see docker-compose.yml.

# Stage 1: the web UIs. frontend/ is today's UI; web/ is the new app, served at /next.
# Dependencies first, so a source change reuses the npm ci layers.
FROM node:24-slim AS ui
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci
COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci
COPY frontend/ frontend/
RUN cd frontend && npm run build
COPY web/ web/
RUN cd web && npm run build

# Stage 2: the engine, installed editable so it finds frontend/dist and web/dist.
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1
# The app's user. docker/entrypoint.sh drops to it; /app/state starts out as its own, so a
# new volume is created with that owner.
RUN groupadd --system --gid 10001 dj-ledfx \
 && useradd --system --uid 10001 --gid dj-ledfx --home-dir /app --no-create-home dj-ledfx \
 && mkdir -p /app/state && chown dj-ledfx:dj-ledfx /app/state
WORKDIR /app
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev --extra web --extra metrics --no-install-project
COPY src/ src/
RUN uv sync --frozen --no-dev --extra web --extra metrics
COPY --from=ui /build/frontend/dist frontend/dist
COPY --from=ui /build/web/dist web/dist
COPY docker/entrypoint.sh /usr/local/bin/entrypoint
ENV PATH="/app/.venv/bin:$PATH"

# /api/running answers once the engine is up; 8080 is the deployment's web.port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request as r; r.urlopen('http://127.0.0.1:8080/api/running', timeout=4)"]

# config.toml is mounted read-only and only seeds a fresh state.db, which lives on a
# volume. No --demo: the beat comes from Pro DJ Link.
ENTRYPOINT ["entrypoint"]
CMD ["python", "-m", "dj_ledfx", "--web", "--web-host", "0.0.0.0", \
     "--config", "/app/config/config.toml", "--db", "/app/state/state.db"]

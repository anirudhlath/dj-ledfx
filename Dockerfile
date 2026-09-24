# dj-ledfx: the home lighting engine and its web UIs (engine spec §6.7).
# Deploy with docker compose: see docker-compose.yml.

# Stage 1: the web UIs. frontend/ is today's UI; web/ is the new app, served at /next
# once F0 has landed (until then web/dist stays empty).
FROM node:24-slim AS ui
WORKDIR /build
COPY . .
RUN cd frontend && npm ci && npm run build
RUN if [ -f web/package.json ]; then cd web && npm ci && npm run build; else mkdir -p web/dist; fi

# Stage 2: the engine, installed editable so it finds frontend/dist and web/dist.
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev --extra web --extra metrics --no-install-project
COPY src/ src/
RUN uv sync --frozen --no-dev --extra web --extra metrics
COPY --from=ui /build/frontend/dist frontend/dist
COPY --from=ui /build/web/dist web/dist
ENV PATH="/app/.venv/bin:$PATH"

# config.toml is mounted read-only and only seeds a fresh state.db, which lives on a
# volume. No --demo: the beat comes from Pro DJ Link.
CMD ["python", "-m", "dj_ledfx", "--web", "--web-host", "0.0.0.0", \
     "--config", "/app/config/config.toml", "--db", "/app/state/state.db"]

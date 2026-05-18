FROM node:24-bookworm-slim AS webui-build

WORKDIR /build/webui

COPY proxypool/webui/package*.json ./
RUN npm ci

COPY proxypool/webui/index.html ./index.html
COPY proxypool/webui/vite.config.js ./vite.config.js
COPY proxypool/webui/css ./css
COPY proxypool/webui/src ./src
RUN npm run build


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PROXYPOOL_DB_PATH=/app/data/proxies.db \
    PROXYPOOL_OUTPUT_DIR=/app/output \
    PROXYPOOL_SOURCES_FILE=/app/configs/sources.txt \
    PROXYPOOL_SINGBOX_ROUTES_FILE=/app/configs/singbox-routes.json \
    PROXYPOOL_SINGBOX_RUNTIME_CONFIG=/app/data/runtime/singbox.json \
    PROXYPOOL_SINGBOX_RUNTIME_LOG=/app/data/runtime/singbox.log \
    PROXYPOOL_SINGBOX_BINARY=/app/bin/sing-box \
    PROXYPOOL_MIHOMO_BINARY=/app/bin/mihomo \
    PROXYPOOL_MIHOMO_RUNTIME_DIR=/app/data/runtime/mihomo

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PROXYPOOL_WEBUI_HOST=0.0.0.0 \
    PROXYPOOL_WEBUI_PORT=8080

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

COPY proxypool ./proxypool
COPY README.md ./README.md
COPY --from=webui-build /build/webui/dist ./proxypool/webui/dist

RUN mkdir -p /app/data/runtime/mihomo /app/output /app/configs /app/bin

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PROXYPOOL_WEBUI_PORT:-8080}/api/health" || exit 1

CMD ["python", "-m", "proxypool.main"]

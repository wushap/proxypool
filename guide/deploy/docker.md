# Docker Deployment

This project can run as a Docker container with FastAPI, the built Vite Web UI, SQLite runtime data, and local proxy backend binaries mounted from the host.

## Files

- `Dockerfile` builds the Web UI in a Node stage, installs Python dependencies with `uv`, then copies the static `dist/` assets into a slim Python runtime image.
- `docker-compose.yml` starts the app on port `8080` and mounts runtime directories.
- `.dockerignore` keeps local databases, output, frontend dependencies, and host binaries out of the build context.

## Host Directories

The compose service uses these mounts:

- `./data:/app/data` for SQLite and runtime process files.
- `./output:/app/output` for generated exports and task output.
- `./configs:/app/configs` for source lists and route configuration.
- `./bin:/app/bin:ro` for `sing-box` and `mihomo`.

Put Linux-compatible backend binaries here before starting the service:

```bash
mkdir -p bin data output configs
chmod +x bin/sing-box bin/mihomo
```

The image does not copy `./bin` by default because those binaries are platform-specific and are ignored by git.

## Start

```bash
docker compose up -d --build
```

Open the Web UI:

```text
http://127.0.0.1:8080/
```

View logs:

```bash
docker compose logs -f proxypool
```

Stop:

```bash
docker compose down
```

## Environment

Common runtime variables:

- `PROXYPOOL_API_KEY` protects mutating API calls with `X-API-Key`.
- `PROXYPOOL_HTTP_GATEWAY_DEFAULT_HOST` defaults to `0.0.0.0` in Docker so published proxy ports can be reached from the host.
- `PROXYPOOL_HTTP_GATEWAY_DEFAULT_PORT` defaults to `8899`.
- `PROXYPOOL_SOURCES_FILE` defaults to `/app/configs/sources.txt`.
- `PROXYPOOL_DB_PATH` defaults to `/app/data/proxies.db`.
- `PROXYPOOL_OUTPUT_DIR` defaults to `/app/output`.
- `PROXYPOOL_SINGBOX_BINARY` defaults to `/app/bin/sing-box`.
- `PROXYPOOL_MIHOMO_BINARY` defaults to `/app/bin/mihomo`.

Example:

```bash
PROXYPOOL_API_KEY=change-me PROXYPOOL_HTTP_GATEWAY_DEFAULT_PORT=18899 docker compose up -d --build
```

## HTTP Proxy Endpoint Ports

The Web UI/API always runs on container port `8080`. HTTP proxy endpoints are separate listeners, so each endpoint that must be accessed from the host needs both:

1. The endpoint listen host set to `0.0.0.0`.
2. A matching compose port mapping.

For example, if an endpoint listens on `18899`, add:

```yaml
ports:
  - "8080:8080"
  - "18899:18899"
```

If the endpoint listens on `127.0.0.1` inside the container, Docker port publishing will not expose it reliably to the host. Use `0.0.0.0` for container deployments.

## Data Persistence

The database and runtime state live in `./data`. Rebuilding the image does not delete them. To start from a clean state, stop the container and remove or archive `./data/proxies.db`.

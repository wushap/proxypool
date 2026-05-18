# Docker Deployment

This project can run as a Docker container with FastAPI, the built Vite Web UI, SQLite runtime data, and local proxy backend binaries mounted from the host.

## Files

- `Dockerfile` builds the Web UI in a Node stage, installs Python dependencies with `uv`, then copies the static `dist/` assets into a slim Python runtime image.
- `docker-compose.yml` runs the app with host networking and mounts runtime directories.
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

The compose service uses `network_mode: host`, so the app binds directly on the host network stack. Open the Web UI:

```text
http://127.0.0.1:18080/
```

On native Linux Docker, host networking means listeners are created directly on the host. On Docker Desktop or WSL-based Docker, host networking may be scoped to the Docker VM rather than the WSL/user host; in that environment, verify access from your actual deployment host before relying on external clients.

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
- `PROXYPOOL_WEBUI_HOST` defaults to `0.0.0.0` in Docker.
- `PROXYPOOL_WEBUI_PORT` defaults to `18080` in Docker.
- `PROXYPOOL_HTTP_GATEWAY_DEFAULT_HOST` defaults to `0.0.0.0` in Docker so proxy ports can be reached from outside the host when firewall rules allow it.
- `PROXYPOOL_HTTP_GATEWAY_DEFAULT_PORT` defaults to `18899`.
- `PROXYPOOL_SOURCES_FILE` defaults to `/app/configs/sources.txt`.
- `PROXYPOOL_DB_PATH` defaults to `/app/data/proxies.db`.
- `PROXYPOOL_OUTPUT_DIR` defaults to `/app/output`.
- `PROXYPOOL_SINGBOX_BINARY` defaults to `/app/bin/sing-box`.
- `PROXYPOOL_MIHOMO_BINARY` defaults to `/app/bin/mihomo`.

Example:

```bash
PROXYPOOL_API_KEY=change-me PROXYPOOL_WEBUI_PORT=18080 PROXYPOOL_HTTP_GATEWAY_DEFAULT_PORT=18899 docker compose up -d --build
```

## HTTP Proxy Endpoint Ports

The Web UI/API listens on host port `18080` by default. HTTP proxy endpoints are separate listeners and use `18899` by default. Because compose uses host networking, newly created endpoint ports do not need explicit `ports` mappings.

Use these rules:

- For local-only access on the host, use `127.0.0.1`.
- For access from other machines, set the endpoint listen host to `0.0.0.0` and allow the port through the host firewall.

Host networking is intentional here because proxy endpoints can be added dynamically from the Web UI/API. Bridge networking would require updating compose port mappings for every new listener.

## Data Persistence

The database and runtime state live in `./data`. Rebuilding the image does not delete them. To start from a clean state, stop the container and remove or archive `./data/proxies.db`.

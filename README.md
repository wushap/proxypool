# ProxyPool

[![CI](https://github.com/your-org/proxypool/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/proxypool/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> High-performance proxy pool manager with health checks, chain routing, and WebUI.

## Features

- **Multi-protocol Support**: Trojan, VMess, SS, Hysteria2
- **Health Checks**: Automatic proxy health monitoring with configurable intervals
- **Chain Routing**: Multi-hop proxy chains with session persistence and sticky routes
- **WebUI**: Modern Vue 3.5 dashboard with real-time updates
- **API**: RESTful API with OpenAPI documentation and rate limiting
- **Docker**: Production-ready containerization with health checks
- **Security**: SSRF protection, path traversal prevention, API key authentication
- **Performance Monitoring**: Real-time metrics, bottleneck detection, and capacity planning
- **Configuration Wizards**: Guided setup for pools, subscriptions, and backend
- **Export/Import**: CSV and JSON export for proxies, pools, and configurations
- **System Health Dashboard**: Health scoring, trend analysis, and alerting rules

## Quick Start

### Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/proxypool.git
cd proxypool

# Prepare binary files
mkdir -p bin
cp /path/to/sing-box bin/
cp /path/to/mihomo bin/
chmod +x bin/*

# Start with Docker Compose
make docker

# Access WebUI
open http://localhost:18080
```

### Local Development

```bash
# Prerequisites
# - Python 3.12+
# - Node.js 20+ (for WebUI)
# - sing-box and mihomo binaries (optional)

# Install dependencies
make install

# Run tests
make test

# Start development server
make run
```

### Manual Setup

```bash
# Install dependencies (uv manages virtualenv automatically)
uv sync

# Install and build WebUI
cd proxypool/webui
npm install
npm run build
cd ../..

# Start server
uv run python -m proxypool.main
```

## Documentation

Comprehensive documentation is available in the [docs/](docs/) directory:

- **[Deployment Guide](docs/deployment.md)**: Docker, manual, and systemd deployment instructions
- **[Troubleshooting Guide](docs/troubleshooting.md)**: Common issues and solutions
- **[API Reference](docs/api.md)**: Complete API endpoint documentation
- **[Contributing Guidelines](CONTRIBUTING.md)**: How to contribute to the project
- **[Product Benchmark](docs/product-benchmark.md)**: Feature comparison with competitors
- **[Interactive API Docs](http://localhost:8080/docs)**: Swagger UI (when running)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXYPOOL_DB_PATH` | `./data/proxies.db` | SQLite database path |
| `PROXYPOOL_API_KEY` | (empty) | API key for authentication |
| `PROXYPOOL_WEBUI_PORT` | `8080` | WebUI port |
| `PROXYPOOL_SINGBOX_BINARY` | `sing-box` | Path to sing-box binary |
| `PROXYPOOL_MIHOMO_BINARY` | `mihomo` | Path to mihomo binary |
| `PROXYPOOL_BACKEND_ENGINE` | `singbox` | Backend engine (singbox/mihomo) |
| `PROXYPOOL_SOURCES_FILE` | `./configs/sources.txt` | Proxy sources file |
| `PROXYPOOL_TEST_URL` | `https://www.cloudflare.com/cdn-cgi/trace` | Test URL for health checks |
| `PROXYPOOL_HTTP_GATEWAY_DEFAULT_HOST` | `127.0.0.1` | Default gateway listen host |
| `PROXYPOOL_HTTP_GATEWAY_DEFAULT_PORT` | `8899` | Default gateway listen port |
| `PROXYPOOL_MAX_PROXY_COUNT` | `50000` | Maximum number of proxies to store |
| `PROXYPOOL_FETCH_MAX_CONTENT_LENGTH` | `10485760` | Max content size for subscription fetches (bytes) |
| `PROXYPOOL_MAX_FAILURES_THRESHOLD` | `5` | Auto-mark proxies unavailable after N failures |
| `PROXYPOOL_LOG_MAX_BYTES` | `52428800` | Max log file size before rotation (bytes) |
| `PROXYPOOL_LOG_BACKUP_COUNT` | `5` | Number of rotated log files to keep |

### Example `.env`

```env
PROXYPOOL_API_KEY=my-secret-key
PROXYPOOL_WEBUI_PORT=8080
PROXYPOOL_SINGBOX_BINARY=/usr/local/bin/sing-box
PROXYPOOL_BACKEND_ENGINE=singbox
```

### Authentication

When `PROXYPOOL_API_KEY` is set, write endpoints require authentication:

```bash
# Example: Start tester with API key
curl -X POST http://localhost:8080/api/tester/run \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"limit": 100}'
```

Read-only endpoints (GET /api/health, /api/stats, /api/proxies) don't require authentication.

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Pool statistics |
| GET | `/api/proxies` | List proxies |
| GET | `/api/proxies/stats` | Proxy statistics |
| POST | `/api/pools` | Create proxy pool |
| GET | `/api/pools` | List pools |
| GET | `/api/pools/{id}/metrics` | Pool metrics |
| POST | `/api/collector/import-urls` | Import from URLs |
| POST | `/api/collector/import-files` | Import from files |
| POST | `/api/tester/run` | Run health tests |
| POST | `/api/tasks/tester/start` | Start async tester |
| GET | `/api/subscription` | Export subscription |
| POST | `/api/backend/start` | Start backend |
| GET | `/api/system/health` | Detailed system health |
| GET | `/api/system/metrics` | System performance metrics |
| GET | `/api/config/export` | Export configuration |
| POST | `/api/config/import` | Import configuration |

## Architecture

```
proxypool/
├── api/            # FastAPI routes and schemas
├── collector/      # Subscription and source management
├── configs/        # Configuration files
├── gateway/        # HTTP/CONNECT proxy gateway
├── pool/           # Proxy pool and chain service
├── security/       # Security utilities (SSRF protection, etc.)
├── storage/        # SQLite storage layer
├── tasks/          # Background task manager
├── tester/         # Proxy health testing
├── webui/          # Vue 3.5 frontend
└── main.py         # Application entry point
```

### Key Components

- **Collector**: Multi-protocol link parsing, Base64 subscription parsing, Clash YAML parsing
- **Tester**: Health testing via sing-box socks inbound (fallback to TCP if sing-box unavailable)
- **Backend Manager**: Multiple inbound ports mapped to different outbound proxies
- **Storage**: SQLite persistence with status writeback and statistics
- **Security**: SSRF protection, path traversal prevention, API key authentication
- **GeoIP**: IP geolocation enrichment (country/city)
- **Scheduler**: Scheduled collection and testing

## Development

### Commands

```bash
make help           # Show all commands
make test           # Run tests
make test-cov       # Run tests with coverage
make test-security  # Run security tests
make test-e2e       # Run E2E tests (Playwright, requires server running)
make lint           # Check code style
make lint-fix       # Fix linting issues
make format         # Format code
make type-check     # Run type checks
make check          # Run all checks (lint + type-check + test)
make clean          # Clean temporary files
```

### Code Quality

The project uses:
- **Ruff** for linting and formatting
- **Mypy** for type checking
- **Pytest** for testing
- **Pre-commit** for git hooks

```bash
# Install pre-commit hooks
make install

# Run all checks before commit
make check
```

### Adding Tests

1. Create test file: `tests/test_<module>.py`
2. Use fixtures from `tests/conftest.py`
3. Run: `make test`

### Security

- All API mutations require authentication (when `PROXYPOOL_API_KEY` is set)
- SSRF protection: Internal IPs and metadata endpoints are blocked
- Path traversal protection: File access is restricted to allowed directories
- Rate limiting: Applied to prevent abuse

## Docker

### Build and Run

```bash
# Build image
make build

# Start containers
make docker

# Stop containers
make stop-docker
```

### Volumes

| Volume | Container Path | Description |
|--------|----------------|-------------|
| `./data` | `/app/data` | SQLite database and runtime files |
| `./output` | `/app/output` | Export and task output |
| `./configs` | `/app/configs` | Subscription sources, routes config |
| `./bin` | `/app/bin` | sing-box, mihomo binaries (read-only) |

### Ports

- **18080**: WebUI and API (configurable via `PROXYPOOL_WEBUI_PORT`)
- **18899**: HTTP proxy endpoint (configurable in WebUI)

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/import_output_sources.py` | Import sample proxies from output/ |
| `scripts/import_sources_file.py` | Import from configs/sources.txt |
| `scripts/run_once_tester.py` | Run one-time health test |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) for detailed information.

### Quick Start

### Development Workflow

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run checks (`make check`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Code Standards

- **Python**: Follow PEP 8, use type hints, write docstrings
- **JavaScript/Vue**: Follow ESLint rules, use Composition API
- **Testing**: Write tests for new features, maintain >80% coverage
- **Commits**: Use conventional commits (feat:, fix:, docs:, etc.)

### Development Setup

```bash
# Install development dependencies
make install

# Run pre-commit hooks
pre-commit install

# Run full check suite before committing
make check
```

### Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_api_pools.py -v

# Run security tests
make test-security
```

### Documentation

- Update README.md for new features
- Add docstrings to new functions
- Update API documentation if adding endpoints
- See [docs/](docs/) for detailed guides

## Support

- Documentation: https://your-org.github.io/proxypool
- Issues: https://github.com/your-org/proxypool/issues
- Discussions: https://github.com/your-org/proxypool/discussions

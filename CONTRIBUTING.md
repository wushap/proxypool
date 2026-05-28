# Contributing to ProxyPool

Thank you for your interest in contributing to ProxyPool! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

- Be respectful and constructive
- Focus on what is best for the community
- Show empathy towards other contributors

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+ (for WebUI)
- Git
- sing-box or mihomo binaries (optional, for testing backend)

### Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/your-username/proxypool.git
cd proxypool
git remote add upstream https://github.com/your-org/proxypool.git
```

---

## Development Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Install WebUI dependencies (optional)
cd proxypool/webui
npm install
cd ../..
```

### 2. Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit .env with your settings
# At minimum, set:
# PROXYPOOL_API_KEY=test-key
```

### 3. Verify Setup

```bash
# Run all checks
make check

# Start development server
make run
```

---

## Code Style

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use double quotes for strings

**Example**:
```python
def get_proxy_by_id(proxy_id: int) -> ProxyNode | None:
    """Get proxy by ID from storage."""
    return storage.get_proxy(proxy_id)
```

### JavaScript/Vue

- Follow ESLint configuration in `.eslintrc.js`
- Use Composition API for Vue components
- Use `<script setup>` syntax

**Example**:
```vue
<script setup>
import { ref, onMounted } from 'vue'

const data = ref([])

onMounted(async () => {
  const response = await fetch('/api/proxies')
  data.value = await response.json()
})
</script>
```

### Linting

```bash
# Check Python code
make lint

# Auto-fix issues
make lint-fix

# Format code
make format

# Check frontend
cd proxypool/webui
npm run lint
```

---

## Testing Requirements

### Writing Tests

1. Create test file: `tests/test_<module>.py`
2. Use fixtures from `tests/conftest.py`
3. Follow pytest naming conventions: `test_<function_name>`

**Example**:
```python
import pytest
from proxypool.storage.sqlite import SQLiteProxyStorage

def test_upsert_proxy():
    """Test inserting a proxy."""
    storage = SQLiteProxyStorage(":memory:")
    proxy = ProxyNode(
        protocol="trojan",
        host="example.com",
        port=443,
        raw_link="trojan://example.com:443"
    )
    result = storage.upsert_proxy(proxy)
    assert result is not None

@pytest.mark.anyio
async def test_api_health():
    """Test health endpoint."""
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
```

### Running Tests

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

### Coverage Requirements

- Maintain >80% code coverage
- New features must include tests
- Bug fixes must include regression tests

---

## Pull Request Process

### 1. Create Branch

```bash
# Sync with upstream
git fetch upstream
git checkout -b feature/your-feature upstream/master
```

### 2. Make Changes

- Write clean, focused commits
- Follow code style guidelines
- Add tests for new functionality
- Update documentation if needed

### 3. Run Checks

```bash
# Run all checks before committing
make check

# This runs:
# - ruff check (linting)
# - ruff format (formatting)
# - pytest (tests)
```

### 4. Commit Changes

Use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Feature
git commit -m "feat: add proxy comparison view"

# Bug fix
git commit -m "fix: resolve health check timeout"

# Documentation
git commit -m "docs: update API documentation"

# Refactoring
git commit -m "refactor: simplify pool filter logic"

# Tests
git commit -m "test: add pool creation tests"
```

### 5. Push and Create PR

```bash
git push origin feature/your-feature
```

Then create a Pull Request on GitHub with:

- **Title**: Clear, concise description
- **Description**: What changed and why
- **Testing**: How you tested the changes
- **Screenshots**: If UI changes (attach screenshots)

### 6. Code Review

- Address reviewer feedback
- Make requested changes
- Push updates to the same branch

### 7. Merge

Once approved, a maintainer will merge your PR.

---

## Reporting Issues

### Bug Reports

Include:

1. **Environment**: OS, Python version, ProxyPool version
2. **Steps to Reproduce**: Clear steps
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Logs**: Relevant error messages

### Feature Requests

Include:

1. **Use Case**: Why this feature is needed
2. **Proposed Solution**: How it should work
3. **Alternatives**: Other approaches considered

---

## Development Guidelines

### Adding New API Endpoints

1. Create route in appropriate `proxypool/api/routers/` file
2. Add response model in `proxypool/api/schemas.py`
3. Add tests in `tests/test_api_<module>.py`
4. Update `docs/api.md`

### Adding New Features

1. Create feature branch
2. Implement with tests
3. Update documentation
4. Submit PR with clear description

### Fixing Bugs

1. Create test that reproduces the bug
2. Verify test fails
3. Fix the bug
4. Verify test passes
5. Submit PR with bug description and fix

---

## Questions?

- Open a [Discussion](https://github.com/your-org/proxypool/discussions)
- Check [Documentation](docs/)
- Review existing [Issues](https://github.com/your-org/proxypool/issues)

Thank you for contributing!

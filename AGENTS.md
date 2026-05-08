# Repository Guidelines

## Project Structure & Module Organization
Core application code lives in `proxypool/`. Key modules are `api/` for FastAPI routes and schemas, `collector/` for source import and parsing, `tester/` for proxy checks, `backend/` for `sing-box` process management, `storage/` for SQLite persistence, `scheduler/` for periodic jobs, and `tasks/` for long-running task state. Tests are in `tests/`. Runtime configs and sample inputs live in `configs/`, and supporting design notes are in `docs/`. Utility entry scripts are in `scripts/`.

## Build, Test, and Development Commands
Create a local environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the API and Web UI locally with `python3 -m proxypool.main`. Import source lists with `python3 scripts/import_sources_file.py`, or load sample output data with `python3 scripts/import_output_sources.py`. Run one manual test pass with `python3 scripts/run_once_tester.py`.

## Coding Style & Naming Conventions
Follow existing Python conventions: 4-space indentation, `snake_case` for functions and modules, `PascalCase` for classes, and explicit type hints where practical. Keep FastAPI handlers thin and move storage, parsing, or probing logic into service classes under `proxypool/`. Match the current import style and avoid introducing a formatter-only reflow unless the file already needs edits. There is no committed linter config, so use standard PEP 8 judgment and keep changes minimal.

## Testing Guidelines
This repo uses both `unittest` and `pytest`; async API cases are marked with `pytest.mark.anyio`. Run the full suite with `python3 -m pytest tests -v`. Name new tests as `tests/test_<feature>.py`, and keep test classes or functions aligned with the module under test. Add coverage for API behavior, storage effects, and failure paths when changing collector, tester, or backend logic.

## Commit & Pull Request Guidelines
Recent history uses Conventional Commit prefixes such as `feat:`. Prefer messages like `fix: handle empty source list` or `test: cover backend restart failure`. Pull requests should summarize behavior changes, list verification commands, link related issues, and include screenshots only when `proxypool/webui/index.html` changes.

## Security & Configuration Tips
Do not commit live secrets or generated databases. Configure sensitive values through environment variables such as `PROXYPOOL_API_KEY`, `PROXYPOOL_BACKEND_ENGINE`, and `PROXYPOOL_SOURCES_FILE`. Treat `proxies.db` and local source files as development artifacts unless the change explicitly updates fixtures.

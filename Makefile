.PHONY: help test test-fast test-security test-cov test-parallel lint lint-fix format type-check check clean run run-debug build docker stop-docker install

# Default target
help:
	@echo "ProxyPool Development Commands:"
	@echo ""
	@echo "  make install       - Install dependencies"
	@echo "  make test          - Run all tests"
	@echo "  make test-fast     - Run fast tests (skip slow tests)"
	@echo "  make test-security - Run security tests"
	@echo "  make test-cov      - Run tests with coverage report"
	@echo "  make test-parallel - Run tests in parallel"
	@echo "  make lint          - Run linting"
	@echo "  make lint-fix      - Run linting with auto-fix"
	@echo "  make format        - Format code"
	@echo "  make type-check    - Run type checking"
	@echo "  make check         - Run all checks (lint + type-check + test)"
	@echo "  make clean         - Clean temporary files"
	@echo "  make run           - Start development server"
	@echo "  make run-debug     - Start server with debug mode"
	@echo "  make build         - Build Docker image"
	@echo "  make docker        - Start with Docker Compose"
	@echo "  make stop-docker   - Stop Docker Compose"
	@echo ""

# Install dependencies
install:
	pip install -e ".[dev]"
	pre-commit install

# Testing
test:
	python3 -m pytest tests/ -v

test-fast:
	python3 -m pytest tests/ -v -m "not slow"

test-security:
	python3 -m pytest tests/test_security*.py -v

test-cov:
	python3 -m pytest tests/ \
		--cov=proxypool \
		--cov-report=html \
		--cov-report=term-missing \
		-v
	@echo "Coverage report: htmlcov/index.html"

test-parallel:
	python3 -m pytest tests/ -v -n auto

# Linting
lint:
	ruff check proxypool/ tests/

lint-fix:
	ruff check --fix proxypool/ tests/

format:
	ruff format proxypool/ tests/

# Type checking
type-check:
	mypy proxypool/

# Complete check
check: lint type-check test

# Clean
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .mypy_cache .ruff_cache
	rm -rf dist build *.egg-info

# Development server
run:
	python3 -m proxypool.main

run-debug:
	DEBUG=1 python3 -m proxypool.main

# Docker
build:
	docker build -t proxypool:local .

docker:
	docker compose up -d

stop-docker:
	docker compose down

# Database migrations (if added in future)
migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(msg)"

# APEX Runtime Makefile

.PHONY: install test lint clean run migrate help

help:
	@echo "APEX Runtime - Available targets:"
	@echo "  install   - Install dependencies"
	@echo "  test      - Run tests"
	@echo "  lint      - Run linter (flake8)"
	@echo "  clean     - Remove cache and build files"
	@echo "  run       - Start the runtime server"
	@echo "  migrate   - Run database migrations"
	@echo "  help      - Show this help message"

install:
	pip install -e ".[dev]"

test:
	pytest -v --tb=short

lint:
	flake8 src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:
	python scripts/run_server.py

migrate:
	psql -h $(DB_HOST) -U $(DB_USER) -d $(DB_NAME) -f migrations/001_initial_schema.sql

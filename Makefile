# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  Makefile
# ============================================================

.PHONY: install dev build clean test lint

# ── Dev setup ────────────────────────────────────────────────
dev:
	pip install -e ".[dev]"
	pip install requests zstandard python-gnupg pyinstaller pytest

# ── Run directly ─────────────────────────────────────────────
run:
	python -m sven $(ARGS)

# ── Build binary via PyInstaller ─────────────────────────────
build:
	python3 -m PyInstaller sven.spec
	@echo ""
	@echo "Binary ready: dist/sven"

# ── Tests ────────────────────────────────────────────────────
test:
	pytest tests/ -v

# ── Lint ─────────────────────────────────────────────────────
lint:
	python -m py_compile sven/**/*.py && echo "No syntax errors"

# ── Clean ────────────────────────────────────────────────────
clean:
	rm -rf dist/ build/ __pycache__ \
		sven/__pycache__ sven/**/__pycache__

# ── Release (tag + push) ─────────────────────────────────────
release:
	@echo "Tagging v$(VERSION)..."
	git tag v$(VERSION)
	git push origin v$(VERSION)

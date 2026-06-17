# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  Makefile
# ============================================================

.PHONY: install dev build build-no-archive clean test lint

CC      = gcc
CFLAGS  = -O2 -Wall -fPIC -shared

# Core C sources (no external deps required)
CORE_SRC = libsven/vercmp.c    \
           libsven/hooks.c      \
           libsven/resolver.c   \
           libsven/filter.c     \
           libsven/graph.c      \
           libsven/checksum.c   \
           libsven/conflicts.c  \
           libsven/pacnew.c

# Check whether libarchive is available
HAVE_ARCHIVE := $(shell pkg-config --exists libarchive 2>/dev/null && echo 1 || echo 0)

ifeq ($(HAVE_ARCHIVE),1)
  ALL_SRC     = $(CORE_SRC) libsven/extract.c
  ARCHIVE_FLAGS = $(shell pkg-config --cflags --libs libarchive)
  ARCHIVE_NOTE  = (with libarchive extractor)
else
  ALL_SRC     = $(CORE_SRC)
  ARCHIVE_FLAGS =
  ARCHIVE_NOTE  = (without libarchive — Python extractor fallback active)
  $(info [sven] libarchive-dev not found — extract.c excluded. Install libarchive-dev to enable C extractor.)
endif

# ── Dev setup ────────────────────────────────────────────────
dev:
	pip install -e ".[dev]"
	pip install requests zstandard python-gnupg pyinstaller pytest

# ── Run directly ─────────────────────────────────────────────
run:
	python -m sven $(ARGS)

# ── Build binary ─────────────────────────────────────────────
build:
	@echo "[sven] Compiling libsven_core.so $(ARCHIVE_NOTE)..."
	$(CC) $(CFLAGS) -o sven/libsven_core.so $(ALL_SRC) $(ARCHIVE_FLAGS)
	@echo "[sven] Building sven binary via PyInstaller..."
	python3 -m PyInstaller sven.spec
	@echo ""
	@echo "Binary ready: dist/sven"

# ── Build without libarchive (Python extractor fallback) ─────
build-no-archive:
	@echo "[sven] Compiling libsven_core.so (core only, no libarchive)..."
	$(CC) $(CFLAGS) -o sven/libsven_core.so $(CORE_SRC)
	@echo "[sven] Building sven binary via PyInstaller..."
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
		sven/__pycache__ sven/**/__pycache__ \
		sven/libsven_core.so

# ── Release (tag + push) ─────────────────────────────────────
release:
	@echo "Tagging v$(VERSION)..."
	git tag v$(VERSION)
	git push origin v$(VERSION)

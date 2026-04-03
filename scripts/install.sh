#!/bin/bash
# ============================================================
#  Sven — Seven OS Installer
#  HANS TECH © 2024 — GPL v3
#  scripts/install.sh — The foolproof installer for Sven
# ============================================================

set -e

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[sven]${NC} $1"; }
ok()    { echo -e "${GREEN}[  ✓ ]${NC} $1"; }
warn()  { echo -e "${YELLOW}[ !! ]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

# ── Header ───────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║                                                  ║"
echo "  ║   Sven Package Manager Installer - Seven OS      ║"
echo "  ║           HANS TECH © 2024 - v1.0.0              ║"
echo "  ║                                                  ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# ── Root Check ───────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    fail "Installer must be run with root privileges (sudo)."
fi

# ── Dependency Check ─────────────────────────────────────────
info "Verifying system prerequisites..."

CHECK_FAILED=0

check_tool() {
    if command -v "$1" &> /dev/null; then
        ok "$1 found"
    else
        warn "$1 and required dependencies NOT found."
        echo "      -> Required for: $2"
        echo "      -> LFS/BLFS Chapter: $3"
        CHECK_FAILED=1
    fi
}

check_tool "python3" "Sven Runtime Engine" "LFS 9.4"
check_tool "tar" "Package Extraction" "LFS 9.4"
check_tool "zstd" "Archive Decompression" "LFS 9.4"
check_tool "gpg" "Security Verification" "BLFS 9.6"
check_tool "git" "AUR Integration" "BLFS 12.1"
check_tool "fakeroot" "Safe Package Assembly" "BLFS (General)"
check_tool "sudo" "Privileged Operations" "BLFS 15.3"

if [ $CHECK_FAILED -eq 1 ]; then
    echo ""
    fail "System check failed. Please install the missing tool(s) from LFS/BLFS before continuing."
fi

# ── Directory Setup ──────────────────────────────────────────
info "Creating system directory structure..."
mkdir -p /etc/sven
mkdir -p /var/lib/sven/sync
mkdir -p /var/lib/sven/installed
mkdir -p /var/lib/sven/snapshots
mkdir -p /var/cache/sven/pkgs
mkdir -p /var/log/sven
ok "Directories ready."

# ── Binary Placement ─────────────────────────────────────────
info "Deploying Sven executable..."
if [ -f "dist/sven" ]; then
    cp -v dist/sven /usr/bin/sven
elif [ -f "./sven" ]; then
    cp -v ./sven /usr/bin/sven
else
    info "Binary not found locally. Attempting GitHub download..."
    LATEST_URL="https://github.com/haroldmth/sven/releases/latest/download/sven-linux-x86_64"
    if command -v wget &> /dev/null; then
        wget -q --show-progress "$LATEST_URL" -O /usr/bin/sven
    elif command -v curl &> /dev/null; then
        curl -L "$LATEST_URL" -o /usr/bin/sven
    else
        fail "Neither wget nor curl found. Cannot download binary."
    fi
fi

chmod +x /usr/bin/sven
ok "Sven binary installed to /usr/bin/sven"

# ── Adoption ─────────────────────────────────────────────────
info "Running Seven OS Adoption scripts..."

# Determine script locations
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

if [ -f "$SCRIPT_DIR/adopt_lfs.py" ]; then
    # We need to set PYTHONPATH because the python module is not in site-packages
    SVEN_MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    PYTHONPATH="$SVEN_MODULE_DIR" python3 "$SCRIPT_DIR/adopt_lfs.py"
    PYTHONPATH="$SVEN_MODULE_DIR" python3 "$SCRIPT_DIR/adopt_blfs.py"
else
    warn "Adoption scripts not found in $SCRIPT_DIR. Skipping initial adoption."
    echo "      Manual adoption recommended: sven search base --adopt"
fi

ok "System adoption complete."

# ── Finalize ─────────────────────────────────────────────────
info "Refreshing sync databases..."
sven sync || warn "Failed to sync. Please check network connection later."

echo ""
ok "Sven installation finished successfully."
info "Next Steps:"
echo "    - Run 'sven list --explicit' to see your adopted system."
echo "    - Try 'sven search python' to test repo connectivity."
echo ""

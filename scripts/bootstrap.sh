#!/bin/bash
# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  scripts/bootstrap.sh — bootstrap Sven on a fresh LFS system
# ============================================================
#
#  This script gets Sven running on a bare LFS installation.
#  It installs Python dependencies, creates directory structure,
#  and runs initial setup.
#
#  Usage:  sudo bash scripts/bootstrap.sh
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

# ── Root check ───────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    fail "This script must be run as root (sudo bash scripts/bootstrap.sh)"
fi

echo ""
echo "  ╭──────────────────────────────────────────╮"
echo "  │        Sven Bootstrap for Seven OS       │"
echo "  │            HANS TECH © 2024              │"
echo "  ╰──────────────────────────────────────────╯"
echo ""

# ── Step 1: Check Python ────────────────────────────────────
info "Checking Python 3..."
if command -v python3 &> /dev/null; then
    PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    ok "Python ${PYVER} found"
else
    fail "Python 3 is not installed. Build Python >= 3.9 from LFS Chapter 8."
fi

# Check version >= 3.9
PYMAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYMINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYMAJOR" -lt 3 ] || ([ "$PYMAJOR" -eq 3 ] && [ "$PYMINOR" -lt 9 ]); then
    fail "Python >= 3.9 required (found ${PYVER})"
fi

# ── Step 2: Ensure pip is available ─────────────────────────
info "Checking pip..."
if ! python3 -m pip --version &> /dev/null; then
    info "pip not found. Bootstrapping via ensurepip..."
    python3 -m ensurepip --upgrade 2>/dev/null || {
        warn "ensurepip failed. Trying get-pip.py..."
        if command -v curl &> /dev/null; then
            curl -sS https://bootstrap.pypa.io/get-pip.py | python3
        elif command -v wget &> /dev/null; then
            wget -qO- https://bootstrap.pypa.io/get-pip.py | python3
        else
            fail "Cannot install pip. Install curl or wget first."
        fi
    }
fi
ok "pip available"

# ── Step 3: Install Python dependencies ─────────────────────
info "Installing Python dependencies..."
python3 -m pip install --quiet --break-system-packages \
    requests \
    python-gnupg \
    2>/dev/null || \
python3 -m pip install --quiet \
    requests \
    python-gnupg
ok "Python dependencies installed"

# ── Step 4: Check system tools ──────────────────────────────
info "Checking system tools..."

MISSING_TOOLS=""

for tool in git readelf tar zstd; do
    if command -v "$tool" &> /dev/null; then
        ok "$tool found"
    else
        warn "$tool NOT found"
        MISSING_TOOLS="$MISSING_TOOLS $tool"
    fi
done

if command -v gpg2 &> /dev/null || command -v gpg &> /dev/null; then
    ok "GPG found"
else
    warn "GPG not found (install gnupg2 from BLFS)"
    MISSING_TOOLS="$MISSING_TOOLS gpg"
fi

if [ -n "$MISSING_TOOLS" ]; then
    warn "Missing tools:$MISSING_TOOLS"
    warn "Sven will work partially. Install missing tools from BLFS."
fi

# ── Step 5: Create directory structure ──────────────────────
info "Creating Sven directories..."

mkdir -p /var/lib/sven/installed
mkdir -p /var/lib/sven/sync
mkdir -p /var/lib/sven/aur_cache
mkdir -p /var/lib/sven/snapshots
mkdir -p /var/cache/sven/pkgs
mkdir -p /var/cache/sven/aur
mkdir -p /var/log/sven
mkdir -p /etc/sven
mkdir -p /tmp/sven/aur
mkdir -p /tmp/sven/build

ok "Directory structure created"

# ── Step 6: Create default config if missing ────────────────
CONFIG="/etc/sven/sven.conf"
if [ ! -f "$CONFIG" ]; then
    info "Creating default config..."
    cat > "$CONFIG" << 'EOF'
[general]
install_root = /
cache_dir    = /var/cache/sven
db_path      = /var/lib/sven
log_file     = /var/log/sven/sven.log
init_system  = sysvinit

[repos]
use_official = true
use_aur      = true
aur_review   = prompt

[build]
build_dir         = /tmp/sven/aur
keep_cache        = true
parallel_jobs     = 4

[download]
parallel_downloads = 5
mirror             = auto

[upgrade]
ignored_packages =
held_packages    =
EOF
    ok "Default config created at ${CONFIG}"
else
    ok "Config already exists"
fi

# ── Step 7: Create default mirrorlist ───────────────────────
MIRRORLIST="/etc/sven/mirrorlist"
if [ ! -f "$MIRRORLIST" ]; then
    info "Creating default mirrorlist..."
    cat > "$MIRRORLIST" << 'EOF'
# Sven Mirrorlist for Seven OS
# Lines starting with # are comments.
# One mirror URL per line. Fastest mirrors first.
# Run 'sven mirror fastest' to auto-detect.
https://mirror.rackspace.com/archlinux
https://mirrors.kernel.org/archlinux
https://ftp.halifax.rwth-aachen.de/archlinux
https://mirror.aarnet.edu.au/pub/archlinux
https://mirrors.rit.edu/archlinux
EOF
    ok "Default mirrorlist created at ${MIRRORLIST}"
else
    ok "Mirrorlist already exists"
fi

# ── Step 8: Verify sven is importable ───────────────────────
info "Verifying sven module..."
SVEN_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if PYTHONPATH="$SVEN_DIR" python3 -c "import sven; print(f'sven {sven.constants.VERSION}')" 2>/dev/null; then
    ok "Sven module verified"
else
    warn "Could not import sven module. Check installation."
fi

# ── Done ────────────────────────────────────────────────────
echo ""
echo "  ╭──────────────────────────────────────────╮"
echo "  │          Bootstrap Complete!              │"
echo "  ╰──────────────────────────────────────────╯"
echo ""
info "Next steps:"
echo "    1. Run 'sven sync' to download package databases"
echo "    2. Run 'sven mirror fastest' to find your fastest mirror"
echo "    3. Run 'sven preflight' to verify your environment"
echo ""

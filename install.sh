#!/usr/bin/env bash
# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  install.sh — one liner installer
#  Usage: curl -fsSL https://sevenOS.dev/install-sven.sh | bash
# ============================================================

set -e

REPO="https://github.com/haroldmth/sven"
BINARY_URL="$REPO/releases/latest/download/sven-x86_64-linux"
INSTALL_PATH="/usr/local/bin/sven"
DB_DIRS=(
    "/var/lib/sven/installed"
    "/var/lib/sven/sync"
    "/var/lib/sven/aur_cache"
    "/var/lib/sven/snapshots"
    "/var/cache/sven/pkgs"
    "/var/cache/sven/aur"
    "/var/log/sven"
    "/etc/sven/initscripts"
    "/tmp/sven/aur"
)

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Installing Sven — Seven OS pkg manager  ║"
echo "║   by HANS TECH                            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Check root ───────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo "✗  Please run as root"
    exit 1
fi

# ── Download binary ──────────────────────────────────────────
echo ":: Downloading sven binary..."
curl -fsSL "$BINARY_URL" -o "$INSTALL_PATH"
chmod +x "$INSTALL_PATH"
echo "   → installed to $INSTALL_PATH"

# ── Create directory structure ───────────────────────────────
echo ":: Creating directory structure..."
for dir in "${DB_DIRS[@]}"; do
    mkdir -p "$dir"
done
echo "   → done"

# ── Write default config ─────────────────────────────────────
if [ ! -f /etc/sven/sven.conf ]; then
    echo ":: Writing default config → /etc/sven/sven.conf"
    cat > /etc/sven/sven.conf << 'EOF'
[general]
install_root      = /
cache_dir         = /var/cache/sven
db_path           = /var/lib/sven
init_system       = sysvinit

[repos]
use_official      = true
use_aur           = true
aur_review        = prompt

[build]
parallel_jobs     = 4
keep_cache        = true

[download]
parallel_downloads = 5
mirror             = auto

[upgrade]
ignored_packages  =
held_packages     =
EOF
fi

echo ""
echo "✓  Sven installed successfully!"
echo ""
echo "   Get started:"
echo "   → sven sync"
echo "   → sven install firefox"
echo ""
echo "   Docs: $REPO"
echo ""

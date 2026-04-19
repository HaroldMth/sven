#!/bin/bash
# ============================================================
#  Sven — Seven OS Installer
#  HANS TECH © 2024 — GPL v3
#  Run from the repository root: sudo bash install.sh
# ============================================================

set -e

VERBOSE=0
NO_SYNC=0
while [ $# -gt 0 ]; do
  case "$1" in
    -v|--verbose) VERBOSE=1; shift ;;
    --no-sync|--quick) NO_SYNC=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: sudo bash install.sh [options]

  -v, --verbose        Trace every command, environment summary, and timings
  --no-sync, --quick   Skip the final "sven sync" (faster; run sync when you want)
  -h, --help           Show this help

Examples:
  sudo bash install.sh
  sudo bash install.sh --quick
  sudo bash install.sh -v
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1 (try --help)" >&2
      exit 1
      ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[sven]${NC} $1"; }
ok()    { echo -e "${GREEN}[  ✓ ]${NC} $1"; }
warn()  { echo -e "${YELLOW}[ !! ]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

STEP_TOTAL=5
step() {
  local n="$1"; shift
  if [ "$VERBOSE" -eq 1 ]; then
    echo ""
    echo -e "${BOLD}━━ Step ${n}/${STEP_TOTAL} ━━${NC} $*"
  else
    echo -e "${CYAN}[${n}/${STEP_TOTAL}]${NC} $*"
  fi
}

vtime() {
  local start="$SECONDS"
  "$@"
  if [ "$VERBOSE" -eq 1 ]; then
    echo -e "${DIM}    (step took $((SECONDS - start))s)${NC}"
  fi
}

if [ "$VERBOSE" -eq 1 ]; then
  export PS4='+ [\t] ${BASH_SOURCE##*/}:${LINENO}: '
  set -x
  echo ""
  echo -e "${BOLD}Verbose mode${NC} — shell tracing is on; every check is shown in full."
  echo -e "${DIM}Host: $(uname -a)${NC}"
  echo -e "${DIM}User: $(id -un) (uid $(id -u))  PWD will be: $(pwd)${NC}"
  echo ""
fi

if [ "$VERBOSE" -eq 0 ]; then
  echo ""
  echo -e "  ${BOLD}Sven installer${NC} — Seven OS package manager"
  echo -e "  ${DIM}This script checks your tools, prepares system paths, installs the sven binary,${NC}"
  echo -e "  ${DIM}runs adoption helpers if they are present, then optionally refreshes databases.${NC}"
  echo ""
fi

if [ "$(id -u)" -ne 0 ]; then
  fail "Please run as root (e.g. sudo bash install.sh)."
fi

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
if [[ "$SCRIPT_DIR" == */scripts ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
ADOPT_DIR="$REPO_ROOT/scripts"

if [ "$VERBOSE" -eq 1 ]; then
  echo -e "${DIM}REPO_ROOT=$REPO_ROOT  ADOPT_DIR=$ADOPT_DIR${NC}"
fi

step 1 "Checking prerequisites"
REQUIRED=(python3 tar zstd gpg git fakeroot sudo)
MISSING=()
for t in "${REQUIRED[@]}"; do
  if command -v "$t" &>/dev/null; then
    if [ "$VERBOSE" -eq 1 ]; then
      ok "$t → $(command -v "$t")"
    fi
  else
    MISSING+=("$t")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo ""
  for t in "${MISSING[@]}"; do
    warn "$t is missing (required for Sven on Seven OS / LFS)."
  done
  echo ""
  fail "Install the missing tools from your LFS/BLFS build, then run this script again."
fi

if [ "$VERBOSE" -eq 0 ]; then
  echo -e "      ${DIM}All required tools are available (${REQUIRED[*]}).${NC}"
fi

step 2 "Creating directories"
vtime mkdir -p \
  /etc/sven \
  /var/lib/sven/sync \
  /var/lib/sven/installed \
  /var/lib/sven/snapshots \
  /var/cache/sven/pkgs \
  /var/log/sven

if [ -f "$REPO_ROOT/sven/ui/sven-cnf.sh" ]; then
  cp "$REPO_ROOT/sven/ui/sven-cnf.sh" /etc/sven/sven-cnf.sh
fi

ok "Layout under /etc/sven, /var/lib/sven, /var/cache/sven is ready."

step 3 "Installing the sven binary"
CP_FLAGS=()
[ "$VERBOSE" -eq 1 ] && CP_FLAGS=(-v)

if [ -f "$REPO_ROOT/dist/sven" ]; then
  vtime cp "${CP_FLAGS[@]}" "$REPO_ROOT/dist/sven" /usr/bin/sven
elif [ -f "$REPO_ROOT/sven" ]; then
  vtime cp "${CP_FLAGS[@]}" "$REPO_ROOT/sven" /usr/bin/sven
else
  info "No local binary in dist/ — downloading latest release…"
  LATEST_URL="https://github.com/haroldmth/sven/releases/latest/download/sven-linux-x86_64"
  if command -v wget &>/dev/null; then
    vtime wget -q --show-progress "$LATEST_URL" -O /usr/bin/sven
  elif command -v curl &>/dev/null; then
    vtime curl -fL --progress-bar "$LATEST_URL" -o /usr/bin/sven
  else
    fail "Need wget or curl to download the binary."
  fi
fi

chmod +x /usr/bin/sven
ok "Installed → /usr/bin/sven"

step 4 "Seven OS adoption (optional)"
if [ -f "$ADOPT_DIR/adopt_lfs.py" ]; then
  if [ "$VERBOSE" -eq 1 ]; then
    info "PYTHONPATH=$REPO_ROOT python3 $ADOPT_DIR/adopt_lfs.py"
  fi
  vtime env PYTHONPATH="$REPO_ROOT" python3 "$ADOPT_DIR/adopt_lfs.py"
  vtime env PYTHONPATH="$REPO_ROOT" python3 "$ADOPT_DIR/adopt_blfs.py"
  ok "Adoption scripts finished."
else
  warn "No adopt_lfs.py under $ADOPT_DIR — skipped."
  if [ "$VERBOSE" -eq 0 ]; then
    echo -e "      ${DIM}You can adopt the base system later with your usual workflow.${NC}"
  fi
fi

step 5 "Finishing up"
if [ "$NO_SYNC" -eq 1 ]; then
  info "Skipping database sync (--no-sync). Run ${BOLD}sven sync${NC} when you are online."
else
  info "Refreshing package databases (sven sync)…"
  vtime sven sync || warn "Sync failed — check the network and run: sven sync"
fi

echo ""
ok "Sven is installed."
if [ "$VERBOSE" -eq 0 ]; then
  echo -e "  ${DIM}Try:${NC} ${BOLD}sven search vim${NC}  ${DIM}·${NC}  ${BOLD}sven list --explicit${NC}  ${DIM}·${NC}  ${BOLD}sven path <pkg>${NC}"
  echo -e "  ${DIM}For shell integration:${NC} ${BOLD}source /etc/sven/sven-cnf.sh${NC}"
  echo ""
fi

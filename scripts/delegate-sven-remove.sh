#!/bin/bash
# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  delegate-sven-remove.sh — ALPM PreTransaction hook script
# ============================================================
#  Intercepts pacman -R on Sven-managed packages and delegates
#  removal to Sven instead. This ensures Sven's hooks, rollback
#  snapshots, and cleanup logic all run properly.
#
#  If ALL packages in the transaction are Sven-managed, we
#  delegate the entire operation to Sven and abort pacman.
#  If MIXED (some Sven, some pacman), we abort and tell the user
#  to split the operation.
# ============================================================

PACMAN_LOCAL="/var/lib/pacman/local"
SVEN_LOCK="/var/lib/sven/lock"

# Pacman passes the target list as arguments to the hook script
# Format: pkgname pkgname ...
TARGETS="$@"

if [ -z "$TARGETS" ]; then
    exit 0
fi

SVEN_PKGS=""
PACMAN_PKGS=""

for pkg in $TARGETS; do
    # Find the package directory in pacman local DB
    found=""
    for entry in "$PACMAN_LOCAL"/*; do
        [ -d "$entry" ] || continue
        basename_entry=$(basename "$entry")
        # entry name is "name-version"; check if it starts with "pkg-"
        if [ "$basename_entry" = "$pkg" ] || echo "$basename_entry" | grep -q "^${pkg}-"; then
            found="$entry"
            break
        fi
    done

    if [ -n "$found" ] && [ -f "$found/.sven" ]; then
        SVEN_PKGS="$SVEN_PKGS $pkg"
    else
        PACMAN_PKGS="$PACMAN_PKGS $pkg"
    fi
done

# Nothing is Sven-managed → let pacman handle it normally
if [ -z "$SVEN_PKGS" ]; then
    exit 0
fi

# Mixed: some Sven, some pacman → abort, tell user to split
if [ -n "$PACMAN_PKGS" ]; then
    echo "error: Cannot mix Sven-managed and pacman-managed packages in one removal."
    echo ""
    echo "       Sven-managed: $SVEN_PKGS"
    echo "       Pacman-managed: $PACMAN_PKGS"
    echo ""
    echo "       Run separately:"
    echo "         sven remove$SVEN_PKGS"
    echo "         pacman -R$PACMAN_PKGS"
    exit 1
fi

# All targets are Sven-managed → delegate to Sven
# Check if Sven is already running (would deadlock)
if [ -f "$SVEN_LOCK" ]; then
    PID=$(cat "$SVEN_LOCK" 2>/dev/null)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "error: Sven is currently running (PID: $PID)."
        echo "       Wait for it to finish, then retry."
        exit 1
    else
        rm -f "$SVEN_LOCK"
    fi
fi

echo "[sven] Delegating removal to Sven: $SVEN_PKGS"
if command -v sven >/dev/null 2>&1; then
    sven remove $SVEN_PKGS
    SVEN_EXIT=$?
    if [ $SVEN_EXIT -eq 0 ]; then
        # Sven succeeded — abort the pacman transaction since there's nothing
        # left for pacman to do. Exit 1 is the only way ALPM hooks can stop a
        # transaction, but this is an intentional, successful delegation, not
        # an error. Print a clear message so pacman's own "error: target not found"
        # doesn't look like something went wrong.
        echo "[sven] Removal complete. Pacman transaction cancelled (nothing left to do)."
        exit 1
    else
        echo "error: Sven removal failed (exit $SVEN_EXIT)."
        exit 1
    fi
else
    echo "error: sven command not found. Cannot delegate removal."
    echo "       Use 'sven remove$SVEN_PKGS' manually."
    exit 1
fi

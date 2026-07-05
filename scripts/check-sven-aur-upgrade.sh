#!/bin/bash
# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  check-sven-aur-upgrade.sh — ALPM PreTransaction hook script
# ============================================================
#  Blocks pacman from upgrading packages that Sven installed from AUR.
#  These packages are identified by a .sven sidecar file with origin=aur.
#  Users should use 'sven upgrade' or 'sven install' for AUR packages.
# ============================================================

PACMAN_LOCAL="/var/lib/pacman/local"
BLOCKED=""

if [ ! -d "$PACMAN_LOCAL" ]; then
    exit 0
fi

for entry in "$PACMAN_LOCAL"/*; do
    [ -d "$entry" ] || continue
    sven_file="$entry/.sven"
    if [ -f "$sven_file" ]; then
        origin=$(grep '"origin"' "$sven_file" 2>/dev/null | sed 's/.*: *"//; s/".*//')
        if [ "$origin" = "aur" ]; then
            # Extract package name from dirname (name-version)
            pkg_name=$(basename "$entry" | sed 's/-[^-]*-[^-]*$//')
            BLOCKED="$BLOCKED $pkg_name"
        fi
    fi
done

if [ -n "$BLOCKED" ]; then
    echo "error: The following packages were installed by Sven from AUR:"
    for pkg in $BLOCKED; do
        echo "       - $pkg"
    done
    echo "       Use 'sven upgrade <pkg>' or 'sven install <pkg>' instead of pacman."
    exit 1
fi

exit 0

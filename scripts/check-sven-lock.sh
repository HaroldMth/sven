#!/bin/bash
# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  check-sven-lock.sh — ALPM PreTransaction hook script
# ============================================================
#  Aborts pacman if Sven is currently holding its database lock.
#  Also cleans up stale locks (dead PID).
# ============================================================

SVEN_LOCK="/var/lib/sven/lock"

if [ -f "$SVEN_LOCK" ]; then
    PID=$(cat "$SVEN_LOCK" 2>/dev/null)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "error: Sven is currently running (PID: $PID, lock: $SVEN_LOCK)"
        echo "       Wait for Sven to finish, then retry."
        exit 1
    else
        # Stale lock — clean it up and let pacman proceed
        rm -f "$SVEN_LOCK"
    fi
fi

exit 0

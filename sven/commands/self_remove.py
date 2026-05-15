# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/self_remove.py — Uninstall Sven itself
# ============================================================

import os
import sys
import shutil

from ..ui.output import print_section, print_success, print_error, print_info, print_warning
from ..ui.prompt import confirm

# Everything sven owns on the filesystem
_SVEN_PATHS = [
    "/usr/bin/sven",
    "/etc/sven",
    "/var/lib/sven",
    "/var/cache/sven",
    "/var/log/sven",
    "/tmp/sven",
]


def run() -> None:
    print_section("Sven Self-Remove")

    if os.geteuid() != 0:
        print_error("self-remove must be run as root.")
        print("   Try: sudo sven self-remove")
        sys.exit(1)

    print_warning("This will permanently delete Sven and all its data:")
    print()
    for p in _SVEN_PATHS:
        exists = os.path.exists(p)
        marker = "  ✗" if exists else "  ·"
        label = p if exists else f"{p}  (not present)"
        print(f"   {marker}  {label}")
    print()

    if not confirm("Are you sure you want to remove Sven completely?", default=False):
        print_info("Aborted — Sven is still installed.")
        sys.exit(0)

    errors = []
    for path in _SVEN_PATHS:
        if not os.path.exists(path):
            continue
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            print_info(f"Removed: {path}")
        except Exception as e:
            errors.append(f"{path}: {e}")

    if errors:
        print()
        print_error("Some paths could not be removed:")
        for err in errors:
            print(f"   · {err}")
        sys.exit(1)

    print()
    print_success("Sven has been completely removed from this system.")
    print("   Goodbye. You can reinstall anytime from:")
    print("   https://github.com/haroldmth/sven")
    # No sys.exit — the process ends naturally after this print.
    # (The binary may already be gone, but we're still running in-memory.)

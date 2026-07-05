# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/remove.py
# ============================================================
import sys
import subprocess
from pathlib import Path
from ..transaction import RemoveTransaction
from ..db.local_db import LocalDB
from ..installer.alpm_mirror import is_sven_managed_alpm_entry, remove_alpm_local_entry
from ..ui import print_banner, print_section, print_success, print_error, print_info, confirm

def _classify_packages(packages: list[str]) -> tuple[list[str], list[str], list[str]]:
    """
    Classify packages into:
      • sven_managed   — tracked by Sven (including Sven-tagged ALPM entries)
      • pacman_only    — tracked by pacman only, not Sven
      • not_found      — not installed at all
    """
    local_db = LocalDB()
    sven_managed = []
    pacman_only = []
    not_found = []

    pacman_local = Path("/var/lib/pacman/local")

    for p in packages:
        sven_pkg = local_db.get(p)
        if sven_pkg:
            sven_managed.append(p)
            continue

        # Not in Sven DB — check pacman local
        found_in_pacman = False
        if pacman_local.exists():
            for entry in pacman_local.iterdir():
                if not entry.is_dir():
                    continue
                if entry.name.startswith(f"{p}-"):
                    version = entry.name[len(p)+1:]
                    # Even if pacman has it, check if it was originally Sven-managed
                    if is_sven_managed_alpm_entry(p, version):
                        sven_managed.append(p)
                    else:
                        pacman_only.append(p)
                    found_in_pacman = True
                    break

        if not found_in_pacman:
            not_found.append(p)

    return sven_managed, pacman_only, not_found


def run(packages: list[str], recursive: bool = False, force_protected: bool = False):
    print_banner()

    if not packages:
        print_error("No targets specified for removal.")
        sys.exit(1)

    # ── Step 1: Classify (no locks needed, just reading) ───────
    sven_pkgs, pacman_pkgs, missing = _classify_packages(packages)

    if missing:
        print_error(f"Package(s) not installed: {', '.join(missing)}")
        sys.exit(1)

    # ── Step 2: Handle pacman-only packages (NO Sven lock held) ─
    if pacman_pkgs:
        print_info(
            f"The following packages are managed by pacman: {', '.join(pacman_pkgs)}"
        )
        print_info("Sven will delegate removal to pacman -R.")
        if not confirm("Proceed with pacman removal?"):
            print_error("Removal aborted by user.")
            sys.exit(0)

        cmd = ["pacman", "-R"]
        if recursive:
            cmd.append("-s")
        cmd.extend(pacman_pkgs)
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print_error(f"pacman removal failed: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print_error("pacman not found. Cannot remove pacman-managed packages.")
            sys.exit(1)

        for p in pacman_pkgs:
            print_success(f"{p} removed via pacman")

    # ── Step 3: Handle Sven-managed packages (acquire lock) ────
    if not sven_pkgs:
        return  # Nothing left for Sven to do

    print_section("Computing reverse dependencies...")

    if not confirm("Proceed with Sven removal?"):
        print_error("Removal aborted by user.")
        sys.exit(0)

    tx = RemoveTransaction()

    # Check for synced_only packages (pacman-managed, not removable by Sven)
    removable = []
    for p in sven_pkgs:
        sven_pkg = LocalDB().get(p)
        if sven_pkg:
            # Check if this is a synced-only entry (pacman-managed, not removable by Sven).
            # The .sven file is the JSON sidecar — desc is ALPM key-value format, not JSON.
            sidecar_path = Path("/var/lib/sven/installed") / sven_pkg.full_name / ".sven"
            if sidecar_path.exists():
                import json
                try:
                    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
                    if data.get("sven_synced_only"):
                        print_error(f"{p} was installed by pacman, not Sven.")
                        print_info(f"Use 'pacman -R {p}' to remove it.")
                        continue
                except (OSError, json.JSONDecodeError):
                    pass
            removable.append(p)
        else:
            removable.append(p)

    if not removable:
        print_error("No Sven-managed packages to remove.")
        sys.exit(1)

    # Collect versions BEFORE execute() deregisters the packages from LocalDB —
    # get() returns None after removal, so the ALPM cleanup call would silently
    # do nothing if we looked up versions after the transaction.
    versions_before = {}
    ldb = LocalDB()
    for p in removable:
        pkg = ldb.get(p)
        if pkg:
            versions_before[p] = pkg.version

    if tx.execute(removable, force_protected=force_protected):
        for p in removable:
            print_success(f"{p} removed successfully")
            # Clean up ALPM mirror entry using the version we captured before removal
            ver = versions_before.get(p)
            if ver:
                remove_alpm_local_entry(p, ver)
    else:
        print_error("Removal failed.")
        sys.exit(1)

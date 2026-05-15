from pathlib import Path

from ..db.local_db import LocalDB
from ..ui import print_banner, print_info, print_section, print_warning


def run():
    """
    Reconcile LocalDB cache from on-disk installed entries.
    Useful when package directories exist but cache/state is stale.
    """
    print_banner()
    print_section("Adopt installed entries")

    local = LocalDB()
    local.load()
    known = set(local.list_installed())
    recovered = 0

    for entry in local.db_path.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / "desc").exists():
            continue

        pkg = local._read_pkg_dir(entry)
        if not pkg:
            continue
        if pkg.name in known:
            continue

        files_path = entry / "files"
        files = []
        if files_path.exists():
            files = [ln.strip() for ln in files_path.read_text().splitlines() if ln.strip()]

        local.register(pkg, files=files, explicit=pkg.explicit)
        known.add(pkg.name)
        recovered += 1

    if recovered:
        print_info(f"Recovered {recovered} package entr{'y' if recovered == 1 else 'ies'} into LocalDB cache.")
    else:
        print_warning("No missing entries found. LocalDB cache is already consistent.")

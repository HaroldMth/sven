# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/ui/output.py — Output formatting and styling
# ============================================================
import os

color_enabled = True

def disable_colors():
    global color_enabled
    color_enabled = False

def _format_elapsed(seconds: float) -> str:
    if seconds < 90:
        return "just now"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m ago"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)}h ago"
    days = hours / 24
    return f"{int(days)}d ago"


def _sync_status() -> tuple[str, str]:
    """Returns (color_code, label) for the sync-freshness portion of the banner."""
    try:
        from ..db.sync_db import SyncDB
        state = SyncDB.read_sync_state()
    except Exception:
        state = None

    if state is None:
        return ("\033[1;33m", "never synced")

    if not state.get("ok", False):
        return ("\033[1;31m", "sync failed")

    elapsed = __import__("time").time() - state.get("timestamp", 0)
    label = f"synced {_format_elapsed(elapsed)}"
    color = "\033[1;32m" if elapsed < 86400 else "\033[1;33m"
    return (color, label)


def _disk_free_label(path: str) -> str:
    try:
        import shutil
        free_gb = shutil.disk_usage(path).free / (1024 ** 3)
        return f"{free_gb:.1f} GB free"
    except Exception:
        return None


def _collect_status() -> dict:
    """
    Gather every field the status banners can show, each independently
    best-effort — one field failing (e.g. no sync data yet) never blocks
    the others. Shared by print_banner() and the bare `sven` help screen
    so the two can't drift into reporting different numbers.
    """
    status = {
        "init_system": "unknown",
        "pkg_label": "? packages",
        "upgrades": None,
        "orphans": None,
        "disk_free": None,
        "dry_run": False,
        "custom_root": None,
        "sync_color": "\033[1;33m",
        "sync_label": "never synced",
    }

    config = None
    try:
        from ..config import get_config
        config = get_config()
        status["init_system"] = config.init_system
    except Exception:
        pass

    local_db = None
    try:
        from ..db.local_db import LocalDB
        local_db = LocalDB()
        pkgs = local_db.all_packages()
        explicit = sum(1 for p in pkgs if p.explicit)
        status["pkg_label"] = f"{len(pkgs):,} packages ({explicit:,} explicit)"
    except Exception:
        pass

    if local_db is not None:
        try:
            status["orphans"] = len(local_db.orphans())
        except Exception:
            pass
        try:
            status["upgrades"] = local_db.count_upgradable()
        except Exception:
            pass

    status["sync_color"], status["sync_label"] = _sync_status()

    if config is not None:
        status["dry_run"] = bool(getattr(config, "dry_run", False))
        try:
            from ..constants import DEFAULT_ROOT
            if config.install_root not in (DEFAULT_ROOT, "/"):
                status["custom_root"] = config.install_root
            status["disk_free"] = _disk_free_label(config.install_root)
        except Exception:
            pass

    return status


def print_banner():
    """
    Status-aware header shown before most commands. Carries real, glanceable
    state instead of branding: the bar+dot color *is* the health signal
    (green = synced & healthy, yellow = stale/never synced, red = last
    sync failed) — one signal to read, not separate icons to learn.
    """
    from ..constants import VERSION

    s = _collect_status()
    color = s["sync_color"]
    dim, reset, bold, rev = "\033[2m", "\033[0m", "\033[1m", "\033[7m"

    if not color_enabled:
        color = dim = reset = bold = rev = ""

    print(f"{color}┃{reset} {color}●{reset} {bold}{rev} SVEN {reset} v{VERSION}")
    print(f"{color}┃{reset} {dim}{s['init_system']} · {s['pkg_label']} · {reset}{color}{s['sync_label']}{reset}")

    line3 = []
    if s["upgrades"] is not None:
        line3.append(f"{s['upgrades']} upgrade{'s' if s['upgrades'] != 1 else ''} available")
    if s["orphans"]:
        line3.append(f"{s['orphans']} orphan{'s' if s['orphans'] != 1 else ''}")
    if s["disk_free"]:
        line3.append(s["disk_free"])
    if line3:
        print(f"{color}┃{reset} {dim}{' · '.join(line3)}{reset}")

    extras = []
    if s["dry_run"]:
        extras.append("dry-run")
    if s["custom_root"]:
        extras.append(f"root={s['custom_root']}")
    if extras:
        warn = "\033[1;33m" if color_enabled else ""
        print(f"{warn}┃ ⚠ {' · '.join(extras)}{reset}")


def print_error_box(message: str, max_len: int = 60):
    """
    Shared crash-handler display for __main__.py and run_sven.py — single
    implementation so the two entry points can't drift from each other.
    Callers should wrap the import of this function itself in a try/except,
    since it's invoked from top-level exception handlers that may be
    catching an error from deep inside sven's own import chain.
    """
    red = "\033[1;31m" if color_enabled else ""
    reset = "\033[0m" if color_enabled else ""
    truncated = message[:max_len] + ("…" if len(message) > max_len else "")
    print(f"\n{red}┃{reset} {red}●{reset} SVEN ERROR")
    print(f"{red}┃{reset} {truncated}")
    print("  Check /var/log/sven/error.log for technical details.")


def print_section_banner(title: str):
    """
    Neutral bar-style header for scripts/subcommands that need a title block
    but aren't reporting sync health (preflight, adoption scripts) — cyan,
    deliberately distinct from the health-coded green/yellow/red elsewhere,
    so it never reads as a status signal.
    """
    accent = "\033[1;36m" if color_enabled else ""
    reset = "\033[0m" if color_enabled else ""
    print(f"\n{accent}┃{reset} {title}\n")

def print_section(title: str):
    """Sleek modern section header with colored left prefix"""
    if color_enabled:
        print(f"\n\033[1;38;5;99m▍\033[0;1m {title}\033[0m")
    else:
        print(f"\n::: {title} :::")

def print_step(text: str):
    """→ cyan for steps/logs"""
    if color_enabled:
        print(f"   \033[1;38;5;45m→\033[0m {text}")
    else:
        print(f"   → {text}")

def print_success(text: str):
    """✔ green for success"""
    if color_enabled:
        print(f"   \033[1;32m✔\033[0m  {text}")
    else:
        print(f"   ✓  {text}")

def print_error(text: str):
    """✘ red for errors"""
    if color_enabled:
        print(f"   \033[1;31m✘\033[0m  {text}")
    else:
        print(f"   ✗  {text}")

def print_warning(text: str):
    """⚠ yellow for warnings"""
    if color_enabled:
        print(f"   \033[1;33m⚠\033[0m  {text}")
    else:
        print(f"   ⚠  {text}")

def print_info(text: str):
    """Standard print with indentation"""
    print(f"   {text}")

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


def print_banner():
    """
    Status-aware header shown before most commands. Carries real, glanceable
    state instead of branding: the bar+dot color *is* the health signal
    (green = synced & healthy, yellow = stale or never synced, red = last
    sync failed) — one signal to read, not separate icons to learn.
    """
    from ..constants import VERSION

    try:
        from ..config import get_config
        config = get_config()
        init_system = config.init_system
    except Exception:
        config = None
        init_system = "unknown"

    try:
        from ..db.local_db import LocalDB
        pkg_count = len(LocalDB().list_installed())
        pkg_label = f"{pkg_count:,} package{'s' if pkg_count != 1 else ''}"
    except Exception:
        pkg_label = "? packages"

    color, sync_label = _sync_status()
    dim, reset, bold, rev = "\033[2m", "\033[0m", "\033[1m", "\033[7m"

    if not color_enabled:
        color = dim = reset = bold = rev = ""

    line1 = f"{color}┃{reset} {color}●{reset} {bold}{rev} SVEN {reset} v{VERSION}"
    line2 = f"{color}┃{reset} {dim}{init_system} · {pkg_label} · {reset}{color}{sync_label}{reset}"
    print(line1)
    print(line2)

    extras = []
    if config is not None:
        if getattr(config, "dry_run", False):
            extras.append("dry-run")
        try:
            from ..constants import DEFAULT_ROOT
            if config.install_root not in (DEFAULT_ROOT, "/"):
                extras.append(f"root={config.install_root}")
        except Exception:
            pass

    if extras:
        warn = "\033[1;33m" if color_enabled else ""
        print(f"{warn}┃ ⚠ {' · '.join(extras)}{reset}")

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

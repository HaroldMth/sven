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

def print_banner():
    """Compact header for transactional commands (install, etc.)."""
    from ..constants import VERSION

    b = (
        "╔══════════════════════════════════════════════════╗\n"
        f"║   Sven v{VERSION}  ·  Seven OS  ·  by HANS TECH      ║\n"
        "╚══════════════════════════════════════════════════╝"
    )
    if color_enabled:
        print(f"\033[94m{b}\033[0m")
    else:
        print(b)

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

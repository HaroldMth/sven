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
    """:: cyan for section headers"""
    msg = f":: {title}"
    if color_enabled:
        print(f"\033[96m{msg}\033[0m")  # Cyan
    else:
        print(msg)

def print_step(text: str):
    """→ white for steps/logs"""
    msg = f"   → {text}"
    if color_enabled:
        print(f"\033[97m{msg}\033[0m")  # White
    else:
        print(msg)

def print_success(text: str):
    """✓ green for success"""
    msg = f"✓  {text}"
    if color_enabled:
        print(f"\033[92m{msg}\033[0m")  # Green
    else:
        print(msg)

def print_error(text: str):
    """✗ red for errors"""
    msg = f"✗  {text}"
    if color_enabled:
        print(f"\033[91m{msg}\033[0m")  # Red
    else:
        print(msg)

def print_warning(text: str):
    """⚠ yellow for warnings"""
    msg = f"⚠  {text}"
    if color_enabled:
        print(f"\033[93m{msg}\033[0m")  # Yellow
    else:
        print(msg)

def print_info(text: str):
    """Standard print with indentation"""
    print(f"   {text}")

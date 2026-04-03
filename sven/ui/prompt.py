# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/ui/prompt.py — User Interactions & Confirmation
# ============================================================

import sys
import os
from pathlib import Path
from .output import print_section, print_info, print_warning


def confirm(prompt: str, default: bool = True) -> bool:
    """
    Y/n confirmation — triggers INSTANTLY on keypress (no Enter needed).
    Falls back to standard input() if not running in a terminal.
    """
    options = "[Y/n]" if default else "[y/N]"
    sys.stdout.write(f":: {prompt} {options} \n")
    sys.stdout.flush()

    # Instant keypress mode (raw terminal)
    if os.isatty(sys.stdin.fileno()):
        try:
            import tty
            import termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
            # Echo the choice back
            if ch in ('\r', '\n'):
                sys.stdout.write("Y\n" if default else "N\n")
                return default
            sys.stdout.write(ch + "\n")
            sys.stdout.flush()
            return ch.lower() in ('y',) if not default else ch.lower() not in ('n',)
        except (ImportError, termios.error):
            pass  # Fallback below

    # Fallback: standard input (pipes, non-TTY)
    try:
        reply = input().strip().lower()
        if not reply:
            return default
        return reply in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        return False


def show_package_list(packages, total_download_bytes: int = 0, total_install_bytes: int = 0):
    """
    Display resolved packages with sizes before the Y/n prompt.
    
    Format:
    :: Packages (N):
       name-version  name-version  name-version
       
       Total Download: X MiB  Total Installed Size: Y MiB
    """
    if not packages:
        return

    # Handle both dict and Package objects
    names = []
    for p in packages:
        if isinstance(p, dict):
            names.append(f"{p['name']}-{p['version']}")
        else:
            names.append(f"{p.name}-{p.version}")

    print_section(f"Packages ({len(packages)}):")
    
    # Print names in 2-column layout
    col_width = 38
    for i in range(0, len(names), 2):
        left = names[i]
        right = names[i + 1] if i + 1 < len(names) else ""
        print(f"   {left:<{col_width}}{right}")

    print()
    dl = format_size(total_download_bytes)
    inst = format_size(total_install_bytes)
    print(f"   Total Download Size   :  {dl}")
    print(f"   Total Installed Size  :  {inst}")
    print()


def show_pkgbuild_review(pkg_name: str, pkgbuild_path: str):
    """Prompt user to review PKGBUILD"""
    print_warning(f"AUR Package {pkg_name} requires review.")
    if confirm("Review PKGBUILD now?", default=True):
        content = Path(pkgbuild_path).read_text(errors="replace")
        print("\n--- PKGBUILD ---")
        print(content)
        print("----------------\n")


def show_hook_review(pkg_name: str, install_path: str):
    """Prompt user to review .INSTALL scripts"""
    print_warning(f"AUR Package {pkg_name} has .INSTALL scripts.")
    if confirm("Review .INSTALL now?", default=True):
        content = Path(install_path).read_text(errors="replace")
        print("\n--- .INSTALL ---")
        print(content)
        print("----------------\n")


def next_steps(manual_steps: list[str]):
    """Prints manual steps after install"""
    if manual_steps:
        print_section("Manual Action Required:")
        for step in manual_steps:
            print_info(f" - {step}")


def format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MiB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GiB"

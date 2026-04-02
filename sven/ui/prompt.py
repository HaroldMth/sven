# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/ui/prompt.py — User Interactions & Confirmation
# ============================================================

import sys
from pathlib import Path
from .output import print_section, print_info, print_warning

def confirm(prompt: str, default: bool = True) -> bool:
    """Y/n confirmation with default"""
    options = "[Y/n]" if default else "[y/N]"
    print_section(f"{prompt} {options} ")
    try:
        reply = input().strip().lower()
        if not reply:
            return default
        return reply in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        return False

def show_package_list(packages: list[dict], total_download_bytes: int, total_install_bytes: int):
    """
    Format:
    :: Packages (N): [list]
       Total Download: X MiB  Install: Y MiB
    """
    names = [f"{p['name']}-{p['version']}" for p in packages]
    print_section(f"Packages ({len(packages)}): {'  '.join(names)}")
    
    dl = format_size(total_download_bytes)
    inst = format_size(total_install_bytes)
    print(f"   Total Download: {dl}  Install: {inst}")

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
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MiB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GiB"

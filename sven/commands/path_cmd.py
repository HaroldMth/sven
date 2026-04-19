# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/path_cmd.py — installed package paths
# ============================================================
import os
import sys
from pathlib import Path

from ..config import get_config
from ..db.local_db import LocalDB
from ..exceptions import PackageNotInstalledError
from ..ui import print_banner, print_error, print_info, print_section, print_warning


def _nf(p: str) -> str:
    """POSIX-ish path without leading slash, for comparisons."""
    return p.replace("\\", "/").lstrip("/")


def _is_bin_path(rel: str) -> bool:
    n = _nf(rel)
    return "/bin/" in n or n.startswith("usr/bin/")


def _priority_bin(rel: str) -> tuple:
    """
    Sort key: lower = show first. Prefer /usr/bin, then JVM java/javac, then other JVM bins.
    """
    n = _nf(rel).lower()
    if n == "usr/bin/java" or n.endswith("/usr/bin/java"):
        return (0, rel)
    if n == "usr/bin/javac" or n.endswith("/usr/bin/javac"):
        return (1, rel)
    if "/lib/jvm/" in n and "/bin/" in n:
        if n.endswith("/bin/java"):
            return (2, rel)
        if n.endswith("/bin/javac"):
            return (3, rel)
        return (4, rel)
    if n.startswith("usr/bin/"):
        return (5, rel)
    if "/bin/" in n:
        return (6, rel)
    return (7, rel)


def _find_jvm_java(rel_files: list[str]) -> list[str]:
    """Paths that are likely the JDK/JRE launcher inside /usr/lib/jvm/.../bin/."""
    out = []
    for f in rel_files:
        n = _nf(f).lower()
        if "/lib/jvm/" not in n:
            continue
        if not n.endswith("/bin/java"):
            continue
        base = Path(f).name
        if base == "java":
            out.append(f)
    return sorted(set(out))


def _has_usr_bin_java(rel_files: list[str]) -> bool:
    for f in rel_files:
        n = _nf(f)
        if n == "usr/bin/java" or n.endswith("/usr/bin/java"):
            return True
    return False


def _is_jdkish_package(pkg_name: str, rel_files: list[str]) -> bool:
    n = pkg_name.lower()
    if any(x in n for x in ("jdk", "jre", "openjdk", "java-")):
        return True
    return any("/lib/jvm/" in _nf(f).lower() for f in rel_files)


def run(package: str, list_files: bool = False):
    print_banner()
    config = get_config()
    local = LocalDB()
    pkg = local.get(package)
    if not pkg:
        print_error(f"Package '{package}' is not installed.")
        sys.exit(1)

    db_entry = (local.db_path / pkg.full_name).resolve()
    print_section(f"Paths for '{pkg.name}' ({pkg.version})")
    print(f"   Database entry : {db_entry}")
    ir = config.install_root.rstrip("/") or "/"
    print(f"   Install root   : {Path(ir).resolve() if ir != '/' else Path('/')}")

    try:
        rel_files = local.get_files(pkg.name)
    except PackageNotInstalledError:
        rel_files = []

    if not rel_files:
        print("   (No file list recorded in the database.)")
        return

    def abs_path(rel: str) -> Path:
        rel = rel.lstrip("/")
        return Path(config.rooted("/" + rel if rel else "")).resolve()

    if list_files:
        print(f"   Files on disk ({len(rel_files)}):")
        for line in sorted(rel_files, key=_nf):
            p = abs_path(line)
            mark = ""
            try:
                if p.is_file() and os.access(p, os.X_OK):
                    mark = "  (executable)"
            except OSError:
                pass
            print(f"      {p}{mark}")
    else:
        bins = [f for f in rel_files if _is_bin_path(f)]
        show = sorted(bins, key=_priority_bin)[:20]
        print(f"   Tracked files  : {len(rel_files)}")
        print("   Notable paths (bin directories first):")
        for line in show:
            p = abs_path(line)
            mark = ""
            try:
                if p.is_file() and os.access(p, os.X_OK):
                    mark = "  ← executable"
            except OSError:
                pass
            print(f"      {p}{mark}")
        if len(show) < len(bins):
            print(
                f"   … {len(bins) - len(show)} more paths under */bin/; "
                f"use: sven path {pkg.name} --files"
            )
        elif len(show) < len(rel_files) and not bins:
            print(
                f"   … {len(rel_files) - len(show)} more paths; "
                f"use: sven path {pkg.name} --files"
            )

    # ── JDK/JRE: why `java` is not on PATH (Arch layout) ─────
    if _is_jdkish_package(pkg.name, rel_files):
        jvm_java = _find_jvm_java(rel_files)
        if jvm_java and not _has_usr_bin_java(rel_files):
            primary = abs_path(jvm_java[0])
            print()
            print_section("Java launcher")
            print_info(
                "This package installs the JDK under /usr/lib/jvm/… — there is often "
                "no /usr/bin/java unless you also install java-runtime-common (Arch)."
            )
            print_info(f"Run the JDK’s java directly, for example:\n      {primary} -version")
            print_info(
                "Or add its bin directory to PATH for this shell:\n"
                f"      export PATH=\"{primary.parent}:$PATH\""
            )
            print_info(
                "On Arch you can also install java-runtime-common and run: "
                "archlinux-java set <name>"
            )
            print_info("JVM uses -version (not -v) to print version text.")
        elif not jvm_java and not _has_usr_bin_java(rel_files):
            print()
            print_warning(
                "No java binary found in this package’s file list — "
                "try sven path --files or check a headless JRE package."
            )

# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  cli.py — argument parsing + command routing
# ============================================================

import argparse
import sys

from .constants import VERSION, APP_NAME, OS_NAME, BRAND


BANNER = f"""
╔══════════════════════════════════════════════════╗
║                                                  ║
║   ███████╗██╗   ██╗███████╗███╗   ██╗            ║
║   ██╔════╝██║   ██║██╔════╝████╗  ██║            ║
║   ███████╗██║   ██║█████╗  ██╔██╗ ██║            ║
║   ╚════██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║            ║
║   ███████║ ╚████╔╝ ███████╗██║ ╚████║            ║
║   ╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝            ║
║                                                  ║
║   v{VERSION}  ·  {OS_NAME} Package Manager            ║
║   by {BRAND}                                   ║
╚══════════════════════════════════════════════════╝
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=f"Sven — {OS_NAME} Package Manager by {BRAND}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"GitHub: https://github.com/haroldmth/sven"
    )

    parser.add_argument(
        "--version", action="version", version=f"sven {VERSION}"
    )
    parser.add_argument(
        "--root", metavar="PATH", default=None,
        help="Install to a custom root directory (e.g. /mnt/sevenos)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate operation without touching the filesystem"
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colored output"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show detailed output"
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # ── install ───────────────────────────────────────────────
    p_install = subparsers.add_parser("install", help="Install packages")
    p_install.add_argument("packages", nargs="+", metavar="PKG")
    p_install.add_argument("--source", action="store_true", help="Force build from source")
    p_install.add_argument("--binary", action="store_true", help="Force binary install")

    # ── remove ────────────────────────────────────────────────
    p_remove = subparsers.add_parser("remove", help="Remove packages")
    p_remove.add_argument("packages", nargs="+", metavar="PKG")
    p_remove.add_argument("-s", action="store_true", help="Remove unneeded dependencies")
    p_remove.add_argument("--orphans", action="store_true", help="Remove all orphans")

    # ── upgrade ───────────────────────────────────────────────
    p_upgrade = subparsers.add_parser("upgrade", help="Upgrade packages")
    p_upgrade.add_argument("packages", nargs="*", metavar="PKG",
                           help="Specific packages (omit for full upgrade)")
    p_upgrade.add_argument("--ignore", metavar="PKG", nargs="+",
                           help="Skip these packages")
    p_upgrade.add_argument("--devel", action="store_true",
                           help="Also rebuild -git AUR packages")

    # ── update ────────────────────────────────────────────────
    subparsers.add_parser("update", help="Sync databases + full upgrade")

    # ── search ────────────────────────────────────────────────
    p_search = subparsers.add_parser("search", help="Search official repos + AUR")
    p_search.add_argument("query", metavar="QUERY")
    p_search.add_argument("--aur", action="store_true", help="AUR only")
    p_search.add_argument("--official", action="store_true", help="Official repos only")
    p_search.add_argument("--installed", action="store_true", help="Installed only")

    # ── info ──────────────────────────────────────────────────
    p_info = subparsers.add_parser("info", help="Show package details")
    p_info.add_argument("package", metavar="PKG")

    # ── list ──────────────────────────────────────────────────
    p_list = subparsers.add_parser("list", help="List installed packages")
    p_list.add_argument("--aur",      action="store_true", help="AUR packages only")
    p_list.add_argument("--explicit", action="store_true", help="Explicitly installed")
    p_list.add_argument("--orphans",  action="store_true", help="Orphaned packages")

    # ── sync ──────────────────────────────────────────────────
    p_sync = subparsers.add_parser("sync", help="Refresh package databases")
    p_sync.add_argument("--force", action="store_true", help="Force even if fresh")

    # ── clean ─────────────────────────────────────────────────
    p_clean = subparsers.add_parser("clean", help="Clear package cache")
    p_clean.add_argument("--all", action="store_true", help="Remove all cached packages")

    # ── verify ────────────────────────────────────────────────
    p_verify = subparsers.add_parser("verify", help="Verify installed package integrity")
    p_verify.add_argument("package", metavar="PKG")

    # ── orphans ───────────────────────────────────────────────
    subparsers.add_parser("orphans", help="List unneeded packages")

    # ── snapshots ─────────────────────────────────────────────
    subparsers.add_parser("snapshots", help="List all rollback snapshots")

    # ── rollback ──────────────────────────────────────────────
    p_rollback = subparsers.add_parser("rollback", help="Undo last operation")
    p_rollback.add_argument("snapshot_id", nargs="?", metavar="ID",
                            help="Specific snapshot ID (omit for last)")

    # ── mirror ────────────────────────────────────────────────
    p_mirror = subparsers.add_parser("mirror", help="Mirror management")
    mirror_sub = p_mirror.add_subparsers(dest="mirror_cmd")
    mirror_sub.add_parser("list",    help="Show available mirrors")
    mirror_sub.add_parser("fastest", help="Benchmark and pick fastest mirror")

    # ── deps ──────────────────────────────────────────────────
    p_deps = subparsers.add_parser("deps", help="Show dependency tree")
    p_deps.add_argument("package", metavar="PKG")

    # ── rdeps ─────────────────────────────────────────────────
    p_rdeps = subparsers.add_parser("rdeps", help="Show reverse dependencies")
    p_rdeps.add_argument("package", metavar="PKG")

    return parser


def main():
    parser  = build_parser()
    args    = parser.parse_args()

    # Apply --root override to config
    if args.root:
        from .config import get_config
        get_config().install_root = args.root

    if args.command is None:
        print(BANNER)
        parser.print_help()
        sys.exit(0)

    # ── Route to command handlers (stubs for now) ─────────────
    cmd = args.command

    if cmd == "install":
        from .commands.install import run
        run(args)
    elif cmd == "remove":
        from .commands.remove import run
        run(args)
    elif cmd == "upgrade":
        from .commands.upgrade import run
        run(args)
    elif cmd == "update":
        from .commands.update import run
        run(args)
    elif cmd == "search":
        from .commands.search import run
        run(args)
    elif cmd == "info":
        from .commands.info import run
        run(args)
    elif cmd == "list":
        from .commands.list_cmd import run
        run(args)
    elif cmd == "sync":
        from .commands.sync import run
        run(args)
    elif cmd == "clean":
        from .commands.clean import run
        run(args)
    elif cmd == "verify":
        from .commands.verify import run
        run(args)
    elif cmd == "orphans":
        from .commands.orphans import run
        run(args)
    elif cmd == "snapshots":
        from .commands.snapshots import run
        run(args)
    elif cmd == "rollback":
        from .commands.rollback import run
        run(args)
    elif cmd == "mirror":
        from .commands.mirror import run
        run(args)
    elif cmd in ("deps", "rdeps"):
        from .commands.deps import run
        run(args)
    else:
        parser.print_help()
        sys.exit(1)

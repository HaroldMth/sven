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
        "--verbose",
        action="store_true",
        dest="global_verbose",
        help="Verbose logging for any command (must come *before* the subcommand, e.g. sven --verbose sync)",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # ── install ───────────────────────────────────────────────
    p_install = subparsers.add_parser("install", help="Install packages")
    p_install.add_argument("packages", nargs="+", metavar="PKG")
    p_install.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="install_verbose",
        help="Verbose install output (may appear after package names)",
    )
    p_install.add_argument("--source", action="store_true", help="Force build from source")
    p_install.add_argument("--binary", action="store_true", help="Force binary install")
    p_install.add_argument("--force-protected", action="store_true", help="Allow managing protected LFS packages")

    # ── remove ────────────────────────────────────────────────
    p_remove = subparsers.add_parser("remove", help="Remove packages")
    p_remove.add_argument("packages", nargs="+", metavar="PKG")
    p_remove.add_argument("-s", action="store_true", help="Remove unneeded dependencies")
    p_remove.add_argument("--orphans", action="store_true", help="Remove all orphans")
    p_remove.add_argument("--force-protected", action="store_true", help="Allow removing protected LFS packages")

    # ── upgrade ───────────────────────────────────────────────
    p_upgrade = subparsers.add_parser("upgrade", help="Upgrade packages")
    p_upgrade.add_argument("packages", nargs="*", metavar="PKG",
                           help="Specific packages (omit for full upgrade)")
    p_upgrade.add_argument("--ignore", metavar="PKG", nargs="+",
                           help="Skip these packages")
    p_upgrade.add_argument("--devel", action="store_true",
                           help="Also rebuild -git AUR packages")
    p_upgrade.add_argument("--force-protected", action="store_true", help="Allow upgrading protected LFS packages")


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

    # ── update ────────────────────────────────────────────────
    subparsers.add_parser("check-update", help="Check for a newer version of Sven")
    subparsers.add_parser("self-update",  help="Download and install latest Sven release")

    return parser


LARGE_BANNER = f"""\033[94m╔══════════════════════════════════════════════════╗
║                                                  ║
║   ███████╗██╗   ██╗███████╗███╗   ██╗            ║
║   ██╔════╝██║   ██║██╔════╝████╗  ██║            ║
║   ███████╗██║   ██║█████╗  ██╔██╗ ██║            ║
║   ╚════██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║            ║
║   ███████║ ╚████╔╝ ███████╗██║ ╚████║            ║
║   ╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝            ║
║                                                  ║
║   v{VERSION}  ·  Seven OS Package Manager            ║
║   by {BRAND}                                   ║
╚══════════════════════════════════════════════════╝\033[0m
"""

def main():
    parser = build_parser()
    args = parser.parse_args()

    verbose = bool(
        getattr(args, "global_verbose", False) or getattr(args, "install_verbose", False)
    )

    # ── Configure Logging ─────────────────────────────────────
    import logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="\033[90mDEBUG: %(message)s\033[0m")
    else:
        logging.basicConfig(level=logging.WARNING)

    # constants.py natively captures --root from sys.argv at module load time.
    # We only need to sync the Config singleton.
    if args.root:
        from .config import get_config
        get_config().install_root = args.root

    if args.command is None:
        if not (hasattr(args, "no_color") and args.no_color):
            print(LARGE_BANNER)
        else:
            print(LARGE_BANNER.replace("\033[94m", "").replace("\033[0m", ""))
        parser.print_help()
        sys.exit(0)

    # ── Automagic Update Check ────────────────────────────────
    # We do not check on self-update or check-update commands to avoid redundancy
    if args.command not in ("self-update", "check-update"):
        from .core.updater import check_for_updates_silently
        check_for_updates_silently()

    # ── Route to command handlers (stubs for now) ─────────────
    cmd = args.command

    if hasattr(args, "no_color") and args.no_color:
        from .ui.output import disable_colors
        disable_colors()

    if cmd == "install":
        from .commands.install import run
        run(
            args.packages,
            root=args.root if hasattr(args, "root") else None,
            force_protected=args.force_protected,
            verbose=verbose,
        )
    elif cmd == "remove":
        from .commands.remove import run
        run(
            args.packages, 
            recursive=args.orphans if hasattr(args, "orphans") else False,
            force_protected=args.force_protected
        )
    elif cmd == "upgrade":
        from .commands.upgrade import run
        run(args.packages, force_protected=args.force_protected)

    elif cmd == "update":
        from .commands.update import run
        run()
    elif cmd == "search":
        from .commands.search import run
        run(args.query)
    elif cmd == "info":
        from .commands.info import run
        run(args.package)
    elif cmd == "list":
        from .commands.list_cmd import run
        run()
    elif cmd == "sync":
        from .commands.sync import run
        run()
    elif cmd == "clean":
        from .commands.clean import run
        run(all_cache=args.all if hasattr(args, "all") else False)
    elif cmd == "verify":
        from .commands.verify import run
        run(args.package if hasattr(args, "package") else None)
    elif cmd == "orphans":
        from .commands.orphans import run
        run()
    elif cmd == "snapshots":
        from .commands.snapshots import run
        run()
    elif cmd == "rollback":
        from .commands.rollback import run
        run(args.snapshot_id if hasattr(args, 'snapshot_id') else None)
    elif cmd == "mirror":
        from .commands.mirror import run
        run(benchmark=(args.mirror_cmd == "fastest" if hasattr(args, "mirror_cmd") else False))
    elif cmd == "self-update":
        from .commands.self_update import run
        run()
    elif cmd == "check-update":
        from .core.updater import run_check_update
        run_check_update()
    elif cmd in ("deps", "rdeps"):
        from .commands.deps import run
        run(args.package, reverse=(cmd == "rdeps"))
    else:
        parser.print_help()
        sys.exit(1)

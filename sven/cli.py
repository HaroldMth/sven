# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  cli.py — argument parsing + command routing
# ============================================================

import argparse
import sys

from .constants import VERSION, APP_NAME, OS_NAME, BRAND


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
    p_install.add_argument(
        "--force",
        action="store_true",
        help="Install or reinstall even if packages are already installed (refetch/rebuild as needed)",
    )
    p_install.add_argument(
        "--version",
        metavar="VER",
        help="Install a specific version of the package",
    )
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
    p_upgrade.add_argument("--skip-aur", action="store_true",
                           help="Don't check AUR for updates — skips the network round-trip to the AUR RPC for every installed AUR package")


    # ── update ────────────────────────────────────────────────
    p_update = subparsers.add_parser("update", help="Sync databases + full upgrade")
    p_update.add_argument("--skip-aur", action="store_true",
                          help="Don't check AUR for updates — skips the network round-trip to the AUR RPC for every installed AUR package")

    # ── search ────────────────────────────────────────────────
    p_search = subparsers.add_parser("search", help="Search official repos + AUR")
    p_search.add_argument("query", metavar="QUERY")
    p_search.add_argument("--aur", action="store_true", help="AUR only")
    p_search.add_argument("--official", action="store_true", help="Official repos only")
    p_search.add_argument("--installed", action="store_true", help="Installed only")

    # ── info ──────────────────────────────────────────────────
    p_info = subparsers.add_parser("info", help="Show package details")
    p_info.add_argument("package", metavar="PKG")

    # ── path ──────────────────────────────────────────────────
    p_path = subparsers.add_parser(
        "path",
        help="Show filesystem paths for an installed package",
    )
    p_path.add_argument("package", metavar="PKG")
    p_path.add_argument(
        "--files",
        action="store_true",
        help="List every tracked file (can be long)",
    )

    # ── list ──────────────────────────────────────────────────
    p_list = subparsers.add_parser("list", help="List installed packages")
    p_list.add_argument("--aur",      action="store_true", help="AUR packages only")
    p_list.add_argument("--explicit", action="store_true", help="Explicitly installed")
    p_list.add_argument("--orphans",  action="store_true", help="Orphaned packages")

    # ── sync ──────────────────────────────────────────────────
    p_sync = subparsers.add_parser("sync", help="Refresh package databases")
    p_sync.add_argument("--force", action="store_true", help="Force even if fresh")

    # ── check-version ──────────────────────────────────────────
    p_check = subparsers.add_parser("check-version", help="Check available versions of a package")
    p_check.add_argument("package", metavar="PKG")
    subparsers.add_parser("version", help="Show Sven, runtime, and tool versions")

    # ── doctor ─────────────────────────────────────────────────
    p_doctor = subparsers.add_parser("doctor", help="Run a full system health check")
    p_doctor.add_argument("--offline", action="store_true", help="Skip network/mirror reachability checks")

    # ── preflight ─────────────────────────────────────────────
    subparsers.add_parser(
        "preflight",
        help="Quick pre-install environment check (Python, requests, GPG, git, tar+zstd)",
    )

    # ── clean ─────────────────────────────────────────────────
    p_clean = subparsers.add_parser("clean", help="Clear package cache")
    p_clean.add_argument("--all", action="store_true", help="Remove all cached packages")

    # ── verify ────────────────────────────────────────────────
    p_verify = subparsers.add_parser("verify", help="Verify installed package integrity")
    p_verify.add_argument("package", metavar="PKG")

    # ── orphans ───────────────────────────────────────────────
    subparsers.add_parser("orphans", help="List unneeded packages")
    subparsers.add_parser("adopt-installed", help="Reconcile installed DB entries into LocalDB cache")

    # ── snapshots ─────────────────────────────────────────────
    subparsers.add_parser("snapshots", help="List all rollback snapshots")

    # ── rollback ──────────────────────────────────────────────
    p_rollback = subparsers.add_parser("rollback", help="Undo last operation")
    p_rollback.add_argument("snapshot_id", nargs="?", metavar="ID",
                            help="Specific snapshot ID (omit for last)")

    # ── mirror ────────────────────────────────────────────────
    p_mirror = subparsers.add_parser("mirror", help="Mirror management")
    p_mirror.add_argument(
        "--rank",
        action="store_true",
        help="Benchmark mirrors and persist a ranked mirrorlist",
    )
    mirror_sub = p_mirror.add_subparsers(dest="mirror_cmd")
    mirror_sub.add_parser("list",    help="Show available mirrors")
    mirror_sub.add_parser("fastest", help="Benchmark and pick fastest mirror")
    mirror_sub.add_parser("rank", help="Benchmark mirrors and persist a ranked mirrorlist")

    # ── deps ──────────────────────────────────────────────────
    p_deps = subparsers.add_parser("deps", help="Show dependency tree")
    p_deps.add_argument("package", metavar="PKG")

    # ── rdeps ─────────────────────────────────────────────────
    p_rdeps = subparsers.add_parser("rdeps", help="Show reverse dependencies")
    p_rdeps.add_argument("package", metavar="PKG")

    # ── update ────────────────────────────────────────────────
    # ── cnf ──────────────────────────────────────────────────
    p_cnf = subparsers.add_parser("cnf", help="Command-not-found handler lookup")
    p_cnf.add_argument("cmd", metavar="COMMAND")

    subparsers.add_parser("check-update",  help="Check for a newer version of Sven")
    subparsers.add_parser("self-update",   help="Download and install latest Sven release")
    subparsers.add_parser("self-remove",   help="Completely uninstall Sven from this system")

    return parser


LARGE_LOGO = """╔══════════════════════════════════════════════════╗
║                                                  ║
║   ███████╗██╗   ██╗███████╗███╗   ██╗            ║
║   ██╔════╝██║   ██║██╔════╝████╗  ██║            ║
║   ███████╗██║   ██║█████╗  ██╔██╗ ██║            ║
║   ╚════██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║            ║
║   ███████║ ╚████╔╝ ███████╗██║ ╚████║            ║
║   ╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝            ║
║                                                  ║
╚══════════════════════════════════════════════════╝"""


def print_large_banner(no_color: bool = False):
    """
    Shown only on bare `sven` with no command. The logo box stays fixed-width
    ASCII art; live status (package count, sync health, upgrades) prints
    below it using the same bar+dot convention as print_banner(), rather than
    trying to cram variable-length numbers inside fixed box-drawing borders.
    """
    from .ui.output import _collect_status, color_enabled

    if no_color:
        print(LARGE_LOGO)
    else:
        print(f"\033[94m{LARGE_LOGO}\033[0m")

    s = _collect_status()
    color = s["sync_color"]
    dim, reset = "\033[2m", "\033[0m"
    if no_color or not color_enabled:
        color = dim = reset = ""

    print(f"{color}●{reset} v{VERSION} · {dim}{s['init_system']} · {s['pkg_label']}{reset}")
    line2 = [s["sync_label"]]
    if s["upgrades"] is not None:
        line2.append(f"{s['upgrades']} upgrade{'s' if s['upgrades'] != 1 else ''} available")
    if s["orphans"]:
        line2.append(f"{s['orphans']} orphan{'s' if s['orphans'] != 1 else ''}")
    print(f"  {dim}{' · '.join(line2)}{reset}")
    print()

def main():
    parser = build_parser()
    args = parser.parse_args()

    verbose = bool(
        getattr(args, "global_verbose", False) or getattr(args, "install_verbose", False)
    )

    # ── Configure Logging ─────────────────────────────────────
    import logging
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format=(
                "\033[90m%(asctime)s.%(msecs)03d %(name)s %(levelname)s: "
                "%(message)s\033[0m"
            ),
            datefmt="%H:%M:%S",
        )
        for _name in ("sven", "urllib3", "requests"):
            logging.getLogger(_name).setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # constants.py natively captures --root from sys.argv at module load time.
    # We only need to sync the Config singleton.
    from .config import get_config
    config = get_config()
    if args.root:
        config.install_root = args.root
    config.dry_run = bool(getattr(args, "dry_run", False))

    if args.command is None:
        print_large_banner(no_color=bool(getattr(args, "no_color", False)))
        parser.print_help()
        sys.exit(0)

    # ── Automagic Update Check ────────────────────────────────
    # We do not check on self-update or check-update commands to avoid redundancy
    if args.command not in ("self-update", "check-update", "doctor", "preflight"):
        from .core.updater import check_for_updates_silently
        check_for_updates_silently()

    # ── Route to command handlers (stubs for now) ─────────────
    cmd = args.command

    if hasattr(args, "no_color") and args.no_color:
        from .ui.output import disable_colors
        disable_colors()

    if config.was_created:
        from .ui.output import print_info
        print_info(
            f"Created default config at {config.path} "
            f"(init_system={config.init_system}, parallel_downloads={config.parallel_downloads})."
        )

    if cmd == "install":
        from .commands.install import run
        run(
            args.packages,
            root=args.root if hasattr(args, "root") else None,
            force_protected=args.force_protected,
            force_reinstall=getattr(args, "force", False),
            verbose=verbose,
            version=getattr(args, "version", None),
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
        run(args.packages, force_protected=args.force_protected, skip_aur=args.skip_aur)

    elif cmd == "update":
        from .commands.update import run
        run(skip_aur=args.skip_aur)
    elif cmd == "search":
        from .commands.search import run
        run(args.query)
    elif cmd == "info":
        from .commands.info import run
        run(args.package)
    elif cmd == "path":
        from .commands.path_cmd import run as path_run
        path_run(args.package, list_files=args.files if hasattr(args, "files") else False)
    elif cmd == "list":
        from .commands.list_cmd import run
        run()
    elif cmd == "sync":
        from .commands.sync import run
        run()
    elif cmd == "check-version":
        from .commands.check_version import run
        run(args.package)
    elif cmd == "version":
        from .commands.version import run
        run()
    elif cmd == "doctor":
        from .commands.doctor import run as doctor_run
        doctor_run(offline=getattr(args, "offline", False))
    elif cmd == "preflight":
        from .preflight import run_preflight, print_preflight_report
        ok, results = run_preflight()
        print_preflight_report(results)
        if not ok:
            sys.exit(1)
    elif cmd == "clean":
        from .commands.clean import run
        run(all_cache=args.all if hasattr(args, "all") else False)
    elif cmd == "verify":
        from .commands.verify import run
        run(args.package if hasattr(args, "package") else None)
    elif cmd == "orphans":
        from .commands.orphans import run
        run()
    elif cmd == "adopt-installed":
        from .commands.adopt_installed import run
        run()
    elif cmd == "snapshots":
        from .commands.snapshots import run
        run()
    elif cmd == "rollback":
        from .commands.rollback import run
        run(args.snapshot_id if hasattr(args, 'snapshot_id') else None)
    elif cmd == "mirror":
        from .commands.mirror import run
        mirror_cmd = args.mirror_cmd if hasattr(args, "mirror_cmd") else None
        run(
            benchmark=(mirror_cmd == "fastest"),
            rank=(mirror_cmd == "rank" or getattr(args, "rank", False)),
        )
    elif cmd == "self-update":
        from .commands.self_update import run
        run()
    elif cmd == "self-remove":
        from .commands.self_remove import run
        run()
    elif cmd == "check-update":
        from .core.updater import run_check_update
        run_check_update()
    elif cmd in ("deps", "rdeps"):
        from .commands.deps import run
        run(args.package, reverse=(cmd == "rdeps"))
    elif cmd == "cnf":
        from .commands.find_command import run
        run(args.cmd)
    else:
        parser.print_help()
        sys.exit(1)

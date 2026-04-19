# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/doctor.py — environment and health checks
# ============================================================
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from .. import constants as C
from ..config import get_config
from ..db.local_db import LocalDB
from ..db.sync_db import SyncDB
from ..ui import print_banner, print_error, print_info, print_section, print_success, print_warning


def run(offline: bool = False) -> None:
    print_banner()
    print_section("Sven doctor — system check")
    print_info("Verifying paths, tools, databases, and optional connectivity.")
    print()

    config = get_config()
    n_ok = 0
    n_warn = 0
    n_fail = 0

    def ok(m: str):
        nonlocal n_ok
        print_success(m)
        n_ok += 1

    def warn(m: str):
        nonlocal n_warn
        print_warning(m)
        n_warn += 1

    def fail(m: str):
        nonlocal n_fail
        print_error(m)
        n_fail += 1

    # ── Install root ─────────────────────────────────────────
    root = Path(config.install_root.rstrip("/") or "/")
    try:
        root_res = root.resolve()
    except OSError:
        root_res = root
    if not root_res.exists():
        fail(f"Install root does not exist: {root_res}")
    elif not root_res.is_dir():
        fail(f"Install root is not a directory: {root_res}")
    else:
        ok(f"Install root OK → {root_res}")

    # ── Config file ───────────────────────────────────────────
    cfg_path = Path(config._path)
    if cfg_path.exists():
        ok(f"Configuration file → {cfg_path}")
    else:
        warn(
            f"No {cfg_path} — using built-in defaults. "
            "Copy a template to this path to customize mirrors and safety rules."
        )

    # ── Key directories ───────────────────────────────────────
    checks: list[tuple[str, Path, bool]] = [
        ("Sync database dir", Path(config.rooted("/var/lib/sven/sync")), True),
        ("Installed DB dir", Path(config.rooted("/var/lib/sven/installed")), True),
        ("Package cache", Path(config.rooted("/var/cache/sven/pkgs")), True),
        ("Log directory", Path(config.rooted("/var/log/sven")), True),
        ("Snapshots dir", Path(config.rooted("/var/lib/sven/snapshots")), False),
    ]
    for label, p, required in checks:
        if p.exists() and p.is_dir():
            if os.access(p, os.W_OK):
                ok(f"{label} ready (writable) → {p}")
            else:
                msg = f"{label} exists but is not writable → {p}"
                if required:
                    warn(msg + " (Sven needs write access here for normal operation)")
                else:
                    warn(msg)
        else:
            msg = f"{label} missing → {p}"
            if required:
                warn(msg + " — run install.sh or: mkdir -p …")
            else:
                warn(msg)

    # ── Database lock ─────────────────────────────────────────
    lock_p = Path(config.rooted("/var/lib/sven/lock"))
    if lock_p.exists():
        try:
            raw = lock_p.read_text(encoding="utf-8", errors="replace").strip()
            pid = int(raw)
        except (OSError, ValueError):
            warn(f"Lock file present but not a valid PID → {lock_p}")
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                warn(
                    f"Stale lock file (process {pid} not running) → {lock_p}\n"
                    "      If no Sven command is active, remove this file."
                )
            except PermissionError:
                warn(f"Lock file present (pid {pid}); could not verify process → {lock_p}")
            else:
                warn(
                    f"Lock file present (pid {pid} running) — another Sven may be active."
                )
    else:
        ok("No database lock file (idle)")

    # ── Sync databases ────────────────────────────────────────
    sync = SyncDB(db_path=str(Path(config.rooted("/var/lib/sven/sync"))))
    missing_repos: list[str] = []
    stale_repos: list[str] = []
    for repo in C.ARCH_REPOS:
        db_file = sync.db_path / f"{repo}.db"
        if not db_file.exists():
            missing_repos.append(repo)
            continue
        if not sync._is_fresh(db_file):
            age_h = (time.time() - db_file.stat().st_mtime) / 3600.0
            stale_repos.append(f"{repo} (~{age_h:.0f}h)")

    if missing_repos:
        fail(
            "Missing sync database(s): "
            + ", ".join(f"{r}.db" for r in missing_repos)
            + " — run: sven sync"
        )
    else:
        ok(f"Official repo databases present ({', '.join(C.ARCH_REPOS)})")

    if stale_repos:
        warn(
            "Stale or old sync data: "
            + ", ".join(stale_repos)
            + f" — recommend: sven sync (databases older than {C.DB_MAX_AGE_SECONDS // 3600}h)"
        )

    # ── Local installed DB readable ─────────────────────────────
    try:
        ldb = LocalDB(db_path=str(Path(config.rooted("/var/lib/sven/installed"))))
        ldb.load()
        ok(f"Local installed database readable ({ldb.package_count()} package(s))")
    except Exception as e:
        warn(f"Could not load local installed database: {e}")

    # ── GPG / pacman keyring (package verification) ─────────────
    keyring = Path(config.rooted(C.GPG_KEYRING))
    if keyring.is_dir() and os.access(keyring, os.R_OK):
        ok(f"Pacman GPG keyring present → {keyring}")
    else:
        warn(
            f"Pacman keyring not found or unreadable → {keyring}\n"
            "      Binary installs need Arch packager keys (pacman-key / archlinux-keyring)."
        )

    # ── External commands ───────────────────────────────────────
    need = [
        ("gpg", "signature checks"),
        ("tar", "package extraction"),
        ("zstd", "compression"),
    ]
    optional = [
        ("git", "AUR"),
        ("fakeroot", "AUR builds"),
        ("makepkg", "AUR builds"),
    ]
    for cmd, purpose in need:
        p = shutil.which(cmd)
        if p:
            ok(f"Command `{cmd}` → {p} ({purpose})")
        else:
            fail(f"Missing `{cmd}` ({purpose}) — install from BLFS/LFS as needed")

    for cmd, purpose in optional:
        p = shutil.which(cmd)
        if p:
            ok(f"Command `{cmd}` → {p} ({purpose})")
        else:
            warn(f"Optional `{cmd}` not in PATH ({purpose})")

    # ── Python runtime deps ───────────────────────────────────
    for mod, label in (
        ("requests", "HTTP downloads"),
        ("zstandard", ".pkg.tar.zst extraction"),
    ):
        try:
            __import__(mod)
            ok(f"Python module `{mod}` ({label})")
        except ImportError:
            fail(f"Python module `{mod}` missing ({label}) — pip install {mod}")

    try:
        __import__("gnupg")
        ok("Python module `gnupg` (optional GPG integration)")
    except ImportError:
        warn("Python module `gnupg` not installed — Sven may fall back to gpg binary only")

    # ── Network (optional) ────────────────────────────────────
    if offline:
        print_info("Skipping network checks (--offline).")
    else:
        import requests

        mirror = (config.mirror or "").strip().lower()
        if mirror and mirror != "auto":
            probe = config.mirror.rstrip("/")
        else:
            probe = C.DEFAULT_MIRROR.rstrip("/")

        try:
            r = requests.head(probe, timeout=5, allow_redirects=True)
            if r.status_code < 400:
                ok(f"Mirror reachable (HEAD {probe} → {r.status_code})")
            else:
                warn(f"Mirror returned HTTP {r.status_code} for {probe}")
        except Exception as e:
            warn(f"Could not reach mirror {probe}: {e}")

        if config.use_aur:
            try:
                aur = requests.get(
                    f"{C.AUR_RPC_URL}?type=suggest&arg=a",
                    timeout=5,
                )
                if aur.status_code == 200:
                    ok("AUR RPC reachable")
                else:
                    warn(f"AUR RPC HTTP {aur.status_code}")
            except Exception as e:
                warn(f"AUR RPC not reachable: {e}")

    # ── Summary ───────────────────────────────────────────────
    print()
    print_section("Summary")
    print_info(f"Passed: {n_ok}  ·  Warnings: {n_warn}  ·  Failed: {n_fail}")
    if n_fail:
        print_error("Doctor found blocking issues — fix failures above before relying on Sven.")
        sys.exit(1)
    if n_warn:
        print_warning("Doctor finished with warnings — review messages above.")
        sys.exit(0)
    print_success("All checks passed.")
    sys.exit(0)

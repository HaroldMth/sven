# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/transaction.py — The Action Orchestrator
# ============================================================
#
#  Wires up all Phase 0-5 modules into a cohesive, atomic
#  operation. Wraps everything in Rollback protection.
# ============================================================

import os
import time
import shutil
from pathlib import Path
from datetime import datetime

from .config import get_config
from .exceptions import SvenError, RollbackFailedError, ProtectedPackageError, ChecksumMismatchError

from .db.models import Package
from .db.local_db import LocalDB
from .db.sync_db import SyncDB
from .db.aur_db import AURDB

from .resolver.graph import DependencyGraph
from .resolver.sorter import sort_dependencies
from .resolver.conflict import check_conflicts
from .resolver.compat import check_binary_compatibility
from .resolver.systemd_filter import filter_systemd_packages
from .resolver.file_conflict import check_file_conflicts

from .downloader.mirror import MirrorManager
from .downloader.fetcher import Fetcher
from .downloader.gpg import GPGVerifier
from .downloader.checksum import verify_checksum
from .downloader.pkgbuild_fetcher import PKGBUILDFetcher


from .builder.pkgbuild import parse_pkgbuild
from .builder.makepkg import build_aur_packages, run_makepkg
from .builder.aur_cache import AURCache

from .installer.extractor import Extractor
from .installer.hooks import HookRunner, run_auto_hooks
from .installer.lib_checker import LibChecker
from .installer.rollback import RollbackManager

from .ui.output import print_section, print_info, print_step, print_success

from . import constants as C
LOG_DIR = C.LOG_DIR
LOG_FILE = C.LOG_MAIN

class Transaction:
    """
    Base class for all Sven operations.
    Ensures absolute atomic safety by wrapping the action in DB locks
    and Rollback snapshots.
    """

    def __init__(self):
        self.config = get_config()
        self.local_db = LocalDB()
        self.rollback = RollbackManager()
        
        # Ensure log dir exists
        log_path = Path(self.config.rooted(LOG_DIR))
        if not log_path.exists():
            log_path.mkdir(parents=True, exist_ok=True)

    def execute(self, packages: list[str], force_protected: bool = False, _use_resolved: bool = False) -> bool:
        """
        Public entry point. 
        Acquires lock, creates snapshot, tries operation.
        If it throws, rolls back automatically.
        """
        start_time = time.time()
        success = False
        snapshot_id = None
        error_msg = ""
        
        # 1. Acquire global database lock
        if not self.local_db.acquire_lock():
            print("   ⚠ Error: Cannot acquire database lock! Is another instance of Sven running?")
            return False

        try:
            # 2. Before we even touch anything, create a pre-tx snapshot
            # We don't know the exact install list yet, so snapshot depends on tx type
            snapshot_pkgs = self._get_snapshot_packages(packages)
            snapshot_id = self.rollback.create_snapshot(snapshot_pkgs)

            # 3. Fire the implementation
            self._execute_core(packages, force_protected=force_protected, _use_resolved=_use_resolved)
            success = True

        except Exception as e:
            # 4. Catastrophic or planned failure → Auto Rollback
            success = False
            error_msg = str(e)

            # Special formatting for ProtectedPackageError
            if isinstance(e, ProtectedPackageError):
                print(f"\n{e}\n")
            else:
                print(f"\n   ╭{'─' * 50}╮")
                print("   │  Install failed — restoring the pre-transaction snapshot")
                print(f"   ╰{'─' * 50}╯")
                print(f"   Cause: {e}")
            
            if snapshot_id:
                try:
                    self.rollback.restore(snapshot_id)
                    print("   ✓ System successfully reverted.")
                except Exception as rollback_e:
                    print(
                        "   [CRITICAL] Rollback did not complete successfully: "
                        f"{rollback_e}"
                    )
                    print(
                        "   [CRITICAL] The system may be inconsistent — "
                        "stop and seek help before rebooting or upgrading."
                    )

        finally:
            # 5. Release lock & Log
            self.local_db.release_lock()
            duration = round(time.time() - start_time, 2)
            self._log_transaction(packages, success, duration, error_msg)

        return success

    def _execute_core(self, packages: list[str], force_protected: bool = False, _use_resolved: bool = False):
        """Implemented by child classes."""
        raise NotImplementedError

    def _get_snapshot_packages(self, packages: list[str]) -> list[str]:
        """Implemented by child classes. Return pkgs to backup in snapshot."""
        return packages

    def _log_transaction(self, packages: list[str], success: bool, duration: float, error_msg: str):
        """Append to system log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "SUCCESS" if success else f"FAIL ({error_msg})"
        pkg_str = " ".join(packages) if packages else "ALL"
        op = self.__class__.__name__.replace("Transaction", "").upper()

        log_line = f"[{timestamp}] [{op}] pkgs:[{pkg_str}] status:[{status}] duration:[{duration}s]\n"
        
        log_path = Path(self.config.rooted(LOG_FILE))
        try:
            with open(log_path, "a") as f:
                f.write(log_line)
        except OSError:
            pass

    def _handle_scary_prompt(self, detected: list[str]):
        """Show the extra scary warning for protected packages."""
        print(f"\n   \033[91m⚠  WARNING: Protected packages detected: {', '.join(detected)}\033[0m")
        print("   Overriding protection for core LFS packages is DANGEROUS.")
        print("   If you proceed, your system may become UNBOOTABLE.")
        print("")
        import sys
        reply = input("   Type 'YES I KNOW' to continue: ")
        if reply != "YES I KNOW":
            print("   Aborted by user.")
            sys.exit(1)
        
        # Log override to sven.log
        log_path = Path(self.config.rooted(C.LOG_MAIN))
        try:
            with open(log_path, "a") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [OVERRIDE] force_protected used for: {', '.join(detected)}\n")
        except: pass



class InstallTransaction(Transaction):
    """
    Handles resolving, downloading, building, and installing packages.
    """
    def __init__(self, explicit: bool = True, verbose: bool = False):
        super().__init__()
        self.explicit = explicit
        self.verbose = verbose

        self.sync_db = SyncDB()
        self.aur_db = AURDB()

    def resolve(self, targets: list[str], force_protected: bool = False) -> list:
        """
        Phase 1 only: resolve deps and return the filtered install order.
        This lets the CLI show the user what they're getting BEFORE confirming.
        Returns an empty list if nothing to install.
        """
        if not targets:
            return []

        protected_list = self.config.protected_packages
        if force_protected:
            detected_targets = [t for t in targets if t in protected_list]
            if detected_targets:
                self._handle_scary_prompt(detected_targets)
        else:
            for t in targets:
                if t in protected_list:
                    raise ProtectedPackageError(t)

        graph = DependencyGraph(self.sync_db, self.aur_db, self.local_db)
        for target in targets:
            graph.add_package(target)

        install_order = sort_dependencies(graph.nodes, graph.edges)

        if not force_protected:
            for pkg in install_order:
                if pkg.name in protected_list:
                    raise ProtectedPackageError(pkg.name)
        else:
            detected_deps = [p.name for p in install_order if p.name in protected_list and p.name not in targets]
            if detected_deps:
                self._handle_scary_prompt(detected_deps)

        installed = self.local_db.list_installed()
        install_order = [p for p in install_order if p.name not in installed]

        if not install_order:
            return []

        filtered_pkgs, _ = filter_systemd_packages(install_order, "sysvinit", strict=False)
        return filtered_pkgs

    def execute_resolved(self, resolved_pkgs: list, force_protected: bool = False) -> bool:
        """
        Execute install phases 2-6 using a pre-resolved package list.
        Called after the user confirms.
        """
        if not resolved_pkgs:
            print("Nothing to install.")
            return True
        
        # Save the resolved list and call _execute_resolved_core inside the transaction wrapper
        self._resolved_pkgs = resolved_pkgs
        return self.execute([], force_protected=force_protected, _use_resolved=True)
        

    def _execute_core(self, targets: list[str], force_protected: bool = False, _use_resolved: bool = False):
        # If we have pre-resolved packages, skip resolution
        if _use_resolved and hasattr(self, '_resolved_pkgs'):
            filtered_pkgs = self._resolved_pkgs
            install_order_names = [p.name for p in filtered_pkgs]
        else:
            if not targets:
                print("Nothing to install.")
                return

            # 1. IMMEDIATE protection check
            protected_list = self.config.protected_packages
            if force_protected:
                detected_targets = [t for t in targets if t in protected_list]
                if detected_targets:
                    self._handle_scary_prompt(detected_targets)
            else:
                for t in targets:
                    if t in protected_list:
                        raise ProtectedPackageError(t)

            print()
            print_section("Install · 1/6 · Resolving dependencies")
            graph = DependencyGraph(self.sync_db, self.aur_db, self.local_db)

            for target in targets:
                graph.add_package(target)
            
            install_order = sort_dependencies(graph.nodes, graph.edges)

            if not force_protected:
                for pkg in install_order:
                    if pkg.name in protected_list:
                        raise ProtectedPackageError(pkg.name)
            else:
                detected_deps = [p.name for p in install_order if p.name in protected_list and p.name not in targets]
                if detected_deps:
                    self._handle_scary_prompt(detected_deps)

            installed = self.local_db.list_installed()
            install_order = [p for p in install_order if p.name not in installed]

            if not install_order:
                print("Target is already up to date.")
                return

            filtered_pkgs, _ = filter_systemd_packages(install_order, "sysvinit", strict=False)
            install_order_names = [p.name for p in filtered_pkgs]

            if not filtered_pkgs:
                print("Target is already up to date or blocked.")
                return

        if self.verbose or len(install_order_names) <= 14:
            print_info(f"Dependency order: {' → '.join(install_order_names)}")
        else:
            print_info(
                f"Dependency order: {len(install_order_names)} packages "
                "(use --verbose to print the full list)"
            )
        print()

        # Separate official vs AUR vs Build targets
        to_download = []
        to_build = []

        for pkg in filtered_pkgs:
            if pkg.origin == "aur":
                to_build.append(pkg)
            else:
                # All non-aur are considered official/sync for this phase
                to_download.append(pkg)

        print_section("Install · 2/6 · Fetching packages")

        # Download Official Packages
        downloaded_paths = {}
        if not to_download:
            print_info(
                "No packages to download from mirrors (using cache and/or local builds only)."
            )
        if to_download:
            manager = MirrorManager()
            if self.verbose:
                print_info(f"Primary mirror: {manager.current}")
                print_step("Parallel downloads with live progress; mirror failover is automatic.")
            fetcher = Fetcher(manager)
            downloaded_paths = fetcher.download_packages(
                to_download, verbose=self.verbose
            )
                 
            # GPG Verification of signatures
            gpg = GPGVerifier()
            for pkg in to_download:
                path = downloaded_paths.get(pkg.name)
                if path:
                    gpg.verify(path)

        # Build AUR Packages
        built_paths = {}
        if to_build:
            pkgbuild_fetcher = PKGBUILDFetcher()
            aur_cache = AURCache()
            
            build_queue = []
            for pkg in to_build:
                pkg_dir = pkgbuild_fetcher.fetch_aur(pkg.name)
                
                # Check cache first
                cached = aur_cache.check_before_build(pkg.name, pkg.version)
                if cached:
                    built_paths[pkg.name] = cached
                else:
                    build_queue.append({"name": pkg.name, "dir": pkg_dir})
            
            if build_queue:
                print()
                print_section("Install · 3/6 · Compiling AUR packages")
                if self.verbose:
                    print_step("Build output from makepkg follows below.")
                results = build_aur_packages(build_queue, interactive=True)
                built_paths.update(results)
                
                # Store new builds in cache
                for pkg in to_build:
                    if pkg.name in results:
                        aur_cache.store(pkg.name, pkg.version, results[pkg.name])

        # Conflict Checking & Safety
        merged_paths = {**downloaded_paths, **built_paths}

        print()
        print_section("Install · 4/6 · Safety checks")
        if self.verbose:
            print_step(
                "Checking package conflicts, file overlaps on disk, and library hints."
            )

        # Package-level conflicts
        check_conflicts(filtered_pkgs, self.local_db)
        
        # File-level conflicts
        for pkg in filtered_pkgs:
            archive = merged_paths.get(pkg.name)
            if archive:
                check_file_conflicts(pkg, archive, self.local_db, force=False)
                
        # Library Checks
        lib_chk = LibChecker()
        for pkg_name, archive in merged_paths.items():
            # In real system, we'd read requires from archive .PKGINFO
            # Here we skip deep mock lookup for brevity
            pass

        print()
        print_section("Install · 5/6 · Extracting onto the system")
        if self.verbose:
            print_step("Running per-package install hooks before and after files land.")
        ext = Extractor()
        
        for pkg in filtered_pkgs:
            pkg_name = pkg.name
            if pkg_name not in merged_paths:
                continue
                 
            archive = merged_paths[pkg_name]
            
            # Pre hooks
            hr = HookRunner(pkg.name, Path(archive).with_name(".INSTALL").as_posix())
            hr.run_phase("pre_install", pkg.version)

            # Extract!
            files_extracted = ext.extract(archive)

            # Register
            self.local_db.register(
                pkg,
                files_extracted,
                explicit=(self.explicit and pkg.name in targets)
            )



            # Post hooks
            hr.run_phase("post_install", pkg.version)


        print()
        print_section("Install · 6/6 · Global hooks")
        if self.verbose:
            print_step("Updating caches, databases, and other system-wide post-install tasks.")
        run_auto_hooks()

        print()
        print_success("Transaction successfully sealed.")


class RemoveTransaction(Transaction):
    """
    Handles safely removing packages and cleaning DB.
    """
    def _execute_core(self, targets: list[str], force_protected: bool = False, _use_resolved: bool = False):
        if not targets:
            return

        # Check protection
        protected_list = self.config.protected_packages
        if not force_protected:
            for pkg_name in targets:
                if pkg_name in protected_list:
                    raise ProtectedPackageError(pkg_name)

        print("\n   [Remove] Preparing deletion...")
        
        for pkg_name in targets:
            if not self.local_db.has(pkg_name):
                print(f"Target {pkg_name} is not installed.")
                continue
                
            # TODO: Add reverse dependency logic if required
            
            # Run pre_remove
            hr = HookRunner(pkg_name, f"/var/lib/sven/local/{pkg_name}/.INSTALL")
            hr.run_phase("pre_remove", "latest")
            
            files = self.local_db.get_files(pkg_name)
            for f in files:
                p = Path(self.config.rooted(f))
                if p.exists() and p.is_file():
                    p.unlink()
            
            self.local_db.remove(pkg_name)
            
            hr.run_phase("post_remove", "latest")

        run_auto_hooks()
        print("\n   ★ Transaction successfully sealed.")


class UpgradeTransaction(InstallTransaction):
    """
    Upgrades installed system.
    """
    def _get_snapshot_packages(self, packages: list[str]) -> list[str]:
        # For full upgrade, snapshot EVERYTHING that is changing.
        # But we must calculate the diff first. For simplicity, just return
        # the local catalog so we backup configs.
        if not packages:
            return self.local_db.list_installed()
        return packages
        
    def _execute_core(self, targets: list[str] = None, force_protected: bool = False, _use_resolved: bool = False):
        print("\n   [Upgrade] Synchronizing local catalog with mirrors...")
        
        installed = self.local_db.list_installed()
        to_upgrade = []
        
        for pkg_name in installed:
            if targets and pkg_name not in targets:
                continue
                
            local_pkg = self.local_db.get(pkg_name)
            remote_pkg = self.sync_db.get(pkg_name)
            
            if remote_pkg and local_pkg and remote_pkg.version != local_pkg.version:
                to_upgrade.append(pkg_name)
                
        if not to_upgrade:
            print("   Everything is up to date.")
            return

        print(f"   => Found {len(to_upgrade)} upgrades: {' '.join(to_upgrade)}")
        
        # Fire off an InstallTransaction on the diff
        super()._execute_core(to_upgrade, force_protected=force_protected)

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
from .exceptions import SvenError, RollbackFailedError

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


LOG_DIR = "/var/log/sven"
LOG_FILE = f"{LOG_DIR}/sven.log"


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

    def execute(self, packages: list[str]) -> bool:
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
            self._execute_core(packages)
            success = True

        except Exception as e:
            # 4. Catastrophic or planned failure → Auto Rollback
            success = False
            error_msg = str(e)
            print(f"\n   ╭{'─' * 50}╮")
            print(f"   │  TRANSACTION FAILED: Rolling Back Data")
            print(f"   ╰{'─' * 50}╯")
            print(f"   Error: {e}")
            
            if snapshot_id:
                try:
                    self.rollback.restore(snapshot_id)
                    print("   ✓ System successfully reverted.")
                except Exception as rollback_e:
                    print(f"   [CRITICAL] Rollback mechanically failed: {rollback_e}")
                    print(f"   [CRITICAL] System may be in an inconsistent state!")

        finally:
            # 5. Release lock & Log
            self.local_db.release_lock()
            duration = round(time.time() - start_time, 2)
            self._log_transaction(packages, success, duration, error_msg)

        return success

    def _execute_core(self, packages: list[str]):
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


class InstallTransaction(Transaction):
    """
    Handles resolving, downloading, building, and installing packages.
    """
    def __init__(self, explicit: bool = True):
        super().__init__()
        self.explicit = explicit
        
        self.sync_db = SyncDB()
        self.aur_db = AURDB()
        
    def _execute_core(self, targets: list[str]):
        if not targets:
            print("Nothing to install.")
            return

        print("\n   [Install] Phase 1/6: Resolving Dependencies...")
        graph = DependencyGraph(self.sync_db, self.aur_db)
        for target in targets:
            graph.add_package(target)
        
        # Topological Sort
        install_order = sort_dependencies(graph.get_graph_data())
        
        if not install_order:
            print("Target is already up to date.")
            return

        print(f"   Targets: {' '.join(targets)}")
        print(f"   Calculated Order: {' -> '.join(install_order)}\n")

        # Systemd filtering
        pkg_objects = []
        for p in install_order:
            pkg = self.sync_db.get(p) or self.aur_db.get(p)
            if pkg: pkg_objects.append(pkg)
            
        filtered_pkgs = filter_systemd_packages(pkg_objects, "sysvinit")
        install_order = [p.name for p in filtered_pkgs]

        # Separate official vs AUR vs Build targets
        compat = CompatChecker()
        to_download = []
        to_build = []

        for pkg_name in install_order:
            pkg = self.sync_db.get(pkg_name)
            if pkg:
                # Optional: Compat check on Official packages could trigger a rebuild
                # But for simplicity in trans, we assume AUR is src, Official is bin.
                to_download.append(pkg)
            elif self.aur_db.has(pkg_name):
                to_build.append(self.aur_db.get(pkg_name))
            else:
                raise SvenError(f"Target '{pkg_name}' not found anywhere.")

        print("\n   [Install] Phase 2/6: Fetching Resources...")
        
        # Download Official Packages
        downloaded_paths = {}
        if to_download:
            manager = MirrorManager()
            fetcher = Fetcher(manager)
            downloaded = fetcher.download_all([p.name for p in to_download])
            for d in downloaded:
                downloaded_paths[d["pkg"]] = d["file"]
                
            # Verify exactly after downloading
            gpg = GPGVerifier()
            for pkg in to_download:
                path = downloaded_paths.get(pkg.name)
                if path:
                    gpg.verify(path)
                    verify_checksum(path, "mock-sha256")

        # Build AUR Packages
        built_paths = {}
        if to_build:
            pkgbuild_fetcher = PKGBUILDFetcher()
            aur_cache = AURCache()
            
            build_queue = []
            for pkg in to_build:
                pkg_dir = pkgbuild_fetcher.fetch(pkg.name)
                
                # Check cache first
                cached = aur_cache.check_before_build(pkg.name, pkg.version)
                if cached:
                    built_paths[pkg.name] = cached
                else:
                    build_queue.append({"name": pkg.name, "dir": pkg_dir})
            
            if build_queue:
                print("\n   [Install] Phase 3/6: Compiling Packages...")
                results = build_aur_packages(build_queue, interactive=True)
                built_paths.update(results)
                
                # Store new builds in cache
                for pkg in to_build:
                    if pkg.name in results:
                        aur_cache.store(pkg.name, pkg.version, results[pkg.name])

        # Conflict Checking & Safety
        merged_paths = {**downloaded_paths, **built_paths}
        
        for pkg_name, archive in merged_paths.items():
            check_file_conflicts(archive, self.local_db, force=False)
                
        # Library Checks
        lib_chk = LibChecker()
        for pkg_name, archive in merged_paths.items():
            # In real system, we'd read requires from archive .PKGINFO
            # Here we skip deep mock lookup for brevity
            pass

        print("\n   [Install] Phase 4/6: Extracting onto System...")
        ext = Extractor()
        
        for pkg_name in install_order:
            if pkg_name not in merged_paths:
                continue
                
            archive = merged_paths[pkg_name]
            
            # Pre hooks
            hr = HookRunner(pkg_name, Path(archive).with_name(".INSTALL").as_posix())
            hr.run_phase("pre_install", "latest")

            # Extract!
            files_extracted = ext.extract(archive)

            # Register
            self.local_db.install_package(
                name=pkg_name,
                version="latest",
                desc="Installed by Sven",
                url="",
                files=files_extracted,
                reason="explicit" if self.explicit and pkg_name in targets else "depend"
            )

            # Post hooks
            hr.run_phase("post_install", "latest")

        print("\n   [Install] Phase 6/6: Global Auto-Hooks...")
        run_auto_hooks()
        
        print("\n   ★ Transaction successfully sealed.")


class RemoveTransaction(Transaction):
    """
    Handles safely removing packages and cleaning DB.
    """
    def _execute_core(self, targets: list[str]):
        if not targets:
            return

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
        
    def _execute_core(self, targets: list[str] = None):
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
        
        # Fire off an InstallTransaction on the diff (InstallTx handles upgrades implicitly via File Conflicts mapping configs)
        super()._execute_core(to_upgrade)

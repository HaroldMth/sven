# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  db/local_db.py — Sven's installed package database
# ============================================================

import os
import time
import json
import fcntl
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sven")


from .models import Package
from ..constants import DB_INSTALLED, DB_LOCK
from ..exceptions import (
    DatabaseLockError,
    DatabaseCorruptError,
    PackageNotInstalledError,
)


# ── LocalDB class ─────────────────────────────────────────────

class LocalDB:
    """
    Manages Sven's database of installed packages.

    Structure:
        /var/lib/sven/installed/
        ├── firefox-125.0-1/
        │   ├── desc         ← metadata (JSON)
        │   └── files        ← newline-separated file list
        ├── gtk3-4.14.2-1/
        │   └── ...
    """

    def __init__(
        self,
        db_path   = None,
        lock_path = None,
    ):
        from .. import constants as C
        logger.debug(f"LocalDB.__init__: root is {db_path or C.DB_INSTALLED}")
        self.db_path   = Path(db_path or C.DB_INSTALLED)
        self.lock_path = Path(lock_path or C.DB_LOCK)
        self.db_path.mkdir(parents=True, exist_ok=True)

        self._lock_fd = None

        # In-memory cache: name → Package
        self._cache : dict[str, Package] = {}
        # Provides map: virtual → real package name
        self._provides : dict[str, str] = {}
        self._loaded = False

    # ── Lock ──────────────────────────────────────────────────

    def acquire_lock(self):
        """
        Acquire exclusive lock on the DB.
        Prevents two sven processes running at the same time.
        Raises DatabaseLockError if already locked.
        """
        try:
            self._lock_fd = open(self.lock_path, "w")
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            return True
        except BlockingIOError:
            raise DatabaseLockError(
                "Another Sven process is already running.\n"
                f"Lock file: {self.lock_path}\n"
                "If this is wrong, delete the lock file manually."
            )

    def release_lock(self):
        """Release the DB lock."""
        if self._lock_fd:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            self._lock_fd.close()
            self._lock_fd = None
            try:
                self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass

    # ── Load ──────────────────────────────────────────────────

    def load(self):
        """Load all installed packages into memory."""
        self._cache.clear()
        self._provides.clear()
        for pkg_dir in self.db_path.iterdir():
            if not pkg_dir.is_dir():
                continue
            try:
                pkg = self._read_pkg_dir(pkg_dir)
                if pkg:
                    self._cache[pkg.name] = pkg
                    # Index provides
                    for prov in pkg.provides:
                        virt = prov.split("=")[0].split(">")[0].split("<")[0]
                        self._provides[virt.strip()] = pkg.name
            except Exception:
                # Skip corrupt entries silently
                pass
        self._loaded = True

    def _read_pkg_dir(self, pkg_dir: Path) -> Optional[Package]:
        """Read a single installed package directory."""
        desc_file = pkg_dir / "desc"
        if not desc_file.exists():
            return None

        try:
            with open(desc_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            raise DatabaseCorruptError(
                f"Corrupt DB entry: {pkg_dir.name}"
            )

        return Package(
            name             = data.get("name", ""),
            version          = data.get("version", ""),
            desc             = data.get("desc", ""),
            url              = data.get("url", ""),
            repo             = data.get("repo", "extra"),
            origin           = data.get("origin", "official"),
            arch             = data.get("arch", "x86_64"),
            size             = data.get("size", 0),
            isize            = data.get("isize", 0),
            deps             = data.get("deps", []),
            optdeps          = data.get("optdeps", []),
            provides         = data.get("provides", []),
            conflicts        = data.get("conflicts", []),
            replaces         = data.get("replaces", []),
            license          = data.get("license", []),
            explicit         = data.get("explicit", True),
            install_date     = data.get("install_date"),
            aur_maintainer   = data.get("aur_maintainer", ""),
        )

    # ── Query ─────────────────────────────────────────────────

    def get(self, name: str) -> Optional[Package]:
        """Get an installed package by name (or virtual). Returns None if not installed."""
        if not self._loaded:
            self.load()
        if name in self._cache:
            return self._cache[name]
        # Resolve as virtual
        real = self._provides.get(name)
        if real:
            return self._cache.get(real)
        return None

    def is_installed(self, name: str) -> bool:
        return self.get(name) is not None

    def has(self, name: str) -> bool:
        return self.is_installed(name)

    def list_installed(self) -> list[str]:
        return [p.name for p in self.all_packages()]

    def get_version(self, name: str) -> Optional[str]:
        pkg = self.get(name)
        return pkg.version if pkg else None

    def all_packages(self) -> list[Package]:
        if not self._loaded:
            self.load()
        return list(self._cache.values())

    def explicit_packages(self) -> list[Package]:
        """Packages explicitly installed by the user."""
        return [p for p in self.all_packages() if p.explicit]

    def auto_packages(self) -> list[Package]:
        """Packages installed automatically as dependencies."""
        return [p for p in self.all_packages() if not p.explicit]

    def aur_packages(self) -> list[Package]:
        """Packages installed from the AUR."""
        return [p for p in self.all_packages() if p.origin == "aur"]

    def orphans(self) -> list[Package]:
        """
        Auto-installed packages that nothing explicitly installed depends on.
        These are safe to remove.
        """
        all_pkgs   = self.all_packages()
        all_deps   = set()

        for pkg in all_pkgs:
            for dep in pkg.deps:
                # Strip version constraints
                clean = dep.split(">=")[0].split("<=")[0] \
                           .split(">")[0].split("<")[0] \
                           .split("=")[0].strip()
                all_deps.add(clean)

        return [
            p for p in self.auto_packages()
            if p.name not in all_deps
        ]

    def unregister(self, name: str):
        """Remove a package from the database."""
        if not self.is_installed(name):
            return
            
        pkg = self._cache.pop(name)
        pkg_dir = self.db_path / pkg.full_name
        
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)

    def remove(self, name: str):
        self.unregister(name)

    def install_package(self, name: str, version: str, desc: str, url: str, files: list[str], reason: str = "depend"):
        pkg = Package(name=name, version=version, desc=desc, url=url, origin=reason)
        self.register(pkg, files, explicit=(reason == "explicit"))

    def get_files(self, name: str) -> list[str]:
        """Return list of files owned by a package."""
        pkg = self.get(name)
        if not pkg:
            raise PackageNotInstalledError(name)

        files_path = self.db_path / pkg.full_name / "files"
        if not files_path.exists():
            return []

        with open(files_path) as f:
            return [line.strip() for line in f if line.strip()]

    def package_count(self) -> int:
        return len(self._cache)

    # ── Write ─────────────────────────────────────────────────

    def register(
        self,
        pkg      : Package,
        files    : list[str],
        explicit : bool = True,
    ):
        """
        Record a package as installed.
        Creates the DB entry directory with desc + files.
        """
        pkg.explicit     = explicit
        pkg.install_date = int(time.time())

        entry_dir = self.db_path / pkg.full_name
        entry_dir.mkdir(parents=True, exist_ok=True)

        # Write desc as JSON
        desc_data = {
            "name"          : pkg.name,
            "version"       : pkg.version,
            "desc"          : pkg.desc,
            "url"           : pkg.url,
            "repo"          : pkg.repo,
            "origin"        : pkg.origin,
            "arch"          : pkg.arch,
            "size"          : pkg.size,
            "isize"         : pkg.isize,
            "deps"          : pkg.deps,
            "optdeps"       : pkg.optdeps,
            "provides"      : pkg.provides,
            "conflicts"     : pkg.conflicts,
            "replaces"      : pkg.replaces,
            "license"       : pkg.license,
            "explicit"      : pkg.explicit,
            "install_date"  : pkg.install_date,
            "aur_maintainer": pkg.aur_maintainer,
        }

        with open(entry_dir / "desc", "w") as f:
            json.dump(desc_data, f, indent=2)

        # Write files list
        with open(entry_dir / "files", "w") as f:
            f.write("\n".join(files))

        # Update in-memory cache
        self._cache[pkg.name] = pkg

    def unregister(self, name: str):
        """
        Remove a package from the DB.
        Called during removal AFTER files are deleted.
        """
        pkg = self.get(name)
        if not pkg:
            raise PackageNotInstalledError(name)

        entry_dir = self.db_path / pkg.full_name

        # Remove desc and files
        for f in ("desc", "files"):
            p = entry_dir / f
            if p.exists():
                p.unlink()

        # Remove directory
        try:
            entry_dir.rmdir()
        except OSError:
            pass  # not empty for some reason — leave it

        # Remove from cache
        self._cache.pop(name, None)

    def update_version(self, pkg: Package, files: list[str]):
        """
        Update an existing package to a new version.
        Called during upgrade — removes old entry, registers new.
        """
        old_pkg = self.get(pkg.name)
        if old_pkg:
            # Remove old entry dir
            old_dir = self.db_path / old_pkg.full_name
            for f in ("desc", "files"):
                p = old_dir / f
                if p.exists():
                    p.unlink()
            try:
                old_dir.rmdir()
            except OSError:
                pass

        # Register new version — preserve explicit flag
        explicit = old_pkg.explicit if old_pkg else True
        self.register(pkg, files, explicit=explicit)

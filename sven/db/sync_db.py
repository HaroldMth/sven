# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  db/sync_db.py — fetches + parses Arch sync databases
# ============================================================

import os
import tarfile
import time
import requests
from pathlib import Path
from typing import Optional

from .models import Package
from ..constants import (
    ARCH_REPOS, ARCH_ARCH,
    DEFAULT_MIRROR, MIRROR_DB_URL,
    DB_SYNC, DB_MAX_AGE_SECONDS,
)
from ..exceptions import DatabaseError, DatabaseStaleError


# ── Parser ───────────────────────────────────────────────────

def _parse_desc(desc_text: str, repo: str) -> Package:
    """
    Parse a single package desc file from the Arch sync DB.

    Format is alternating %FIELD% / value blocks:
        %NAME%
        firefox
        %VERSION%
        125.0-1
        %DEPENDS%
        gtk3
        nss
    """
    fields: dict[str, list[str]] = {}
    current_key = None

    for line in desc_text.splitlines():
        line = line.strip()
        if not line:
            current_key = None
            continue
        if line.startswith("%") and line.endswith("%"):
            current_key = line[1:-1]          # strip % %
            fields[current_key] = []
        elif current_key is not None:
            fields[current_key].append(line)

    def get(key: str) -> str:
        return fields.get(key, [""])[0]

    def get_list(key: str) -> list[str]:
        return fields.get(key, [])

    return Package(
        name        = get("NAME"),
        version     = get("VERSION"),
        desc        = get("DESC"),
        url         = get("URL"),
        repo        = repo,
        origin      = "official",
        arch        = get("ARCH") or ARCH_ARCH,
        filename    = get("FILENAME"),
        csum        = get("SHA256SUM"),
        size        = int(get("CSIZE") or 0),
        isize       = int(get("ISIZE") or 0),
        packager    = get("PACKAGER"),
        builddate   = int(get("BUILDDATE") or 0),
        deps        = get_list("DEPENDS"),
        makedeps    = get_list("MAKEDEPENDS"),
        optdeps     = get_list("OPTDEPENDS"),
        checkdeps   = get_list("CHECKDEPENDS"),
        conflicts   = get_list("CONFLICTS"),
        provides    = get_list("PROVIDES"),
        replaces    = get_list("REPLACES"),
        license     = get_list("LICENSE"),
    )


# ── SyncDB class ─────────────────────────────────────────────

class SyncDB:
    """
    Manages Arch Linux sync databases.

    Fetches .db files from mirrors, caches them locally,
    parses them into Package objects on demand.
    """

    def __init__(
        self,
        mirror  : str = None,
        db_path : str = None,
        repos   : list[str] = None,
        arch    : str = None,
    ):
        from .. import constants as C
        self.mirror   = (mirror or C.DEFAULT_MIRROR).rstrip("/")
        self.db_path  = Path(db_path or C.DB_SYNC)
        self.repos    = repos or C.ARCH_REPOS
        self.arch     = arch or C.ARCH_ARCH
        self.db_path.mkdir(parents=True, exist_ok=True)

        # In-memory index: name → Package
        self._index : dict[str, Package] = {}

        # Provides map: virtual → real package name
        self._provides : dict[str, str] = {}

    # ── Sync ─────────────────────────────────────────────────

    def sync(self, force: bool = False) -> dict[str, bool]:
        """
        Download fresh .db files from the mirror.
        Returns dict of repo → success.
        Skips repos that are still fresh unless force=True.
        """
        results = {}
        for repo in self.repos:
            db_file = self.db_path / f"{repo}.db"

            if not force and self._is_fresh(db_file):
                print(f"   {repo}.db        [up to date]")
                results[repo] = True
                continue

            url = MIRROR_DB_URL.format(
                mirror=self.mirror,
                repo=repo,
                arch=self.arch,
            )

            try:
                self._download_db(url, db_file, repo)
                results[repo] = True
            except Exception as e:
                print(f"   ✗ {repo}.db failed: {e}")
                results[repo] = False

        return results

    def _download_db(self, url: str, dest: Path, repo: str):
        """Download a single .db file with progress."""
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 8192
        last_shown_pct = -1

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct_bar = min(20, int(downloaded / total * 20))
                    if pct_bar != last_shown_pct or downloaded >= total:
                        last_shown_pct = pct_bar
                        bar = "#" * pct_bar + "·" * (20 - pct_bar)
                        mb = downloaded / 1_000_000
                        total_mb = total / 1_000_000
                        print(
                            f"\r\033[2K   {repo}.db  [{bar}]  "
                            f"{mb:.1f}/{total_mb:.1f} MiB",
                            end="",
                            flush=True,
                        )
        print(f"\r\033[2K   {repo}.db  ✓", flush=True)

    def _is_fresh(self, db_file: Path) -> bool:
        """Return True if the .db file exists and is less than 24h old."""
        if not db_file.exists():
            return False
        age = time.time() - db_file.stat().st_mtime
        return age < DB_MAX_AGE_SECONDS

    # ── Load ─────────────────────────────────────────────────

    def load(self):
        """
        Parse all cached .db files into the in-memory index.
        Must be called after sync() or at startup.
        """
        self._index.clear()
        self._provides.clear()

        for repo in self.repos:
            db_file = self.db_path / f"{repo}.db"
            if not db_file.exists():
                raise DatabaseError(
                    f"Sync DB not found: {db_file}\n"
                    f"Run: sven sync"
                )
            self._parse_db(db_file, repo)

    def _parse_db(self, db_file: Path, repo: str):
        """
        Extract + parse a single .db tarball.

        Structure inside the tarball:
            firefox-125.0-1/
                desc
            gtk3-4.14.2-1/
                desc
        """
        try:
            with tarfile.open(db_file, "r:*") as tar:
                desc_files = [
                    m for m in tar.getmembers()
                    if m.name.endswith("/desc")
                ]
                for member in desc_files:
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    text = f.read().decode("utf-8", errors="replace")
                    pkg  = _parse_desc(text, repo)
                    if pkg.name:
                        self._index[pkg.name] = pkg
                        # Index all provides as virtual → real
                        for prov in pkg.provides:
                            # Strip version constraint e.g. "sh=1.0" → "sh"
                            virt = prov.split("=")[0].split(">")[0].split("<")[0]
                            self._provides[virt.strip()] = pkg.name

        except tarfile.TarError as e:
            raise DatabaseError(f"Failed to parse {db_file}: {e}")

    # ── Query ─────────────────────────────────────────────────

    def _ensure_loaded(self):
        if not self._index:
            self.load()

    def get(self, name: str) -> Optional[Package]:
        """
        Get a package by exact name.
        Also resolves virtual packages via provides map.
        """
        self._ensure_loaded()
        if name in self._index:
            return self._index[name]
        # Try resolving as a virtual
        real = self._provides.get(name)
        if real:
            return self._index.get(real)
        return None

    def search(self, query: str) -> list[Package]:
        """
        Fuzzy search packages by name or description.
        Returns list sorted by relevance (exact match first).
        """
        self._ensure_loaded()
        query_lower = query.lower()
        exact   = []
        starts  = []
        contains= []

        for pkg in self._index.values():
            name_lower = pkg.name.lower()
            if name_lower == query_lower:
                exact.append(pkg)
            elif name_lower.startswith(query_lower):
                starts.append(pkg)
            elif query_lower in name_lower or query_lower in pkg.desc.lower():
                contains.append(pkg)

        return exact + starts + contains

    def all_packages(self) -> list[Package]:
        """Return all known packages across all repos."""
        self._ensure_loaded()
        return list(self._index.values())

    def is_loaded(self) -> bool:
        return len(self._index) > 0

    def package_count(self) -> int:
        return len(self._index)

    # ── Stale check ───────────────────────────────────────────

    def check_freshness(self):
        """Warn if any .db file is stale."""
        for repo in self.repos:
            db_file = self.db_path / f"{repo}.db"
            if not db_file.exists():
                raise DatabaseStaleError(
                    f"{repo}.db missing. Run: sven sync"
                )
            if not self._is_fresh(db_file):
                age_hours = (time.time() - db_file.stat().st_mtime) / 3600
                print(
                    f"⚠  {repo}.db is {age_hours:.0f}h old. "
                    f"Consider running: sven sync"
                )

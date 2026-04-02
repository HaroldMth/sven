# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  builder/aur_cache.py — AUR build artifact cache
# ============================================================
#
#  Caches built .pkg.tar.zst files to avoid rebuilding.
#  Key: {name}-{version}-{arch}.pkg.tar.zst
#  Location: /var/cache/sven/aur/
# ============================================================

import os
import glob
import shutil
from pathlib import Path

from ..constants import CACHE_AUR, ARCH_ARCH
from ..config import get_config


class AURCache:
    """
    Manages cached AUR build artifacts.

    Built packages are stored in /var/cache/sven/aur/ to avoid
    rebuilding the same version. If a cached version exists and
    matches the requested version, it's returned directly.
    """

    def __init__(self, cache_dir: str = CACHE_AUR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Cache key ────────────────────────────────────────────

    def _cache_key(self, name: str, version: str, arch: str = ARCH_ARCH) -> str:
        """Generate the cache filename."""
        return f"{name}-{version}-{arch}.pkg.tar.zst"

    def _cache_path(self, name: str, version: str, arch: str = ARCH_ARCH) -> Path:
        """Full path to the cached package."""
        return self.cache_dir / self._cache_key(name, version, arch)

    # ── Lookup ───────────────────────────────────────────────

    def get(self, name: str, version: str, arch: str = ARCH_ARCH) -> str | None:
        """
        Check if a built package is cached.
        Returns the full path if found, None otherwise.
        """
        path = self._cache_path(name, version, arch)
        if path.exists() and path.stat().st_size > 0:
            return str(path)
        return None

    def has(self, name: str, version: str, arch: str = ARCH_ARCH) -> bool:
        """Check if a cached version exists."""
        return self.get(name, version, arch) is not None

    # ── Store ────────────────────────────────────────────────

    def store(self, name: str, version: str, built_path: str, arch: str = ARCH_ARCH) -> str:
        """
        Copy a built package into the cache.

        Args:
            name: Package name
            version: Full version (e.g. "1.0-1")
            built_path: Path to the .pkg.tar.zst from makepkg
            arch: Architecture (default x86_64)

        Returns:
            Path to the cached file
        """
        src = Path(built_path)
        if not src.exists():
            raise FileNotFoundError(f"Built package not found: {built_path}")

        dest = self._cache_path(name, version, arch)
        shutil.copy2(str(src), str(dest))

        print(f"   ✓ Cached: {dest.name}")
        return str(dest)

    # ── Remove ───────────────────────────────────────────────

    def remove(self, name: str, version: str = None, arch: str = ARCH_ARCH):
        """
        Remove a cached package.
        If version is None, removes ALL cached versions for this package.
        """
        if version:
            path = self._cache_path(name, version, arch)
            if path.exists():
                path.unlink()
        else:
            # Remove all versions
            for f in self.cache_dir.glob(f"{name}-*.pkg.tar.zst"):
                f.unlink()

    # ── List ─────────────────────────────────────────────────

    def list_cached(self) -> list[dict]:
        """
        List all cached packages.
        Returns list of dicts: [{name, file, size_mb}, ...]
        """
        results = []
        for f in sorted(self.cache_dir.glob("*.pkg.tar.zst")):
            size_mb = f.stat().st_size / (1024 * 1024)
            results.append({
                "name": f.stem.rsplit("-", 2)[0] if f.stem.count("-") >= 2 else f.stem,
                "file": f.name,
                "size_mb": round(size_mb, 2),
            })
        return results

    def total_size(self) -> int:
        """Total cache size in bytes."""
        return sum(f.stat().st_size for f in self.cache_dir.glob("*.pkg.tar.zst"))

    def total_size_mb(self) -> float:
        """Total cache size in MB."""
        return round(self.total_size() / (1024 * 1024), 2)

    # ── Clean ────────────────────────────────────────────────

    def clean(self) -> int:
        """
        Remove ALL cached AUR packages.
        (Called by `sven clean --aur`)

        Returns:
            Number of files removed
        """
        count = 0
        for f in self.cache_dir.glob("*.pkg.tar.zst"):
            f.unlink()
            count += 1

        # Also clean .pkg.tar.xz if any
        for f in self.cache_dir.glob("*.pkg.tar.xz"):
            f.unlink()
            count += 1

        if count:
            print(f"   ✓ Removed {count} cached AUR package(s)")
        else:
            print("   ✓ AUR cache is already empty")

        return count

    # ── Check before build ───────────────────────────────────

    def check_before_build(self, name: str, version: str, arch: str = ARCH_ARCH) -> str | None:
        """
        Check the cache before triggering a build.
        If keep_cache is disabled in config, always returns None (forces rebuild).

        Returns:
            Cached path if available and cache enabled, else None
        """
        config = get_config()

        if not config.keep_cache:
            return None

        cached = self.get(name, version, arch)
        if cached:
            print(f"   ✓ Using cached build: {Path(cached).name}")
        return cached

# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  downloader/fetcher.py — parallel HTTPS package downloader
# ============================================================

import os
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from ..constants import (
    CACHE_PKGS,
    MIRROR_PKG_URL,
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_TIMEOUT,
    PARALLEL_DOWNLOADS,
    ARCH_ARCH,
)
from ..db.models import Package
from ..exceptions import DownloadError
from .mirror import MirrorManager


class Fetcher:
    """
    Downloads .pkg.tar.zst files over HTTPS from Arch mirrors.

    Features:
      - Parallel downloads (configurable)
      - Resume partial downloads via HTTP Range header
      - Per-file progress bar with real bytes
      - Cache-aware: skips already cached + valid files
      - Automatic mirror failover on failure
    """

    def __init__(
        self,
        mirror_manager: MirrorManager,
        cache_dir: str = CACHE_PKGS,
        parallel: int = PARALLEL_DOWNLOADS,
    ):
        self.mirror = mirror_manager
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.parallel = parallel
        
        # Performance tuning for unstable networks:
        # Use a pooled session with automatic low-level retries for connection blips
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=parallel,
            pool_maxsize=parallel,
            max_retries=3,  # Connection retries before giving up on a specific mirror
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ── Public API ───────────────────────────────────────────

    def download_packages(self, packages: list[Package]) -> dict[str, Path]:
        """
        Download a list of packages in parallel.
        Returns a dict of {pkg_name: local_file_path}.
        Skips already-cached files.
        """
        from ..ui.progress import MultiProgressDisplay
        from .checksum import verify_checksum

        results: dict[str, Path] = {}
        to_download: list[Package] = []

        # Check cache first
        for pkg in packages:
            cached = self._cached_path(pkg)
            if cached and cached.exists() and cached.stat().st_size > 0:
                # Even if cached, check if it's actually valid!
                try:
                    verify_checksum(cached, pkg.csum)
                    print(f"   {pkg.filename:<45s}  [cached/valid]")
                    results[pkg.name] = cached
                except Exception:
                    print(f"   {pkg.filename:<45s}  [cached/corrupt] -> re-downloading")
                    cached.unlink(missing_ok=True)
                    to_download.append(pkg)
            else:
                to_download.append(pkg)

        if not to_download:
            return results

        # Initialize multi-line display for the remaining downloads
        display = MultiProgressDisplay([pkg.filename for pkg in to_download])

        # Download with industrial-strength failover
        with ThreadPoolExecutor(max_workers=self.parallel) as pool:
            futures = {
                pool.submit(self._download_with_failover, pkg, display): pkg
                for pkg in to_download
            }
            for future in as_completed(futures):
                pkg = futures[future]
                try:
                    path = future.result()
                    results[pkg.name] = path
                    display.finish_single(pkg.filename)
                except Exception as e:
                    # After all retries exhausted, this package failed
                    raise DownloadError(
                        f"Target {pkg.filename} failed after all mirror failovers: {e}"
                    )
        
        display.finish_all()
        return results

    # ── Failover Logic ───────────────────────────────────────

    def _download_with_failover(self, pkg: Package, display: 'MultiProgressDisplay') -> Path:
        """
        Wraps single download with a retry loop that iterates through mirrors.
        This ensures that a 'Max Retries' error on one mirror doesn't kill the transaction.
        """
        from .checksum import verify_checksum
        
        MAX_MIRRORS_PER_PKG = 10
        last_error = None

        for attempt in range(MAX_MIRRORS_PER_PKG):
            mirror_url = self.mirror.current
            try:
                # attempt the actual download
                dest = self._download_single(pkg, display, mirror_url)
                
                # IMMEDIATE INTEGRITY CHECK
                # If we got trash, we failing over to next mirror now!
                try:
                    if pkg.csum:
                        verify_checksum(dest, pkg.csum)
                    return dest # SUCCESS!
                except Exception as e:
                    # Checksum mismatch!
                    dest.unlink(missing_ok=True)
                    print(f"\n   ⚠ Data Corruption: {mirror_url} sent bad content for {pkg.filename}.")
                    last_error = e
                    self.mirror.blacklist_current()
                    self.mirror.next_mirror()
                    continue

            except (requests.RequestException, DownloadError) as e:
                last_error = e
                # Connection failed, timeout, or server error
                try:
                    self.mirror.next_mirror()
                except Exception:
                    # No more mirrors
                    break
                continue
        
        raise DownloadError(str(last_error) or "All mirrors failed.")

    def _download_single(self, pkg: Package, display: 'MultiProgressDisplay', mirror_url: str) -> Path:
        """
        The low-level file download for a specific mirror.
        """
        dest = self.cache_dir / pkg.filename

        url = MIRROR_PKG_URL.format(
            mirror=mirror_url,
            repo=pkg.repo,
            arch=ARCH_ARCH,
            filename=pkg.filename,
        )

        # Resume support: check if file exists
        resume_pos = 0
        headers = {}
        
        if dest.exists():
            file_size = dest.stat().st_size
            if file_size >= pkg.size and pkg.size > 0:
                return dest
            
            # Partial file: Resume if supported
            resume_pos = file_size
            headers["Range"] = f"bytes={resume_pos}-"

        resp = self.session.get(
            url,
            headers=headers,
            stream=True,
            timeout=DOWNLOAD_TIMEOUT,
        )

        # If server doesn't support Range, start over
        if resp.status_code == 200 and resume_pos > 0:
            resume_pos = 0
        elif resp.status_code == 206:
            pass  # Partial content — resume
        elif resp.status_code >= 400:
            if resp.status_code == 416:
                # Range not satisfiable -> partial file is corrupt or server file changed
                dest.unlink(missing_ok=True)
                resp = self.session.get(url, headers={}, stream=True, timeout=15)
                resume_pos = 0
            resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0)) + resume_pos
        downloaded = resume_pos

        mode = "ab" if resume_pos > 0 and resp.status_code == 206 else "wb"

        with open(dest, mode) as f:
            for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                f.write(chunk)
                downloaded += len(chunk)

                # Update unified multi-line progress
                if total > 0:
                    display.update(pkg.filename, downloaded, total)

        # Final verification: did we get everything?
        if total > 0 and downloaded < total:
            raise requests.RequestException(f"Download truncated: got {downloaded}/{total} bytes")

        return dest


    # ── Helpers ──────────────────────────────────────────────

    def _cached_path(self, pkg: Package) -> Optional[Path]:
        """Return the expected cache path for a package file."""
        if not pkg.filename:
            return None
        return self.cache_dir / pkg.filename

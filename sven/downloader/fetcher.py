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

    # ── Public API ───────────────────────────────────────────

    def download_packages(self, packages: list[Package]) -> dict[str, Path]:
        """
        Download a list of packages in parallel.
        Returns a dict of {pkg_name: local_file_path}.
        Skips already-cached files.
        """
        from ..ui.progress import MultiProgressDisplay

        results: dict[str, Path] = {}
        to_download: list[Package] = []

        # Check cache first
        for pkg in packages:
            cached = self._cached_path(pkg)
            if cached and cached.exists() and cached.stat().st_size > 0:
                print(f"   {pkg.filename:<45s}  [cached]")
                results[pkg.name] = cached
            else:
                to_download.append(pkg)

        if not to_download:
            return results

        # Initialize multi-line display for the remaining downloads
        display = MultiProgressDisplay([pkg.filename for pkg in to_download])

        # Download in parallel
        with ThreadPoolExecutor(max_workers=self.parallel) as pool:
            futures = {
                pool.submit(self._download_single, pkg, display): pkg
                for pkg in to_download
            }
            for future in as_completed(futures):
                pkg = futures[future]
                try:
                    path = future.result()
                    results[pkg.name] = path
                    display.finish_single(pkg.filename)
                except Exception as e:
                    raise DownloadError(
                        f"Failed to download {pkg.filename}: {e}"
                    )
        
        display.finish_all()
        return results

    # ── Single File Download ─────────────────────────────────

    def _download_single(self, pkg: Package, display: 'MultiProgressDisplay', _retried: bool = False) -> Path:
        """
        Download a single package file with progress and resume support.
        Automatically fails over to the next mirror on failure.
        """
        dest = self.cache_dir / pkg.filename
        mirror_url = self.mirror.current

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
                # File is complete or oversized in cache
                # The transaction logic handles final checksum, but for sanity
                # we return it now to skip download.
                return dest
            
            # Partial file: Resume if supported
            resume_pos = file_size
            headers["Range"] = f"bytes={resume_pos}-"

        try:
            resp = requests.get(
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
                    resp = requests.get(url, headers={}, stream=True, timeout=15)
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

        except requests.RequestException as e:
            if not _retried:
                # Failover to next mirror
                try:
                    self.mirror.next_mirror()
                    return self._download_single(pkg, display, _retried=True)
                except Exception:
                    pass
            raise DownloadError(f"Download failed for {pkg.filename}: {e}")

    # ── Helpers ──────────────────────────────────────────────

    def _cached_path(self, pkg: Package) -> Optional[Path]:
        """Return the expected cache path for a package file."""
        if not pkg.filename:
            return None
        return self.cache_dir / pkg.filename

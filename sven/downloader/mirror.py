# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  downloader/mirror.py — mirror discovery, benchmarking, failover
# ============================================================

import json
import logging
import socket
import time
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from ..constants import (
    ARCH_MIRROR_STATUS_URL,
    DEFAULT_MIRROR,
    DB_BASE,
    CONFIG_DIR,
    MIRROR_BENCH_COUNT,
    DOWNLOAD_TIMEOUT,
)
from ..exceptions import MirrorError, MirrorTimeoutError


MIRROR_CACHE_FILE = f"{DB_BASE}/mirrors.json"
MIRRORLIST_FILE   = f"{CONFIG_DIR}/mirrorlist"

logger = logging.getLogger("sven")


def _url_resolves_to_loopback(url: str) -> bool:
    """
    True if the mirror hostname resolves only to loopback (e.g. /etc/hosts typo).
    Skips DNS failures — we do not drop mirrors we could not resolve here.
    """
    try:
        host = urlparse(url).hostname
    except Exception:
        return False
    if not host:
        return False
    h = host.lower()
    if h in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        ip = info[4][0]
        if ip not in ("127.0.0.1", "::1") and not ip.startswith("127."):
            return False
    return True


def _strip_loopback_mirrors(
    mirrors: list[dict],
    *,
    max_dns_check: int = 120,
) -> list[dict]:
    """
    Remove mirrors whose host resolves only to 127.0.0.1 / ::1.
    max_dns_check limits how many entries get a DNS lookup (full Arch list is huge).
    """
    if not mirrors:
        return mirrors
    head_n = min(max_dns_check, len(mirrors))
    head, tail = mirrors[:head_n], mirrors[head_n:]
    kept: list[dict] = []
    dropped = 0
    for m in head:
        u = m.get("url") or ""
        if _url_resolves_to_loopback(u):
            dropped += 1
            logger.warning("Dropping mirror (resolves to loopback): %s", u)
            continue
        kept.append(m)
    out = kept + tail
    if not out:
        return [
            {
                "url": DEFAULT_MIRROR,
                "country": "Default",
                "score": 0,
                "ping_ms": None,
            }
        ]
    if dropped and not tail:
        logger.info("Removed %d loopback mirror(s); using public mirrors.", dropped)
    return out


class MirrorManager:
    """
    Discovers, benchmarks, and manages Arch Linux mirrors.
    Provides automatic failover if a mirror fails mid-operation.
    """

    def __init__(self, cache_path: str = MIRROR_CACHE_FILE):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Ranked list — fastest first
        self._mirrors: list[dict] = []
        self._current_index: int = 0
        self._blacklist: set[str] = set()
        # Suppress mirror failover prints while parallel download UI owns the terminal
        self._parallel_dl_depth: int = 0

    @property
    def mirrors(self) -> list[dict]:
        """Expose the internal ranked mirror list."""
        if not self._mirrors:
            self._load_cached()
        if not self._mirrors:
            self._mirrors = self.fetch_mirror_list()
            self._save_cached(self._mirrors)
        return self._mirrors

    # ── Public API ───────────────────────────────────────────

    @property
    def current(self) -> str:
        """Return the URL of the currently selected mirror."""
        self.mirrors # trigger load
        if not self._mirrors:
            return DEFAULT_MIRROR
            
        # Ensure we're not on a blacklisted mirror
        while self._mirrors[self._current_index]["url"] in self._blacklist:
            self._current_index += 1
            if self._current_index >= len(self._mirrors):
                self._current_index = 0 # wrap around or fail
                break

        return self._mirrors[self._current_index]["url"]

    def begin_parallel_downloads(self) -> None:
        self._parallel_dl_depth += 1

    def end_parallel_downloads(self) -> None:
        self._parallel_dl_depth = max(0, self._parallel_dl_depth - 1)

    def _downloads_ui_active(self) -> bool:
        return self._parallel_dl_depth > 0

    def next_mirror(self) -> str:
        """
        Advance to the next mirror in the ranked list.
        Called automatically on download failure for failover.
        """
        self._current_index += 1
        if self._current_index >= len(self._mirrors):
            raise MirrorError("All mirrors exhausted. No more mirrors to try.")
            
        url = self._mirrors[self._current_index]["url"]
        if url in self._blacklist:
            return self.next_mirror() # recursive skip
            
        if not self._downloads_ui_active():
            print(f"   ⟳ Failing over to: {url}")
        return url

    def blacklist_current(self):
        """Mark the current mirror as unreliable for this session."""
        url = self.current
        if url not in self._blacklist:
            if not self._downloads_ui_active():
                print(f"   ⚠ Blacklisting unreliable mirror: {url}")
            self._blacklist.add(url)

    def reset(self):
        """Reset back to the fastest mirror (index 0)."""
        self._current_index = 0

    # ── Fetch Mirror List ────────────────────────────────────

    def fetch_mirror_list(self) -> list[dict]:
        """
        Fetch the official Arch Linux mirror list from the status API.
        Falls back to /etc/sven/mirrorlist if API is unreachable.
        Falls back to cached mirrors if mirrorlist doesn't exist.
        Returns a list of dicts: [{url, country, protocol, score}, ...]
        """
        print("   Fetching mirror list from archlinux.org...")
        try:
            resp = requests.get(ARCH_MIRROR_STATUS_URL, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"   ⚠ Mirror API unreachable: {e}")
            # Fallback 1: manual mirrorlist file
            manual = self._load_from_mirrorlist()
            if manual:
                print(f"   ↳ Using /etc/sven/mirrorlist ({len(manual)} mirrors)")
                return manual
            # Fallback 2: cached mirrors
            self._load_cached()
            if self._mirrors:
                print(f"   ↳ Using cached mirror list ({len(self._mirrors)} mirrors)")
                return self._mirrors
            # Fallback 3: default mirror
            print("   ↳ Using default mirror")
            return [{"url": DEFAULT_MIRROR, "country": "Default", "score": 0, "ping_ms": None}]

        mirrors = []
        for m in data.get("urls", []):
            # Only HTTPS mirrors, only active, only scored
            if (
                m.get("protocol") == "https"
                and m.get("active")
                and m.get("score") is not None
                and m.get("url")
            ):
                mirrors.append({
                    "url":      m["url"].rstrip("/"),
                    "country":  m.get("country", "Unknown"),
                    "score":    m.get("score", 999),
                    "ping_ms":  None,
                })

        # Sort by Arch's mirror score (lower is better)
        mirrors.sort(key=lambda m: m["score"])
        return mirrors

    # ── Manual Mirrorlist ────────────────────────────────────

    def _load_from_mirrorlist(self) -> list[dict]:
        """
        Load mirrors from /etc/sven/mirrorlist.
        Format: one URL per line, lines starting with # are comments.
        """
        path = Path(MIRRORLIST_FILE)
        if not path.exists():
            return []

        mirrors = []
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    mirrors.append({
                        "url":     line.rstrip("/"),
                        "country": "Manual",
                        "score":   0,
                        "ping_ms": None,
                    })
        except OSError:
            pass

        return _strip_loopback_mirrors(mirrors)

    # ── Benchmark ────────────────────────────────────────────

    def benchmark(self, count: int = MIRROR_BENCH_COUNT) -> list[dict]:
        """
        Benchmark mirrors by timing a HEAD request.
        Picks the fastest `count` mirrors, saves them, and returns the list.
        """
        all_mirrors = self.fetch_mirror_list()

        # Only benchmark the top candidates by score (limit to save time)
        candidates = all_mirrors[:max(count * 3, 15)]

        print(f"   Benchmarking {len(candidates)} mirrors...")
        results = []

        for m in candidates:
            url = m["url"]
            # HEAD request to a known small file
            test_url = f"{url}/core/os/x86_64/core.db"
            try:
                start = time.monotonic()
                resp = requests.head(test_url, timeout=5, allow_redirects=True)
                elapsed = (time.monotonic() - start) * 1000  # ms
                resp.raise_for_status()

                m["ping_ms"] = round(elapsed, 1)
                results.append(m)
                print(f"   {m['country']:>20s}  {url:<55s}  {elapsed:6.1f} ms")
            except requests.RequestException:
                print(f"   {m['country']:>20s}  {url:<55s}  TIMEOUT")
                continue

        # Sort by ping
        results.sort(key=lambda m: m["ping_ms"])

        # Take top N (re-check loopback in case list / DNS changed)
        best = _strip_loopback_mirrors(results[:count])
        self._mirrors = best
        self._current_index = 0

        # Save to cache
        self._save_cached(best)

        if best:
            print(f"\n   ★ Fastest mirror: {best[0]['url']} ({best[0]['ping_ms']} ms)")
        else:
            print("   ⚠ No mirrors responded. Using default.")
            self._mirrors = [{"url": DEFAULT_MIRROR, "country": "Default", "score": 0, "ping_ms": 0}]

        return best

    # ── List ─────────────────────────────────────────────────

    def list_mirrors(self) -> list[dict]:
        """
        Show currently saved mirrors with ping times.
        If no saved mirrors, fetch and display the top ones by score.
        """
        self._load_cached()
        if self._mirrors:
            return self._mirrors

        # No cached mirrors — show remote list
        all_mirrors = self.fetch_mirror_list()
        return all_mirrors[:20]

    # ── Cache ────────────────────────────────────────────────

    def _load_cached(self):
        """Load mirror list from local cache."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path) as f:
                    raw = json.load(f)
                if not isinstance(raw, list):
                    raw = []
                before = len(raw)
                self._mirrors = _strip_loopback_mirrors(raw)
                self._current_index = 0
                if before and len(self._mirrors) < before:
                    self._save_cached(self._mirrors)
            except (json.JSONDecodeError, OSError):
                self._mirrors = []

    def _save_cached(self, mirrors: list[dict]):
        """Save mirror list to local cache."""
        try:
            with open(self.cache_path, "w") as f:
                json.dump(mirrors, f, indent=2)
        except OSError:
            pass  # non-fatal

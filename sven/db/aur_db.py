# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  db/aur_db.py — AUR RPC API client + local cache
# ============================================================

import json
import time
import requests
from pathlib import Path
from typing import Optional

from .models import Package
from ..constants import (
    AUR_RPC_URL,
    AUR_CLONE_URL,
    AUR_CACHE_TTL,
    DB_AUR_CACHE,
)
from ..exceptions import AURError, AURPackageNotFoundError


# ── AUR API response → Package ────────────────────────────────

def _parse_aur_result(data: dict) -> Package:
    """
    Convert a single AUR RPC result dict into a Package object.

    Real AUR response fields (from reference):
    {
        "Name": "spotify",
        "Version": "1:1.2.84.476-1",
        "Description": "A proprietary music streaming service",
        "Depends": ["alsa-lib>=1.0.14", "gtk3", ...],
        "OptDepends": ["ffmpeg4.4", "zenity", ...],
        "NumVotes": 255,
        "Popularity": 10.30106,
        "Maintainer": "gromit",
        "URLPath": "/cgit/aur.git/snapshot/spotify.tar.gz",
        "URL": "https://www.spotify.com",
        "ID": 1996051,
        "OutOfDate": null,
        ...
    }
    """
    return Package(
        name             = data.get("Name", ""),
        version          = data.get("Version", ""),
        desc             = data.get("Description", ""),
        url              = data.get("URL", ""),
        repo             = "aur",
        origin           = "aur",
        deps             = _clean_deps(data.get("Depends", [])),
        makedeps         = _clean_deps(data.get("MakeDepends", [])),
        optdeps          = data.get("OptDepends", []),
        checkdeps        = _clean_deps(data.get("CheckDepends", [])),
        conflicts        = data.get("Conflicts", []),
        provides         = data.get("Provides", []),
        replaces         = data.get("Replaces", []),
        license          = data.get("License", []),
        aur_id           = data.get("ID"),
        aur_votes        = data.get("NumVotes", 0),
        aur_popularity   = data.get("Popularity", 0.0),
        aur_maintainer   = data.get("Maintainer", ""),
        aur_out_of_date  = data.get("OutOfDate"),
        aur_snapshot_url = data.get("URLPath", ""),
    )


def _clean_deps(deps: list[str]) -> list[str]:
    """
    Strip version constraints from dep names for internal use.
    e.g. "alsa-lib>=1.0.14" → "alsa-lib"
    We keep the raw string in the Package but also store clean names.
    Actually — we keep them raw so the resolver can handle constraints.
    This just strips obviously broken entries.
    """
    return [d.strip() for d in deps if d.strip()]


# ── AURDB class ───────────────────────────────────────────────

class AURDB:
    """
    Client for the AUR RPC v5 API.

    Caches responses locally so repeat searches are instant.
    Cache TTL default: 1 hour (AUR_CACHE_TTL in constants).
    """

    def __init__(
        self,
        cache_dir : str = DB_AUR_CACHE,
        ttl       : int = AUR_CACHE_TTL,
    ):
        self.cache_dir = Path(cache_dir)
        self.ttl       = ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────

    def info(self, name: str) -> Optional[Package]:
        """
        Get full info for an exact package name.
        Returns None if not found.
        """
        cached = self._load_cache(name)
        if cached is not None:
            return cached

        data = self._rpc("info", arg=name)

        if data["resultcount"] == 0:
            return None

        pkg = _parse_aur_result(data["results"][0])
        self._save_cache(name, data["results"][0])
        return pkg

    def info_multi(self, names: list[str]) -> list[Package]:
        """
        Batch lookup multiple packages in one API call.
        More efficient than calling info() in a loop.
        """
        # Check cache first — only fetch what's missing
        results  = []
        to_fetch = []

        for name in names:
            cached = self._load_cache(name)
            if cached:
                results.append(cached)
            else:
                to_fetch.append(name)

        if not to_fetch:
            return results

        data = self._rpc("info", arg=to_fetch)

        for item in data.get("results", []):
            pkg = _parse_aur_result(item)
            results.append(pkg)
            self._save_cache(item["Name"], item)

        return results

    def search(self, query: str, by: str = "name-desc") -> list[Package]:
        """
        Search AUR by name/description.
        by: name | name-desc | maintainer | depends | makedepends
        Returns list sorted by popularity descending.
        """
        data = self._rpc("search", arg=query, by=by)

        packages = [
            _parse_aur_result(r)
            for r in data.get("results", [])
        ]

        # Sort by popularity descending
        packages.sort(key=lambda p: p.aur_popularity, reverse=True)
        return packages

    def exists(self, name: str) -> bool:
        """Quick check if a package exists on AUR."""
        return self.info(name) is not None

    def clone_url(self, name: str) -> str:
        """Return the git clone URL for a package's PKGBUILD."""
        return AUR_CLONE_URL.format(pkg=name)

    # ── RPC ───────────────────────────────────────────────────

    def _rpc(self, rpc_type: str, arg, by: str = None) -> dict:
        """
        Make a raw RPC call to the AUR API.

        Endpoints:
          info:   /rpc/v5/info?arg[]=pkg1&arg[]=pkg2
          search: /rpc/v5/search/query?by=name-desc
        """
        try:
            if rpc_type == "info":
                # arg can be str or list
                if isinstance(arg, list):
                    params = [("arg[]", a) for a in arg]
                else:
                    params = {"arg": arg}
                url  = f"{AUR_RPC_URL}/info"
                resp = requests.get(url, params=params, timeout=10)
            elif rpc_type == "search":
                url  = f"{AUR_RPC_URL}/search/{requests.utils.quote(arg)}"
                params = {}
                if by:
                    params["by"] = by
                resp = requests.get(url, params=params, timeout=10)
            else:
                raise AURError(f"Unknown RPC type: {rpc_type}")

            resp.raise_for_status()
            data = resp.json()

            if data.get("type") == "error":
                raise AURError(f"AUR API error: {data.get('error')}")

            return data

        except requests.exceptions.ConnectionError:
            raise AURError("Cannot reach AUR. Check your internet connection.")
        except requests.exceptions.Timeout:
            raise AURError("AUR API timed out.")
        except requests.exceptions.HTTPError as e:
            raise AURError(f"AUR API HTTP error: {e}")

    # ── Cache ─────────────────────────────────────────────────

    def _cache_path(self, name: str) -> Path:
        safe = name.replace("/", "_")
        return self.cache_dir / f"{safe}.json"

    def _load_cache(self, name: str) -> Optional[Package]:
        """Load cached AUR result if it exists and isn't expired."""
        path = self._cache_path(name)
        if not path.exists():
            return None

        age = time.time() - path.stat().st_mtime
        if age > self.ttl:
            return None  # expired

        try:
            with open(path) as f:
                data = json.load(f)
            return _parse_aur_result(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_cache(self, name: str, data: dict):
        """Save raw AUR result dict to cache."""
        path = self._cache_path(name)
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except OSError:
            pass  # cache write failure is non-fatal

    def clear_cache(self):
        """Delete all cached AUR responses."""
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)

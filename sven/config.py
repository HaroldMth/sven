# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  config.py — reads and validates /etc/sven/sven.conf
# ============================================================

import configparser
import os
from pathlib import Path

from .constants import (
    CONFIG_FILE, DEFAULT_ROOT,
    CACHE_BASE, DB_BASE, LOG_MAIN,
    INIT_SYSVINIT, SUPPORTED_INIT,
    PARALLEL_DOWNLOADS,
)
from .exceptions import ConfigNotFoundError, InvalidConfigError


# ── Defaults ─────────────────────────────────────────────────

DEFAULTS = {
    "general": {
        "install_root"      : DEFAULT_ROOT,
        "cache_dir"         : CACHE_BASE,
        "db_path"           : DB_BASE,
        "log_file"          : LOG_MAIN,
        "init_system"       : INIT_SYSVINIT,
    },
    "repos": {
        "use_official"      : "true",
        "use_aur"           : "true",
        "aur_review"        : "prompt",    # always | prompt | never
    },
    "build": {
        "build_dir"         : "/tmp/sven/aur",
        "keep_cache"        : "true",
        "parallel_jobs"     : "4",
    },
    "download": {
        "parallel_downloads": str(PARALLEL_DOWNLOADS),
        "mirror"            : "auto",
    },
    "upgrade": {
        "ignored_packages"  : "",
        "held_packages"     : "",
    },
}


# ── Config class ─────────────────────────────────────────────

class Config:
    """
    Reads /etc/sven/sven.conf and exposes typed config values.
    Falls back to DEFAULTS for any missing key.
    Can be overridden at runtime (e.g. --root flag).
    """

    def __init__(self, config_path: str = CONFIG_FILE):
        self._path   = config_path
        self._parser = configparser.ConfigParser()
        self._load()

    # ── Load ─────────────────────────────────────────────────

    def _load(self):
        # Apply defaults first
        for section, values in DEFAULTS.items():
            self._parser[section] = values

        # Read actual config if it exists
        if Path(self._path).exists():
            self._parser.read(self._path)
        # No config file is fine — defaults are used

        self._validate()

    # ── Validate ─────────────────────────────────────────────

    def _validate(self):
        init = self.init_system
        if init not in SUPPORTED_INIT:
            raise InvalidConfigError("init_system", init)

        aur_review = self.aur_review
        if aur_review not in ("always", "prompt", "never"):
            raise InvalidConfigError("aur_review", aur_review)

    # ── General ──────────────────────────────────────────────

    @property
    def install_root(self) -> str:
        return self._parser.get("general", "install_root")

    @install_root.setter
    def install_root(self, value: str):
        self._parser["general"]["install_root"] = value

    @property
    def cache_dir(self) -> str:
        return self._parser.get("general", "cache_dir")

    @property
    def db_path(self) -> str:
        return self._parser.get("general", "db_path")

    @property
    def log_file(self) -> str:
        return self._parser.get("general", "log_file")

    @property
    def init_system(self) -> str:
        return self._parser.get("general", "init_system").lower()

    # ── Repos ────────────────────────────────────────────────

    @property
    def use_official(self) -> bool:
        return self._parser.getboolean("repos", "use_official")

    @property
    def use_aur(self) -> bool:
        return self._parser.getboolean("repos", "use_aur")

    @property
    def aur_review(self) -> str:
        return self._parser.get("repos", "aur_review").lower()

    # ── Build ────────────────────────────────────────────────

    @property
    def build_dir(self) -> str:
        return self._parser.get("build", "build_dir")

    @property
    def keep_cache(self) -> bool:
        return self._parser.getboolean("build", "keep_cache")

    @property
    def parallel_jobs(self) -> int:
        return self._parser.getint("build", "parallel_jobs")

    # ── Download ─────────────────────────────────────────────

    @property
    def parallel_downloads(self) -> int:
        return self._parser.getint("download", "parallel_downloads")

    @property
    def mirror(self) -> str:
        return self._parser.get("download", "mirror")

    # ── Upgrade ──────────────────────────────────────────────

    @property
    def ignored_packages(self) -> list[str]:
        raw = self._parser.get("upgrade", "ignored_packages")
        return [p.strip() for p in raw.split() if p.strip()]

    @property
    def held_packages(self) -> list[str]:
        raw = self._parser.get("upgrade", "held_packages")
        return [p.strip() for p in raw.split() if p.strip()]

    # ── Derived paths (respect install_root) ─────────────────

    def rooted(self, path: str) -> str:
        """Prepend install_root to a path."""
        root = self.install_root.rstrip("/")
        return f"{root}{path}" if root != "/" else path

    # ── Debug ────────────────────────────────────────────────

    def __repr__(self):
        return (
            f"<Config init={self.init_system} "
            f"root={self.install_root} "
            f"aur={self.use_aur}>"
        )


# ── Singleton ────────────────────────────────────────────────

_config: Config | None = None

def get_config(path: str = CONFIG_FILE) -> Config:
    global _config
    if _config is None:
        _config = Config(path)
    return _config

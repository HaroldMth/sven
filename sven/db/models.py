# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  db/models.py — shared Package dataclass
# ============================================================

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Package:
    """
    Universal package object.
    Returned by sync_db, aur_db, and local_db alike.
    The resolver + installer never care where it came from.
    """

    # ── Identity ─────────────────────────────────────────────
    name        : str
    version     : str
    desc        : str                   = ""
    url         : str                   = ""

    # ── Source ───────────────────────────────────────────────
    repo        : str                   = "extra"   # core/extra/multilib/aur
    origin      : str                   = "official" # official | aur | local

    # ── Dependencies ─────────────────────────────────────────
    deps        : list[str]             = field(default_factory=list)
    makedeps    : list[str]             = field(default_factory=list)
    optdeps     : list[str]             = field(default_factory=list)
    checkdeps   : list[str]             = field(default_factory=list)

    # ── Relations ────────────────────────────────────────────
    conflicts   : list[str]             = field(default_factory=list)
    provides    : list[str]             = field(default_factory=list)
    replaces    : list[str]             = field(default_factory=list)

    # ── Size ─────────────────────────────────────────────────
    size        : int                   = 0          # bytes compressed
    isize       : int                   = 0          # bytes installed

    # ── Meta ─────────────────────────────────────────────────
    arch        : str                   = "x86_64"
    license     : list[str]             = field(default_factory=list)
    packager    : str                   = ""
    builddate   : int                   = 0
    filename    : str                   = ""         # e.g. firefox-125.0-1-x86_64.pkg.tar.zst

    # ── AUR specific ─────────────────────────────────────────
    aur_id          : Optional[int]     = None
    aur_votes       : int               = 0
    aur_popularity  : float             = 0.0
    aur_maintainer  : str               = ""
    aur_out_of_date : Optional[int]     = None
    aur_snapshot_url: str               = ""

    # ── Install state ─────────────────────────────────────────
    explicit        : bool              = True       # manually installed
    install_date    : Optional[int]     = None       # unix timestamp

    # ── Helpers ──────────────────────────────────────────────

    @property
    def is_aur(self) -> bool:
        return self.origin == "aur"

    @property
    def is_installed(self) -> bool:
        return self.install_date is not None

    @property
    def full_name(self) -> str:
        return f"{self.name}-{self.version}"

    def __str__(self):
        tag = "[AUR]" if self.is_aur else f"[{self.repo}]"
        return f"{self.name} {self.version} {tag}"

    def __repr__(self):
        return f"<Package {self.name} {self.version} origin={self.origin}>"

    def __eq__(self, other):
        if not isinstance(other, Package):
            return False
        return self.name == other.name and self.version == other.version

    def __hash__(self):
        return hash((self.name, self.version))

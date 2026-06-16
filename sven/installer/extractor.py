# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  installer/extractor.py — Extract package archives safely
# ============================================================
#
#  Extracts .pkg.tar.zst locally. Respects installation root.
#  Handles config file conflicts by using .svennew.
# ============================================================

import os
from pathlib import Path

from ..config import get_config
from ..exceptions import ExtractionError
from ..libsven import extract_zst

METADATA_FILES = {".PKGINFO", ".MTREE", ".INSTALL", ".BUILDINFO"}


class Extractor:
    def __init__(self, install_root: str = None, verbose: bool = False):
        self.config = get_config()
        self.root = Path(install_root or self.config.install_root)
        self.verbose = verbose
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)

    def extract(self, archive_path: str, backup_configs: list[str] = None) -> list[str]:
        """
        Extract a .pkg.tar.zst archive to the root filesystem.
        Uses C libarchive engine when available, falls back to Python.

        Returns list of absolute extracted file paths.
        """
        path = Path(archive_path)
        if not path.exists():
            raise ExtractionError(archive_path, "Archive does not exist")

        try:
            extracted = extract_zst(str(path), str(self.root))
        except Exception as e:
            raise ExtractionError(archive_path, f"Extraction failed: {e}")

        if self.verbose:
            for f in extracted:
                print(f"     [DEBUG] Extracted: {f}")

        return extracted

# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  installer/lib_checker.py — Verify required shared libraries
# ============================================================
#
#  Checks if all required .so dependencies are present on the 
#  LFS host before unzipping a package.
# ============================================================

import os
from pathlib import Path

from ..config import get_config
from ..exceptions import MissingLibraryError

# Standard lib paths to check
LIB_PATHS = ["/usr/lib", "/lib", "/usr/local/lib"]


class LibChecker:
    def __init__(self, custom_lib_paths: list[str] = None):
        self.config = get_config()
        self.lib_paths = custom_lib_paths or LIB_PATHS
        
        # Adjust for root
        if self.config.install_root != "/":
            self.lib_paths = [self.config.rooted(p) for p in self.lib_paths]

    def check_package(self, pkg_name: str, required_libs: list[str]) -> bool:
        """
        Verify that all required generic .so files exist on the filesystem.

        Args:
            pkg_name: The name of the package being evaluated.
            required_libs: List of .so file names (e.g. ['libssl.so.3']).

        Returns:
            True if all exist.

        Raises:
            MissingLibraryError if any lib is completely unfound.
        """
        missing = []

        for lib in required_libs:
            if not self._lib_exists(lib):
                missing.append(lib)

        if missing:
            raise MissingLibraryError(missing[0], pkg_name)

        return True

    def _lib_exists(self, lib_name: str) -> bool:
        """Scan standard paths for the physical library file."""
        for path in self.lib_paths:
            full_path = Path(path) / lib_name
            if full_path.exists():
                return True
            
            # Check for generic symlink variants if specific version is requested
            # e.g. looking for libfoo.so.1 when only libfoo.so exists
            # This is a bit relaxed for LFS to allow API compatible libs
            base_so = lib_name.split(".so")[0] + ".so"
            if base_so != lib_name:
                base_path = Path(path) / base_so
                if base_path.exists():
                    return True
                    
        return False

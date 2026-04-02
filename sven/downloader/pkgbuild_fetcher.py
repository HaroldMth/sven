# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  downloader/pkgbuild_fetcher.py — git clone PKGBUILDs
# ============================================================

import subprocess
from pathlib import Path
from typing import Optional

from ..constants import (
    AUR_CLONE_URL,
    ARCH_GITLAB_URL,
    TMP_AUR,
)
from ..exceptions import AURError, BuildError


class PKGBUILDFetcher:
    """
    Clones PKGBUILDs from AUR and Arch GitLab.

    AUR:       https://aur.archlinux.org/{pkg}.git
    Official:  https://gitlab.archlinux.org/archlinux/packaging/packages/{pkg}

    Saves to:  /tmp/sven/aur/{pkg}/
    Handles:   git clone + git pull (update if already cloned)
    """

    def __init__(self, build_dir: str = TMP_AUR):
        self.build_dir = Path(build_dir)
        self.build_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ───────────────────────────────────────────

    def fetch_aur(self, pkg_name: str) -> Path:
        """
        Clone or update an AUR package's PKGBUILD.
        Returns the path to the cloned directory.
        """
        url = AUR_CLONE_URL.format(pkg=pkg_name)
        dest = self.build_dir / pkg_name
        return self._clone_or_pull(url, dest, pkg_name)

    def fetch_official(self, pkg_name: str) -> Path:
        """
        Clone or update an official package's PKGBUILD from Arch GitLab.
        Used for source builds of official packages.
        Returns the path to the cloned directory.
        """
        url = f"{ARCH_GITLAB_URL}/{pkg_name}.git"
        dest = self.build_dir / pkg_name
        return self._clone_or_pull(url, dest, pkg_name)

    # ── Internal ─────────────────────────────────────────────

    def _clone_or_pull(self, url: str, dest: Path, pkg_name: str) -> Path:
        """
        If dest exists and has a .git directory, run git pull.
        Otherwise, do a fresh git clone.
        """
        git_dir = dest / ".git"

        if git_dir.is_dir():
            # Already cloned — update
            return self._git_pull(dest, pkg_name)
        else:
            # Fresh clone
            return self._git_clone(url, dest, pkg_name)

    def _git_clone(self, url: str, dest: Path, pkg_name: str) -> Path:
        """Clone a git repository."""
        print(f"   Cloning {pkg_name}...")

        # Remove dest if it exists but isn't a git repo
        if dest.exists():
            import shutil
            shutil.rmtree(dest)

        try:
            result = subprocess.run(
                ["git", "clone", "--depth=1", url, str(dest)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise BuildError(
                    pkg_name,
                    f"git clone failed:\n{result.stderr.strip()}"
                )
        except FileNotFoundError:
            raise BuildError(pkg_name, "git is not installed")
        except subprocess.TimeoutExpired:
            raise BuildError(pkg_name, "git clone timed out (120s)")

        # Verify PKGBUILD exists
        pkgbuild = dest / "PKGBUILD"
        if not pkgbuild.exists():
            # Some Arch GitLab repos use a subdirectory structure
            # Check common paths
            for sub in dest.iterdir():
                if sub.is_dir() and (sub / "PKGBUILD").exists():
                    print(f"   ✓ PKGBUILD found in {sub.name}/")
                    return dest

            print(f"   ⚠ No PKGBUILD found in cloned directory")
        else:
            print(f"   ✓ PKGBUILD ready: {dest}")

        return dest

    def _git_pull(self, dest: Path, pkg_name: str) -> Path:
        """Update an existing clone."""
        print(f"   Updating {pkg_name}...")
        try:
            result = subprocess.run(
                ["git", "-C", str(dest), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                # Pull failed — try a fresh clone
                print(f"   ⚠ Pull failed, re-cloning...")
                import shutil
                shutil.rmtree(dest, ignore_errors=True)
                # Can't re-clone here without URL, so raise
                raise BuildError(
                    pkg_name,
                    f"git pull failed:\n{result.stderr.strip()}"
                )
        except FileNotFoundError:
            raise BuildError(pkg_name, "git is not installed")
        except subprocess.TimeoutExpired:
            raise BuildError(pkg_name, "git pull timed out (60s)")

        print(f"   ✓ {pkg_name} updated")
        return dest

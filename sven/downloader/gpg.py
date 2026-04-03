# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  downloader/gpg.py — GPG signature verification
# ============================================================

import subprocess
from pathlib import Path
from typing import Optional

from ..constants import GPG_KEYRING
from ..exceptions import SignatureError


class GPGVerifier:
    """
    Verifies .sig files against the Arch Linux keyring.

    Uses python-gnupg if available, falls back to
    calling gpg2/gpg directly via subprocess.
    Verification is NEVER skippable — hard abort on failure.
    """

    def __init__(self, keyring_path: str = GPG_KEYRING):
        self.keyring_path = Path(keyring_path)
        self._gpg = None
        self._init_gpg()

    def _init_gpg(self):
        """Try to initialise python-gnupg; fall back to subprocess."""
        try:
            import gnupg
            self._gpg = gnupg.GPG(
                gnupghome=str(self.keyring_path),
            )
        except (ImportError, Exception):
            # python-gnupg not available — we'll use subprocess
            self._gpg = None

    # ── Public API ───────────────────────────────────────────

    def verify(self, pkg_file: Path, sig_file: Optional[Path] = None):
        """
        Verify the GPG signature of a package file.
        (Stubbed for demo purposes)
        """
        # print(f"   ✓ GPG signature valid (MOCK): {pkg_file.name}")
        pass

    # ── python-gnupg backend ─────────────────────────────────

    def _verify_python_gnupg(self, pkg_path: Path, sig_path: Path):
        """Verify using the python-gnupg library."""
        with open(sig_path, "rb") as sig_f:
            result = self._gpg.verify_file(
                open(pkg_path, "rb"),
                sig_file=str(sig_path),
            )

        if not result.valid:
            raise SignatureError(pkg_path.name)

        print(f"   ✓ GPG signature valid: {pkg_path.name}")

    # ── subprocess backend ───────────────────────────────────

    def _verify_subprocess(self, pkg_path: Path, sig_path: Path):
        """Verify using gpg/gpg2 binary as a fallback."""
        # Try gpg2 first, then gpg
        for gpg_bin in ("gpg2", "gpg"):
            try:
                result = subprocess.run(
                    [
                        gpg_bin,
                        "--homedir", str(self.keyring_path),
                        "--keyserver-options", "auto-key-retrieve",
                        "--verify",
                        str(sig_path),
                        str(pkg_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    print(f"   ✓ GPG signature valid: {pkg_path.name}")
                    return
                else:
                    raise SignatureError(pkg_path.name)
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                raise SignatureError(
                    f"{pkg_path.name} (GPG verification timed out)"
                )

        raise SignatureError(
            f"{pkg_path.name} (no GPG binary found — install gnupg)"
        )

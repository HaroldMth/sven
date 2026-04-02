# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  downloader/checksum.py — SHA256 verification
# ============================================================

import hashlib
from pathlib import Path

from ..exceptions import ChecksumMismatchError


def verify_checksum(filepath: str | Path, expected_sha256: str) -> bool:
    """
    Verify the SHA256 checksum of a downloaded file.

    The expected hash comes from the sync DB (%SHA256SUM% field).
    Must be called AFTER GPG verification.

    Raises ChecksumMismatchError if the hash does not match.
    Returns True on success.
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise ChecksumMismatchError(filepath.name)

    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha.update(chunk)

    computed = sha.hexdigest()

    if computed.lower() != expected_sha256.lower():
        raise ChecksumMismatchError(filepath.name)

    print(f"   ✓ SHA256 verified: {filepath.name}")
    return True

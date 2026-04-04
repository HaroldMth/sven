# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  downloader/checksum.py — Native SHA256 verification
# ============================================================

import subprocess
from pathlib import Path
from ..exceptions import ChecksumMismatchError


def verify_checksum(
    filepath: str | Path,
    expected_sha256: str,
    *,
    quiet_success: bool = False,
):
    """
    Verify the SHA256 checksum of a file using the system's sha256sum utility.
    This is more robust on LFS systems than a custom Python implementation.

    Args:
        filepath: Path to the file to check
        expected_sha256: Expected hex digest
        quiet_success: If True, do not print the success line (for parallel UI)

    Raises:
        ChecksumMismatchError if sums don't match or file missing
    """
    p = Path(filepath)
    if not p.exists():
        if expected_sha256:
            raise ChecksumMismatchError(p.name, expected_sha256, "(file not found)")
        raise FileNotFoundError(f"File not found for checksum: {p}")

    # Don't verify if no checksum provided
    if not expected_sha256:
        return True

    try:
        # Run native sha256sum utility
        output = subprocess.check_output(["sha256sum", str(p)], stderr=subprocess.STDOUT).decode()
        # Output format: "hash  filename"
        actual = output.split()[0].strip()
    except Exception as e:
        print(f"   ⚠ Error running sha256sum: {e}")
        # Fallback to a basic check or fail
        raise

    if actual != expected_sha256:
        print(f"   ⚠ Checksum mismatch for {p.name}")
        print(f"     Expected: {expected_sha256}")
        print(f"     Actual:   {actual}")
        
        # Diagnostic: peek at the file content
        try:
            with p.open("rb") as f:
                head = f.read(128)
                if b"<!DOCTYPE html" in head or b"<html" in head.lower():
                    print("   🔍 HINT: This looks like an HTML error page, not a package!")
                elif b"ustar" in head:
                    print("   🔍 HINT: This is a valid TAR archive, just wrong content.")
                elif head.startswith(b"\x28\xb5\x2f\xfd"):
                    print("   🔍 HINT: This is a valid Zstd archive, possibly truncated.")
                else:
                    print(f"   🔍 HINT: Data starts with: {head[:20].hex()}")
        except:
            pass
            
        raise ChecksumMismatchError(p.name, expected_sha256, actual)

    if not quiet_success:
        print(f"   ✓ SHA256 verified: {p.name}")
    return True

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
import tarfile
from pathlib import Path

try:
    import zstandard as zstd
except ImportError:
    zstd = None

from ..config import get_config
from ..exceptions import ExtractionError

# Files to skip expanding onto the filesystem
METADATA_FILES = {".PKGINFO", ".MTREE", ".INSTALL", ".BUILDINFO"}


class Extractor:
    def __init__(self, install_root: str = None):
        self.config = get_config()
        self.root = Path(install_root or self.config.install_root)
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)

    def extract(self, archive_path: str, backup_configs: list[str] = None) -> list[str]:
        """
        Extract a .pkg.tar.zst archive to the root filesystem.

        Handles .pacnew (mapped to .svennew) dynamically if backup_configs 
        are provided and the file is locally modified.
        
        Args:
            archive_path: Path to the zst-compressed tarball.
            backup_configs: List of relative paths (from PKGINFO backup arr)
            
        Returns:
            List of absolutely extracted file paths.
            
        Raises:
            ExtractionError on corrupt archive.
        """
        path = Path(archive_path)
        if not path.exists():
            raise ExtractionError(archive_path, "Archive does not exist")

        if zstd is None:
            raise ExtractionError(archive_path, "zstandard Python module is required for extraction")

        extracted_files = []
        backup_configs = backup_configs or []
        backup_configs_set = set(backup_configs)

        try:
            with open(path, "rb") as f_in:
                dctx = zstd.ZstdDecompressor()
                with dctx.stream_reader(f_in) as z_stream:
                    with tarfile.open(fileobj=z_stream, mode="r|") as tar:
                        for member in tar:
                            # Skip metadata
                            if member.name in METADATA_FILES:
                                continue

                            dest = self.root / member.name
                            dest_str = str(dest)

                            # Handle config backups (.svennew)
                            # Arch calls them .pacnew, we use .svennew
                            if member.name in backup_configs_set and dest.exists():
                                # We simplify "is modified" by just checking if it exists
                                # A true implementation would hash check against LocalDB
                                print(f"   ⚠ Config conflict: {member.name}")
                                print(f"     Installing as {member.name}.svennew")
                                dest = Path(f"{dest_str}.svennew")
                                dest_str = str(dest)

                            # Create directories
                            if member.isdir():
                                dest.mkdir(parents=True, exist_ok=True)
                                continue

                            # Ensure parent dir exists
                            dest.parent.mkdir(parents=True, exist_ok=True)

                            # Extract file
                            if member.isreg():
                                with tar.extractfile(member) as source, open(dest, "wb") as target:
                                    target.write(source.read())
                                
                                # Preserve permissions
                                os.chmod(dest, member.mode)
                                extracted_files.append(dest_str)
                            
                            elif member.issym():
                                if dest.exists() or dest.is_symlink():
                                    dest.unlink()
                                dest.symlink_to(member.linkname)
                                extracted_files.append(dest_str)

        except (zstd.ZstdError, tarfile.TarError) as e:
            raise ExtractionError(archive_path, f"Decompression failed: {e}")
        except OSError as e:
            raise ExtractionError(archive_path, f"OS error during extraction: {e}")

        return extracted_files

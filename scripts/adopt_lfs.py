# ============================================================
#  Sven — Seven OS Adoption Script
#  HANS TECH © 2024 — GPL v3
#  scripts/adopt_lfs.py — registers LFS base into LocalDB
# ============================================================
import argparse
import os
import sys

# Add project to path
sys.path.append(os.getcwd())

from sven.config import get_config
from sven.db.local_db import LocalDB
from sven.db.models import Package


def adopt(dry_run: bool = False):
    config = get_config()
    db = LocalDB()
    
    # We want to adopt the protected list
    protected = config.protected_packages
    
    print(f"   :: Adopting {len(protected)} core LFS packages...")
    
    adopted = 0
    skipped = 0
    for pkg_name in protected:
        if db.has(pkg_name):
            print(f"      = Skipping {pkg_name} (already registered)")
            skipped += 1
            continue

        print(f"      + Adopting {pkg_name} as LFS-BASE...")

        
        provides = []
        if pkg_name == "bash":
            provides = ["sh"]
        elif pkg_name == "pkgconf":
            provides = ["pkg-config"]
        elif pkg_name == "gawk":
            provides = ["awk"]
        elif pkg_name == "util-linux":
            provides = ["libuuid.so", "libblkid.so", "libmount.so", "uuid"]
        elif pkg_name == "zlib":
            provides = ["libz.so"]
        elif pkg_name == "openssl":
            provides = ["libssl.so", "libcrypto.so"]
        elif pkg_name == "curl":
            provides = ["libcurl.so"]
            
        if not dry_run:
            db.register(
                Package(
                    name=pkg_name,
                    version="LFS-BASE",
                    desc="Core LFS system package (managed by original build)",
                    url="https://www.linuxfromscratch.org",
                    provides=provides,
                    origin="explicit"
                ),
                files=[],
                explicit=True
            )
        adopted += 1

    print(f"\n   ✓ Adoption complete. Added: {adopted}, skipped: {skipped}.")
    if dry_run:
        print("   ✓ Dry-run mode: LocalDB was not modified.")

def main():
    parser = argparse.ArgumentParser(description="Adopt core LFS packages into Sven LocalDB")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be adopted")
    args = parser.parse_args()
    adopt(dry_run=args.dry_run)

if __name__ == "__main__":
    main()

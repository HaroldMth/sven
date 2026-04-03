# ============================================================
#  Sven — Seven OS Adoption Script
#  HANS TECH © 2024 — GPL v3
#  scripts/adopt_lfs.py — registers LFS base into LocalDB
# ============================================================
import sys
import os
from pathlib import Path

# Add project to path
sys.path.append(os.getcwd())

from sven.config import get_config
from sven.db.local_db import LocalDB
from sven.db.models import Package


def adopt():
    config = get_config()
    db = LocalDB()
    
    # We want to adopt the protected list
    protected = config.protected_packages
    
    print(f"   :: Adopting {len(protected)} core LFS packages...")
    
    for pkg_name in protected:
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


    print("\n   ✓ Adoption complete. Sven now recognizes the base system.")

if __name__ == "__main__":
    adopt()

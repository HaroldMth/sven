# ============================================================
#  Sven — Seven OS Adoption Script
#  HANS TECH © 2024 — GPL v3
#  scripts/adopt_lfs.py — registers LFS base into LocalDB
#
#  For each protected package this script:
#    1. Verifies it's actually present on this system (no phantom
#       registrations for things that were never built)
#    2. Detects its REAL version via sven.version_probe — never a
#       fake placeholder string
#    3. Discovers the real on-disk files it owns (binaries + libs)
#       so the file-conflict resolver can actually do its job
# ============================================================
import argparse
import glob
import os
import shutil
import sys

# Add project to path
sys.path.append(os.getcwd())

from sven.config import get_config
from sven.db.local_db import LocalDB
from sven.db.models import Package
from sven.version_probe import detect_version, is_present, _REPRESENTATIVE_BINARY


# ── Known multi-binary packages ──────────────────────────────
# Packages that ship many tools under one source package. Listing
# the well-known ones gives the file-conflict resolver real ownership
# data instead of nothing. Not exhaustive — best-effort, verified
# against disk before being claimed.

_KNOWN_BINARIES: dict[str, list[str]] = {
    "coreutils": [
        "ls", "cat", "cp", "mv", "rm", "mkdir", "rmdir", "touch", "chmod",
        "chown", "chgrp", "ln", "df", "du", "echo", "printf", "sort",
        "uniq", "cut", "tr", "wc", "head", "tail", "basename", "dirname",
        "pwd", "sleep", "true", "false", "yes", "date", "env", "expr",
        "install", "mktemp", "nice", "nohup", "od", "readlink", "realpath",
        "seq", "shred", "shuf", "split", "stat", "sync", "tac", "tee",
        "timeout", "tty", "uname", "unlink", "who", "whoami", "id",
        "groups", "logname", "nproc", "numfmt", "base64", "md5sum",
        "sha1sum", "sha256sum", "sha512sum", "comm", "fmt", "fold",
        "join", "nl", "dd", "dir", "vdir",
    ],
    "util-linux": [
        "mount", "umount", "fdisk", "sfdisk", "blkid", "lsblk", "losetup",
        "swapon", "swapoff", "mkswap", "fsck", "dmesg", "hwclock", "kill",
        "lscpu", "findmnt", "flock", "nsenter", "unshare", "uuidgen",
        "wipefs", "column", "script", "rev", "look", "logger", "agetty",
        "setterm", "rename", "renice",
    ],
    "procps-ng": [
        "ps", "top", "free", "pkill", "pgrep", "pmap", "pwdx", "slabtop",
        "sysctl", "tload", "uptime", "vmstat", "w", "watch",
    ],
    "findutils": ["find", "xargs", "locate", "updatedb"],
    "e2fsprogs": [
        "mke2fs", "mkfs.ext2", "mkfs.ext3", "mkfs.ext4", "e2fsck",
        "fsck.ext2", "fsck.ext3", "fsck.ext4", "tune2fs", "dumpe2fs",
        "resize2fs", "debugfs", "badblocks", "e2label", "filefrag",
        "lsattr", "chattr",
    ],
    "shadow": [
        "passwd", "login", "useradd", "userdel", "usermod", "groupadd",
        "groupdel", "groupmod", "chage", "chfn", "chsh", "gpasswd",
        "newgrp", "newusers", "pwck", "grpck", "vipw", "vigr", "faillog",
        "lastlog", "nologin",
    ],
    "binutils": [
        "ld", "as", "ar", "nm", "objdump", "objcopy", "ranlib", "strip",
        "readelf", "addr2line", "size", "strings", "c++filt", "gprof",
    ],
}

# Library name hints per package, used to discover real .so paths on
# disk via glob. This is the file-ownership counterpart to the old
# hardcoded `provides` list — same names, but now backed by real paths.
_KNOWN_LIBS: dict[str, list[str]] = {
    "util-linux": ["uuid", "blkid", "mount", "smartcols", "fdisk"],
    "zlib":       ["z"],
    "openssl":    ["ssl", "crypto"],
    "curl":       ["curl"],
    "pcre2":      ["pcre2-8"],
    "expat":      ["expat"],
    "libxml2":    ["xml2"],
    "ncurses":    ["ncurses", "ncursesw", "panel", "form", "menu"],
    "readline":   ["readline", "history"],
    "libffi":     ["ffi"],
    "libcap":     ["cap"],
    "glibc":      ["c", "m", "pthread", "dl", "rt", "resolv", "util"],
}

_LIB_DIRS = [
    "/usr/lib", "/usr/lib64", "/lib", "/lib64",
    "/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu",
]

# Packages whose real, ownable file IS a header (no binary at all) —
# these genuinely exist on disk and should be tracked for conflict
# detection, same as any other file.
_KNOWN_HEADERS: dict[str, list[str]] = {
    "zlib":              ["/usr/include/zlib.h"],
    "readline":          ["/usr/include/readline/readline.h", "/usr/include/readline/history.h"],
    "linux-api-headers": ["/usr/include/linux/version.h"],
}

# Known file paths for packages with no binary and no header — the
# cert bundle itself is the real artifact worth tracking.
_KNOWN_DATA_FILES: dict[str, list[str]] = {
    "ca-certificates": ["/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem"],
}


def _discover_files(pkg_name: str) -> list[str]:
    """
    Best-effort discovery of real on-disk files owned by a package.
    Only claims paths that actually exist — never invents anything.
    """
    found: set[str] = set()

    # Binaries: multi-binary packages use the curated list; everything
    # else falls back to its representative binary (or its own name).
    bin_names = _KNOWN_BINARIES.get(
        pkg_name, [_REPRESENTATIVE_BINARY.get(pkg_name, pkg_name)]
    )
    for b in bin_names:
        path = shutil.which(b)
        if path:
            found.add(path)

    # Libraries: glob for lib{name}.so* in standard lib dirs
    for lib in _KNOWN_LIBS.get(pkg_name, []):
        for lib_dir in _LIB_DIRS:
            for match in glob.glob(f"{lib_dir}/lib{lib}.so*"):
                if os.path.exists(match):
                    found.add(match)

    # Headers / data files: packages with no binary, but a real on-disk
    # artifact that genuinely belongs to them (zlib.h, the cert bundle, etc.)
    for path in _KNOWN_HEADERS.get(pkg_name, []) + _KNOWN_DATA_FILES.get(pkg_name, []):
        if os.path.exists(path):
            found.add(path)

    return sorted(found)


def _discover_provides(pkg_name: str) -> list[str]:
    """Virtual package names this adopted package satisfies for resolver purposes."""
    provides_map = {
        "bash":        ["sh"],
        "pkgconf":     ["pkg-config"],
        "gawk":        ["awk"],
        "util-linux":  ["libuuid.so", "libblkid.so", "libmount.so", "uuid"],
        "zlib":        ["libz.so"],
        "openssl":     ["libssl.so", "libcrypto.so"],
        "curl":        ["libcurl.so"],
        "ncurses":     ["libncurses.so", "libncursesw.so"],
        "readline":    ["libreadline.so"],
        "libxml2":     ["libxml2.so"],
        "libffi":      ["libffi.so"],
        "libcap":      ["libcap.so"],
    }
    return provides_map.get(pkg_name, [])


def adopt(dry_run: bool = False):
    config = get_config()
    db = LocalDB()

    protected = config.protected_packages

    print(f"   :: Checking {len(protected)} core LFS packages...")

    adopted = 0
    skipped = 0
    missing = 0
    unverified = 0

    for pkg_name in protected:
        if db.has(pkg_name):
            print(f"      = Skipping {pkg_name} (already registered)")
            skipped += 1
            continue

        if not is_present(pkg_name):
            print(f"      ! Not found on system, skipping: {pkg_name}")
            missing += 1
            continue

        version, verified = detect_version(pkg_name)
        files = _discover_files(pkg_name)
        provides = _discover_provides(pkg_name)

        tag = version if verified else f"{version} (unverified)"
        file_note = f", {len(files)} files tracked" if files else ", no files tracked"
        print(f"      + Adopting {pkg_name} as {tag}{file_note}")
        if not verified:
            unverified += 1

        if not dry_run:
            db.register(
                Package(
                    name=pkg_name,
                    version=version,
                    version_verified=verified,
                    desc="Core LFS system package (managed by original build)",
                    url="https://www.linuxfromscratch.org",
                    provides=provides,
                    origin="local",
                ),
                files=files,
                explicit=True,
            )
        adopted += 1

    print(f"\n   ✓ Adoption complete. Added: {adopted}, skipped: {skipped}, "
          f"not found: {missing}.")
    if unverified:
        print(f"   ⚠ {unverified} package(s) adopted with an unverified version "
              f"(no reliable version source exists for them). Version-constraint "
              f"checks involving them will be skipped, not silently wrong.")
    if dry_run:
        print("   ✓ Dry-run mode: LocalDB was not modified.")


def main():
    parser = argparse.ArgumentParser(description="Adopt core LFS packages into Sven LocalDB")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be adopted")
    args = parser.parse_args()
    adopt(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

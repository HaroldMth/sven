# Sven Installation Guide (Enterprise LFS Edition)

This document provides a comprehensive, professional guide to deploying Sven onto your **Seven OS** or **Linux From Scratch (LFS)** distribution.

## 1. System Dependency Table (Prerequisites)

Before installing Sven, your base LFS system must provide the following core toolchain components. While Seven OS ships with many of these, ensure your build was configured with the appropriate flags according to the **LFS (12.x+)** or **BLFS** books.

| Tool | Purpose | LFS/BLFS Chapter | Notes |
|------|---------|-----------------|-------|
| `python3` | Core execution runtime | LFS 9.4 | Required version: >= 3.10 |
| `tar` | Package extraction | LFS 9.4 | Must be compiled with `zstd` support |
| `zstd` | Archive decompression | LFS 9.4 | High-performance compression engine |
| `gpg` | Signature verification | BLFS 9.6 | Essential for repository security |
| `git` | Source cloning | BLFS 12.1 | Required for AUR build integration |
| `fakeroot`| Safe package builds | BLFS (General) | Prevents builds from leaking into root |
| `sudo` | Permission elevation | BLFS 15.3 | Used for atomic filesystem merges |
| `wget` | Asset fetching | BLFS 12.7 | Required for initial bootstrap/self-update |

## 2. Automated One-Command Installation (Recommended)

The easiest way to install Sven on Seven OS is by using our **Foolproof Bootstrap Script**. This script checks every dependency, creates the necessary directories, and automatically "adopts" your system (registers your LFS base into the Sven database).

Run this directly from the repository source:

```bash
sudo bash scripts/install.sh
```

### What the installer does:
1. **Dependency Analysis**: It scans for each tool listed above and provides the exact LFS/BLFS chapter number if one is missing.
2. **Directory Hardening**: It creates `/etc/sven`, `/var/lib/sven`, and the logging/caching folders with standard permissions.
3. **Standalone Deployment**: It places the static binary (built with static C-libs) into `/usr/bin/sven`.
4. **LFS Adoption**: It executes the adoption scripts to ensure Sven knows NOT to overwrite your core system files (e.g., `glibc`, `bash`).

## 3. Manual Installation (For LFS Purists)

If you prefer to build Sven manually using your local compiler and static libraries, follow these steps:

### A. Environment Configuration
Navigate to the Sven project root and prepare the build environment:
```bash
git clone https://github.com/haroldmth/sven.git /tmp/sven
cd /tmp/sven
make build
```

### B. Deployment
Manually place the files to adhere to FHS (Filesystem Hierarchy Standard):
```bash
cp dist/sven /usr/bin/sven
chmod 755 /usr/bin/sven
mkdir -p /etc/sven /var/lib/sven/sync /var/cache/sven/pkgs /var/log/sven
```

### C. Manual System Adoption (Crucial)
You **must** run the adoption scripts once to synchronize Sven's LocalDB with your existing LFS build state. Failing to do this can lead to "conflicts" when trying to install software that depends on shared libraries like `libz.so` or `libc.so`.

```bash
python3 scripts/adopt_lfs.py
python3 scripts/adopt_blfs.py
```

## 4. Advanced: Building Requirements from Source (BLFS)

If you find that your LFS build is missing `zstd` support or `fakeroot`, follow these official build patterns:

### Adding Zstd Support directly into Tar
If `tar --version` does not list `zstd` as a capability, you must recompile `tar` against the `zstd` library:
```bash
# Inside tar source directory
./configure --prefix=/usr --bindir=/bin --with-zstd
make && make install
```

### Building Fakeroot (Required for AUR)
Fakeroot allows `makepkg` to assume root privileges for ownership assignment without actual risks:
```bash
wget http://ftp.debian.org/debian/pool/main/f/fakeroot/fakeroot_1.24.orig.tar.gz
# Standard build: ./configure --prefix=/usr && make && sudo make install
```

## 5. Post-Install Verification
Confirm Sven is operational and honors your Seven OS core:
```bash
sven list --explicit
```
Every core tool (like `grep`, `sed`, `perl`) should be listed as `LFS-BASE`.

## 6. Uninstallation
To completely remove Sven from your system without touching your LFS base:
```bash
sudo rm -rf /usr/bin/sven /etc/sven /var/lib/sven /var/cache/sven /var/log/sven
```
Caution: This will delete your Sven package databases and rollbacks, but won't touch your manually installed software.

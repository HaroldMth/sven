# Sven Installation Guide (Enterprise LFS Edition) 🦁🏁

This document provides a comprehensive, professional guide to deploying Sven onto your **Seven OS** or **Linux From Scratch (LFS)** distribution.

---

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

---

## 2. Automated One-Command Installation (Recommended)

The easiest way to install Sven on Seven OS is by using our **Foolproof Bootstrap Script**. This script checks every dependency, creates the necessary directories, and automatically "adopts" your system (registers your LFS base into the Sven database).

Run this directly from the repository source:

```bash
# Inside the Seven OS host/chroot
sudo bash install.sh
```

### What the installer does:
1. **Dependency Analysis**: It scans for each tool listed above and provides the exact LFS/BLFS chapter number if one is missing.
2. **Directory Hardening**: It creates `/etc/sven`, `/var/lib/sven`, and the logging/caching folders with standard permissions.
3. **Standalone Deployment**: It places the static binary (built with static C-libs) into `/usr/bin/sven`.
4. **LFS Adoption**: It executes the adoption scripts to ensure Sven knows NOT to overwrite your core system files (e.g., `glibc`, `bash`).

---

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

---

## 4. Troubleshooting Connectivity (Flaky/Trash Networks)

If you are operating on a high-latency or unstable connection (e.g., 30%+ packet loss), Sven includes a **Zero-Trust Downloader** with built-in resilience. You can further tune your environment in `sven/constants.py`:

- **Timeouts**: Increase `DOWNLOAD_TIMEOUT` (default: 120s) if mirrors are timing out.
- **Parallelism**: Decrease `PARALLEL_DOWNLOADS` (default: 3) to reduce connection overhead on lossy links.
- **Failover**: Sven automatically attempts up to **10 different mirrors** per package if a checksum mismatch or connection error occurs.

---

## 5. Development Mode (Source-Linking)

If you are a Seven OS core developer and want to test Sven changes instantly without rebuilding the binary, you can "link" your source folder to the system's `/usr/bin/sven` entry point.

**On the Host/Chroot:**
```bash
# 1. Back up the existing binary
sudo mv /usr/bin/sven /usr/bin/sven.bin

# 2. Create a development launcher script
sudo tee /usr/bin/sven << 'EOF'
#!/bin/bash
export PYTHONPATH="/home/harold/Desktop/sven"
python3 "/home/harold/Desktop/sven/run_sven.py" "$@"
EOF

# 3. Mark as executable
sudo chmod +x /usr/bin/sven
```
Now, any change you make to the `.py` files in your git repository will be **immediately live** in your Seven OS shell!

---

## 6. Architecture Overview (The LFS Bridge)

```text
  [ ARCH REPOS ] <────> [ SVEN DOWNLOADER ] <────> [ SVEN INSTALLER ]
    (Official)           (Parallel/Failover)         (Atomic Merge)
                                 │                         │
                                 ▼                         ▼
  [ AUR ENGINE ] <─────> [ MAKEPKG CHROOT ] <─────> [ SEVEN OS / LFS ]
    (Source)              (Safe Sandbox)             (Final Binary)
                                                           │
                                                           ▼
                                                    [ SYSVINIT RUNTIME ]
```

---

## 7. Uninstallation

To completely remove Sven from your system without touching your LFS base:
```bash
sudo rm -rf /usr/bin/sven /usr/bin/sven.bin /etc/sven /var/lib/sven /var/cache/sven /var/log/sven
```
*Note: This will delete your Sven package databases and rollbacks, but won't touch your manually installed software.*

Developed with passion by **HANS TECH © 2024**. 🦁🏁
🏁 *Sven: Speed, Stability, and the Freedom of LFS.* 🏁

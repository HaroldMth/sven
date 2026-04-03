# Sven Installation Guide

This guide ensures a professional-grade deployment of Sven on your **Seven OS** or **Linux From Scratch (LFS)** environment. 

## 1. System Dependencies (LFS Prereqs)

Before Sven can operate, your base LFS system must provide the following core toolchain. While Seven OS ships with many of these, ensure you have these installed from the LFS/BLFS book:

### Required Runtime:
- **Python 3.10+**: Core runtime for Sven. 
- **Python-Requests**: For all HTTP API and repository communications. 
- **Zstandard (zstd)**: Required for Arch Linux `.zst` package extraction.
- **Tar & GnuPG**: For archive handling and signature verification.

### For AUR Builds (Build-time):
- **Binutils**: Provides `ar`, `strip`, and `objdump` for `makepkg`.
- **Fakeroot**: For safe package creation without root permissions.
- **Git**: Required to clone AUR sources.
- **Sudo**: Used by Sven to elevate permissions for atomic filesystem merges.

## 2. Fast Installation (Standalone Binary)

If you are using a standard x86\_64 system, download our pre-compiled standalone binary which bundles most Python dependencies:

```bash
wget https://github.com/haroldmth/sven/releases/latest/download/sven-linux-x86_64 -O /usr/bin/sven
chmod +x /usr/bin/sven
```

## 3. Manual Installation (From Source)

To build Sven natively on your LFS system using your local Python toolchain:

```bash
git clone https://github.com/haroldmth/sven.git /tmp/sven
cd /tmp/sven
make build
cp dist/sven /usr/bin/sven
chmod +x /usr/bin/sven
```

## 4. Post-Installation (The Seven OS Adoption)

Sven needs to "adopt" your existing LFS base so it doesn't attempt to reinstall core system libraries.

1. Ensure the directory structure exists:
   ```bash
   mkdir -p /etc/sven /var/lib/sven/sync /var/cache/sven/pkgs /var/log/sven
   ```
2. Initialize the default configuration:
   ```bash
   cp /tmp/sven/sven.conf /etc/sven/
   ```
3. Run the Adoption Script to register your existing LFS packages into the LocalDB:
   ```bash
   python3 /tmp/sven/scripts/adopt_lfs.py
   python3 /tmp/sven/scripts/adopt_blfs.py
   ```

## 5. Verification
Confirm Sven is operational and recognizes your core system:
```bash
sven list --explicit
```
You should see `bash`, `glibc`, `binutils`, etc., listed as `LFS-BASE`.

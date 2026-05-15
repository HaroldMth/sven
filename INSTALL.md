# Sven Installation Guide

This guide documents the current, supported installation flow for Sven on Seven OS / LFS-style systems.

## 1. Prerequisites

Required runtime tools (validated by `install.sh`):

- `python3`
- `tar`
- `zstd`
- `gpg`
- `git`
- `fakeroot`
- `sudo`

For release-binary download fallback (when no local `dist/sven` exists):

- `wget` or `curl`

Notes:

- Sven preflight expects Python `>= 3.9`.
- Install tools from your LFS/BLFS build as needed.

## 2. Recommended Installation

From repository root:

```bash
git clone https://github.com/HaroldMth/sven.git
cd sven
sudo bash install.sh
```

What this does:

1. Verifies required tools.
2. Creates Sven directories under `/etc/sven`, `/var/lib/sven`, `/var/cache/sven`, `/var/log/sven`.
3. Installs `/usr/bin/sven` (from local `dist/sven` if present, otherwise downloads release binary).
4. Runs adoption scripts (`adopt_lfs.py`, `adopt_blfs.py`) unless skipped.
5. Runs `sven sync` unless skipped.

## 3. Installer Options

```bash
sudo bash install.sh --help
```

Supported options:

- `-v`, `--verbose`: detailed execution output
- `--no-sync`, `--quick`: skip final `sven sync`
- `--skip-adopt`: skip adoption scripts
- `--sven-version <ver>`: download a specific Sven release binary (example: `1.2.0`)

Examples:

```bash
sudo bash install.sh --quick
sudo bash install.sh --skip-adopt
sudo bash install.sh --sven-version 1.2.0
sudo bash install.sh --verbose
```

## 4. Manual Installation

If you prefer manual deployment:

```bash
# from repo root
cp dist/sven /usr/bin/sven
chmod +x /usr/bin/sven

mkdir -p /etc/sven
mkdir -p /var/lib/sven/{sync,installed,snapshots}
mkdir -p /var/cache/sven/pkgs
mkdir -p /var/log/sven
```

Then adopt your existing system packages:

```bash
PYTHONPATH=. python3 scripts/adopt_lfs.py
PYTHONPATH=. python3 scripts/adopt_blfs.py -y
```

## 5. Adoption Script Modes

LFS base adoption:

```bash
PYTHONPATH=. python3 scripts/adopt_lfs.py --dry-run
PYTHONPATH=. python3 scripts/adopt_lfs.py
```

BLFS auto-discovery adoption:

```bash
PYTHONPATH=. python3 scripts/adopt_blfs.py --dry-run
PYTHONPATH=. python3 scripts/adopt_blfs.py --min-score 8 --dry-run
PYTHONPATH=. python3 scripts/adopt_blfs.py -y
```

Options:

- `--dry-run`: preview only (no LocalDB writes)
- `--min-score <n>`: confidence threshold for BLFS matching
- `-y`, `--yes`: non-interactive confirmation

## 6. Post-Install Checks

Run:

```bash
sven version
sven sync
sven search bash
```

Useful version commands:

- `sven version`: Sven/runtime/tooling status
- `sven check-version <pkg>`: package versions across local/sync/AUR/cache

## 7. Uninstall

Remove Sven binary and state directories:

```bash
sudo rm -f /usr/bin/sven /usr/bin/sven.bin
sudo rm -rf /etc/sven /var/lib/sven /var/cache/sven /var/log/sven
```

This removes Sven-managed metadata, cache, and logs.

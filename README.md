# Sven

Sven is a package manager for Seven OS (LFS/BLFS-based systems) that integrates official Arch repositories and AUR workflows while preserving non-systemd environments.

## Highlights

- Dependency resolution with rollback snapshots
- systemd dependency filtering for SysVinit/OpenRC hosts
- Official repo + AUR install flow
- Mirror management and cache reuse
- BLFS/LFS adoption helpers for existing systems

## Install

```bash
git clone https://github.com/haroldmth/sven.git
cd sven
sudo bash install.sh
```

### Installer options

```bash
sudo bash install.sh --help
```

- `--sven-version <ver>`: install a specific Sven release binary (example: `1.2.0`)
- `--skip-adopt`: skip running adoption scripts
- `--no-sync` / `--quick`: skip final `sven sync`
- `--verbose`: detailed execution output

## Core commands

- `sven install <pkg ...>`: install packages
- `sven install <pkg> --version <ver>`: install a specific package version when available
- `sven remove <pkg ...>`: remove packages
- `sven upgrade`: full system upgrade
- `sven sync`: refresh sync databases
- `sven search <query>`: search packages
- `sven info <pkg>`: package metadata
- `sven check-version <pkg>`: compare installed/sync/AUR/cache package versions
- `sven version`: show Sven + runtime tool versions
- `sven check-update`: check for newer Sven release
- `sven self-update`: update Sven binary

## Adoption scripts

Sven includes scripts to register existing LFS/BLFS software into LocalDB.

- `scripts/adopt_lfs.py`
  - `--dry-run`: preview changes only

- `scripts/adopt_blfs.py`
  - `--min-score <n>`: tighten or loosen matching confidence
  - `--dry-run`: preview changes only
  - `-y` / `--yes`: non-interactive mode

Examples:

```bash
PYTHONPATH=. python3 scripts/adopt_lfs.py --dry-run
PYTHONPATH=. python3 scripts/adopt_blfs.py --min-score 8 --dry-run
PYTHONPATH=. python3 scripts/adopt_blfs.py -y
```

## Paths

- Config: `/etc/sven/`
- Databases: `/var/lib/sven/`
- Cache: `/var/cache/sven/`
- Logs: `/var/log/sven/`

## Notes

- `sven version` is for Sven/runtime tooling status.
- `sven check-version <pkg>` is for package version visibility across sources.
- For source/build and deeper platform details, see `INSTALL.md`.

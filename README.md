# Sven

**Sven** is the package manager for **Seven OS** — a Linux From Scratch (LFS)
based distribution. It bridges two worlds: the convenience of a real
repository-backed package manager (à la `pacman`), and the reality of a
hand-built, non-systemd LFS/BLFS system.

Concretely, Sven:

- Resolves and installs packages from the **official Arch repos + AUR**
- **Filters out systemd-only dependencies** so packages stay installable on
  SysVinit/OpenRC hosts, suggesting non-systemd alternatives where one exists
- Tracks everything it installs in a **local package database**, with
  rollback snapshots for safe undos
- Can **adopt** software you already built by hand from LFS/BLFS — so you
  don't have to start your package-managed history from zero
- Leans on a small **C core** (`libsven`) for the hot paths — version
  comparison, dependency resolution, systemd filtering, topological sort,
  and (when `libarchive-dev` is available) extraction — with safe pure-Python
  fallbacks for everything else

## How this project is built

Sven is **architected by a human, coded by AI.** Harold (HANS BYTE) designs
the system — the package format strategy, the systemd-filtering approach,
the adoption heuristics, what tradeoffs are acceptable for an LFS-targeted
tool — and directs an AI coding assistant to implement, test, and harden it
against that design. Every change ships after the human has reviewed the
reasoning and the AI has verified the behavior, not just written code that
looks plausible.

This isn't a disclaimer, it's how the project actually gets built — and it's
worth saying plainly so nobody has to guess.

## Quick install

```bash
git clone https://github.com/HaroldMth/sven.git
cd sven
sudo bash install.sh
```

This checks your tools, lays out `/etc/sven`, `/var/lib/sven`,
`/var/cache/sven`, installs the `sven` binary, **syncs package databases**,
then runs the LFS/BLFS adoption helpers (in that order — adoption needs
synced data to match against, so it always runs last).

See **[INSTALL.md](INSTALL.md)** for prerequisites, manual installation,
troubleshooting, and what each install path (`install.sh`, `bootstrap.sh`,
`PKGBUILD`) is actually for.

### Installer options

```bash
sudo bash install.sh --help
```

| Flag | What it does |
|---|---|
| `--sven-version <ver>` | Install a specific Sven release (e.g. `1.2.0`) instead of latest |
| `--skip-adopt` | Skip both adoption scripts entirely |
| `--no-sync` / `--quick` | Skip the database sync (adoption will then also be skipped — it needs synced data) |
| `-v`, `--verbose` | Full command tracing, timings, environment summary |

## Checking your system

```bash
sven doctor       # full health check: paths, DBs, GPG, network, C library status
sven preflight     # quick check before you've even installed anything
```

`doctor` tells you things like whether the fast C extractor is active or
you're on the Python fallback, whether your sync DBs exist, and whether
required Python modules are present. Run it any time something feels off.

## Command reference

### Package management
| Command | What it does |
|---|---|
| `sven install <pkg...>` | Install one or more packages |
| `sven install <pkg> --version <ver>` | Install a specific available version |
| `sven remove <pkg...>` | Remove packages |
| `sven upgrade` | Upgrade all installed packages |
| `sven upgrade --skip-aur` | Upgrade without checking AUR — skips the network round-trip to the AUR RPC for every installed AUR package |
| `sven update` | Sync databases, then upgrade (like `pacman -Syu`) |
| `sven update --skip-aur` | Same, but skip the AUR check too |
| `sven sync` | Refresh package databases only |
| `sven search <query>` | Search official repos + AUR |
| `sven info <pkg>` | Show package metadata |
| `sven list` | List installed packages |
| `sven path <pkg>` | Show install path / owned files |

### Version & info
| Command | What it does |
|---|---|
| `sven version` | Show Sven's own version + detected runtime tool versions |
| `sven check-version <pkg>` | Compare installed vs. sync vs. AUR vs. cache versions |
| `sven deps <pkg>` | Show the dependency tree |
| `sven rdeps <pkg>` | Show what depends on a package (reverse deps) |
| `sven cnf <command>` | "Command not found" lookup — which package provides this? |

### Maintenance & safety
| Command | What it does |
|---|---|
| `sven doctor [--offline]` | Full system health check |
| `sven preflight` | Quick pre-install environment check |
| `sven clean` | Clear the package cache |
| `sven verify` | Verify installed package integrity |
| `sven orphans` | List packages nothing depends on anymore |
| `sven adopt-installed` | Reconcile installed DB entries into the local cache |
| `sven snapshots` | List rollback snapshots |
| `sven rollback` | Undo the last operation |

### Mirrors
| Command | What it does |
|---|---|
| `sven mirror list` | Show configured mirrors |
| `sven mirror fastest` | Benchmark mirrors, pick the fastest for this session |
| `sven mirror rank` | Benchmark and persist a ranked mirrorlist |

### Self-management
| Command | What it does |
|---|---|
| `sven check-update` | Check whether a newer Sven release exists |
| `sven self-update` | Download and install the latest Sven release |
| `sven self-remove` | Completely uninstall Sven from this system |

## Adoption scripts

These register software you already built by hand into Sven's local
database, so Sven knows about it without you reinstalling anything.

- **`scripts/adopt_lfs.py`** — registers the ~40 core LFS base packages
  (glibc, bash, coreutils, binutils, etc.). For each one it verifies the
  package is actually present, detects its **real** version (via `--version`
  probing, header macros for header-only libs like zlib, or `pkg-config`),
  and records the real files it owns for conflict detection. Where no
  reliable version source exists at all (`filesystem`, `ca-certificates`,
  `linux-firmware`), it's honest about that — it marks the version
  *unverified* rather than guessing, and Sven will skip version-constraint
  checks for that package rather than comparing nonsense.

- **`scripts/adopt_blfs.py`** — scans your filesystem for binaries,
  libraries, `.pc` files, and headers, then matches them against the synced
  Arch package database to guess what you've already built. A package is
  only adopted if it has **one strong signal** (an exact binary-name match)
  **or signals from at least two independent categories** — a single
  coincidental library-name match is no longer enough on its own. Where
  possible it cross-checks the matched version against a live `--version`
  probe of the real binary; otherwise it's marked unverified rather than
  trusting the heuristic match blindly.

```bash
PYTHONPATH=. python3 scripts/adopt_lfs.py --dry-run
PYTHONPATH=. python3 scripts/adopt_blfs.py --min-score 8 --dry-run
PYTHONPATH=. python3 scripts/adopt_blfs.py -y
```

Both scripts require a successful `sven sync` first — `adopt_lfs.py` doesn't
strictly need it, but `adopt_blfs.py` matches against the synced database
and will refuse to run without it. `install.sh` already runs them in the
correct order automatically.

## Paths

| What | Where |
|---|---|
| Config | `/etc/sven/` |
| Databases (sync + installed + snapshots) | `/var/lib/sven/` |
| Package cache | `/var/cache/sven/` |
| Logs | `/var/log/sven/` |

## Performance: the C core

Hot-path logic lives in `libsven/` (C) and is loaded via ctypes from
`sven/libsven.py`: version comparison, dependency-string parsing, systemd
classification, topological sort, and — when `libarchive-dev` is present at
build time — package extraction. Every function has a pure-Python fallback,
so Sven works even on a system without a C toolchain; it's just faster with
one. Run `sven doctor` to see which path you're actually on.

## More

- **[INSTALL.md](INSTALL.md)** — prerequisites, manual install, troubleshooting
- **[CONTRIBUTIONS.md](CONTRIBUTIONS.md)** — dev setup, building from source

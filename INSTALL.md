# Installing Sven

This is the complete installation guide for Sven on Seven OS / LFS-BLFS
systems — what's required, what each install path actually does, and what
to do when something goes wrong.

## 1. Prerequisites

Checked automatically by `install.sh`, required before it will proceed:

| Tool | Why |
|---|---|
| `python3` (≥ 3.9) | Sven itself is Python + a small C extension |
| `tar` | Package extraction (fallback path) |
| `zstd` | Package extraction (fallback path) |
| `gpg` | Verifying signed package databases/packages |
| `git` | Cloning AUR package sources |
| `fakeroot` | Building AUR packages without real root |

You do **not** need `sudo` installed as a tool — `install.sh` checks that
you're running as root directly (`id -u`); it never shells out to `sudo`
itself. Running the script with `sudo bash install.sh` (or already being
root, e.g. inside a chroot) is what actually matters.

Optional, but recommended:

| Tool | Why |
|---|---|
| `wget` or `curl` | Only needed if you have no local `dist/sven` build (the installer downloads a release binary instead) |
| `libarchive-dev` | Compiles in the fast C package extractor. Without it, Sven falls back to a pure-Python extractor — correct, just slower. Run `sven doctor` after install to see which one you're on. |

Install whatever's missing from your LFS/BLFS build, then run the installer
(again, if needed).

## 2. Recommended install

```bash
git clone https://github.com/HaroldMth/sven.git
cd sven
sudo bash install.sh
```

What this actually does, **in order**:

1. **Checks prerequisites** (the table above).
2. **Creates directories** — `/etc/sven`, `/var/lib/sven/{sync,installed,snapshots}`,
   `/var/cache/sven/pkgs`, `/var/log/sven` — and writes a default `sven.conf`.
3. **Installs the binary** to `/usr/bin/sven` — from `dist/sven` if you've
   built one, from `run_sven.py` as a source-tree launcher if not, or by
   downloading the latest (or `--sven-version`-pinned) GitHub release.
4. **Syncs package databases** (`sven sync`) — unless `--no-sync`.
5. **Runs adoption scripts** — unless `--skip-adopt`. `adopt_lfs.py` always
   runs if its prerequisites are met; `adopt_blfs.py` only runs if step 4
   actually succeeded, since it matches against the synced database and
   has nothing to match against otherwise.

**Sync runs before adoption, not after** — this matters if you're scripting
around `install.sh` or reading its source, since earlier revisions had this
backwards and would crash. If you ever see `DatabaseError: No sync DBs found`
from an adoption script, it means sync hasn't succeeded yet — run `sven sync`
first.

## 3. Installer options

```bash
sudo bash install.sh --help
```

| Flag | Effect |
|---|---|
| `-v`, `--verbose` | Full command tracing, timings, environment summary |
| `--no-sync`, `--quick` | Skip step 4 — and step 5's BLFS half, since it depends on step 4 |
| `--skip-adopt` | Skip step 5 entirely |
| `--sven-version <ver>` | Install a specific release (e.g. `1.2.0`) instead of latest |

```bash
sudo bash install.sh --quick
sudo bash install.sh --skip-adopt
sudo bash install.sh --sven-version 1.2.0
sudo bash install.sh --verbose
```

## 4. Alternative: bootstrap.sh

`scripts/bootstrap.sh` is a lighter-weight setup path: it installs Python
dependencies, creates the same directory layout, writes default config +
mirrorlist, and creates a `/usr/bin/sven` source launcher — but it does
**not** download or build a compiled binary, and it does **not** run
adoption or sync for you. Useful if you've already cloned the repo and just
want the environment prepared without the full `install.sh` flow.

```bash
sudo bash scripts/bootstrap.sh
sven sync
sven preflight
```

If you're not sure which one to use: use `install.sh`. `bootstrap.sh` is
for when you specifically want to skip the binary-acquisition step.

## 5. Manual installation

If you want full control over each step (or are scripting your own LFS
build process), do it in this order — **sync before adopt is mandatory**,
adoption reads from the synced database:

```bash
# 1. Directories
mkdir -p /etc/sven
mkdir -p /var/lib/sven/{sync,installed,snapshots}
mkdir -p /var/cache/sven/pkgs
mkdir -p /var/log/sven

# 2. Binary
cp dist/sven /usr/bin/sven
chmod +x /usr/bin/sven

# 3. Sync — must happen before adoption
sven sync

# 4. Adopt your existing LFS/BLFS packages
PYTHONPATH=. python3 scripts/adopt_lfs.py
PYTHONPATH=. python3 scripts/adopt_blfs.py -y
```

## 6. Adoption script reference

```bash
PYTHONPATH=. python3 scripts/adopt_lfs.py --dry-run     # preview only
PYTHONPATH=. python3 scripts/adopt_lfs.py               # registers core LFS packages

PYTHONPATH=. python3 scripts/adopt_blfs.py --dry-run               # preview only
PYTHONPATH=. python3 scripts/adopt_blfs.py --min-score 8 --dry-run # stricter matching
PYTHONPATH=. python3 scripts/adopt_blfs.py -y                      # non-interactive
```

- `--dry-run` — preview only, no LocalDB writes
- `--min-score <n>` — confidence threshold for BLFS matching (default `5`)
- `-y`, `--yes` — skip the confirmation prompt

Both scripts try to record a **real, verified version** for each package
(via `--version` probing, header macros, or `pkg-config`) rather than a
placeholder. When no reliable version source exists, the package is marked
*unverified* and Sven will skip version-constraint checks for it rather than
comparing against a fake string. You'll see this called out explicitly in
the script's output (`⚠ N package(s) adopted with an unverified version`).

## 7. Verifying the install

```bash
sven version          # Sven + runtime tool versions
sven doctor            # full health check — paths, DBs, GPG, network, C library status
sven search bash       # confirm sync actually worked
```

`sven doctor` is the one to reach for any time something feels off — it
checks config, sync DBs, the local DB, GPG keyring, required tools and
Python modules, and whether the fast C extractor or the Python fallback is
active.

## 8. Troubleshooting

**`DatabaseError: No sync DBs found under: /var/lib/sven/sync`**
Adoption (specifically `adopt_blfs.py`) ran before sync succeeded. Run
`sven sync`, confirm it actually completes, then re-run the adoption script.

**Sync reports success but `sven search` finds nothing**
That shouldn't happen anymore — `sven sync` now reports per-repo failures
honestly and exits non-zero if every mirror failed, instead of printing a
blanket "synchronized successfully." If you still see this, run `sven
doctor --offline` and `sven mirror fastest` to check connectivity and
mirror health.

**`sudo: command not found` during `install.sh`'s prerequisite check**
This shouldn't happen — `sudo` is not in the required-tools list. If you
hit this, you're likely on an old copy of the script; pull the latest.

**Installed binary is not runnable**
Usually an architecture mismatch on a downloaded release, or a noexec mount
on the destination path. Check `uname -m` matches the release asset, and
that `/usr/bin` isn't mounted `noexec`.

**Extraction feels slow**
Run `sven doctor` and check the "C performance library" line. If it warns
that the C extractor isn't compiled in, install `libarchive-dev` and run
`make build` from the repo root to rebuild `libsven_core.so` with it.

## 9. Uninstall

```bash
sven self-remove
```

or manually:

```bash
sudo rm -f /usr/bin/sven
sudo rm -rf /etc/sven /var/lib/sven /var/cache/sven /var/log/sven
```

This removes the binary, all Sven-managed metadata, cache, and logs. It does
**not** remove any packages Sven installed — those stay on your system.

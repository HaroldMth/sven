# Sven Package Manager

![License](https://img.shields.io/badge/License-GPL_v3-blue.svg)
![Version](https://img.shields.io/badge/Version-1.0.0-green.svg)
![OS](https://img.shields.io/badge/OS-Seven_OS_|_LFS-orange.svg)

**Sven** is the official package manager for **Seven OS**, a high-performance Linux From Scratch (LFS) distribution utilizing SysVinit. Sven acts as a hybrid bridge, allowing users to effortlessly install pure Arch Linux packages and build from the Arch User Repository (AUR) without systemd contaminating their LFS base.

## Features
- **Zero-Traceback Safety Shield**: Globally catches execution crashes and presents clean, actionable error UI—keeping users abstracted from Python stack traces.
- **Atomic Rollbacks**: Every transaction generates an instantaneous filesystem snapshot beforehand. If an installation fails, gets corrupted, or is aborted, Sven automatically rewinds the system state to ensure complete stability.
- **SysVinit Native**: Actively filters out hard `systemd` dependencies and automatically translates standard Arch update hooks (like `systemctl restart`) into `SysVinit` equivalents.
- **Fail-Fast Integrity**: Uses a "Double-Check" engine validating both exact network chunk sizes and `/usr/bin/sha256sum` hashes, with auto-failover to alternative mirrors upon corruption.
- **AUR Integration**: Fetches, compiles, and packages AUR repositories dynamically into `.pkg.tar.zst` files for standard integration.

## Installation
For LFS Base Systems, download and execute the latest standalone binary from the releases page into `/usr/bin/`:

```bash
wget https://github.com/haroldmth/sven/releases/latest/download/sven-linux-x86_64 -O /usr/bin/sven
chmod +x /usr/bin/sven
```

## Basic Usage

Sven focuses on simplicity. The interface strips away complex flags in favor of clear UX pipelines.

* **Install** official packages or automatically build from AUR:
  ```bash
  sven install neovim firefox spotify
  ```
* **Remove** a package (handles reverse-dependency checking safely):
  ```bash
  sven remove htop
  ```
* **Upgrade** the entire system catalog:
  ```bash
  sven upgrade
  ```
* **Search** packages in Core, Extra, Multilib, and AUR:
  ```bash
  sven search "web browser"
  ```
* **Auto-Update** Sven itself to the latest GitHub release:
  ```bash
  sudo sven self-update
  ```

## Project Directories
* `/etc/sven/sven.conf`: Global configuration and mirror lists.
* `/var/lib/sven/`: Sven's internal Sync and Local DBs tracking package states.
* `/var/log/sven/`: Log outputs, including the `error.log` for the Safety Shield.
* `/var/cache/sven/pkgs`: The offline package download cache.

## Copyright
Developed for Seven OS by **HANS TECH © 2024**. Licensed under the GNU Public License version 3 (GPLv3).

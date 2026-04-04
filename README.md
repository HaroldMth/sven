# Sven — The Seven OS Package Manager 🦁🏁

[![License](https://img.shields.io/badge/License-GPL_v3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.1.0-green.svg)](https://github.com/haroldmth/sven/releases/latest)
[![OS Architecture](https://img.shields.io/badge/OS-Seven_OS_|_LFS-orange.svg)](https://www.linuxfromscratch.org)
[![Build Status](https://img.shields.io/badge/Build-Stable-brightgreen.svg)]()

```text
  ███████╗██╗   ██╗███████╗███╗   ██╗
  ██╔════╝██║   ██║██╔════╝████╗  ██║
  ███████╗██║   ██║█████╗  ██╔██╗ ██║
  ╚════██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║
  ███████║ ╚████╔╝ ███████╗██║ ╚████║   v1.1.0 - Forge
  ╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝   by HANS TECH
```

**Sven** is a high-performance, production-grade package manager designed specifically for **Seven OS**. It serves as an industrial-strength bridge between a custom **Linux From Scratch (LFS)** base and the vast ecosystem of Arch Linux and the **Arch User Repository (AUR)**.

Sven's core philosophy is **Zero-Contamination**: It allows you to utilize Arch's binary repositories without a single line of `systemd` code entering your SysVinit system.

---

## ⚡ The Sven Edge

| Feature | Description |
|---------|-------------|
| **🦁 Safety Shield** | Globally catches all execution crashes. No Python tracebacks ever reach the user—only clean, actionable UI logs in `/var/log/sven/error.log`. |
| **🏁 Atomic Snapshots** | Automated `os.replace` filesystem merges. If a download corrupts or a build fails, Sven ensures the previously stable system state remains untouched. |
| **⚙️ SysVinit Translator** | Automatically filters `systemd` hard-dependencies (like `systemd-libs` or `dbus-systemd`) and routes them to standard Seven OS equivalents. |
| **🚀 Mirror Benchmarking** | Native `sven mirror fastest` command ranks your mirrors by latency and bandwidth, automatically rewriting your configuration for peak speed. |
| **📦 Dynamic AUR Engine** | A built-in orchestration layer for `makepkg` that resolves, compiles, and installs AUR packages with standard dependency resolution. |

---

## 🚀 Quick Start (Production)

The fastest way to deploy Sven onto a fresh Seven OS build is through our **Foolproof Bootstrap Script** which performs a full system dependency audit:

```bash
# Clone the repository
git clone https://github.com/haroldmth/sven.git /tmp/sven
cd /tmp/sven

# Run the production installer (performs LFS dependency audit + system adoption)
sudo bash install.sh
```

---

## 🛠️ Essential Commands

| Command | Action |
|---------|--------|
| `sven install <pkg>` | Install from official Core/Extra/Multilib or the AUR. |
| `sven upgrade` | Perform a full system synchronization and rolling upgrade. |
| `sven remove <pkg>` | Securely remove a package and its orphaned dependencies. |
| `sven check-update` | Check for a newer standalone Sven version on GitHub. |
| `sven self-update` | Automagically upgrade the Sven binary to the latest stable release. |
| `sven mirror fastest` | Rank and select the highest performing mirrors for your region. |

---

## 📂 System Architecture

Sven stays out of your way and adheres to the **FHS** standard:

- **`/etc/sven/`**: Global configuration, mirror lists, and SysVinit initscripts.
- **`/var/lib/sven/`**: Local databases and synchronization catalogs.
- **`/var/cache/sven/`**: High-performance package cache and temporary AUR build roots.
- **`/var/log/sven/`**: The Zero-Traceback audit log.

---

## 🤝 Community & Support

- **Found a bug?** Check [ISSUES.md](ISSUES.md) and report it to the HANS TECH team.
- **Want to build Sven?** See the [INSTALL.md](INSTALL.md) for a deep dive into the LFS requirements.
- **Want to contribute?** Use the guidelines in [CONTRIBUTIONS.md](CONTRIBUTIONS.md).

Developed with passion by **HANS TECH © 2024**. Licensed under the **GPLv3**.
🏁 *Sven: Speed, Stability, and the Freedom of LFS.* 🏁

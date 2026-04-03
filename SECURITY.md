# Security Policy

Sven is the core package management software underlying Seven OS. We take vulnerabilities critically, especially those involving signature verification, dependency resolution parsing, or the snapshot/rollback algorithms.

## Supported Versions

Only the **latest release** (currently `v1.x.x`) actively receives security patches. Users are strongly encouraged to utilize the `sven self-update` mechanism regularly or stay current with the Seven OS automated updater.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a vulnerability in Sven (for example, a method to bypass the `Double-Check` integrity engine or poison the LocalDB), **do not report it publicly via a GitHub Issue**.

Instead, please email the vulnerability details directly to:
**harold@hanstech.com** (Placeholder for official security contact)

You should expect an initial acknowledgement within 48 hours, and a full vulnerability assessment and potential patch timeline within 7 days.

## Automated Hardening Features
Before reporting, please verify if your issue is handled by Sven's built-in defenses:
* **Checksum Engine**: All files are checked natively against `/usr/bin/sha256sum` prior to caching.
* **Corrupted Chunk Detection**: If a mirror drops bytes, the file size validator will trip, permanently banning the mirror for the session, failing over to a new mirror automatically, and wiping the rogue file.
* **Traceback Shield**: If a deliberate exploit crashes the Python runtime, Sven shields the stack trace, prevents the bad transaction, creates a safe rollback, and writes to `error.log`.

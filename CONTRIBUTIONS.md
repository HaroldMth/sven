# Contributing to Sven

Thank you for your interest in contributing to the Sven Package Manager! Sven is a critical component of Seven OS, and we rely on the open-source community to maintain its stability, security, and feature set.

## Code Standards
To maintain the "Safety Shield" architecture, all code must follow strict integrity rules:
1. **Zero Raw Tracebacks**: Exceptions should be intercepted gracefully. Avoid naked `try/except Exception: pass` without proper UI wrappers or logs written to `error.log`.
2. **Atomic Rules**: All package transactions must acquire the LocalDB lock and generate a Rollback snapshot. Never implement a feature that edits `/usr/` without generating a rollback snapshot first!
3. **Type Hinting**: All new Python methods must include standard type hints (`def execute(packages: list[str]) -> bool:`).

## Pull Request Process
1. Fork the repository and create your feature branch: `git checkout -b feature/my-new-feature`
2. Ensure you have tested your update on an actual SysVinit LFS environment or standard Arch Linux virtual machine.
3. Verify that your feature does NOT introduce any hard `systemd` dependencies.
4. Issue a Pull Request with a clear, descriptive title.
5. Link any related bug tracking issues directly in the PR summary.

## Commit Guidelines
Sven follows the standard Conventional Commits specification:
* `feat:` A new feature.
* `fix:` A bug fix.
* `docs:` Documentation only changes.
* `refactor:` A code change that neither fixes a bug nor adds a feature.
* `test:` Adding or updating tests.

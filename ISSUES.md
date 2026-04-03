# Issue Reporting Guidelines

Before you submit a bug report, please run `sven self-update` to verify your issue hasn't already been patched in a newer release.

## Submitting an Issue

When filing a bug on GitHub, please use the following template to help us rapidly trace your failure:

### 1. Environment
* **Sven Version**: (Run `sven info` or state your version)
* **Host OS**: (e.g., Seven OS 1.0, LFS 12.1 SysVinit)

### 2. What happened?
Describe the exact command you ran and what went wrong. Include the exact output leading up to the failure.

### 3. The Logs
If Sven displayed the `TRANSACTION FAILED: Rolling Back Data` screen, you **must** attach the relevant section of your error log.
Run this and paste the output:
```bash
cat /var/log/sven/error.log | tail -n 25
```

### Feature Requests
If you are submitting a feature request rather than a bug, please outline:
1. What the feature is.
2. Why the existing tools (or Arch pacman) don't solve this for you natively.
3. How this fits into Sven's SysVinit atomic rollback design philosophy.

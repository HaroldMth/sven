# Sven Logging Migration Audit

The following files were modified to replace direct `print("DEBUG ...")` statements with standard Python `logging`.

## Modified Files

| File | Change Details |
| :--- | :--- |
| `sven/cli.py` | Configured `logging.basicConfig` level based on the `--verbose` flag. Added subtle gray formatting for debug messages. |
| `sven/db/local_db.py` | Migrated `LocalDB.__init__` debug printing to `logger.debug`. Moved logging imports to top-level. |

## Verification Results

- **Standard Run**: 
  - `sven list` → Clean output, no debug lines.
- **Verbose Run**:
  - `sven --verbose list` → Shows `DEBUG: LocalDB.__init__: root is ...` in gray.
- **Stability**:
  - Resolved `LD_LIBRARY_PATH` environment leak that was causing system-wide segmentation faults during testing.

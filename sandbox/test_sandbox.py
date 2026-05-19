import os
import sys
from pathlib import Path

# Add the parent directory to Python path so we can import sven
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sven.installer.alpm_hooks import ALPMHookEngine

# 1. Create fake hook directory
sandbox_dir = Path(__file__).resolve().parent
hook_dir = sandbox_dir / "hooks"
hook_dir.mkdir(exist_ok=True)

# 2. Write a mock mkinitcpio hook
hook_file = hook_dir / "90-mkinitcpio-install.hook"
hook_file.write_text("""
[Trigger]
Type = Path
Operation = Install
Operation = Upgrade
Target = usr/lib/modules/*/vmlinuz
Target = boot/vmlinuz-*

[Action]
Description = Updating linux initcpios (SANDBOX MOCK)
When = PostTransaction
Exec = echo "SUCCESS: mkinitcpio was triggered because vmlinuz was touched!"
""")

print("--- Hook Sandbox Test ---")
engine = ALPMHookEngine(hook_dirs=[str(hook_dir)])

# 3. Faked list of extracted files during an upgrade
fake_extracted_files = [
    "usr/share/doc/linux/README",
    "usr/lib/modules/6.1.1-arch/vmlinuz",  # This should trigger the first Target
    "boot/vmlinuz-linux",                  # This should trigger the second Target
    "usr/bin/some_other_file"
]

print("Extracted files:")
for f in fake_extracted_files:
    print(f"  - {f}")

print("\nEvaluating hooks via C engine...")
engine.evaluate_and_run(fake_extracted_files)
print("--- End Sandbox ---")

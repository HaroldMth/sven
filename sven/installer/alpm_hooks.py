import os
import subprocess
from pathlib import Path
from ..libsven import match_path
from ..config import get_config

# ============================================================
#  Sven — Seven OS Package Manager
#  installer/alpm_hooks.py — Native Arch Hook Execution
# ============================================================

class ALPMHookEngine:
    """
    Parses ALPM (Pacman) .hook files and executes their actions if 
    any files in the transaction match their Trigger Targets.
    Powered by libsven.so for blazing-fast regex glob matching.
    """
    def __init__(self, hook_dirs: list[str] = None):
        self.config = get_config()
        self.hook_dirs = hook_dirs or [
            "/usr/share/libalpm/hooks",
            "/etc/pacman.d/hooks"
        ]

    def _parse_hook(self, file_path: Path) -> dict:
        """Custom parser because configparser doesn't like multiple 'Target=' lines."""
        targets = []
        action = {}
        
        try:
            content = file_path.read_text(errors='replace')
        except OSError:
            return None
            
        current_section = None
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'): continue
            
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                continue
                
            if '=' in line:
                key, val = line.split('=', 1)
                key, val = key.strip(), val.strip()
                
                if current_section == "Trigger":
                    if key == "Target":
                        targets.append(val)
                elif current_section == "Action":
                    action[key] = val
                    
        if not targets or "Exec" not in action:
            return None
            
        return {"targets": targets, "action": action, "file": file_path.name}

    def evaluate_and_run(self, extracted_files: list[str]):
        """
        Scan all .hook files. If ANY target glob matches ANY file in extracted_files,
        we queue the hook. Then we run all queued hooks sequentially.
        """
        hooks_to_run = []
        
        for d in self.hook_dirs:
            hook_dir = Path(self.config.rooted(d))
            if not hook_dir.exists() or not hook_dir.is_dir():
                continue
                
            for h in sorted(hook_dir.glob("*.hook")):
                hook_data = self._parse_hook(h)
                if not hook_data: continue
                
                # Check for match using C engine
                is_match = False
                for target in hook_data["targets"]:
                    if match_path(target, extracted_files):
                        is_match = True
                        break
                        
                if is_match:
                    hooks_to_run.append(hook_data)
                    
        if not hooks_to_run:
            return

        print("\n   [ALPM Hooks] Running post-transaction hooks...")
        for h in hooks_to_run:
            desc = h["action"].get("Description", f"Running {h['file']}...")
            exec_cmd = h["action"]["Exec"]
            
            print(f"      • {desc}")
            try:
                import shlex
                cmd = shlex.split(exec_cmd)
                
                # Make sure the Exec path is absolute within the root
                if cmd[0].startswith("/"):
                    cmd[0] = self.config.rooted(cmd[0])
                    
                subprocess.run(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.STDOUT, 
                    timeout=120
                )
            except Exception as e:
                print(f"      ⚠ Failed to execute {h['file']}: {e}")

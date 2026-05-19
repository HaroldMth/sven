# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/commands/self_update.py — GitHub Auto-Updater
# ============================================================

import os
import sys
import tempfile
import stat
import requests

from ..ui.output import print_section, print_success, print_error, print_info
from ..constants import VERSION
from ..ui.prompt import confirm

def run():
    print_section("Checking for Sven Auto-Updates")
    
    # Must be root to replace /usr/bin/sven
    if os.geteuid() != 0:
        print_error("self-update must be run as root.")
        print("   Try: sudo sven self-update")
        sys.exit(1)

    from ..core.updater import get_latest_version, source_tree_install_detected
    
    print_info("Contacting GitHub API...")
    latest_tag, download_url = get_latest_version(force=True)

    if not latest_tag:
        print_error("Failed to reach GitHub. Check your internet connection.")
        sys.exit(1)

    print(f"   Current Version  :  {VERSION}")
    print(f"   Latest Release   :  {latest_tag}")

    if latest_tag == VERSION:
        print_success("Sven is already fully up to date.")
        sys.exit(0)

    if not download_url:
        if source_tree_install_detected():
            print_info("source-tree install detected — download binary manually or run install.sh")
        else:
            print_error("Release exists, but Linux standalone binary was not found in assets.")
        sys.exit(1)

    print()
    if not confirm(f"Update Sven to v{latest_tag}?", default=True):
        print_info("Update aborted.")
        sys.exit(0)

    # Determine execution path
    executable_path = sys.executable
    if not executable_path or "python" in executable_path.lower():
        # If we aren't running as a frozen pyinstaller bin, attempt standard target
        executable_path = "/usr/bin/sven"
        
    print_info(f"Downloading v{latest_tag}...")
    
    # Download securely to a temporary file
    try:
        fd, temp_path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            chunk_resp = requests.get(download_url, stream=True, timeout=30)
            chunk_resp.raise_for_status()
            
            total_size = int(chunk_resp.headers.get('content-length', 0))
            downloaded = 0
            
            print("   ", end="") # indentation
            for chunk in chunk_resp.iter_content(chunk_size=1024 * 1024):
                if chunk: 
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        pct = int((downloaded / total_size) * 100)
                        mb_done = downloaded / (1024*1024)
                        mb_tot = total_size / (1024*1024)
                        print(f"\r   \033[94mDownloading:\033[0m {pct:3d}%  [{mb_done:.1f} MB / {mb_tot:.1f} MB]", end="", flush=True)
                    else:
                        mb_done = downloaded / (1024*1024)
                        print(f"\r   \033[94mDownloading:\033[0m {mb_done:.1f} MB downloaded...", end="", flush=True)
            print()
                
    except Exception as e:
        print_error(f"Download failed: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        sys.exit(1)

    print_info("Replacing binary...")
    try:
        # Atomic replace
        os.replace(temp_path, executable_path)
        
        # Ensure it is executable by everyone (755)
        os.chmod(executable_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        
        print_success(f"Successfully updated Sven to v{latest_tag}!")
        print("   The new version is now active.")
        
    except Exception as e:
        print_error(f"Failed to write executable to {executable_path}: {e}")
        sys.exit(1)

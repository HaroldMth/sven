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

# Github repo endpoint
REPO_LATEST_API = "https://api.github.com/repos/haroldmth/sven/releases/latest"
ASSET_NAME = "sven-linux-x86_64"

def run():
    print_section("Checking for Sven Auto-Updates")
    
    # Must be root to replace /usr/bin/sven
    if os.geteuid() != 0:
        print_error("self-update must be run as root.")
        print("   Try: sudo sven self-update")
        sys.exit(1)

    print_info("Contacting GitHub API...")
    try:
        resp = requests.get(REPO_LATEST_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print_error(f"Failed to check for updates: {e}")
        sys.exit(1)

    latest_tag = data.get("tag_name", "").lstrip("v")
    if not latest_tag:
        print_error("Failed to parse latest version from GitHub.")
        sys.exit(1)

    print(f"   Current Version  :  {VERSION}")
    print(f"   Latest Release   :  {latest_tag}")

    if latest_tag == VERSION:
        print_success("Sven is already fully up to date.")
        sys.exit(0)

    # Find the binary asset URL
    download_url = None
    for asset in data.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            download_url = asset.get("browser_download_url")
            break

    if not download_url:
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
            for chunk in chunk_resp.iter_content(chunk_size=8192):
                if chunk: f.write(chunk)
                
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


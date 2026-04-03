# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  core/updater.py — Centralized version management
# ============================================================

import os
import sys
import time
import json
import requests
from pathlib import Path

from ..constants import VERSION, DB_BASE
from ..ui.output import print_info, print_success, print_error

# Github repo endpoint
REPO_LATEST_API = "https://api.github.com/repos/haroldmth/sven/releases/latest"
UPDATE_CACHE_FILE = f"{DB_BASE}/update_check.json"
CHECK_INTERVAL = 86400  # 24 hours in seconds

def get_latest_version(force=False):
    """
    Checks GitHub API for the latest release tag.
    Caches the result locally for 24 hours unless forced.
    """
    now = time.time()
    
    # Check cache first
    cache_path = Path(UPDATE_CACHE_FILE)
    if not force and cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
                if now - data.get('last_check', 0) < CHECK_INTERVAL:
                    return data.get('version'), data.get('url')
        except:
            pass

    # Actually hit the API
    try:
        resp = requests.get(REPO_LATEST_API, timeout=5)
        resp.raise_for_status()
        release_data = resp.json()
        latest_tag = release_data.get("tag_name", "").lstrip("v")
        
        # Find asset URL for standalone bin
        download_url = None
        for asset in release_data.get("assets", []):
            if "linux-x86_64" in asset.get("name", ""):
                download_url = asset.get("browser_download_url")
                break
        
        # Update cache
        if latest_tag:
            try:
                os.makedirs(os.path.dirname(UPDATE_CACHE_FILE), exist_ok=True)
                with open(UPDATE_CACHE_FILE, 'w') as f:
                    json.dump({
                        'last_check': now,
                        'version': latest_tag,
                        'url': download_url
                    }, f)
            except:
                pass
                
        return latest_tag, download_url
        
    except Exception:
        # Silently fail for background checks to avoid annoying the user
        return None, None

def check_for_updates_silently():
    """
    One-line check during CLI startup. 
    If a new version is found, prints a subtle notification.
    """
    # Only perform the check if we haven't checked recently
    latest, _ = get_latest_version(force=False)
    
    if latest and latest != VERSION:
        # We print in faint yellow at the start
        print(f"\n\033[93m:: Note: A new version of Sven is available (v{latest}).\033[0m")
        print(f"\033[93m   Run 'sudo sven self-update' to upgrade.\033[0m\n")

def run_check_update():
    """Explicit sven check-update command."""
    print_info("Contacting GitHub for version information...")
    latest, _ = get_latest_version(force=True)
    
    if not latest:
        print_error("Failed to reach GitHub. Check your internet connection.")
        return

    print(f"   Current local version :  {VERSION}")
    print(f"   Latest remote version  :  {latest}")
    
    if latest == VERSION:
        print_success("Sven is already fully up to date.")
    else:
        print_info(f"Update available! Use 'sudo sven self-update' to upgrade to v{latest}.")

import os
import shutil
import subprocess
import sys

from ..constants import VERSION
from ..db.db_version import check_db_version, read_db_version
from ..ssl_bundle import clean_subprocess_env
from ..ui import print_banner, print_info, print_section


def _tool_version(cmd: list[str]) -> str:
    if not shutil.which(cmd[0]):
        return "not found"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False,
                              env=clean_subprocess_env(os.environ.copy()))
        line = (proc.stdout or proc.stderr or "").strip().splitlines()
        return line[0] if line else "available"
    except Exception:
        return "available (version unknown)"


def run():
    print_banner()
    print_section("Application and runtime versions")
    print_info(f"Sven          : {VERSION}")
    print_info(f"Python        : {sys.version.split()[0]}")
    print_info(f"Git           : {_tool_version(['git', '--version'])}")
    print_info(f"GnuPG         : {_tool_version(['gpg', '--version'])}")
    print_info(f"Tar           : {_tool_version(['tar', '--version'])}")
    print_info(f"zstd          : {_tool_version(['zstd', '--version'])}")

    db_ok, db_msg = check_db_version()
    db_ver = read_db_version()
    print_info(f"Local DB fmt  : {db_ver}")
    print_info(f"DB status     : {'ok' if db_ok else 'warning'} ({db_msg})")
    print()

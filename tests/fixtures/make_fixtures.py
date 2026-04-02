#!/usr/bin/env python3
import os
import subprocess
import shutil
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.resolve()
DB_DIR = FIXTURES_DIR / "fake_sync_db"
PKGS_DIR = FIXTURES_DIR / "fake_packages"

DB_DIR.mkdir(parents=True, exist_ok=True)
PKGS_DIR.mkdir(parents=True, exist_ok=True)

def write_db_desc(pkg_path: Path, name: str, version: str, desc: str):
    content = f"%NAME%\n{name}\n\n%VERSION%\n{version}\n\n%DESC%\n{desc}\n\n%URL%\nhttps://example.com/sys\n"
    (pkg_path / "desc").write_text(content)

def write_db_depends(pkg_path: Path, deps: list, provides: list, conflicts: list):
    content = ""
    if deps:
        content += "%DEPENDS%\n" + "\n".join(deps) + "\n\n"
    if provides:
        content += "%PROVIDES%\n" + "\n".join(provides) + "\n\n"
    if conflicts:
        content += "%CONFLICTS%\n" + "\n".join(conflicts) + "\n\n"
    if content:
        (pkg_path / "depends").write_text(content)

def build_db():
    print("Building fake sync DB...")
    db_build = DB_DIR / "build"
    db_build.mkdir(exist_ok=True)
    
    packages = [
        {"name": "bash", "ver": "5.2-1", "desc": "Bourne again shell", "deps": ["glibc>=2.38"], "prov": ["sh"], "conf": []},
        {"name": "glibc", "ver": "2.38-1", "desc": "GNU C Library", "deps": [], "prov": [], "conf": []},
        {"name": "neovim", "ver": "0.9.5-1", "desc": "Fork of Vim", "deps": ["libuv", "tree-sitter"], "prov": ["vim"], "conf": ["vim"]},
        {"name": "htop", "ver": "3.3.0-1", "desc": "Process viewer", "deps": ["ncurses"], "prov": [], "conf": []},
        {"name": "libuv", "ver": "1.48.0-1", "desc": "Multi-platform support library", "deps": ["glibc"], "prov": [], "conf": []},
        {"name": "tree-sitter", "ver": "0.22.2-1", "desc": "Parser generator tool", "deps": ["glibc"], "prov": [], "conf": []},
        {"name": "ncurses", "ver": "6.4-1", "desc": "System V Release 4.0 curses emulation library", "deps": ["glibc"], "prov": [], "conf": []},
    ]
    
    for p in packages:
        folder = db_build / f"{p['name']}-{p['ver']}"
        folder.mkdir(exist_ok=True)
        write_db_desc(folder, p["name"], p["ver"], p["desc"])
        write_db_depends(folder, p["deps"], p["prov"], p["conf"])
        
    subprocess.run(["tar", "-czf", "../core.db.tar.gz", "."], cwd=db_build)
    core_db = DB_DIR / "core.db"
    if core_db.exists(): core_db.unlink()
    os.symlink("core.db.tar.gz", core_db)
    shutil.rmtree(db_build)


def build_fake_pkg(name: str, files: dict):
    print(f"Building fake package: {name}")
    build_dir = PKGS_DIR / f"{name}_build"
    build_dir.mkdir(exist_ok=True)
    
    for fname, fcontent in files.items():
        dst = build_dir / fname
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(fcontent)
        
    subprocess.run(["tar", "-I", "zstd", "-cf", f"../{name}.pkg.tar.zst", "."], cwd=build_dir)
    shutil.rmtree(build_dir)

def build_pkgs():
    print("Building fake packages...")
    
    build_fake_pkg("clean", {
        ".PKGINFO": "pkgname = clean\npkgver = 1.0-1\n",
        "usr/bin/clean_tool": "#!/bin/bash\necho 'clean'",
    })
    
    build_fake_pkg("with_install", {
        ".PKGINFO": "pkgname = with_install\npkgver = 1.0-1\n",
        ".INSTALL": "post_install() {\n  echo 'post install ran'\n}\n",
        "usr/bin/install_tool": "#!/bin/bash\necho 'install'",
    })
    
    build_fake_pkg("systemd_hook", {
        ".PKGINFO": "pkgname = systemd_hook\npkgver = 1.0-1\n",
        ".INSTALL": "post_install() {\n  systemctl daemon-reload\n  systemctl enable systemd_hook.service\n  systemctl start systemd_hook\n}\n",
        "usr/bin/systemd_tool": "#!/bin/bash\necho 'systemd_hook'",
    })

if __name__ == "__main__":
    build_db()
    build_pkgs()
    print("Fixtures ready.")

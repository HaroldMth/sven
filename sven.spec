# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

datas = [
    ('initscripts', 'initscripts'),
]

import os
if os.path.exists('sven.conf.default'):
    datas.append(('sven.conf.default', 'etc/sven'))

a = Analysis(
    ['run_sven.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['requests', 'zstandard', 'gnupg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='sven',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

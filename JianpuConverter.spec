# -*- mode: python ; coding: utf-8 -*-

# This spec is location-independent: all paths are resolved relative to this
# file (SPECPATH) so the same spec builds correctly from any checkout folder.

import os

_app = os.path.join(SPECPATH, 'app_gui.py')
_pathex = [os.path.join(SPECPATH, 'jianpu_ly_patched')]
_icon = [os.path.join(SPECPATH, 'assets', 'app.ico')]

a = Analysis(
    [_app],
    pathex=_pathex,
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JianpuConverter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JianpuConverter',
)

# -*- mode: python ; coding: utf-8 -*-


# Jianpu Converter -- PyInstaller build script (onedir).
#
#   .venv\Scripts\python -m PyInstaller JianpuConverter.spec
#   Copy-Item -Recurse -Force lilypond-2.26.0 dist\JianpuConverter\
#   makensis installer\JianpuConverter.nsi
#
# app_gui.py is a thin launcher for the jianpu_converter package; pathex lists
# the repo root (so the package is found) BEFORE jianpu_ly_patched (so the
# pre-patched 128th-ready jianpu_ly is bundled instead of the stock one).

a = Analysis(
    ['D:/jianpu/app_gui.py'],
    pathex=['D:/jianpu', 'D:/jianpu/jianpu_ly_patched'],
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
    icon=['D:/jianpu/assets/app.ico'],
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

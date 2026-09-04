"""Build-time patcher: create a 128th-ready copy of jianpu_ly.

PyInstaller bundles modules as compiled code, so the runtime patch in
app_gui (which needs the source file) cannot run inside the frozen .exe.
This script therefore generates a pre-patched package at
jianpu_ly_patched/jianpu_ly and the PyInstaller build must use
--paths jianpu_ly_patched so the patched copy is bundled instead of the
stock site-packages one.

Usage:
    python patch_jianpu_ly_src.py
"""

import importlib
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

import app_gui  # provides _JIANPU_LY_DICT_PATCHES / _JIANPU_LY_FUNC_PATCHES

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "jianpu_ly_patched")
PKG_DIR = os.path.join(OUT_DIR, "jianpu_ly")


def main():
    jianpu_ly = importlib.import_module("jianpu_ly")
    src_path = jianpu_ly.__file__
    with open(src_path, encoding="utf-8") as f:
        src = f.read()

    # Apply every replacement used by the runtime patch, plus the module
    # level note_regex fix and the "already patched" marker.
    for old, new in app_gui._JIANPU_LY_DICT_PATCHES:
        if old not in src:
            print("WARN: dict patch not found:", old[:60])
        src = src.replace(old, new)
    for old, new in app_gui._JIANPU_LY_FUNC_PATCHES:
        if old not in src:
            print("WARN: func patch not found:", old[:60])
        src = src.replace(old, new)
    src = src.replace("'cqsdh", "'cqsdhp")  # note_regex char classes
    if "_JIANPU_LY_PATCHED" not in src:
        src += "\n_JIANPU_LY_PATCHED = True\n"

    os.makedirs(PKG_DIR, exist_ok=True)
    with open(os.path.join(PKG_DIR, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(src)
    shutil.copy2(os.path.join(os.path.dirname(src_path), "__main__.py"),
                 os.path.join(PKG_DIR, "__main__.py"))
    shutil.copytree(os.path.join(os.path.dirname(src_path), "__pycache__"),
                    os.path.join(PKG_DIR, "__pycache__"),
                    dirs_exist_ok=True)

    print("patched jianpu_ly written to:", PKG_DIR)
    print("128th in types table:", '"128th":"p"' in src)
    print("7/8 tuplet support:", "7/8[" in src)
    print("marker:", "_JIANPU_LY_PATCHED = True" in src)


if __name__ == "__main__":
    main()

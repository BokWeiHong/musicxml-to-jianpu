# Copyright (C) 2026 BokWeiHong
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under the GNU GPL v3 or later; see LICENSE.
"""Bump the app version in every place it is written.

Usage::

    python bump_version.py 1.0.1     # set an exact version
    python bump_version.py patch     # 1.0.0 -> 1.0.1
    python bump_version.py minor     # 1.0.0 -> 1.1.0
    python bump_version.py major     # 1.0.0 -> 2.0.0

Files updated (the version only ever lives in these places):
  jianpu_converter/__init__.py    __version__          (what the updater checks)
  installer/JianpuConverter.nsi   APP_VERSION          (also names the setup .exe)
  README.md                       JianpuConverter-Setup-<version>.exe
  release/README.txt              JianpuConverter-Setup-<version>.exe

After bumping, rebuild and publish::

    python patch_jianpu_ly_src.py
    python -m PyInstaller JianpuConverter.spec
    Copy-Item -Recurse -Force lilypond-2.26.0 dist\\JianpuConverter\\
    tools\\nsis\\nsis-3.09\\makensis.exe installer\\JianpuConverter.nsi
    python publish_release.py --notes "what changed"
"""


import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
INIT_PY = os.path.join(ROOT, "jianpu_converter", "__init__.py")
NSI = os.path.join(ROOT, "installer", "JianpuConverter.nsi")
README = os.path.join(ROOT, "README.md")
RELEASE_README = os.path.join(ROOT, "release", "README.txt")

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_version():
    """Return the version currently declared in jianpu_converter/__init__.py."""
    with open(INIT_PY, encoding="utf-8") as handle:
        match = re.search(r'^__version__\s*=\s*"([^"]+)"', handle.read(), re.M)
    if not match:
        raise SystemExit("Could not find __version__ in %s" % INIT_PY)
    return match.group(1)


def next_version(current, kind):
    """Compute the next version: kind is 'major', 'minor' or 'patch'."""
    major, minor, patch = (int(p) for p in current.split("."))
    if kind == "major":
        return "%d.0.0" % (major + 1)
    if kind == "minor":
        return "%d.%d.0" % (major, minor + 1)
    if kind == "patch":
        return "%d.%d.%d" % (major, minor, patch + 1)
    raise SystemExit("Unknown bump kind: %s (use major/minor/patch or x.y.z)"
                     % kind)


def _sub_file(path, pattern, new_version, label):
    if not os.path.isfile(path):
        print("  skip   %-32s (missing)" % label)
        return 0
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    new_text, count = re.subn(pattern, lambda m: m.group(1) + new_version
                              + m.group(2), text)
    if count:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(new_text)
    print("  %-6s %-32s %d change(s)" % ("update" if count else "same",
                                         label, count))
    return count


def apply_version(old_version, new_version):
    """Write new_version into every file that stores it."""
    print("Bumping %s -> %s" % (old_version, new_version))
    _sub_file(INIT_PY,
              r'(__version__\s*=\s*")[^"]+(")', new_version,
              "jianpu_converter/__init__.py")
    _sub_file(NSI,
              r'(!define APP_VERSION\s+")[^"]+(")', new_version,
              "installer/JianpuConverter.nsi")
    for label, path in (("README.md", README),
                        ("release/README.txt", RELEASE_README)):
        _sub_file(path,
                  r"(JianpuConverter-Setup-)" + re.escape(old_version)
                  + r"(\.exe)", new_version, label)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    current = read_version()
    wanted = args[0]
    new_version = wanted if VERSION_RE.match(wanted) else next_version(
        current, wanted)
    if new_version == current:
        raise SystemExit("Already at %s - nothing to do." % current)
    apply_version(current, new_version)
    print("\nNext steps (this order matters):")
    print("  1. python patch_jianpu_ly_src.py")
    print("  2. python -m PyInstaller JianpuConverter.spec")
    print("  3. Copy-Item -Recurse -Force lilypond-2.26.0 dist\\JianpuConverter\\")
    print("  4. tools\\nsis\\nsis-3.09\\makensis.exe installer\\JianpuConverter.nsi")
    print('  5. python publish_release.py --notes "what changed"')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

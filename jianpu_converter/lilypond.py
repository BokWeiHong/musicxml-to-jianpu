"""LilyPond engine discovery and cache maintenance.

find_lilypond() resolves the engraver in a fixed order (LILYPOND env var,
system PATH, then portable trees next to the app).  _freshen_lilypond_ccache()
fixes the timestamp mismatch that portable LilyPond trees get after git
checkouts / zips / installers, which otherwise makes Guile try to recompile
its own core modules and crash with a "Wrong number of arguments" error.
"""


import os
import shutil
import sys
import time


def find_lilypond():
    """Return the path of a usable lilypond executable, or None."""
    # 1) Explicit LILYPOND environment variable
    cand = os.environ.get("LILYPOND")
    if cand:
        if os.path.isfile(cand):
            return cand
        p = os.path.join(cand, "lilypond.exe")
        if os.path.isfile(p):
            return p

    # 2) Already on the system PATH
    found = shutil.which("lilypond")
    if found:
        return found

    # 3) Portable installs near the app / script / cwd / PyInstaller bundle
    base_dirs = [
        os.path.dirname(sys.executable),             # location of the .exe
        os.path.dirname(os.path.abspath(__file__)),  # location of this script
        os.getcwd(),
    ]
    if getattr(sys, "_MEIPASS", None):               # PyInstaller --onefile
        base_dirs.append(sys._MEIPASS)

    for base in base_dirs:
        for direct in (os.path.join(base, "lilypond.exe"),
                       os.path.join(base, "bin", "lilypond.exe")):
            if os.path.isfile(direct):
                return direct
        try:
            for entry in os.listdir(base):
                folder = os.path.join(base, entry)
                if entry.lower().startswith("lilypond") and os.path.isdir(folder):
                    p = os.path.join(folder, "bin", "lilypond.exe")
                    if os.path.isfile(p):
                        return p
        except OSError:
            pass
    return None


def _freshen_lilypond_ccache(lilypond_exe):
    """Make LilyPond's precompiled Guile/LilyPond caches usable again.

    Portable / bundled LilyPond trees (like the ``lilypond-2.26.0`` folder
    shipped next to this app) frequently end up with compiled ``.go`` cache
    files whose timestamps are OLDER than their ``.scm`` sources.  That
    happens because git checkouts, zip extraction and installers do not
    preserve the original file timestamps.

    When that happens, Guile (LilyPond's Scheme interpreter) believes it must
    byte-recompile its own core modules (``ice-9/eval.scm``, ...) on the next
    run.  The recompilation takes minutes and commonly aborts with::

        ERROR: In procedure apply-smob/1:
        Wrong number of arguments to #<boot-closure ... (_ . _)>

    which surfaces to the user as "Failed to generate Jianpu".  Touching the
    shipped ``.go`` files so they are newer than every source file makes Guile
    trust the precompiled bytecode and start normally (a few hundred file
    mtimes, done once per conversion, well under a tenth of a second).

    Only touches files under ``<lilypond-root>/lib`` (the Guile ccache and the
    LilyPond ccache live there in every supported layout).  Runs are cheap and
    idempotent; permission errors (e.g. a read-only system install) are
    ignored -- system installs normally ship consistent timestamps anyway.
    """
    root = os.path.dirname(os.path.dirname(lilypond_exe))  # folder with bin/
    lib_dir = os.path.join(root, "lib")
    if not os.path.isdir(lib_dir):
        return 0
    now = time.time()
    touched = 0
    for dirpath, _dirnames, filenames in os.walk(lib_dir):
        for name in filenames:
            if name.endswith(".go"):
                try:
                    os.utime(os.path.join(dirpath, name), (now, now))
                    touched += 1
                except OSError:
                    pass
    return touched


# Note types jianpu_ly cannot typeset. After the 128th patch below, the
# shortest supported value is a 128th note ("p"); anything faster is mapped
# to 128th, and anything longer than a whole note is printed as a whole.
# Bar alignment is unaffected because jianpu_ly measures bars from the same
# duration table we extend.

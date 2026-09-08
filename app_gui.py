"""MusicXML -> Jianpu (简谱) PDF Converter  —  desktop launcher.

This file used to contain the whole application; the code now lives in the
``jianpu_converter`` package (read the docstrings of its modules for an
overview).  ``app_gui.py`` is kept as the entry point so that double-clicking,
the ".musicxml open with" file association and the PyInstaller spec all keep
working unchanged.

Run from the repository root::

    python app_gui.py ["path/to/song.musicxml"]
"""
import sys

from jianpu_converter.gui import main

if __name__ == "__main__":
    sys.exit(main())

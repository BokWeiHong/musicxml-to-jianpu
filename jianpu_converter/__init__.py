"""jianpu_converter — MusicXML → 简谱 (Jianpu) PDF converter package.

The application used to be a single ~1300-line file (app_gui.py).  To keep it
easy to read and maintain, it is organised here by responsibility:

=================  ==========================================================
Module             Responsibility
=================  ==========================================================
lilypond.py        Find the LilyPond engraver and keep its cache healthy.
musicxml.py        Read/clean the input score (.musicxml/.xml/.mxl) and
                   extract title/composer/arranger/instrument metadata.
layout.py          Every edit applied to the generated .ly before compiling
                   (PDF header markup, fonts, dynamics, sweep arrows).
patches.py         Fixes for stock jianpu_ly (128th notes, tuplets, …) —
                   canonical tables + the runtime patcher.
convert.py         The pipeline: convert_musicxml_to_jianpu(xml_path,
                   header_meta=None) → path of the finished PDF.
gui.py             The tkinter GUI (JianpuConverterApp) and main() entry.
=================  ==========================================================

Launch it from the repository root with either::

    python app_gui.py                # classic entry point (kept for the exe)
    python -m jianpu_converter       # package entry point
"""

from .convert import convert_musicxml_to_jianpu

__version__ = "1.0.0"
__all__ = ["convert_musicxml_to_jianpu"]

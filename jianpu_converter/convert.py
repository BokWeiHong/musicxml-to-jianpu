# Copyright (C) 2026 BokWeiHong
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under the GNU GPL v3 or later; see LICENSE.
"""The conversion pipeline (MusicXML file -> Jianpu PDF path).

convert_musicxml_to_jianpu() is the orchestrator: prepare a scratch input,
patch + run jianpu_ly in-process, post-process the resulting .ly with the
layout module, freshen and invoke LilyPond, then move the PDF next to the
original file with lock-safe alternative names.  _StreamSink keeps warnings
readable when the windowed (--noconsole) build has no stdout/stderr.
"""


import io
import os
import shutil
import subprocess
import sys
import tempfile

from .layout import (_expand_empty_bar_rests, _fit_instrument_names,
                     _fix_finger_marks, _fix_trill_spanners, _hide_bar_numbers,
                     _inject_cjk_text_font, _inject_dynamic_font_size,
                     _inject_header_layout, _inject_note_number_font_size,
                     _mark_sweep_arrows, _replace_header_blocks)
from .lilypond import _freshen_lilypond_ccache, find_lilypond
from .musicxml import _prepare_xml_input, extract_musicxml_metadata
from .patches import _patch_jianpu_ly


class _StreamSink:
    """Write-only sink for the --noconsole GUI build, where Python's
    sys.stdout/sys.stderr are None.  jianpu_ly writes warnings to stderr;
    with None streams every warning crashes the whole conversion."""

    def __init__(self, buffer):
        self._buffer = buffer

    def write(self, s):
        if isinstance(s, bytes):
            s = s.decode("utf-8", "replace")
        self._buffer.write(s)
        return len(s)

    def flush(self):
        pass

    def isatty(self):
        return False

    encoding = "utf-8"
    errors = "replace"





def convert_musicxml_to_jianpu(xml_path, header_meta=None, bar_number_every=5):
    """
    Convert a MusicXML file to a Jianpu PDF next to the original file.

    bar_number_every: print a measure number every N bars (5 -> 5, 10, 15...).
                      None/0 prints no bar numbers at all.

    Returns the path of the generated PDF. Raises RuntimeError on failure.
    """
    base_dir = os.path.dirname(xml_path)
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    out_pdf_target = os.path.join(base_dir, f"{base_name}_jianpu.pdf")

    lilypond_exe = find_lilypond()
    if not lilypond_exe:
        raise RuntimeError(
            "Could not find LilyPond.\n\n"
            "Please do one of the following:\n"
            "  - install LilyPond and add it to your PATH\n"
            "  - set the LILYPOND environment variable\n"
            "  - keep a portable lilypond-*/bin/lilypond.exe folder\n"
            "    next to this application"
        )

    try:
        import jianpu_ly
        _patch_jianpu_ly(jianpu_ly)   # add real 128th-note support
    except ImportError:
        raise RuntimeError(
            "The jianpu_ly package is not installed.\n\n"
            "Run: pip install jianpu-ly"
        )

    temp_dir = tempfile.mkdtemp(prefix="jianpu_")
    temp_ly = os.path.join(temp_dir, f"{base_name}.ly")
    temp_pdf_base = os.path.join(temp_dir, base_name)
    temp_pdf = os.path.join(temp_dir, f"{base_name}.pdf")

    # --noconsole GUI builds have sys.stdout/sys.stderr = None, which makes
    # jianpu_ly crash when it emits warnings ("'NoneType' object has no
    # attribute 'write'").  Redirect them to a sink for the duration of the
    # conversion and keep any warnings for the error dialog.
    saved_stdout, saved_stderr = sys.stdout, sys.stderr
    warn_buf = io.StringIO()
    sink = _StreamSink(warn_buf)
    sys.stdout = sink if sys.stdout is None else sys.stdout
    sys.stderr = sink if sys.stderr is None else sys.stderr

    try:
        # Help jianpu_ly's version detection find the resolved engine
        lp_dir = os.path.dirname(lilypond_exe)
        os.environ["PATH"] = lp_dir + os.pathsep + os.environ.get("PATH", "")

        # "--noStaff" behaviour: force no Western 5-line staff
        jianpu_ly.force_staff = False
        jianpu_ly.export = jianpu_ly.unicode_approx = False

        # Bar numbering: jianpu_ly reads this module-level value while it
        # builds each score (5 = number every 5th bar).  A falsey value means
        # "no numbers", which is applied after generation by hiding the
        # BarNumber stencil.
        hide_bar_numbers = not bar_number_every
        if not hide_bar_numbers:
            jianpu_ly.bar_number_every = max(1, int(bar_number_every))

        # 1. jianpu_ly: MusicXML -> Jianpu LilyPond source (in-process)
        #    (first normalize exotic note types jianpu_ly cannot print)
        input_path = _prepare_xml_input(xml_path, temp_dir)
        in_dat = jianpu_ly.get_input([input_path])
        ly_source = jianpu_ly.process_input(in_dat)

        # Metadata (title/composer/instrument) drives the PDF header layout
        # (see extract_musicxml_metadata/_inject_header_layout).  The GUI lets
        # the user confirm/edit these values before exporting and passes them
        # in header_meta; when header_meta is provided its values are
        # authoritative - including empty ones, so a cleared field stays
        # cleared instead of being resurrected from the file.
        meta = {}
        if header_meta is not None:
            meta = {k: (header_meta.get(k) or "").strip()
                    for k in ("title", "composer", "arranger", "instrument")}
        else:
            try:
                meta = extract_musicxml_metadata(input_path)
            except Exception:
                meta = {}  # never fail the whole conversion over a header
        # Always rewrite the \header blocks and the scoreTitleMarkup.  The
        # header builders simply omit blank fields, and jianpu_ly would
        # otherwise re-fill them from the MusicXML - so a field that is empty
        # or could not be found is guaranteed to stay empty in the PDF.
        ly_source = _replace_header_blocks(ly_source, meta)
        ly_source = _inject_header_layout(ly_source, meta)


        # jianpu_ly cannot resize its dynamic marks; inject the smaller
        # DynamicText override into every voice before LilyPond compiles.
        ly_source = _inject_dynamic_font_size(ly_source)

        # Staccato notes carried a symbol the music font has no glyph for
        # (LilyPond dropped the mark), and trills were drawn twice with a
        # never-closed wavy line trailing into the following bars.
        ly_source = _fix_finger_marks(ly_source)
        ly_source = _fix_trill_spanners(ly_source)

        # Make the jianpu numbers themselves bigger (not the dynamics/text).
        ly_source = _inject_note_number_font_size(ly_source)

        # Instrument names: reserve the room a full score's names need, show
        # them on every system, and give every line one shared left edge.  The
        # same step also removes the duplicate time signature LilyPond prints
        # at both ends of a system break.
        ly_source = _fit_instrument_names(ly_source)

        # Empty measures print one "0" per beat (whole-bar rest -> 0 0 0 0).
        ly_source = _expand_empty_bar_rests(ly_source)

        # Chosen "no bar numbers" mode hides LilyPond's measure numbers.
        if hide_bar_numbers:
            ly_source = _hide_bar_numbers(ly_source)

        # Chinese annotations (扫弦/扫 etc.) must render in a CJK font.
        ly_source = _inject_cjk_text_font(ly_source)

        # Attach ascending-sweep arrows to collapsed octave runs.
        ly_source = _mark_sweep_arrows(ly_source)

        # Save strictly as UTF-8
        with open(temp_ly, "w", encoding="utf-8") as f:
            f.write(ly_source)

        # 2. lilypond: Jianpu LilyPond source -> PDF
        #    Bundled/portable LilyPond trees can carry ccache .go files older
        #    than their .scm sources (git checkouts / zips / installers do not
        #    preserve timestamps); Guile then tries to byte-recompile its own
        #    core modules and dies with "Wrong number of arguments to
        #    #<boot-closure ...>".  Freshen the cache so compilation starts
        #    immediately with the shipped bytecode.
        _freshen_lilypond_ccache(lilypond_exe)

        # In the windowed (--noconsole) .exe build a console child process
        # would flash a black window on every conversion; CREATE_NO_WINDOW
        # keeps LilyPond (and its helper processes) invisible.
        run_kwargs = {}
        if os.name == "nt":
            run_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        proc = subprocess.run(
            [lilypond_exe, "-o", temp_pdf_base, temp_ly],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **run_kwargs
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "LilyPond compilation error:\n" + (proc.stderr or "")[-2000:]
            )

        if not os.path.exists(temp_pdf):
            raise FileNotFoundError("LilyPond finished without creating a PDF file.")

        # 3. Move the finished PDF next to the original MusicXML file
        #    (shutil.move, not os.replace: the temp dir and the target
        #    folder may live on different disk drives).  If the primary
        #    output name is locked (e.g. open in a PDF viewer), fall back
        #    to an alternative name instead of failing.
        target = out_pdf_target
        alt = 1
        while True:
            try:
                if os.path.exists(target):
                    os.remove(target)
                shutil.move(temp_pdf, target)
                break
            except OSError as err:
                if target != out_pdf_target or not os.path.exists(out_pdf_target):
                    raise
                alt += 1
                target = os.path.join(base_dir, f"{base_name}_jianpu_{alt}.pdf")

        return target
    except Exception as err:
        extra = warn_buf.getvalue().strip()
        if extra:
            err.args = ("%s\n\n[jianpu_ly diagnostics]\n%s" % (err, extra),) + err.args[1:]
        raise
    finally:
        sys.stdout, sys.stderr = saved_stdout, saved_stderr
        shutil.rmtree(temp_dir, ignore_errors=True)

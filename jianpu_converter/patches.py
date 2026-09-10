# Copyright (C) 2026 BokWeiHong
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under the GNU GPL v3 or later; see LICENSE.
"""Fixes for the stock jianpu_ly 1.889 library.

jianpu_ly cannot typeset 128th notes (KeyError('128th')) and silently halves
non-power-of-two tuplets (7:8, 8:7 ...).  _JIANPU_LY_DICT_PATCHES /
_JIANPU_LY_FUNC_PATCHES are the canonical replacements; _patch_jianpu_ly()
applies them to the installed library at RUNTIME (source installs).
The build tool patch_jianpu_ly_src.py re-applies the same tables at BUILD
time for the frozen .exe -- keep the two worlds in sync.
"""


import sys


# ---------------------------------------------------------------------------
# jianpu_ly 1.889 cannot handle 128th-note durations (crashes with
# KeyError('128th')) and silently halves non-power-of-2 tuplets (e.g. 7:8).
# The tables below patch the library source so it:
#   * knows a "p" duration letter = 128th note (5 beams, half of a 64th)
#   * keeps tuplets as "actual/normal[" (e.g. 7/8[) instead of plain "7["
# They are applied at RUNTIME (source installs) via _patch_jianpu_ly and at
# BUILD TIME (for the frozen .exe) by patch_jianpu_ly_src.py.
# ---------------------------------------------------------------------------

# xml2jianpu keeps its duration tables as function-local dicts; these edits
# add "128th" to each table and make tuplets carry their actual/normal ratio.
_JIANPU_LY_DICT_PATCHES = (
    ('types={"64th":"h",', 'types={"128th":"p","64th":"h",'),
    ('typesDot={"64th":"h.",', 'typesDot={"128th":"p.","64th":"h.",'),
    ('typesMM={"64th":"64",', 'typesMM={"128th":"128","64th":"64",'),
    ('quavers={"64th":F(1,8),', 'quavers={"128th":F(1,16),"64th":F(1,8),'),
    ('durByQuavers = {F(1,8):"h",', 'durByQuavers = {F(1,16):"p",F(1,8):"h",'),
    ('ourRet.append(tuplet+"[")',
     'ourRet.append((tuplet + (("/" + tupletNormal) if tupletNormal else "")) + "[")'),
    ('if ourI==0: paddingRestList.append(tuplet+"[")',
     'if ourI==0: paddingRestList.append((tuplet + (("/" + tupletNormal) if tupletNormal else "")) + "[")'),
)

# Every function that hard-codes the duration letters gets "p" added, so all
# code paths (notes, chords, grace notes, beaming, western-staff output, the
# tuplet parser) accept 128th notes and "actual/normal[" tuplets.
_JIANPU_LY_FUNC_PATCHES = (
    ("[\\\\qsdh.]", "[\\\\qsdhp.]"),                     # chord/note parsing
    ("[cqsdh\\\\]", "[cqsdhp\\\\]"),                     # parseNote regex
    ("\"cqsdh\"", "\"cqsdhp\""),                         # parseNote index
    ("'cqsdh", "'cqsdhp"),                               # note_regex classes
    ("'qsdh'", "'qsdhp'"),                               # grace/chord letters
    ("1-9qsdh", "1-9qsdhp"),                             # grace group regexes
    ("{'q':8, 's':16, 'd':32, 'h':64}",                     # western-staff durations
     "{'q':8, 's':16, 'd':32, 'h':64, 'p':128}"),
    # jianpu_ly bug: this "strip final barline before repeat" regex uses
    # unescaped | and . so it eats the last two characters of ANY barline
    # string (e.g. \bar ".|" becomes \bar ".", a LilyPond syntax error).
    (r"""re.sub(r' \\bar "|."$',"",out[-1])""",
     r"""re.sub(r' \\bar "\|\.$',"",out[-1])"""),
    # jianpu_ly bug: the OctavesAfter directive is only emitted for the
    # first part of multi-part scores, so later parts fail with "Ambiguous
    # octave marks".  Default to "after" (what xml2jianpu always emits).
    ("self.octavesPosition = None",
     "self.octavesPosition = \"after\" # jianpu-patched default"),

    # Rests are engraved like notes with "-" continuations (0 – – –).  A rest
    # should read as zeros, so every dash that CONTINUES A REST prints "0"
    # instead (whole rest -> 0 0 0 0, half rest -> 0 0).  Dashes that continue
    # a real note keep the dash, because only notes sustain.
    # (single-line anchors on purpose: patch_jianpu_ly_src.py replaces them in
    #  the raw file, while the runtime patcher replaces them after dedenting -
    #  anchors without leading whitespace match in both worlds)
    (r'''if not_angka: figureDash=u"."''',
     r'''if not_angka: figureDash=u"0" if self.last_was_rest else u"."'''),
    (r'''else: figureDash=u"\u2013"''',
     r'''else: figureDash=u"0" if self.last_was_rest else u"\u2013"'''),

    # classic "3[" shorthand.
    ("""            elif re.match(r"[1-9][0-9]*\\[$",word):
                # tuplet start, e.g. 3[
                fitIn = int(word[:-1])
                i=2
                while i<fitIn: i*=2
                if i==fitIn: num=int(fitIn*3/2)
                else: num=int(i/2)
                out.append("\\\\times %d/%d {" % (num,fitIn))
                notehead_markup.tuplet = (num,fitIn)""",
     """            elif re.match(r"[1-9][0-9]*(?:/[1-9][0-9]*)?\\[$",word):
                # tuplet start, e.g. 3[  or  7/8[  (actual/normal notes)
                body = word[:-1]
                if "/" in body:
                    a, b = body.split("/")
                    num, fitIn = int(b), int(a)
                else:
                    fitIn = int(body)
                    i=2
                    while i<fitIn: i*=2
                    if i==fitIn: num=int(fitIn*3/2)
                    else: num=int(i/2)
                out.append("\\\\times %d/%d {" % (num,fitIn))
                notehead_markup.tuplet = (num,fitIn)"""),
)



def _patch_jianpu_ly(jianpu_ly):
    """Give jianpu_ly real 128th-note support at runtime.

    jianpu_ly 1.889 only knows durations down to 64th notes, so MusicXML
    files with 128th notes crash with KeyError('128th').  This adds a
    "p" duration letter (5 beams, toAdd = 1/2 unit) to every place the
    duration letters c/q/s/d/h are recognised, so bars stay perfectly
    aligned and the notes render as true 128th notes in the PDF.

    Safe to call repeatedly (no-op once applied).
    """
    import inspect
    import textwrap

    if getattr(jianpu_ly, "_JIANPU_LY_PATCHED", False):
        return
    if getattr(sys, "frozen", False):
        # In the packaged .exe the module is already pre-patched at build
        # time (patch_jianpu_ly_src.py); without that we have no source file
        # to rebuild from, so fail loudly rather than convert incorrectly.
        raise RuntimeError(
            "The bundled jianpu_ly is not 128th-ready; rebuild the app with "
            "patch_jianpu_ly_src.py in the PyInstaller path."
        )

    _XML_DICT_PATCHES = _JIANPU_LY_DICT_PATCHES
    _REPLACEMENTS = _JIANPU_LY_FUNC_PATCHES
    jianpu_ly.note_regex = jianpu_ly.note_regex.replace("'cqsdh", "'cqsdhp")

    orig_names = set(vars(jianpu_ly))
    # Snapshot the module items BEFORE any rebuild so rebuilt functions
    # (whose source lives in "<patched ...>" strings) are not re-examined.
    module_items = list(vars(jianpu_ly).items())

    def rebuild(obj, owner, name, replacements):
        src = textwrap.dedent(inspect.getsource(obj))
        for old, new in replacements:
            src = src.replace(old, new)
        code = compile(src, "<patched jianpu_ly.%s>" % name, "exec")
        exec(code, vars(jianpu_ly))          # module globals stay available
        setattr(owner, name, vars(jianpu_ly)[name])
        if name in vars(jianpu_ly) and name not in orig_names:
            delattr(jianpu_ly, name)         # drop stray names from exec

    rebuild(jianpu_ly.xml2jianpu, jianpu_ly, "xml2jianpu", _XML_DICT_PATCHES)

    def needs_patch(obj):
        try:
            src = inspect.getsource(obj)
        except OSError:
            return False
        return "qsdh" in src or "cqsdh" in src

    for name, obj in module_items:
        if inspect.isclass(obj) and getattr(obj, "__module__", "") == "jianpu_ly":
            for mname, mobj in list(vars(obj).items()):
                if inspect.isfunction(mobj) and needs_patch(mobj):
                    rebuild(mobj, obj, mname, _REPLACEMENTS)
        elif (inspect.isfunction(obj)
              and getattr(obj, "__module__", "") == "jianpu_ly"
              and needs_patch(obj)):
            rebuild(obj, jianpu_ly, name, _REPLACEMENTS)

    # Multi-part scores only carry the OctavesAfter directive in part 1;
    # default the octave convention to "after" for every part.
    rebuild(
        jianpu_ly.NoteheadMarkup.initOneScore,
        jianpu_ly.NoteheadMarkup,
        "initOneScore",
        (("self.octavesPosition = None",
          "self.octavesPosition = \"after\" # jianpu-patched default"),),
    )

    jianpu_ly._JIANPU_LY_PATCHED = True

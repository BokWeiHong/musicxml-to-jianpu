# Copyright (C) 2026 BokWeiHong
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under the GNU GPL v3 or later; see LICENSE.
"""Every change applied to the jianpu_ly-generated .ly before compiling.

  * header replacement + scoreTitleMarkup   -> the PDF sheet-music header
    (title centred large/bold SimHei, instrument left, credits right);
  * _inject_dynamic_font_size               -> smaller dynamics;
  * _inject_cjk_text_font                   -> KaiTi for Chinese text marks;
  * _fix_finger_marks                       -> staccato as a real "x" glyph
    above the number;
  * _fix_trill_spanners                     -> one "tr" per trill, plus the
    wavy line showing where the trill ends;
  * _inject_note_number_font_size           -> bigger jianpu digit glyphs;
  * _fit_instrument_names                   -> room for full-score instrument
    names, repeated on every system;
  * _set_first_line_indent                  -> one shared left edge on every
    line, and no time signature printed twice at a system break;
  * _expand_empty_bar_rests                 -> empty bars print 0 0 0 0;
  * _hide_bar_numbers                       -> optional "no bar numbers" mode;
  * _mark_sweep_arrows                      -> ascend arrow over collapsed runs.

Strings containing LilyPond backslash syntax are assembled with chr(92) /
chr(34) on purpose (never literal backslashes) so the source stays readable
and CRLF/git friendly.
"""


import re


_JIANPU_DYNAMIC_FONT_SIZE = -3

# Size (in LilyPond \fontsize steps, each step ~20% larger) applied to the
# jianpu number glyphs only.  jianpu_ly engraves every digit (and the "0"
# rest, and the "–" sustain dashes) through the same note-mod markup, so
# injecting a \fontsize there never touches dynamics, Chinese marks or the
# header.
_JIANPU_NOTE_FONT_SIZE = 1

# The exact markup jianpu_ly 1.889 uses for both note heads and rests.
_JIANPU_NOTE_MARKUP_RE = re.compile(
    r"(\\markup \\lower #0\.5 )\\sans \\bold #text"
)


def _inject_dynamic_font_size(ly_source):
    """Insert a font-size override for DynamicText into every voice."""
    size = _JIANPU_DYNAMIC_FONT_SIZE
    if size is None:
        return ly_source
    voice_open = re.compile(r'\\new Voice\s*=\s*"[^"]*"\s*\{')
    if not voice_open.search(ly_source):
        return ly_source  # unexpected layout: leave the file untouched
    return voice_open.sub(
        lambda m: m.group(0) + "\n\\override DynamicText.font-size = #%s" % size,
        ly_source)
_JIANPU_CJK_FONT = "KaiTi"   # guzheng/erhu scores annotate sweeps etc. in KaiTi


def _inject_cjk_text_font(ly_source, font_name=_JIANPU_CJK_FONT):
    """Render MusicXML <words> Chinese annotations in a CJK-capable font.

    jianpu_ly imports <words> (e.g. the guzheng sweep marks "扫"/"扫弦") as
    plain text scripts (^"扫弦") and drops the font-family the score asked
    for.  LilyPond then draws them via Pango's automatic fallback (usually
    SimSun), not KaiTi.  Rewrite every text script that contains CJK
    characters to use the intended font instead.
    """
    if not re.search(r"[\u4e00-\u9fff]", ly_source):
        return ly_source
    script_re = re.compile(r'([\^_])"([^"]*[\u4e00-\u9fff][^"]*)"')

    def repl(m):
        direction, text = m.group(1), m.group(2)
        return ('%s \\markup { \\override #\'(font-name . "%s") "%s" }'
                % (direction, font_name, text))

    return script_re.sub(repl, ly_source)


def _set_first_line_indent(ly_source, indent_mm=0.0):
    """Set the first-system indent and keep every later system aligned.

    LilyPond reserves an indent on the first system (the space normally used
    by an instrument name), which pushes the first line's bars to the right
    of every later line.  Adding ``indent = 0.0`` (jianpu_ly's built-in
    'NoIndent') makes the first bar start at the same x as all the bars that
    follow it; a positive value is used only when instrument names really
    need the room (see _fit_instrument_names) and then ``short-indent`` is
    set to the same width so the systems still share one left edge.

    Also stops LilyPond from printing a metre change twice when it lands
    exactly on a system break: without this, the new time signature is
    engraved at the end of the previous line *and* at the start of the next
    one (bar 18 of samples/lace.musicxml).  Mid-line changes are unaffected -
    ``break-visibility`` only governs line breaks.
    """
    bs = chr(92)                                  # backslash
    if indent_mm:
        width = ("%.1f" % indent_mm) + bs + "mm"
        extra = "\n short-indent = " + width
    else:
        width = "0.0"
        extra = ""
    extra += ("\n " + bs + "context { " + bs + "Score " + bs + "override "
              "TimeSignature.break-visibility = #end-of-line-invisible }")
    result = []
    pos = 0
    for m in re.finditer(r"\\layout\s*\{", ly_source):
        line_start = ly_source.rfind("\n", 0, m.start()) + 1
        if ly_source[line_start:m.start()].strip().startswith("%"):
            continue  # never uncomment a % \layout{...} example
        result.append(ly_source[pos:m.end()])
        result.append(" indent = " + width + extra)
        pos = m.end()
    result.append(ly_source[pos:])
    return "".join(result)


# Width of one character of an 11pt instrument name (LilyPond's InstrumentName
# size) in PDF points.  Measured against LilyPond's own output ("Violin" 30pt,
# "Contrabass" 48pt, "Violin 1" 39pt): Latin text averages ~5pt per character,
# a full-width CJK glyph is about twice that.  Close enough to decide how much
# room a name needs.
_NAME_LATIN_PT = 5.0
_NAME_CJK_PT = 11.0
_NAME_PADDING_PT = 4.0
# Space an instrument name can use without any indent: LilyPond draws the name
# to the left of the staff, and the empty page margin (the staff starts at the
# text area edge, ~15mm in) swallows that much of it.  Only the width beyond
# this has to be reserved with an indent.
_NAME_FREE_MARGIN_PT = 40.0
# ... and never reserve more than this, however long a name is.
_NAME_MAX_INDENT_MM = 40.0

_INSTRUMENT_NAME_RE = re.compile(
    r'(?m)^(?P<indent>[ \t]*)instrumentName[ \t]*=[ \t]*"(?P<name>[^"]*)"')


def _name_width_pt(name):
    """Rough printed width of an instrument name at LilyPond's 11pt."""
    return sum(_NAME_CJK_PT if ord(ch) > 0x2E7F else _NAME_LATIN_PT
               for ch in name)


def _fit_instrument_names(ly_source):
    """Make room for instrument names and show them on every system.

    LilyPond takes the space it leaves for ``instrumentName`` from the
    ``indent`` setting.  Single-part scores here use ``indent = 0`` (bars
    start flush left, the instrument already sits in the sheet header), which
    is fine for a short name: it just spills into the empty page margin.

    A full score is a different story - every one of its staves is labelled,
    the longest name can be much wider than that margin (so it was cut off at
    the page edge), and because ``shortInstrumentName`` is never set,
    LilyPond prints the names on the *first* system only, leaving the rest of
    a full score with no instrument at all.

    So: a full score repeats every name on every system, and a name that is too
    wide for the margin (in a full score, or on a single-part sheet) gets an
    indent for the part the margin cannot absorb.  ``short-indent`` receives
    the same width, so all systems keep one shared left edge.  A single-part
    score with a short name - the common case here - is left exactly as it was.
    """
    matches = list(_INSTRUMENT_NAME_RE.finditer(ly_source))
    if not matches:
        return _set_first_line_indent(ly_source, 0.0)
    widest = max(_name_width_pt(m.group("name")) for m in matches)
    widest += _NAME_PADDING_PT
    full_score = len(matches) > 1
    if not full_score and widest <= _NAME_FREE_MARGIN_PT:
        return _set_first_line_indent(ly_source, 0.0)

    indent_mm = min(max(0.0, widest - _NAME_FREE_MARGIN_PT) / 2.83465,
                    _NAME_MAX_INDENT_MM)
    if full_score:
        ly_source = _INSTRUMENT_NAME_RE.sub(
            lambda m: '%s\n%sshortInstrumentName = "%s"'
                      % (m.group(0), m.group("indent"), m.group("name")),
            ly_source)
    return _set_first_line_indent(ly_source, indent_mm)


def _expand_empty_bar_rests(ly_source):
    """Print a single empty bar as one "0" per beat, keep longer rests combined.

    A MusicXML bar that is silent reaches us either as per-beat rests
    ("0 0 0 0" after the rest patch) or, when the file/notation program
    marked it as a multi-measure rest, as jianpu_ly's ``R<dur>*<n>`` token.
    A single such bar is read as zeros (4/4 -> ``0 0 0 0``), while runs of
    several silent bars stay exactly as jianpu_ly emitted them: one combined
    multi-measure rest (``|--5--|`` for five bars), which is what keeps long
    silences from wasting page space.

    Only the jianpu staff is rewritten, and only when the active time
    signature gives a whole number of quarter beats - otherwise the token is
    left untouched so the bar length can never change.
    """
    begin = ly_source.find("% === BEGIN JIANPU STAFF ===")
    end = ly_source.find("% === END JIANPU STAFF ===")
    if begin < 0 or end < 0 or end <= begin:
        return ly_source
    head, staff, tail = ly_source[:begin], ly_source[begin:end], ly_source[end:]

    quote = chr(34)                    # "
    bs = chr(92)                       # backslash (never written literally)
    zero = bs + "note-mod " + quote + "0" + quote + " r4"

    token_re = re.compile(r"R[0-9.]*\*([0-9]+)")
    time_re = re.compile(r"\\time\s+([0-9]+)/([0-9]+)")

    quarters_per_bar = None
    pieces = []
    pos = 0
    for match in token_re.finditer(staff):
        for time_match in time_re.finditer(staff, pos, match.start()):
            num, den = int(time_match.group(1)), int(time_match.group(2))
            quarters_per_bar = (num * 4 // den
                                if den and (num * 4) % den == 0 else None)
        pos = match.end()
        if not quarters_per_bar:
            continue                    # unknown/irregular meter: leave as-is
        bars = int(match.group(1))
        if bars > 1:
            continue                    # 2+ silent bars: keep them combined
        pieces.append((match.start(), match.end(),
                       " ".join([zero] * (bars * quarters_per_bar))))
    if not pieces:
        return ly_source

    rebuilt = []
    last = 0
    for start, stop, text in pieces:
        rebuilt.append(staff[last:start])
        rebuilt.append(text)
        last = stop
    rebuilt.append(staff[last:])
    return head + "".join(rebuilt) + tail


def _hide_bar_numbers(ly_source):
    """Hide LilyPond's bar numbers completely (GUI "Off" choice).

    jianpu_ly still emits its numbering settings; overriding the BarNumber
    stencil inside every voice is the simplest way to make sure nothing is
    drawn.
    """
    voice_open = re.compile(r'\\new Voice\s*=\s*"[^"]*"\s*\{')
    if not voice_open.search(ly_source):
        return ly_source
    override = "\n" + chr(92) + "override Score.BarNumber #'stencil = ##f"
    return voice_open.sub(lambda m: m.group(0) + override, ly_source)


def _inject_note_number_font_size(ly_source, size=_JIANPU_NOTE_FONT_SIZE):
    """Scale up only the jianpu digit glyphs in the generated .ly.

    jianpu_ly draws each number (and the "0" rest, and the sustain "–"
    dashes) by making note-mod tweak the NoteHead/Rest stencil to print a
    plain bold-sans markup.  Injecting a \\fontsize right after the existing
    \\lower makes those glyphs bigger while everything else (title, dynamics,
    Chinese words, arrows) keeps its current size.

    If the file does not contain jianpu_ly's note-mod markup, the source is
    returned untouched (never mangle an unexpected layout).
    """
    if size is None or size == 0:
        return ly_source
    def _repl(m):
        return m.group(1) + ("\\fontsize #%d " % size) + "\\sans \\bold #text"
    new_source, n = _JIANPU_NOTE_MARKUP_RE.subn(_repl, ly_source)
    if n == 0:
        # no note-mod markup found -> leave the file alone rather than guess
        return ly_source
    return new_source





# ---------------------------------------------------------------------------
# MusicXML metadata extraction
#
# jianpu_ly fills \header fields from the MusicXML itself, but it picks the
# wrong values for display (e.g. it prefers <instrument-name> "Guzheng" over
# the part name 古筝1, and it drops the 编配人 arranger credit).  We parse the
# metadata ourselves so the rendered header shows exactly what we want:
# title centered, instrument on the left, composer/arranger on the right.
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Header layout on the generated .ly file
#
# jianpu_ly prints every \score header centred (LilyPond's default).  We want:
#     title                 -> centre
#     instrument            -> left
#     composer / arranger   -> right
# so we rewrite the per-score \header{...} fields and set a custom
# scoreTitleMarkup inside the file-level \paper block.
# ---------------------------------------------------------------------------

def _lp_escape(text):
    """Escape a string for use inside a LilyPond double-quoted string."""
    return (text.replace("\\", "\\\\").replace('"', '\\"')
                .replace("\r", " ").replace("\n", " "))


def _build_ly_header(meta):
    """Return a LilyPond \\header{...} block for the given metadata dict.

    Composer and arranger get their 作曲人：/ 编配人： labels here so they are
    always shown in the PDF even if the MusicXML credits omit the label.
    """
    fields = []
    for key in ("title", "composer", "arranger", "instrument"):
        value = (meta.get(key) or "").strip()
        if not value:
            continue
        if key == "composer":
            value = "作曲人：" + value
        elif key == "arranger":
            value = "编配人：" + value
        fields.append('%s="%s"' % (key, _lp_escape(value)))
    return "\\header{\n" + "\n".join(fields) + "\n}"


def _replace_header_blocks(ly_source, meta):
    """Replace every *active* \\header{...} block with our own header.

    Commented examples (e.g. jianpu_ly's ``% \\header { tagline="" }``) are
    skipped so we never uncomment code by accident.
    """
    header = _build_ly_header(meta)
    result = []
    pos = 0
    while True:
        start = ly_source.find("\\header", pos)
        if start < 0:
            result.append(ly_source[pos:])
            break
        brace = ly_source.find("{", start)
        if brace < 0:
            result.append(ly_source[pos:])
            break
        # find the matching closing brace
        depth = 0
        end = brace
        while end < len(ly_source):
            if ly_source[end] == "{":
                depth += 1
            elif ly_source[end] == "}":
                depth -= 1
                if depth == 0:
                    end += 1
                    break
            end += 1
        # skip \header tokens that sit on a comment line (starts with %)
        line_start = ly_source.rfind("\n", 0, start) + 1
        prefix = ly_source[line_start:start]
        if prefix.strip().startswith("%"):
            pos = end
            continue
        result.append(ly_source[pos:start])
        result.append(header)
        pos = end
    return "".join(result)


def _build_score_title_markup(meta):
    """Compose the scoreTitleMarkup for our desired title layout."""
    title = (meta.get("title") or "").strip()
    composer = (meta.get("composer") or "").strip()
    arranger = (meta.get("arranger") or "").strip()
    instrument = (meta.get("instrument") or "").strip()

    rows = []
    if title:
        rows.append("    \\fill-line { \\override #'(font-name . \"SimHei\") \\bold \\fontsize #4 \\fromproperty #'header:title }")

    left = "\\fromproperty #'header:instrument" if instrument else ""
    right = []
    if composer:
        right.append("\\fromproperty #'header:composer")
    if arranger:
        right.append("\\fromproperty #'header:arranger")

    if left and right:
        if len(right) == 1:
            rows.append("    \\fill-line { %s %s }" % (left, right[0]))
        else:
            rows.append("    \\fill-line { %s \\right-column { %s } }"
                        % (left, " ".join(right)))
    elif left:
        # instrument alone -> keep it on the left
        rows.append("    \\fill-line { %s \\null }" % left)
    elif right:
        # composer/arranger alone -> keep them on the right
        if len(right) == 1:
            rows.append("    \\fill-line { \\null %s }" % right[0])
        else:
            rows.append("    \\fill-line { \\null \\right-column { %s } }"
                        % " ".join(right))

    return "\n".join(rows)


def _inject_header_layout(ly_source, meta):
    """Insert our scoreTitleMarkup into the file-level \\paper block."""
    markup = _build_score_title_markup(meta)
    if not markup:
        return ly_source
    paper_start = ly_source.find("\\paper {")
    if paper_start < 0:
        return ly_source
    brace = ly_source.find("{", paper_start)
    if brace < 0:
        return ly_source
    inject = ("\n  %% custom header layout: title centred, instrument left, "
              "composer/arranger right\n  scoreTitleMarkup = \\markup \\column {\n"
              + markup + "\n  }\n")
    return ly_source[:brace + 1] + inject + ly_source[brace + 1:]

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


def _mark_sweep_arrows(ly_source, font_name=_JIANPU_CJK_FONT):
    """Place an ascending-sweep arrow above each collapsed octave chord.

    The XML collapse tags each collapsed chord's lowest note with a
    <fingering>SWP</fingering> marker; jianpu_ly renders that as a finger
    markup placed just after the chord (annotations on chords are deferred
    to the next event).  Here we find each marker, delete it, and insert a
    text script right before the chord it labels, so the arrow is drawn
    above that chord.  All backslashes are built with chr() on purpose.
    """
    bs = chr(92)                        # backslash
    q = chr(34)                         # double quote
    jp_end = ly_source.find("% === END JIANPU STAFF ===")
    if jp_end < 0:
        return ly_source
    head, tail = ly_source[:jp_end], ly_source[jp_end:]
    while q + "SWP" + q in head:
        i = head.find(q + "SWP" + q)
        start = head.rfind(bs + "finger", 0, i)
        end = head.find("}", i)
        end = end + 1 if end >= 0 else i + 5
        if start < 0:
            start = i
        # the collapsed chord sits right before this marker; find its
        # closing ">duration" so the arrow can be attached as a tidy
        # postfix (chord...>4 ^ arrow) instead of a separate event.
        chord = head.rfind("< " + bs + "note-mod", 0, start)
        placed = False
        if chord >= 0:
            seg = head[chord:start]
            close = re.search(r">\d+[.]*", seg)
            if close:
                anchor = chord + close.end()
                arrow = ("^ " + bs + "markup { " + bs
                         + "override #'(font-name . " + q + font_name + q + ") "
                         + q + chr(0x2197) + q + " } ")
                head = head[:start] + head[end:]       # drop the marker
                head = head[:anchor] + arrow + head[anchor:]
                placed = True
        if not placed:
            head = head[:start] + head[end:]
    # the same finger markers also appear in the western/MIDI parts; strip
    # them there too (arrows are only meaningful in the jianpu staff)
    while q + "SWP" + q in tail:
        i = tail.find(q + "SWP" + q)
        start = tail.rfind(bs + "finger", 0, i)
        end = tail.find("}", i)
        end = end + 1 if end >= 0 else i + 5
        if start < 0:
            start = i
        tail = tail[:start] + tail[end:]
    return head + tail


# ---------------------------------------------------------------------------
# Articulations jianpu_ly asks LilyPond to draw with a glyph that is missing
# ---------------------------------------------------------------------------

_BS = chr(92)                                  # backslash


def _map_jianpu_region(ly_source, transform):
    """Apply transform() to the jianpu staff region only.

    jianpu_ly marks its own staff with ``% === BEGIN/END JIANPU STAFF ===``
    comments; everything between the first BEGIN and the last END is jianpu
    output.  The western/MIDI copy of the score that follows it is left alone.
    """
    begin = ly_source.find("% === BEGIN JIANPU STAFF ===")
    end = ly_source.rfind("% === END JIANPU STAFF ===")
    if begin < 0 or end <= begin:
        return ly_source
    return ly_source[:begin] + transform(ly_source[begin:end]) + ly_source[end:]


# jianpu_ly renders MusicXML <staccato/> (and the annotation words "down",
# "bend", "tilde") as a *fingering* whose text is a symbol character.  A
# fingering's markup is drawn in LilyPond's music font, which has no such
# character: LilyPond dropped the mark and emitted one "no glyph for character
# '▼'" warning per note (1566 of them for samples/lace.musicxml), so staccato
# notes came out with no staccato at all.  The ▼ it used is also far too easy
# to mistake for an octave dot.  Rewrite these markups as an upward text mark:
# a bold sans "x" above the number for staccato (the convention numbered
# notation uses for it), and any other symbol in a text font that has it.
_FINGER_GLYPH_RE = re.compile(
    r"\\finger\s+\\markup\s*\{\s*\\fontsize\s+#-?[0-9]+\s*\"(?P<char>[^\"]*)\"\s*\}")
_STACCATO_GLYPH = "\u25bc"                     # ▼ - jianpu_ly's staccato mark
_STACCATO_MARKUP = ("^ " + _BS + 'markup { ' + _BS
                    + "override #'(font-name . \"Nimbus Sans\") " + _BS
                    + 'bold "x" }')


def _fix_finger_marks(ly_source, font_name=_JIANPU_CJK_FONT):
    """Draw staccato (and other symbol fingerings) with a real glyph."""
    def repl(match):
        text = match.group("char")
        if text == _STACCATO_GLYPH:
            return _STACCATO_MARKUP
        if all(ord(ch) < 128 for ch in text):
            return match.group(0)      # plain ASCII fingering: renders fine
        return ("^ " + _BS + 'markup { ' + _BS
                + "override #'(font-name . \"%s\") " % font_name
                + _BS + 'bold "%s" }' % text)

    return _map_jianpu_region(
        ly_source, lambda part: _FINGER_GLYPH_RE.sub(repl, part))


# jianpu_ly emits a <trill-mark/> + <wavy-line start/stop> as a \trill *script*
# plus a TrillSpanner, and it defers both to the event *after* the note they
# belong to.  That draws two "tr" glyphs, and whenever the start and the stop
# land on the same event - the normal case when MusicXML puts trill-mark,
# wavy-line start and wavy-line stop on one held note (bar 63 of
# samples/lace.musicxml) - the spanner has no length, LilyPond never closes it
# and its wavy line runs on to the end of the system.
#
# So the span is rebuilt around the trilled note itself: the "tr" moves to the
# note where the trill starts and a single wavy line covers that note, ending
# where the trill stops.  A jianpu note that is held over several beats is a
# digit plus "–" dashes, which is why the span has to end on the event *after*
# the note's last dash (LilyPond ends a trill span in front of the event its
# \stopTrillSpan sits on):
#
#     \note-mod "7" b''4                              <- "tr" + line start
#     \note-mod "–" b''4
#     \note-mod "–" b''4        \stopTrillSpan        <- line ends with the note
#     \note-mod "1" c'''4.
#
# Insertions only ever happen where jianpu_ly puts its own annotations - in the
# gap in front of an event - so chords and beams stay valid.
_EVENT_RE = re.compile(r'\\note-mod\s+"([^"]*)"')
_DASH_MARKUP = "\u2013"                 # – : the sustain dash, not a number
_START_TRILL_RE = re.compile(r"\\startTrillSpan")
_STOP_TRILL_RE = re.compile(r"\\stopTrillSpan")
_TRILL_SCRIPT_RE = re.compile(r"\\trill(?![A-Za-z])")


def _rewrite_trills(part):
    """One "tr" on the trill's first note, wavy line over the trilled note(s)."""
    events = [(m.start(), "dash" if m.group(1) == _DASH_MARKUP else "note")
              for m in _EVENT_RE.finditer(part)]
    if not events:
        return part                      # no jianpu events: leave it alone
    places = [pos for pos, _kind in events]

    def event_before(pos):
        """Index of the last event that starts before pos (None if none)."""
        found = None
        for index, start in enumerate(places):
            if start < pos:
                found = index
            else:
                break
        return found

    def note_start(index):
        while index > 0 and events[index][1] == "dash":
            index -= 1
        return index

    def note_end(index):
        while index + 1 < len(events) and events[index + 1][1] == "dash":
            index += 1
        return index

    removals = []                        # (start, end) ranges to drop
    insertions = []                      # (position, text) to insert
    starts = list(_START_TRILL_RE.finditer(part))
    stops = list(_STOP_TRILL_RE.finditer(part))
    scripts = list(_TRILL_SCRIPT_RE.finditer(part))
    used_stops = set()

    for start_match in starts:
        anchor = event_before(start_match.start())
        if anchor is None:
            continue                     # token before any note: leave as is
        stop_match = next((s for s in stops
                           if s.start() > start_match.start()
                           and s.start() not in used_stops), None)
        for script in scripts:           # the redundant \trill of this trill
            same_gap = (script.start() < start_match.start()
                        and places[anchor] < script.start()
                        and anchor == event_before(script.start()))
            if same_gap:
                removals.append((script.start(), script.end()))
                break
        removals.append((start_match.start(), start_match.end()))

        stop_anchor = None
        if stop_match is not None:
            used_stops.add(stop_match.start())
            removals.append((stop_match.start(), stop_match.end()))
            stop_anchor = event_before(stop_match.start())

        after = None
        if stop_anchor is not None:
            after = note_end(stop_anchor) + 1
        if after is None or after >= len(events):
            # The source gives no end for this trill (or it runs to the end of
            # the score): a lone "tr" is better than a line that never stops.
            insertions.append((places[note_start(anchor)], _BS + "trill "))
            continue
        insertions.append((places[note_start(anchor)], _BS + "startTrillSpan "))
        insertions.append((places[after], _BS + "stopTrillSpan "))

    if not removals and not insertions:
        return part

    pruned = []
    pos = 0
    for start, end in sorted(removals):
        if start < pos:                  # overlapping ranges: drop the rest
            continue
        pruned.append(part[pos:start])
        pos = end
    pruned.append(part[pos:])
    result = "".join(pruned)

    def shifted(position):
        return position - sum(end - start for start, end in removals
                              if end <= position)

    for position, text in sorted(insertions, reverse=True):
        point = shifted(position)
        result = result[:point] + text + result[point:]
    return result


def _fix_trill_spanners(ly_source):
    """Print one "tr" per trill, with the wavy line showing where it ends."""
    return _map_jianpu_region(ly_source, _rewrite_trills)


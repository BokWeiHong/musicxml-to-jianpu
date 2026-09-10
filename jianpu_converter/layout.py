"""Every change applied to the jianpu_ly-generated .ly before compiling.

  * header replacement + scoreTitleMarkup   -> the PDF sheet-music header
    (title centred large/bold SimHei, instrument left, credits right);
  * _inject_dynamic_font_size               -> smaller dynamics;
  * _inject_cjk_text_font                   -> KaiTi for Chinese text marks;
  * _inject_note_number_font_size           -> bigger jianpu digit glyphs;
  * _remove_first_line_indent               -> bars start flush on every line;
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


def _remove_first_line_indent(ly_source):
    """Set the score layout indent to 0 (jianpu_ly's built-in 'NoIndent').

    LilyPond reserves an indent on the first system (the space normally used
    by an instrument name), which pushes the first line's bars to the right
    of every later line.  Adding ``indent = 0.0`` to each un-commented
    \\layout block makes the first bar start at the same x as all the bars
    that follow it.
    """
    result = []
    pos = 0
    for m in re.finditer(r"\\layout\s*\{", ly_source):
        line_start = ly_source.rfind("\n", 0, m.start()) + 1
        if ly_source[line_start:m.start()].strip().startswith("%"):
            continue  # never uncomment a % \layout{...} example
        result.append(ly_source[pos:m.end()])
        result.append(" indent = 0.0")  # like jianpu_ly's NoIndent option
        pos = m.end()
    result.append(ly_source[pos:])
    return "".join(result)


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

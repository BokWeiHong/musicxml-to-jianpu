"""Every change applied to the jianpu_ly-generated .ly before compiling.

  * header replacement + scoreTitleMarkup   -> the PDF sheet-music header
    (title centred large/bold SimHei, instrument left, credits right);
  * _inject_dynamic_font_size               -> smaller dynamics;
  * _inject_cjk_text_font                   -> KaiTi for Chinese text marks;
  * _mark_sweep_arrows                      -> ascend arrow over collapsed runs.

Strings containing LilyPond backslash syntax are assembled with chr(92) /
chr(34) on purpose (never literal backslashes) so the source stays readable
and CRLF/git friendly.
"""


import re


_JIANPU_DYNAMIC_FONT_SIZE = -3


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

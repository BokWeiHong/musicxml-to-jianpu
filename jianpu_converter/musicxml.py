"""Reading, cleaning and describing the input score.

Everything that happens BEFORE jianpu_ly runs:
  * _prepare_xml_input / _normalize_musicxml / _collapse_scale_sweeps make a
    safe working copy in the scratch dir (exotic note types normalised, huge
    one-octave arpeggios folded to their endpoints);
  * extract_musicxml_metadata / _read_mxl_score_xml read the title/composer/
    arranger/instrument that the GUI shows for confirmation and that the PDF
    header is built from.  Handles .musicxml/.xml/.mxl, namespaces and the
    common encodings.
"""


import os
import re


# Note types jianpu_ly cannot typeset. After the 128th patch below, the
# shortest supported value is a 128th note ("p"); anything faster is mapped
# to 128th, and anything longer than a whole note is printed as a whole.
# Bar alignment is unaffected because jianpu_ly measures bars from the same
# duration table we extend.
_UNSUPPORTED_NOTE_TYPES = {
    "256th": "128th",
    "512th": "128th",
    "1024th": "128th",
    "breve": "whole",
    "long": "whole",
    "maxima": "whole",
}


def _normalize_musicxml(xml_text):
    """Replace <type> values jianpu_ly cannot handle (e.g. 256th, breve)
    with the nearest supported value so conversion does not crash."""
    pattern = (r"(<type>)("
               + "|".join(re.escape(k) for k in _UNSUPPORTED_NOTE_TYPES)
               + r")(</type>)")
    return re.sub(pattern,
                  lambda m: m.group(1) + _UNSUPPORTED_NOTE_TYPES[m.group(2)] + m.group(3),
                  xml_text)

_STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_RE = re.compile(r"<note[ >].*?</note>", re.S)


def _note_pitch(note_xml):
    """Approximate MIDI number of a note element (None if no pitch)."""
    st = re.search(r"<step>([A-G])</step>", note_xml)
    if not st:
        return None
    oc = re.search(r"<octave>(\d+)</octave>", note_xml)
    if not oc:
        return None
    al = re.search(r"<alter>(-?\d+)</alter>", note_xml)
    return ((int(oc.group(1)) + 1) * 12
            + _STEP_SEMITONES[st.group(1)]
            + int(al.group(1) if al else 0))


def _collapse_scale_sweeps(xml_text):
    """Collapse octave scale sweeps so jianpu does not stack 8+ numbers.

    Guzheng scores often notate a fast one-octave scale run as a single
    <arpeggiate/> chord of 6-8 notes (e.g. 6 7 1 2 3 4 5 6).  Jianpu-ly
    stacks every member vertically, making an ugly, very tall column of
    numbers.  If an arpeggiated chord has >= 6 notes that rise stepwise,
    keep only the lowest and highest notes (the arpeggio squiggle still
    tells the player to roll/sweep across the range).  Small rolled
    chords (3-5 notes) are left untouched.
    """
    notes = list(_NOTE_RE.finditer(xml_text))
    if len(notes) < 6:
        return xml_text

    # group consecutive <note>s that form a chord (first without <chord/>,
    # the rest marked <chord/>)
    groups = []  # (start_match_index, end_match_index)
    cur_start = None
    prev_end = None
    for idx, m in enumerate(notes):
        if "<chord/>" in m.group(0):
            if cur_start is None:
                cur_start = idx          # chord without an initial note
            continue
        if cur_start is not None:
            groups.append((cur_start, idx - 1))
            cur_start = None
        cur_start = idx
    if cur_start is not None:
        groups.append((cur_start, len(notes) - 1))

    # Find qualifying scale sweeps and replace each group with only its
    # lowest and highest notes.  The arpeggio squiggle is dropped (the sweep
    # is marked with an arrow instead) and the lowest note carries a unique
    # <fingering>SWP</fingering> token so the .ly post-processor can anchor
    # that arrow to this exact chord.
    replacements = []  # (start_char, end_char, new_text)
    for start_i, end_i in groups:
        size = end_i - start_i + 1
        if size < 6:
            continue
        member_pitches = []
        ok = True
        for gi in range(start_i, end_i + 1):
            n = notes[gi].group(0)
            if "<arpeggiate" not in n:
                ok = False
                break
            p = _note_pitch(n)
            if p is None:
                ok = False
                break
            member_pitches.append(p)
        if not ok:
            continue
        if not all(member_pitches[k + 1] > member_pitches[k]
                   for k in range(len(member_pitches) - 1)):
            continue  # not a rising scale run

        def strip_arpeggio(note_xml):
            return re.sub(r"<arpeggiate\b[^>]*/>", "", note_xml)

        def tag_swp(note_xml):
            if "<notations>" not in note_xml:
                return note_xml.replace(
                    "</pitch>",
                    "</pitch><notations><technical>"
                    "<fingering>SWP</fingering></technical></notations>", 1)
            return note_xml.replace(
                "<notations>",
                "<notations><technical><fingering>SWP</fingering></technical>",
                1)

        first = tag_swp(strip_arpeggio(notes[start_i].group(0)))
        last = strip_arpeggio(notes[end_i].group(0))
        replacements.append((notes[start_i].start(), notes[end_i].end(),
                             first + last))

    if not replacements:
        return xml_text

    replacements.sort(reverse=True)
    out = xml_text
    for a, b, new_text in replacements:
        out = out[:a] + new_text + out[b:]
    return out









# ---------------------------------------------------------------------------
# MusicXML metadata extraction
#
# jianpu_ly fills \header fields from the MusicXML itself, but it picks the
# wrong values for display (e.g. it prefers <instrument-name> "Guzheng" over
# the part name 古筝1, and it drops the 编配人 arranger credit).  We parse the
# metadata ourselves so the rendered header shows exactly what we want:
# title centered, instrument on the left, composer/arranger on the right.
# ---------------------------------------------------------------------------

def _tag_local(tag):
    """ElementTree tag -> local name (strips any '{namespace}' prefix)."""
    return tag.rsplit("}", 1)[-1]


def _iter_text(elem):
    """Full text of an element including any nested markup tags."""
    return "".join(elem.itertext()).strip() if elem is not None else ""


def _find_child(parent, name):
    """First direct child with the given local name, namespace-agnostic."""
    if parent is None:
        return None
    for child in parent:
        if _tag_local(child.tag) == name:
            return child
    return None


def _find_children(parent, name):
    """All direct children with the given local name, namespace-agnostic."""
    if parent is None:
        return []
    return [child for child in parent if _tag_local(child.tag) == name]


def _strip_label(value, *prefixes):
    """Remove redundant prefix labels (e.g. '作曲人：') from a credit text."""
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
    return value


def _read_mxl_score_xml(mxl_path):
    """Return the raw bytes of the score XML stored inside a .mxl container.

    Uses the rootfile from META-INF/container.xml when present and otherwise
    falls back to the first .xml member outside META-INF.
    """
    import zipfile
    from xml.etree import ElementTree as _ET

    with zipfile.ZipFile(mxl_path) as zf:
        names = zf.namelist()
        inner = None
        if "META-INF/container.xml" in names:
            try:
                container = _ET.fromstring(zf.read("META-INF/container.xml"))
                for el in container.iter():
                    if el.tag.rsplit("}", 1)[-1] == "rootfile" \
                            and el.get("full-path"):
                        inner = el.get("full-path")
                        break
            except Exception:
                inner = None
        if inner is None or inner not in names:
            candidates = [n for n in names
                          if n.lower().endswith(".xml")
                          and not n.lower().startswith("meta-inf/")]
            candidates.sort(key=len)
            inner = candidates[0] if candidates else None
        if inner is None:
            raise ValueError("No score XML found inside the .mxl file")
        return zf.read(inner)


def extract_musicxml_metadata(xml_path):
    """Return display metadata parsed from a MusicXML file (.musicxml/.xml/.mxl).

    Returns a dict with keys: title, composer, arranger, instrument,
    instrument_type.  Any field that cannot be found is an empty string.
    Handles the default MusicXML namespace, UTF-8/UTF-16 files and BOMs, for
    both partwise and timewise roots.  .mxl (compressed MusicXML) containers
    are transparently unzipped first.
    """
    if xml_path.lower().endswith(".mxl"):
        raw = _read_mxl_score_xml(xml_path)
    else:
        raw = open(xml_path, "rb").read()

    if raw.startswith(b"\xef\xbb\xbf"):
        data = raw.decode("utf-8-sig")
    elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        data = raw.decode("utf-16")
    else:
        try:
            data = raw.decode("utf-8")
        except UnicodeDecodeError:
            data = raw.decode("latin-1")

    import xml.etree.ElementTree as ET
    root = ET.fromstring(data)
    credits = _find_children(root, "credit")

    # --- title ----------------------------------------------------------
    title = ""
    for credit in credits:
        ctype = _find_child(credit, "credit-type")
        if ctype is not None and (ctype.text or "").strip() == "title":
            words = _find_children(credit, "credit-words")
            if words:
                title = _iter_text(words[0])
            break

    # --- composer / arranger -------------------------------------------
    # MuseScore exports one composer <credit> whose <credit-words> entries
    # are 作曲人：... then (optionally) 编配人：...
    composer = arranger = ""
    for credit in credits:
        ctype = _find_child(credit, "credit-type")
        ctext = (ctype.text or "").strip() if ctype is not None else ""
        if ctext == "composer":
            words = _find_children(credit, "credit-words")
            if words:
                composer = _iter_text(words[0])
            if len(words) >= 2:
                arranger = _iter_text(words[1])
            break

    # Some exporters put the arranger in its own credit element
    if not arranger:
        for credit in credits:
            ctype = _find_child(credit, "credit-type")
            ctext = (ctype.text or "").strip() if ctype is not None else ""
            if ctext == "arranger":
                words = _find_children(credit, "credit-words")
                if words:
                    arranger = _iter_text(words[0])
                break

    # --- part / instrument name ----------------------------------------
    instrument = ""
    instrument_type = ""
    part_list = _find_child(root, "part-list")
    score_part = _find_child(part_list, "score-part")
    if score_part is not None:
        part_name = _find_child(score_part, "part-name")
        if part_name is not None:
            instrument = _iter_text(part_name)
        for score_instrument in _find_children(score_part, "score-instrument"):
            nm = _find_child(score_instrument, "instrument-name")
            if nm is not None:
                instrument_type = _iter_text(nm)
                break

    # Older files put the part name into an untagged <credit> instead
    if not instrument:
        for credit in credits:
            if _find_child(credit, "credit-type") is None:
                words = _find_children(credit, "credit-words")
                if words:
                    instrument = _iter_text(words[0])
                break

    # Fallbacks for files that do not use <credit> elements at all and put
    # the metadata in <work>/<movement-title> and <identification><creator>
    # instead (the classic Recordare/Sibelius export layout).
    if not title:
        work = _find_child(root, "work")
        work_title = _find_child(work, "work-title") if work is not None else None
        if work_title is not None:
            title = _iter_text(work_title)
        if not title:
            movement_title = _find_child(root, "movement-title")
            if movement_title is not None:
                title = _iter_text(movement_title)
    if not composer or not arranger:
        identification = _find_child(root, "identification")
        if identification is not None:
            for creator in _find_children(identification, "creator"):
                creator_type = (creator.get("type") or "").strip().lower()
                if creator_type == "composer" and not composer:
                    composer = _iter_text(creator)
                elif creator_type == "arranger" and not arranger:
                    arranger = _iter_text(creator)

    # Drop redundant 作曲人：/ 编配人： prefixes; the header layout already
    # communicates which field is which.
    composer = _strip_label(composer, "作曲人：", "作曲人:")
    arranger = _strip_label(arranger, "编配人：", "编配人:")

    return {
        "title": title,
        "composer": composer,
        "arranger": arranger,
        "instrument": instrument,
        "instrument_type": instrument_type,
    }


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



def _prepare_xml_input(xml_path, temp_dir):
    """Return a path to the score XML ready for jianpu_ly.

    Reads the file (plain XML or .mxl archive), normalizes exotic note
    types, and always returns a copy inside the scratch directory so that
    jianpu_ly (which occasionally rewrites its input file) can never touch
    the user's original MusicXML.
    """
    lower = xml_path.lower()
    if lower.endswith(".mxl"):
        import zipfile
        with zipfile.ZipFile(xml_path) as z:
            names = z.namelist()
            m = re.search(r'rootfile[^>]*full-path="([^"]+)"',
                          z.read("META-INF/container.xml").decode("utf-8", "replace"))
            xml_name = m.group(1) if m else None
            if not xml_name or xml_name not in names:
                xml_name = next((n for n in names
                                 if n.lower().endswith(".xml")
                                 and not n.lower().replace("\\", "/").startswith("meta-inf/")),
                                None)
            if not xml_name:
                raise RuntimeError("Could not find the score inside the .mxl archive.")
            data = z.read(xml_name).decode("utf-8", "replace")
    else:
        raw = open(xml_path, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            data = raw.decode("utf-8-sig")
        elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            data = raw.decode("utf-16")
        else:
            try:
                data = raw.decode("utf-8")
            except UnicodeDecodeError:
                data = raw.decode("latin-1")

    normalized = _normalize_musicxml(data)
    # Collapse one-octave arpeggiated scale sweeps to their endpoints so
    # jianpu does not render a tall stack of 8+ numbers (see function).
    normalized = _collapse_scale_sweeps(normalized)
    out = os.path.join(temp_dir,
                       os.path.splitext(os.path.basename(xml_path))[0] + ".musicxml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(normalized)
    return out

"""
MusicXML to Jianpu (简谱) PDF Converter -- Desktop GUI

Converts a .musicxml file into numbered musical notation (Jianpu) and
compiles it to a PDF saved next to the original file, using:
  * jianpu_ly   (pure-Python package, run in-process)
  * lilypond    (external engine, auto-located)

LilyPond lookup order:
  1. the LILYPOND environment variable (path to lilypond.exe, or a folder)
  2. the system PATH
  3. a portable install sitting next to this script / the packaged .exe,
     i.e. "lilypond.exe", "bin/lilypond.exe" or "lilypond-*/bin/lilypond.exe"
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


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


def _prepare_xml_input(xml_path, temp_dir):
    """Return a path to the score XML ready for jianpu_ly.

    Reads the file (plain XML or .mxl archive), normalizes exotic note
    types, and only writes a temporary copy when changes are needed.
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
    if normalized == data:
        return xml_path  # nothing to fix; let jianpu_ly read the original

    out = os.path.join(temp_dir,
                       os.path.splitext(os.path.basename(xml_path))[0] + ".musicxml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(normalized)
    return out


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


def convert_musicxml_to_jianpu(xml_path):
    """
    Convert a MusicXML file to a Jianpu PDF next to the original file.

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

        # 1. jianpu_ly: MusicXML -> Jianpu LilyPond source (in-process)
        #    (first normalize exotic note types jianpu_ly cannot print)
        input_path = _prepare_xml_input(xml_path, temp_dir)
        in_dat = jianpu_ly.get_input([input_path])
        ly_source = jianpu_ly.process_input(in_dat)

        # Save strictly as UTF-8
        with open(temp_ly, "w", encoding="utf-8") as f:
            f.write(ly_source)

        # 2. lilypond: Jianpu LilyPond source -> PDF
        proc = subprocess.run(
            [lilypond_exe, "-o", temp_pdf_base, temp_ly],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
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


class JianpuConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MusicXML to 简谱 (Jianpu) Converter")
        self.root.geometry("540x380")
        self.root.resizable(False, False)

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.input_file_path = tk.StringVar()
        self.output_pdf_path = ""

        self._build_ui()
        self._prefill_from_args()

    def _prefill_from_args(self):
        """If the app was launched with a MusicXML file (e.g. opened by
        double-clicking a .musicxml file), pre-load it automatically."""
        for arg in sys.argv[1:]:
            if os.path.isfile(arg) and arg.lower().endswith((".musicxml", ".xml", ".mxl")):
                self.input_file_path.set(arg)
                self.status_var.set("File selected. Click Convert.")
                break

    def _build_ui(self):
        # Header Frame
        header_frame = tk.Frame(self.root, bg="#1E293B", height=70)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="MusicXML to 简谱 PDF Converter",
            font=("Segoe UI", 15, "bold"),
            fg="#F8FAFC",
            bg="#1E293B"
        )
        title_label.pack(pady=(12, 0))

        sub_label = tk.Label(
            header_frame,
            text="Powered by jianpu-ly & LilyPond",
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#1E293B"
        )
        sub_label.pack()

        # Main Body Frame
        body_frame = tk.Frame(self.root, padx=25, pady=20)
        body_frame.pack(fill="both", expand=True)

        # File Selection Row
        file_label = tk.Label(body_frame, text="Select MusicXML File:", font=("Segoe UI", 10, "bold"))
        file_label.pack(anchor="w")

        file_select_frame = tk.Frame(body_frame)
        file_select_frame.pack(fill="x", pady=(5, 15))

        self.entry_path = ttk.Entry(file_select_frame, textvariable=self.input_file_path, font=("Segoe UI", 10))
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ttk.Button(file_select_frame, text="Browse...", command=self._browse_file)
        btn_browse.pack(side="right")

        # Action Button
        self.btn_convert = tk.Button(
            body_frame,
            text="Convert to Jianpu PDF",
            font=("Segoe UI", 11, "bold"),
            bg="#4F46E5",
            fg="white",
            activebackground="#4338CA",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            command=self._start_conversion_thread
        )
        self.btn_convert.pack(fill="x", ipady=6, pady=(0, 15))

        # Status & Progress
        self.status_var = tk.StringVar(value="Ready. Select a file to begin.")
        self.status_label = tk.Label(body_frame, textvariable=self.status_var, font=("Segoe UI", 9), fg="#64748B")
        self.status_label.pack(anchor="w", pady=(0, 5))

        self.progress = ttk.Progressbar(body_frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 15))

        # Open PDF Button (Initially Disabled)
        self.btn_open_pdf = ttk.Button(body_frame, text="Open Generated PDF", command=self._open_pdf, state="disabled")
        self.btn_open_pdf.pack(fill="x")


    def _browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select MusicXML File",
            filetypes=[("MusicXML Files", "*.musicxml *.xml"), ("All Files", "*.*")]
        )
        if file_path:
            self.input_file_path.set(file_path)
            self.status_var.set("File selected. Click Convert.")
            self.btn_open_pdf.config(state="disabled")

    def _start_conversion_thread(self):
        file_path = self.input_file_path.get().strip()
        if not file_path or not os.path.exists(file_path):
            messagebox.showwarning("File Missing", "Please select a valid .musicxml or .xml file first.")
            return

        if not find_lilypond():
            messagebox.showerror(
                "LilyPond Not Found",
                "Could not find lilypond.exe.\n\n"
                "Install LilyPond and add it to your PATH, set the "
                "LILYPOND environment variable, or keep a portable "
                "lilypond-*/bin/lilypond.exe folder next to this application.",
            )
            return

        self.btn_convert.config(state="disabled")
        self.btn_open_pdf.config(state="disabled")
        self.progress.start(10)
        self.status_var.set("Running jianpu-ly and compiling with LilyPond...")
        self.status_label.config(fg="#4F46E5")

        # Run conversion in background to prevent GUI freeze
        thread = threading.Thread(target=self._run_conversion, args=(file_path,), daemon=True)
        thread.start()

    def _run_conversion(self, xml_path):
        try:
            out_pdf_target = convert_musicxml_to_jianpu(xml_path)
            self.output_pdf_path = out_pdf_target
            self.root.after(0, self._on_success, out_pdf_target)
        except Exception as err:
            self.root.after(0, self._on_error, str(err))

    def _on_success(self, pdf_path):
        self.progress.stop()
        self.btn_convert.config(state="normal")
        self.btn_open_pdf.config(state="normal")
        self.status_var.set(f"Success! Saved: {os.path.basename(pdf_path)}")
        self.status_label.config(fg="#16A34A")
        messagebox.showinfo("Conversion Complete", f"Jianpu PDF successfully created at:\n\n{pdf_path}")

    def _on_error(self, error_msg):
        self.progress.stop()
        self.btn_convert.config(state="normal")
        self.status_var.set("Conversion failed.")
        self.status_label.config(fg="#DC2626")
        messagebox.showerror("Error", f"Failed to generate Jianpu:\n\n{error_msg}")

    def _open_pdf(self):
        if self.output_pdf_path and os.path.exists(self.output_pdf_path):
            os.startfile(self.output_pdf_path)


if __name__ == "__main__":
    root = tk.Tk()
    app = JianpuConverterApp(root)
    root.mainloop()

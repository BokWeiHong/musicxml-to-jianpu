# MusicXML → 简谱 (Jianpu) PDF Converter

A single-file Windows desktop app that converts a MusicXML score into
**numbered musical notation (jianpu / 简谱)** and compiles it to a PDF, saved
next to the original file. It is used to produce guzheng/erhu-style practice
sheets where the western staff is dropped and every note becomes a digit.

Built around two engines:

* **[jianpu_ly](https://ssb22.user.srcf.net/mwrhome/jianpu-ly.html)** — the
  pure-Python MusicXML → Jianpu LilyPond translator, run **in-process**.
* **[LilyPond](https://lilypond.org/)** — the engraving engine that turns the
  generated `.ly` source into the PDF (auto-located, or shipped as a portable
  `lilypond-2.26.0` tree next to the app).

No web server, no cloud: everything runs locally, and the GUI, the library
calls and all post-processing live in **`app_gui.py`** (one file).

---

## Feature highlights

* One click **`.musicxml` / `.xml` / `.mxl` → `<name>_jianpu.pdf`**
  next to the input file.
* **Editable score header**: after picking a file the GUI auto-detects the
  title, composer, arranger and instrument and lets you confirm/correct them
  before exporting. The PDF header is then laid out like a real sheet-music
  header — title large & bold (SimHei) centred, instrument left,
  composer/arranger right.
* **CJK-friendly rendering** (KaiTi for Chinese annotations, CJK-aware title
  font), smaller dynamic marks, ascending-sweep arrows on collapsed octave
  runs — all applied by post-processing the generated `.ly`.
* **Robustness patches on top of jianpu_ly 1.889**:
  * real 128th-note support (a `p` duration letter, 5 beams),
  * non-power-of-two tuplets kept as ratios (e.g. `7/8[`) instead of being
    silently halved,
  * octave-direction default for multi-part scores,
  * a fixed final-barline regex, tolerance for `None`/missing stdout streams
    in windowed (no-console) builds.
* Namespace-agnostic MusicXML parsing; UTF-8/UTF-16/BOM inputs; `.mxl`
  containers are unzipped transparently.
* If the output PDF is locked (open in a viewer) the app writes
  `<name>_jianpu_2.pdf`, `_3`, … instead of failing.

---

## Architecture

### End-to-end pipeline

```
 ┌───────────────┐     ┌────────────────────────────────────────────────┐
 │  tkinter GUI  │     │  convert_musicxml_to_jianpu(xml_path,          │
 │ (app_gui.py)  │ ──► │                       header_meta)             │
 └───────────────┘     └────────────────────────────────────────────────┘
                                    │
                1  _prepare_xml_input()  ·  decode xml/.mxl → UTF-8 text
                2  _normalize_musicxml() ·  map exotic <type>s (256th…)
                3  _collapse_scale_sweeps() ·  fold 1-octave arpeggios
                   (working copy in a temp dir — jianpu_ly can never touch
                   the user's original file)
                                    │
                4  jianpu_ly.get_input([...])  ─►  process_input(in_dat)
                                    │   (in-process, already patched —
                                    │    runtime or pre-patched build)
                5  generated .ly is post-processed:
                     • _replace_header_blocks() + _inject_header_layout()
                       → title / instrument / composer header markup
                     • _inject_dynamic_font_size()   → smaller dynamics
                     • _inject_cjk_text_font()       → KaiTi for 中文 marks
                     • _mark_sweep_arrows()          → ↗ over collapsed runs
                6  .ly saved as UTF-8
                                    │
                7  _freshen_lilypond_ccache()  ·  subprocess lilypond -o …
                                    │
                8  move PDF to <dir>/<base>_jianpu.pdf   (lock-safe naming)
```

The conversion itself runs on a worker thread so the window stays responsive;
results/errors are marshalled back with `root.after(...)`.

### Why jianpu_ly gets "patched" (two worlds)

jianpu_ly 1.889 crashes on a few notations found in real scores (128th notes,
`7:8` tuplets, multi-part octave ambiguity, …). The fixes live in two tables
at the top of `app_gui.py`:

* `_JIANPU_LY_DICT_PATCHES` — string replacements inside jianpu_ly's duration
  tables;
* `_JIANPU_LY_FUNC_PATCHES` — string replacements inside parser functions.

| Running from source | Packaged .exe |
|---|---|
| `_patch_jianpu_ly()` rewrites the **installed** stock `jianpu_ly` **in memory** (it has a real source file to work from). Idempotent: sets `_JIANPU_LY_PATCHED = True`. | PyInstaller bundles **compiled bytecode** — no source left to patch. So `patch_jianpu_ly_src.py` reads the tables, generates a pre-patched copy at `jianpu_ly_patched/jianpu_ly`, and the PyInstaller build (`pathex=jianpu_ly_patched`) bundles that copy. |

**Keep the tables in sync with `_patch_jianpu_ly()` and regenerate the patched
package every time they change** — otherwise the .exe silently ships the
unpatched library.

### Generated LilyPond text is built by string assembly

When post-processing emits LilyPond markup (backslashes/quotes) it never
writes backslash literals in source. Commands are assembled with
`chr(92)`/`chr(34)` (see `_mark_sweep_arrows()`), or strings are escaped via
`_lp_escape()`. Follow the same convention in new code.

### Code map (`app_gui.py`, ~1,280 lines)

| Area | Functions |
|---|---|
| LilyPond lookup / cache | `find_lilypond`, `_freshen_lilypond_ccache` |
| MusicXML pre-processing | `_normalize_musicxml`, `_collapse_scale_sweeps`, `_prepare_xml_input` |
| Metadata extraction | `_read_mxl_score_xml`, `extract_musicxml_metadata`, `_find_child(ren)`, `_iter_text`, `_strip_label`, `_note_pitch` |
| .ly post-processing | `_inject_dynamic_font_size`, `_inject_cjk_text_font`, `_mark_sweep_arrows` |
| Header markup | `_build_ly_header`, `_replace_header_blocks`, `_build_score_title_markup`, `_inject_header_layout`, `_lp_escape` |
| jianpu_ly patching | `_JIANPU_LY_DICT_PATCHES`, `_JIANPU_LY_FUNC_PATCHES`, `_patch_jianpu_ly` |
| Orchestration | `convert_musicxml_to_jianpu`, `_StreamSink` |
| GUI | `JianpuConverterApp` (`_build_ui`, `_on_path_changed`, `_start_conversion_thread`, `_run_conversion`, …) |

---

## Repository layout

```
D:\jianpu\
├─ app_gui.py                  # the whole app: GUI + converter + post-processing
├─ patch_jianpu_ly_src.py      # build-time patcher → jianpu_ly_patched/
├─ JianpuConverter.spec        # PyInstaller build script (canonical)
├─ make_icon.py                # regenerates assets\app.ico
├─ assets\app.ico              # app / installer icon            (generated)
├─ installer\
│  └─ JianpuConverter.nsi      # NSIS installer script
├─ release\                    # installer output                 (ignored by git)
├─ dist\ build\                # PyInstaller output                (ignored by git)
├─ jianpu_ly_patched\          # generated pre-patched jianpu_ly   (ignored by git)
├─ lilypond-2.26.0\            # portable LilyPond engine          (ignored by git)
└─ tools\nsis\                 # NSIS compiler                     (ignored by git)
```

`lilypond-2.26.0\`, `tools\`, `release\`, `dist\`, `build\` and
`jianpu_ly_patched\` are git-ignored binary/tool trees: clone the source on a
fresh machine and re-supply them (or point the app at a system LilyPond via
`LILYPOND`/`PATH`). An example input lives at the repo root
(`青城山下白素贞 & 壁上观 (E调)-Guzheng.musicxml`) for quick tests.

---

## Development setup ("play around")

Requirements: **Windows**, **Python 3.9+** (install from python.org — the
default options include `tkinter`), and either a **LilyPond install** on
`PATH`/`LILYPOND`, or the portable `lilypond-2.26.0` folder next to the repo.

```powershell
cd D:\jianpu

# 1. virtual environment (once)
python -m venv .venv

# 2. dependencies
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install jianpu-ly      # runtime dependency
.venv\Scripts\pip install pyinstaller     # only needed to build the .exe

# 3. run the app
.venv\Scripts\python app_gui.py

#    ... or open a score directly (also how the file-association launch works):
.venv\Scripts\python app_gui.py "path\to\song.musicxml"
```

When run from source, `convert_musicxml_to_jianpu()` auto-patches the
installed `jianpu_ly` in memory on first use — no manual step needed.

### Quick sanity checks without clicking through the GUI

```powershell
# imports + compiles, then prints the generated header markup
.venv\Scripts\python -c "import app_gui; print(app_gui._build_score_title_markup({'title':'茉莉花','composer':'','arranger':'','instrument':'古筝'}))"

# metadata detection on a real file
.venv\Scripts\python -c "import app_gui, json; print(app_gui.extract_musicxml_metadata('青城山下白素贞 & 壁上观 (E调)-Guzheng.musicxml'))"

# full headless conversion (needs LilyPond reachable)
.venv\Scripts\python -c "import app_gui; print(app_gui.convert_musicxml_to_jianpu('song.musicxml'))"
```

### LilyPond lookup order (for troubleshooting)

1. `LILYPOND` environment variable (path to `lilypond.exe` or its folder);
2. system `PATH`;
3. a portable tree next to the app/script/cwd:
   `lilypond.exe`, `bin/lilypond.exe`, or any `lilypond-*/bin/lilypond.exe`.

---

## Using the app

1. **Browse…** and pick a `.musicxml`, `.xml` or `.mxl` file (double-clicking a
   `.musicxml` that is associated with the app also works).
2. The **Score details** box auto-fills with the title / composer / arranger /
   instrument found in the file — confirm them or edit/clear them as needed.
   (Cleared fields are intentionally kept cleared in the PDF.)
3. Click **Convert to Jianpu PDF**. The worker thread runs jianpu_ly +
   LilyPond while the status bar and progress bar animate.
4. On success, click **Open Generated PDF**. The file is saved as
   `<original name>_jianpu.pdf` in the same folder as the input
   (`…_jianpu_2.pdf`, `…_jianpu_3.pdf` if that name is locked).

### 中文快速使用（给朋友）

1. 打开软件 → **Browse…** 选择 `.musicxml`（或 `.xml`、`.mxl`）曲谱文件；
2. 软件会自动读取**标题 / 作曲 / 编配 / 乐器**，显示在“Score details”栏里，
   可直接修改或清空；
3. 点 **Convert to Jianpu PDF** 转换，完成后点 **Open Generated PDF** 查看；
4. 生成的简谱 PDF 会保存在原曲谱旁边，文件名形如 `歌名_jianpu.pdf`。

---

## Distributing to friends (Windows)

Share **`release\JianpuConverter-Setup-1.0.0.exe`** — one file, ~43 MB. Friends
double-click it:

* installs per-user to `%LOCALAPPDATA%\Programs\JianpuConverter`
  (no admin rights);
* adds Start Menu + Desktop shortcuts;
* associates `.musicxml` files (open-by-double-click);
* adds an “Apps & features” entry for uninstalling.

Because the installer is **not code-signed**, SmartScreen may show
“Windows protected your PC” → **More info → Run anyway**. A code-signing
certificate removes that warning.

Silent install / uninstall (for IT / scripts):

```powershell
JianpuConverter-Setup-1.0.0.exe /S /D=C:\Path\To\Install
"C:\Path\To\Install\Uninstall.exe" /S
```

### Building the .exe + installer from source

```powershell
cd D:\jianpu

# 0. one-time toolchain
#    - NSIS compiler (makensis.exe)   → tools\nsis\nsis-3.09\
#    - portable LilyPond 2.26         → lilypond-2.26.0\

# 1. regenerate the pre-patched jianpu_ly copy (needed by the frozen exe)
.venv\Scripts\python patch_jianpu_ly_src.py

# 2. rebuild the exe (uses JianpuConverter.spec → dist\JianpuConverter\)
.venv\Scripts\python -m PyInstaller JianpuConverter.spec

# 3. ship the portable engine next to the exe
Copy-Item -Recurse -Force lilypond-2.26.0 dist\JianpuConverter\

# 4. build the installer (NSIS)
tools\nsis\nsis-3.09\makensis.exe installer\JianpuConverter.nsi
#    → release\JianpuConverter-Setup-1.0.0.exe
```

Notes:

* The `.spec` file hard-codes `D:/jianpu` paths (and `assets/app.ico`); adjust
  them if you build on another machine.
* Steps 1–3 must run whenever `_JIANPU_LY_*_PATCHES` change. Step 1 can also be
  re-run any time you upgrade/reinstall `jianpu-ly` — it prints
  `WARN: … patch not found` for every replacement string that no longer matches
  the installed library source, which is a good signal the tables and the
  library have drifted.
* The `release\` folder already contains a `README.txt` with the same
  distribution notes to ship inside a zip.

---

## Contributing

### Where things happen

| You want to… | Touch |
|---|---|
| Fix an error for a specific MusicXML file | Start from `convert_musicxml_to_jianpu()` and work backwards: is the failure in jianpu_ly (→ patch table entry), in our XML pre-processing (`_normalize_musicxml`, `_collapse_scale_sweeps`), in the .ly post-processing, or in the GUI layer? |
| Fix something jianpu_ly does wrong/ugly in the notation | Add a replacement pair to `_JIANPU_LY_DICT_PATCHES` / `_JIANPU_LY_FUNC_PATCHES` **and** keep the equivalent code inside `_patch_jianpu_ly()` in sync. |
| Change PDF layout / fonts / header | `_build_*_header*`, `_inject_*`, `_mark_sweep_arrows`, `_lp_escape`. |
| Change the GUI | `JianpuConverterApp` in the lower half of `app_gui.py`. |
| Update packaging | `patch_jianpu_ly_src.py`, `JianpuConverter.spec`, `installer\JianpuConverter.nsi`, `release\README.txt`. |

### Workflow for a converter bug

1. **Reproduce with a file**: prefer a real export (the repo root sample works
   well). Note the LilyPond version found and the exact error text (conversion
   errors now include jianpu_ly stderr diagnostics automatically).
2. **Decide the layer** (see table above). If it is jianpu_ly, also run
   `patch_jianpu_ly_src.py` and check for `WARN: … patch not found` — a missing
   `old` string means the tables drifted from the installed library version.
3. **Patch, then verify in BOTH worlds**:
   ```powershell
   .venv\Scripts\python -m py_compile app_gui.py
   .venv\Scripts\python -c "import app_gui; print(app_gui.convert_musicxml_to_jianpu('your_file.musicxml'))"
   .venv\Scripts\python patch_jianpu_ly_src.py   # must print 128th/7-8/marker all True
   ```
4. **Look at the rendered PDF**, not just the exit code: check bar alignment,
   beams, tuplet numbers, header placement, CJK glyphs, and that the title is
   drawn large & bold. Keep the PDF next to the sample so it can be eyeballed
   in review.
5. Keep a regression sample. Put the smallest failing `.musicxml` that
   reproduces the issue next to the fix (or in a `samples\` folder) and note it
   in the commit message.

### Code conventions

* Everything stays in **`app_gui.py`** (single-file philosophy) unless the
  change is genuinely a build/packaging concern.
* **Python standard library only** at runtime, plus `jianpu_ly`. No new
  third-party runtime dependencies (the venv also carries music21 etc. only as
  leftover/test convenience — don't import them in the app).
* When emitting LilyPond syntax, **never write backslash literals**: build them
  with `chr(92)`/`chr(34)` or use raw string escapes through `_lp_escape()`.
* Keep `_JIANPU_LY_DICT_PATCHES`/`_FUNC_PATCHES` entries short and anchored —
  the `old` fragment must appear **exactly once** in the target source, and it
  must keep matching across small upstream changes.
* Files are CRLF, UTF-8. Comments may be English or Chinese; keep new comments
  in the language of the surrounding block.
* The module docstring of `app_gui.py` documents LilyPond lookup order; update
  it if that logic changes.

### Reporting issues / feature requests

When opening an issue, please include:

* the `.musicxml`/`.mxl` file (or a minimal part of it) that fails,
* what you expected vs. what happened (a screenshot of the PDF helps),
* the app version (Explorer → Properties → Details on `JianpuConverter.exe`),
  or whether you ran from source,
* your LilyPond setup (`where lilypond`, `LILYPOND`, or “portable next to the
  exe”).

---

## Known limitations

* **Notation fidelity is inherited from jianpu_ly.** Ornaments, unusual
  tuplets, tremolos, complex beaming and non-standard meters are simplified or
  approximated; when they crash the translator, they are worked around by the
  patch/pre-process layers rather than fully re-engraved.
* **Windows + Chinese fonts.** CJK rendering depends on system fonts
  (`SimHei` for the title, `KaiTi` for annotations). On a machine without these
  faces LilyPond falls back through fontconfig, which usually still works but
  can look different.
* **Very dense scores** (fast 64th/128th runs, huge chords) may take a while to
  compile and can produce crowded pages — that is LilyPond doing its job, not a
  hang. Watch the status bar/progress bar.
* Output is always **Jianpu (numbers only)**: the western staff is intentionally
  not printed.

## Credits

* **[jianpu_ly]** by Silas S. Brown — the MusicXML → Jianpu LilyPond
  translator this app drives in-process; all jianpu notation logic is its.
* **[LilyPond]** — the GNU music engraver that produces the PDF.
* The tkinter GUI, jianpu_ly patch layer, MusicXML pre-processing and `.ly`
  post-processing in `app_gui.py` are original work in this repository.

[jianpu_ly]: https://ssb22.user.srcf.net/mwrhome/jianpu-ly.html
[LilyPond]: https://lilypond.org/

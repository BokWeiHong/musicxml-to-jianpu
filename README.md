# MusicXML to Jianpu (简谱) PDF Converter

![Take a look](musicxml-to-jianpu.png)

This is a small Windows desktop app that turns MusicXML files into numbered musical notation (jianpu / 简谱) PDFs. It saves the finished PDF right next to your original file.

If you play guzheng or erhu and need practice sheets without standard western staff notation, this is built for that.

Here is what runs under the hood:

* **jianpu_ly** handles the translation from MusicXML to numbered notation.
* **LilyPond** engraves the notes and actually builds the PDF.

Everything runs on your machine. There is no web server, no cloud upload, and no account needed.

---

## What it does

* **One-click conversion:** Pick a `.musicxml`, `.xml`, or `.mxl` file, and you get a `<name>_jianpu.pdf` in the same folder.
* **Editable headers:** The app reads the title, composer, arranger, and instrument from your file. You can change or clear them in the window before exporting.
* **Better Chinese font support:** It formats the output with SimHei for bold titles and KaiTi for Chinese markings so text doesn't look broken.
* **Bug fixes for tricky scores:** Stock `jianpu_ly` often crashes on real-world files. We patched it to support 128th notes, odd tuplets (like 7:8), and multi-part files.
* **Safe file saving:** If you already have the PDF open in a viewer, the app won't crash. It just saves the new one as `_jianpu_2.pdf`.

---

## How it works

The whole process happens in a few steps:

1. You pick a file in the app and tweak the title or composer if needed.
2. The app cleans up the XML in a temp folder (your original file is never touched).
3. It runs our patched version of `jianpu_ly` in memory to generate a LilyPond (`.ly`) file.
4. It tweaks the `.ly` text to fix fonts, clean up headers, and shrink dynamic markings.
5. It calls LilyPond in the background to compile the final PDF.

The conversion runs on a background worker thread, so the app window won't freeze while LilyPond works.

---

## Quick start (running from source)

You will need:

* Windows
* Python 3.9 or newer (make sure `tkinter` is installed)
* LilyPond (either on your system PATH, set via a `LILYPOND` environment variable, or placed as a portable folder named `lilypond-2.26.0` right in the project folder)

### Setup

```powershell
cd D:\jianpu

# Set up a virtual environment
python -m venv .venv

# Install dependencies
.venv\Scripts\pip install -r requirements.txt

# Run the app
.venv\Scripts\python app_gui.py

```

You can also just double-click `run.bat`.

If you want to test conversion straight from the terminal without opening the window:

```powershell
.venv\Scripts\python -c "from jianpu_converter import convert_musicxml_to_jianpu; print(convert_musicxml_to_jianpu('samples\\your_score.musicxml'))"

```

---

## How to use the app

1. Click **Browse…** and select your score file.
2. Check the **Score details** box. Fix the title, composer, or instrument if the auto-detection got something wrong. If you delete a field, it stays blank on the PDF.
3. Click **Convert to Jianpu PDF**.
4. When it finishes, click **Open Generated PDF** to see the result.

### 中文简易说明

1. 打开软件，点 **Browse…** 选你的 `.musicxml`、`.xml` 或 `.mxl` 文件。
2. 软件会自动填好歌名、作作者和乐器。如果有错，直接在输入框里改。
3. 点 **Convert to Jianpu PDF** 开始转。
4. 好了之后点 **Open Generated PDF** 打开看。新文件就在原文件旁边。

---

## Sharing with others

If you just want to give this to someone else to use on Windows, give them `release\JianpuConverter-Setup-1.0.0.exe`.

* It installs for the current user without asking for admin rights.
* It sets up desktop shortcuts and lets them double-click `.musicxml` files to open them.
* Because the installer isn't digitally signed, Windows SmartScreen will complain. Tell them to click **More info** and then **Run anyway**.

### Building the installer yourself

If you changed the code and want to package a fresh `.exe`:

```powershell
cd D:\jianpu

# 1. Generate the pre-patched jianpu_ly files needed for the frozen build
.venv\Scripts\python patch_jianpu_ly_src.py

# 2. Build the app with PyInstaller
.venv\Scripts\python -m PyInstaller JianpuConverter.spec

# 3. Copy the portable LilyPond folder next to the new exe
Copy-Item -Recurse -Force lilypond-2.26.0 dist\JianpuConverter\

# 4. Compile the installer with NSIS
tools\nsis\nsis-3.09\makensis.exe installer\JianpuConverter.nsi

```

Your new installer will be in the `release\` folder.

---

## Project structure

The code used to be one huge file, but we split it up so it is easier to maintain:

* `app_gui.py` — Small launcher script.
* `jianpu_converter/gui.py` — The Tkinter window and buttons.
* `jianpu_converter/convert.py` — Runs the pipeline from start to finish.
* `jianpu_converter/musicxml.py` — Reads XML, unzips `.mxl`, and cleans up odd note types.
* `jianpu_converter/layout.py` — Tweaks the generated LilyPond text (fonts, headers, cleanups).
* `jianpu_converter/patches.py` — Fixes and workarounds for `jianpu_ly` bugs.
* `jianpu_converter/lilypond.py` — Finds the LilyPond executable and handles its cache.
* `patch_jianpu_ly_src.py` — Build tool that creates a patched copy of `jianpu_ly` for PyInstaller.

---

## A note on the patches

Stock `jianpu_ly` breaks on things like 128th notes and certain tuplets.

When you run this project from Python source, it patches `jianpu_ly` in memory on the fly. But PyInstaller bundles compiled bytecode, so in-memory patching doesn't work in the packaged `.exe`.

That is why `patch_jianpu_ly_src.py` exists. If you ever update the patch tables in `jianpu_converter/patches.py`, run `patch_jianpu_ly_src.py` before rebuilding the installer. Otherwise, your built `.exe` will still have the old bugs.

---

## Things to keep in mind

* **It relies on jianpu_ly for musical decisions:** Complex ornaments, weird tuplets, and dense polyphony might get simplified or look a bit off.
* **Chinese fonts:** The app looks for `SimHei` and `KaiTi` on Windows. If they aren't installed, LilyPond will pick a fallback font, so the text might look slightly different.
* **Dense music takes time:** If a score has tons of rapid runs or massive chords, LilyPond will take several seconds to lay out the page. Just let it finish.
* **Numbers only:** This tool strictly makes jianpu sheets. It does not print western staves alongside the numbers.
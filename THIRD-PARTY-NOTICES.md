# Third-party notices

Jianpu Converter bundles and uses the components below. Their licences apply to
those components; the application's own code is covered by `LICENSE`.

## jianpu_ly 1.889 — Apache License 2.0

* Upstream: <https://ssb22.user.srcf.net/mwrhome/jianpu-ly.html> (by Silas S. Brown)
* Licence text: [`licenses/jianpu_ly-Apache-2.0.txt`](licenses/jianpu_ly-Apache-2.0.txt)
* **Modified copy:** this project ships a patched copy of jianpu_ly
  (`jianpu_ly_patched/` and, in the installed app, the bundled module). The
  changes add 128th-note support, keep non-power-of-two tuplets as ratios,
  default the octave convention for multi-part scores, print rest continuations
  as `0` instead of `–`, and fix two parsing bugs. The canonical list of edits
  is in [`jianpu_converter/patches.py`](jianpu_converter/patches.py).
* Apache-2.0 permits this, provided the copyright/licence notices are kept and
  the changes are stated — which is what this file does.

## LilyPond 2.26.0 — GNU GPL v3 (or later)

* Upstream and source code: <https://lilypond.org/> ·
  <https://gitlab.com/lilypond/lilypond> (release v2.26.0)
* The portable `lilypond-2.26.0` folder is redistributed **unmodified** next to
  the application, as a separate program that the app runs through the command
  line. Its own licence text travels with it at
  `lilypond-2.26.0/licenses/lilypond-2.26.0.COPYING`, together with the licences
  of everything else inside that folder (Python, freedesktop/font libraries,
  GUST fonts, …).
* Because it is redistributed unmodified, its corresponding source is the
  upstream release archive linked above.

## Python 3.14 — PSF Licence Agreement

* Licence text: `lilypond-2.26.0/licenses/python-3.14.3-embed-amd64.LICENSE.txt`
  and, for the interpreter embedded in `JianpuConverter.exe`, the copy that
  PyInstaller ships inside the application folder.

## Tcl/Tk (tkinter) — BSD-style licence

* Licence text: shipped with the application at
  `<install folder>\_internal\_tk_data\license.terms`.

## Fonts — not bundled

The PDF layout asks LilyPond for `SimHei` / `KaiTi` when available. These are
Windows system fonts; they are **not** redistributed with this application.

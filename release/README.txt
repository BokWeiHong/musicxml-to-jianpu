Jianpu Converter - Installer Distribution
==========================================

SHARE THIS ONE FILE:  JianpuConverter-Setup-1.0.0.exe  (43 MB)

Your friends just double-click it and follow the wizard:

  * Installs per-user to  %LOCALAPPDATA%\Programs\JianpuConverter
    (no administrator rights required)
  * Adds a Start Menu shortcut and a Desktop shortcut
  * Associates ".musicxml" files, so double-clicking a MusicXML
    score opens it in the converter
  * Adds a normal "Apps & features" entry so it can be uninstalled
    from Windows Settings

The installer already contains:
  - the app itself
  - the bundled Python runtime + jianpu_ly
  - the portable LilyPond engine (found automatically next to the exe)

So friends need ZERO extra software.

Windows SmartScreen
-------------------
Because the installer is not digitally signed, Windows may show
"Windows protected your PC". This is normal for any self-built app.
Click "More info" -> "Run anyway". (The installer is a plain NSIS
package built from the scripts in this project - source is available
on request.) A code-signing certificate (e.g. from a CA or via Azure
Trusted Signing) removes this warning for good.

Silent install (for IT / scripting)
-----------------------------------
  JianpuConverter-Setup-1.0.0.exe /S /D=C:\Path\To\Install
  "C:\Path\To\Install\Uninstall.exe" /S        (silent uninstall)

Rebuilding the installer from source
------------------------------------
  cd D:\jianpu
  python -m venv .venv                       (once)
  .venv\Scripts\pip install pyinstaller jianpu-ly
  .venv\Scripts\python make_icon.py          (regenerate app.ico)
  .venv\Scripts\python patch_jianpu_ly_src.py   (128th-note support for the .exe)
  .venv\Scripts\python -m PyInstaller --noconsole --onedir ^
        --icon assets\app.ico --paths jianpu_ly_patched ^
        --name JianpuConverter app_gui.py
  copy /y lilypond-2.26.0 dist\JianpuConverter\
  tools\nsis\nsis-3.09\makensis.exe installer\JianpuConverter.nsi
  -> release\JianpuConverter-Setup-1.0.0.exe

128th-note support
------------------
Some scores (fast flute/piccolo parts) contain 128th-note durations.
Stock jianpu_ly cannot typeset those.  The app patches the library at
runtime when run from source, and the build above bakes the patched
copy into the .exe, so 128th notes render correctly in both cases.


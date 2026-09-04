JianpuConverter.exe - MusicXML to Jianpu (简谱) PDF Converter
=============================================================

How to use
----------
1. Double-click JianpuConverter.exe
2. Click "Browse..." and choose a .musicxml (or .xml) file
3. Click "Convert to Jianpu PDF"
4. When finished, the PDF is saved next to your MusicXML file
   as "<name>_jianpu.pdf" and you can open it with the
   "Open Generated PDF" button.

Requirements
------------
The application needs a working LilyPond installation. It is located
automatically in this order:

  1. The LILYPOND environment variable (a lilypond.exe path or a folder)
  2. The system PATH (a normal LilyPond installation)
  3. The portable "lilypond-2.26.0" folder shipped next to this .exe

For a portable setup, keep JianpuConverter.exe and the whole
lilypond-2.26.0 folder together (as they are in this dist folder) and
the app will find everything it needs - no installation required.

Notes
-----
- This distribution also contains everything needed for jianpu_ly:
  it is bundled inside the .exe, so no Python or pip is required.
- First launch may take a few seconds while the .exe unpacks itself.
- Building from source:  pip install pyinstaller jianpu-ly
    pyinstaller --noconsole --onefile --name JianpuConverter app_gui.py

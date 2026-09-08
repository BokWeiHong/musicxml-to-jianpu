"""tkinter desktop GUI (JianpuConverterApp) and main() entry point.

Lets the user pick a .musicxml/.xml/.mxl file, shows the auto-detected title/
composer/arranger/instrument for confirmation/editing, then runs the
conversion on a worker thread and offers to open the finished PDF.
Run from the repo root:  python app_gui.py  (or  python -m jianpu_converter)
"""


import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .convert import convert_musicxml_to_jianpu
from .lilypond import find_lilypond
from .musicxml import extract_musicxml_metadata


class JianpuConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MusicXML to 简谱 (Jianpu) Converter")
        self.root.geometry("590x570")
        self.root.resizable(False, False)

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.input_file_path = tk.StringVar()
        self.output_pdf_path = ""

        # Score details shown in the GUI (auto-filled when a file is chosen,
        # editable by the user before exporting).
        self.meta_title = tk.StringVar()
        self.meta_composer = tk.StringVar()
        self.meta_arranger = tk.StringVar()
        self.meta_instrument = tk.StringVar()


        self._build_ui()
        # Keep the editable score details in sync with the chosen file.
        self.input_file_path.trace_add("write", self._on_path_changed)
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

        # Score Details section: the title/composer/arranger/instrument that
        # will be printed on the PDF header.  Auto-filled from the file so the
        # user can confirm or correct them before exporting.
        details_label = tk.Label(body_frame,
                                 text="Score details \u2014 confirm or edit before exporting:",
                                 font=("Segoe UI", 10, "bold"))
        details_label.pack(anchor="w", pady=(0, 6))

        details_frame = tk.Frame(body_frame, bg="#F1F5F9", padx=12, pady=10,
                                 highlightbackground="#CBD5E1",
                                 highlightthickness=1)
        details_frame.pack(fill="x", pady=(0, 14))

        for _row, (_name, _var) in enumerate((
                ("Title", self.meta_title),
                ("Composer", self.meta_composer),
                ("Arranger", self.meta_arranger),
                ("Instrument", self.meta_instrument),
        )):
            tk.Label(details_frame, text=_name + ":", bg="#F1F5F9",
                     font=("Segoe UI", 9, "bold"), width=12,
                     anchor="w").grid(row=_row, column=0, sticky="w",
                                      padx=(0, 6), pady=2)
            ttk.Entry(details_frame, textvariable=_var,
                      font=("Segoe UI", 10)).grid(row=_row, column=1,
                                                  sticky="ew", pady=2)
            details_frame.columnconfigure(1, weight=1)

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
            filetypes=[("MusicXML Files", "*.musicxml *.xml *.mxl"), ("All Files", "*.*")]
        )
        if file_path:
            self.input_file_path.set(file_path)
            self.status_var.set("File selected. Click Convert.")
            self.btn_open_pdf.config(state="disabled")

    def _on_path_changed(self, *_args):
        """Auto-fill the editable score details whenever the file changes."""
        path = self.input_file_path.get().strip()
        for _var in (self.meta_title, self.meta_composer,
                     self.meta_arranger, self.meta_instrument):
            _var.set("")
        if not path or not os.path.isfile(path):
            return
        try:
            meta = extract_musicxml_metadata(path)
        except Exception:
            # Unreadable/unsupported file: leave the fields empty so the
            # user can still type the header values by hand.
            return
        self.meta_title.set(meta.get("title") or "")
        self.meta_composer.set(meta.get("composer") or "")
        self.meta_arranger.set(meta.get("arranger") or "")
        self.meta_instrument.set(meta.get("instrument") or "")
        self.status_var.set("Details loaded from the file - confirm and click Convert.")

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

        # Pass the confirmed/edited score details so the PDF header prints
        # exactly what the user sees (empty values are respected as cleared).
        header_meta = {
            "title": self.meta_title.get().strip(),
            "composer": self.meta_composer.get().strip(),
            "arranger": self.meta_arranger.get().strip(),
            "instrument": self.meta_instrument.get().strip(),
        }

        # Run conversion in background to prevent GUI freeze
        thread = threading.Thread(target=self._run_conversion,
                                  args=(file_path, header_meta), daemon=True)

        thread.start()

    def _run_conversion(self, xml_path, header_meta=None):
        try:
            out_pdf_target = convert_musicxml_to_jianpu(xml_path, header_meta=header_meta)
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


def main():
    """Launch the desktop GUI (used by app_gui.py and ``python -m
    jianpu_converter``)."""
    root = tk.Tk()
    JianpuConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

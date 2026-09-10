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
import webbrowser
from tkinter import filedialog, messagebox, ttk

from . import GITHUB_REPO, __version__
from . import updater
from .convert import convert_musicxml_to_jianpu
from .lilypond import find_lilypond
from .musicxml import extract_musicxml_metadata

# Public GitHub repository for this app: the clickable footer link invites
# users to grab the source code and play around with it.
GITHUB_REPO_URL = "https://github.com/" + GITHUB_REPO

# Installed builds quietly ask GitHub for a newer release shortly after
# startup (see updater.py).  Set to False to make updates fully manual.
AUTO_CHECK_UPDATES = True

# "Bar numbers" dropdown: the chosen string is mapped to the converter's
# bar_number_every value by JianpuConverterApp._bar_number_every().
BAR_NUMBER_CHOICES = (
    "Every 5 bars",
    "Every 3 bars",
    "Every 2 bars",
    "Every bar",
    "Every 10 bars",
    "Off (no numbers)",
)


class JianpuConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MusicXML to 简谱 (Jianpu) Converter")
        self.root.geometry("590x612")
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

        # Update state (guards against two checks running at once).
        self._update_check_running = False
        self._converting = False


        self._build_ui()
        # Keep the editable score details in sync with the chosen file.
        self.input_file_path.trace_add("write", self._on_path_changed)
        self._prefill_from_args()
        # Installed copies look for a newer release a moment after startup so
        # friends never have to check manually; source runs keep quiet (the
        # header link still works on demand).
        if AUTO_CHECK_UPDATES and updater.is_frozen():
            self.root.after(1500, lambda: self.check_for_updates(manual=False))

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

        # Top-right of the header: version + on-demand update check.  Placed
        # below the title/subtitle rows so it can never overlap them.
        self.update_link = tk.Label(
            header_frame,
            text="v%s  \u00b7  Check for updates" % __version__,
            bg="#1E293B", fg="#7DD3FC", cursor="hand2",
            font=("Segoe UI", 8, "underline"),
        )
        self.update_link.place(relx=1.0, x=-14, y=51, anchor="ne")
        self.update_link.bind("<Button-1>",
                              lambda _event: self.check_for_updates(manual=True))
        self.update_link.bind("<Enter>",
                              lambda _e: self.update_link.config(fg="#BAE6FD"))
        self.update_link.bind("<Leave>",
                              lambda _e: self.update_link.config(fg="#7DD3FC"))

        # Footer bar: points users at the public GitHub repository so they can
        # download the code and play around with it. Styled like a hyperlink —
        # hover brightens it, clicking opens the repo in the default browser.
        footer_frame = tk.Frame(self.root, bg="#1E293B", height=38)
        footer_frame.pack(side="bottom", fill="x")
        footer_frame.pack_propagate(False)

        footer_hint = tk.Label(
            footer_frame,
            text="Open source  \u00b7  come play with the code:",
            bg="#1E293B", fg="#94A3B8", font=("Segoe UI", 9),
        )
        footer_hint.pack(side="left", padx=(16, 4), pady=9)

        github_link = tk.Label(
            footer_frame,
            text=GITHUB_REPO_URL.replace("https://", ""),
            bg="#1E293B", fg="#38BDF8", cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        )
        github_link.pack(side="left", pady=9)
        github_link.bind(
            "<Button-1>", lambda _event: webbrowser.open(GITHUB_REPO_URL)
        )
        github_link.bind("<Enter>", lambda _e: github_link.config(fg="#7DD3FC"))
        github_link.bind("<Leave>", lambda _e: github_link.config(fg="#38BDF8"))

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

        # Bar numbering: how often measure numbers are printed in the PDF.
        tk.Label(details_frame, text="Bar numbers:", bg="#F1F5F9",
                 font=("Segoe UI", 9, "bold"), width=12,
                 anchor="w").grid(row=4, column=0, sticky="w",
                                  padx=(0, 6), pady=2)
        self.bar_number_var = tk.StringVar(value=BAR_NUMBER_CHOICES[0])
        ttk.Combobox(details_frame, textvariable=self.bar_number_var,
                     state="readonly", values=BAR_NUMBER_CHOICES,
                     font=("Segoe UI", 10)).grid(row=4, column=1,
                                                 sticky="ew", pady=2)

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
        self._converting = True

        # Pass the confirmed/edited score details so the PDF header prints
        # exactly what the user sees (empty values are respected as cleared).
        header_meta = {
            "title": self.meta_title.get().strip(),
            "composer": self.meta_composer.get().strip(),
            "arranger": self.meta_arranger.get().strip(),
            "instrument": self.meta_instrument.get().strip(),
        }

        # Run conversion in background to prevent GUI freeze
        thread = threading.Thread(
            target=self._run_conversion,
            args=(file_path, header_meta, self._bar_number_every()),
            daemon=True)

        thread.start()

    def _bar_number_every(self):
        """Map the "Bar numbers" dropdown to the converter's value.

        Returns an int (print a number every N bars) or None for no numbers.
        """
        choice = self.bar_number_var.get()
        if choice.startswith("Off"):
            return None
        if choice == "Every bar":
            return 1
        return int(choice.split()[1])

    def _run_conversion(self, xml_path, header_meta=None, bar_number_every=5):
        try:
            out_pdf_target = convert_musicxml_to_jianpu(
                xml_path, header_meta=header_meta,
                bar_number_every=bar_number_every)
            self.output_pdf_path = out_pdf_target
            self.root.after(0, self._on_success, out_pdf_target)
        except Exception as err:
            self.root.after(0, self._on_error, str(err))

    def _on_success(self, pdf_path):
        self.progress.stop()
        self.btn_convert.config(state="normal")
        self.btn_open_pdf.config(state="normal")
        self._converting = False
        self.status_var.set(f"Success! Saved: {os.path.basename(pdf_path)}")
        self.status_label.config(fg="#16A34A")
        messagebox.showinfo("Conversion Complete", f"Jianpu PDF successfully created at:\n\n{pdf_path}")

    def _on_error(self, error_msg):
        self.progress.stop()
        self.btn_convert.config(state="normal")
        self._converting = False
        self.status_var.set("Conversion failed.")
        self.status_label.config(fg="#DC2626")
        messagebox.showerror("Error", f"Failed to generate Jianpu:\n\n{error_msg}")

    def _open_pdf(self):
        if self.output_pdf_path and os.path.exists(self.output_pdf_path):
            os.startfile(self.output_pdf_path)

    # ------------------------------------------------------------------
    # Self-update (see jianpu_converter/updater.py)
    # ------------------------------------------------------------------

    def check_for_updates(self, manual=False):
        """Ask GitHub for a newer release; never blocks the interface."""
        if self._update_check_running:
            return
        self._update_check_running = True
        if manual:
            self.status_var.set("Checking GitHub for a newer version...")
            self.status_label.config(fg="#4F46E5")
        threading.Thread(target=self._check_updates_worker,
                         args=(manual,), daemon=True).start()

    def _check_updates_worker(self, manual):
        try:
            latest = updater.fetch_latest_release()
        except Exception:
            latest = None
        if latest is None:
            status = "unreachable"
        elif updater.is_newer(latest.version):
            status = "update"
        else:
            status = "uptodate"
        self.root.after(0, self._on_update_checked, status, latest, manual)

    def _on_update_checked(self, status, latest, manual):
        self._update_check_running = False
        if status == "update":
            if self._converting:
                # Never close the app while LilyPond is still working.
                self.status_var.set(
                    "Update v%s found - finish this conversion first."
                    % latest.version)
                return
            self._offer_update(latest)
            return
        if not manual:
            return                      # automatic check stays silent
        if status == "uptodate":
            self.status_var.set("You already have the newest version (v%s)."
                                % __version__)
            self.status_label.config(fg="#16A34A")
            messagebox.showinfo("Up to date",
                                "You already have the newest version (v%s)."
                                % __version__)
        else:
            self.status_var.set("Update check failed - no internet?")
            self.status_label.config(fg="#DC2626")
            messagebox.showwarning(
                "Update check failed",
                "Could not reach GitHub.\n\nCheck your internet connection and "
                "try again, or visit:\n" + updater.GITHUB_RELEASES_PAGE)

    def _offer_update(self, info):
        """Tell the user about a newer release and offer to install it."""
        self.status_var.set("Version v%s is available." % info.version)
        message = ("A new version of the converter is available.\n\n"
                   "You have:  v%s\nAvailable:  v%s\n\n"
                   % (__version__, info.version))
        if not updater.is_frozen():
            # Running from source: just open the release page, installing the
            # packaged app here would be unexpected.
            if messagebox.askyesno("Update available",
                                   message + "Open the download page?"):
                webbrowser.open(info.page_url)
            return
        if not messagebox.askyesno(
                "Update available",
                message + "Download and install it now?\n"
                          "The app will close and restart automatically."):
            self.status_var.set("Update postponed - you can check again anytime.")
            return
        self._download_update(info)

    def _download_update(self, info):
        self.btn_convert.config(state="disabled")
        self.btn_open_pdf.config(state="disabled")
        self.progress.start(10)
        self.status_var.set("Downloading update v%s..." % info.version)
        self.status_label.config(fg="#4F46E5")
        threading.Thread(target=self._download_update_worker,
                         args=(info,), daemon=True).start()

    def _download_update_worker(self, info):
        try:
            path = updater.download_installer(
                info,
                progress=lambda done, total: self.root.after(
                    0, self._on_download_progress, done, total))
        except Exception as err:
            self.root.after(0, self._on_update_error, str(err))
            return
        self.root.after(0, self._install_update, path, info)

    def _on_download_progress(self, done, total):
        if total:
            self.status_var.set("Downloading update... %d%%"
                                % (done * 100 // total))
        else:
            self.status_var.set("Downloading update... %.1f MB"
                                % (done / 1048576.0))

    def _install_update(self, path, info):
        self.progress.stop()
        try:
            updater.launch_installer(path, relaunch=True)
        except Exception as err:
            self._on_update_error(str(err))
            return
        # The installer waits for us to exit, replaces the files and starts the
        # new version again (the /RELAUNCH switch).
        messagebox.showinfo(
            "Updating",
            "Version v%s is being installed now.\n\n"
            "This window will close, and the new version will open by itself."
            % info.version)
        self.root.destroy()

    def _on_update_error(self, message):
        self.progress.stop()
        self.btn_convert.config(state="normal")
        self.status_var.set("Update failed.")
        self.status_label.config(fg="#DC2626")
        messagebox.showerror(
            "Update failed",
            "Could not install the update:\n\n%s\n\nYou can also download it "
            "manually from:\n%s" % (message, updater.GITHUB_RELEASES_PAGE))


def main():
    """Launch the desktop GUI (used by app_gui.py and ``python -m
    jianpu_converter``)."""
    root = tk.Tk()
    JianpuConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

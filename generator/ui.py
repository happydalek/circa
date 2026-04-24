#!/usr/bin/env python3
"""Circa card generator — desktop UI.

Run from the generator/ directory:
    uv run ui.py
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext

# ── Stdout redirector ─────────────────────────────────────────────────────────


class _QueueWriter:
    """Redirect print() output from the worker thread into a queue.

    Strips leading carriage returns (used for in-place terminal progress)
    and ensures each chunk ends with a newline, so the log reads cleanly.
    """

    def __init__(self, q: "queue.Queue[str]") -> None:
        self._q = q

    def write(self, text: str) -> None:
        if not text:
            return
        text = text.lstrip("\r")   # drop the overwrite-escape used for terminal progress
        if not text:
            return
        if not text.endswith("\n"):
            text += "\n"
        self._q.put(text)

    def flush(self) -> None:
        pass


# ── Application ───────────────────────────────────────────────────────────────

_BG = "#f5f5f5"
_DARK = "#1a1a2e"
_RED = "#e63946"


class App(tk.Tk):

    _BASE_URL = "https://happydalek.github.io/circa/"

    def __init__(self) -> None:
        super().__init__()
        self.title("Circa — Card Generator")
        self.configure(bg=_BG)
        self.minsize(560, 520)
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._out_path = ""
        self._build()
        self._poll()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Header ────────────────────────────────────────────────────────────
        tk.Label(
            self,
            text="  ♪  Circa — Card Generator",
            font=("Helvetica", 13, "bold"),
            bg=_DARK, fg="white",
            anchor="w", pady=10,
        ).pack(fill="x")

        body = tk.Frame(self, bg=_BG, padx=14, pady=10)
        body.pack(fill="both", expand=True)

        # ── Playlist URLs ──────────────────────────────────────────────────────
        tk.Label(body, text="Playlist URLs  (one per line)",
                 anchor="w", bg=_BG, font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))

        self._urls = tk.Text(
            body, height=5, width=60, wrap="none",
            font=("Courier", 9), relief="solid", bd=1,
        )
        self._urls.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 2))

        tk.Label(body, text="YouTube Music, YouTube, or Spotify",
                 fg="#888", bg=_BG, font=("Helvetica", 8)).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(0, 8))

        # ── Output PDF ────────────────────────────────────────────────────────
        tk.Label(body, text="Output PDF:", anchor="w",
                 bg=_BG, font=("Helvetica", 9, "bold")).grid(
            row=3, column=0, sticky="w", pady=3)
        self._out_var = tk.StringVar(value=str(Path.home() / "cards.pdf"))
        tk.Entry(body, textvariable=self._out_var, relief="solid", bd=1).grid(
            row=3, column=1, sticky="ew", padx=6)
        tk.Button(body, text="Browse…", command=self._browse_out,
                  relief="flat", bg="#e0e0e0", padx=6).grid(
            row=3, column=2, sticky="w")

        # ── Extra CSV ─────────────────────────────────────────────────────────
        tk.Label(body, text="Extra CSV:", anchor="w",
                 bg=_BG, font=("Helvetica", 9, "bold")).grid(
            row=4, column=0, sticky="w", pady=3)
        self._csv_var = tk.StringVar()
        tk.Entry(body, textvariable=self._csv_var, relief="solid", bd=1).grid(
            row=4, column=1, sticky="ew", padx=6)
        tk.Button(body, text="Browse…", command=self._browse_csv,
                  relief="flat", bg="#e0e0e0", padx=6).grid(
            row=4, column=2, sticky="w")
        tk.Label(body, text="(optional — hand-curated songs added first)",
                 fg="#888", bg=_BG, font=("Helvetica", 8)).grid(
            row=5, column=1, columnspan=2, sticky="w")

        body.columnconfigure(1, weight=1)

        # ── Separator ─────────────────────────────────────────────────────────
        tk.Frame(body, height=1, bg="#ccc").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=10)

        # ── Actions row ───────────────────────────────────────────────────────
        act = tk.Frame(body, bg=_BG)
        act.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        self._no_cache_var = tk.BooleanVar()
        tk.Checkbutton(act, text="No cache", variable=self._no_cache_var,
                       bg=_BG, font=("Helvetica", 9)).pack(side="left")

        self._open_btn = tk.Button(
            act, text="Open PDF", command=self._open_pdf,
            state="disabled", relief="flat", bg="#e0e0e0",
            padx=12, pady=5, font=("Helvetica", 9),
        )
        self._open_btn.pack(side="right")

        self._gen_btn = tk.Button(
            act, text="Generate PDF", command=self._start,
            bg=_RED, fg="white", relief="flat",
            padx=16, pady=5, font=("Helvetica", 10, "bold"),
            activebackground="#c62828", activeforeground="white",
            cursor="hand2",
        )
        self._gen_btn.pack(side="right", padx=(0, 8))

        # ── Log output ────────────────────────────────────────────────────────
        tk.Label(body, text="Output:", anchor="w",
                 bg=_BG, font=("Helvetica", 9, "bold")).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(0, 2))

        self._log = scrolledtext.ScrolledText(
            body, height=12, width=60, state="disabled",
            bg=_DARK, fg="#e0e0e0", insertbackground="white",
            font=("Courier", 9), relief="solid", bd=1,
        )
        self._log.grid(row=9, column=0, columnspan=3, sticky="nsew")
        body.rowconfigure(9, weight=1)

    # ── File dialogs ──────────────────────────────────────────────────────────

    def _browse_out(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile="cards.pdf",
        )
        if path:
            self._out_var.set(path)

    def _browse_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            self._csv_var.set(path)

    # ── Log helpers ───────────────────────────────────────────────────────────

    def _log_append(self, text: str) -> None:
        self._log.config(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.config(state="disabled")

    def _log_clear(self) -> None:
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _poll(self) -> None:
        while True:
            try:
                self._log_append(self._queue.get_nowait())
            except queue.Empty:
                break
        self.after(80, self._poll)

    # ── Generation ────────────────────────────────────────────────────────────

    def _start(self) -> None:
        urls = [
            u.strip()
            for u in self._urls.get("1.0", "end").splitlines()
            if u.strip()
        ]
        csv_path = self._csv_var.get().strip() or None
        out_path = self._out_var.get().strip()

        if not urls and not csv_path:
            self._log_append("✖  Provide at least one playlist URL or a CSV file.\n")
            return
        if not out_path:
            self._log_append("✖  Specify an output PDF path.\n")
            return

        self._log_clear()
        self._gen_btn.config(state="disabled", text="Generating…")
        self._open_btn.config(state="disabled")
        self._out_path = out_path

        threading.Thread(
            target=self._worker,
            args=(urls, csv_path, out_path),
            daemon=True,
        ).start()

    def _worker(
        self,
        urls: list[str],
        csv_path: str | None,
        out_path: str,
    ) -> None:
        writer = _QueueWriter(self._queue)
        old_stdout, sys.stdout = sys.stdout, writer  # type: ignore[assignment]
        success = False
        try:
            import csv as _csv

            # Local imports so errors surface in the log, not at startup.
            from fetcher import fetch_playlist
            from generate import generate

            songs: list[dict] = []

            if csv_path:
                with open(csv_path, newline="", encoding="utf-8") as f:
                    for row in _csv.DictReader(f):
                        songs.append({k.strip(): v.strip() for k, v in row.items()})
                print(f"Loaded {len(songs)} song(s) from CSV.")

            cache_dir = (
                None if self._no_cache_var.get()
                else Path.home() / ".cache" / "circa"
            )

            for url in urls:
                songs.extend(fetch_playlist(url, cache_dir))

            # Deduplicate by youtube_id (CSV wins on conflict)
            seen: set[str] = set()
            deduped: list[dict] = []
            for s in songs:
                vid = s.get("youtube_id", "")
                if vid and vid not in seen:
                    seen.add(vid)
                    deduped.append(s)
            songs = deduped

            if not songs:
                print("No songs found.")
                return

            print(f"\nGenerating PDF for {len(songs)} song(s)…")
            generate(songs, Path(out_path), self._BASE_URL)
            success = True

        except SystemExit as exc:
            print(f"\n✖  {exc}")
        except Exception as exc:
            import traceback
            print(f"\n✖  {exc}")
            traceback.print_exc(file=sys.stdout)
        finally:
            sys.stdout = old_stdout
            self.after(0, lambda: self._gen_btn.config(
                state="normal", text="Generate PDF"
            ))
            if success:
                self.after(0, lambda: self._open_btn.config(state="normal"))

    # ── Open PDF ──────────────────────────────────────────────────────────────

    def _open_pdf(self) -> None:
        if not self._out_path:
            return
        if sys.platform == "win32":
            os.startfile(self._out_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", self._out_path], check=False)
        else:
            subprocess.run(["xdg-open", self._out_path], check=False)


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

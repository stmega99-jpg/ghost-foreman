"""Show a QR code in a window on this PC. Nothing is written to disk.

The text to encode is read from the environment variable GF_QR_TEXT (not from the command line, so it does not
appear in the process list). The window closes after GF_QR_SECONDS (default 300) or when any key is pressed.
Requires: pip install segno   (tkinter ships with Python on Windows)
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

import segno

text = os.environ.pop("GF_QR_TEXT", "")
if not text:
    sys.exit("GF_QR_TEXT is empty")
seconds = int(os.environ.pop("GF_QR_SECONDS", "300") or "300")
title = os.environ.pop("GF_QR_TITLE", "QR code")
caption = os.environ.pop("GF_QR_CAPTION", "")

qr = segno.make(text, error="m")
matrix = [list(row) for row in qr.matrix]
quiet = 4  # modules of white border, required for reliable scanning
size = len(matrix) + quiet * 2
cell = max(4, min(10, 640 // size))
px = size * cell

root = tk.Tk()
root.title(title)
root.configure(bg="white")
root.attributes("-topmost", True)
canvas = tk.Canvas(root, width=px, height=px, bg="white", highlightthickness=0)
canvas.pack(padx=16, pady=(16, 8))
for y, row in enumerate(matrix):
    for x, dark in enumerate(row):
        if dark:
            x0, y0 = (x + quiet) * cell, (y + quiet) * cell
            canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill="black", outline="black")
if caption:
    tk.Label(root, text=caption, bg="white", fg="black", font=("Yu Gothic UI", 11), justify="center").pack(padx=16, pady=(0, 6))
remaining = tk.StringVar()
tk.Label(root, textvariable=remaining, bg="white", fg="#666666", font=("Yu Gothic UI", 9)).pack(pady=(0, 12))


def tick(left: int) -> None:
    if left <= 0:
        root.destroy()
        return
    remaining.set(f"このウィンドウは {left} 秒後に自動で閉じます（Esc キーでも閉じます）")
    root.after(1000, tick, left - 1)


root.bind("<Key>", lambda _e: root.destroy())
tick(seconds)
root.focus_force()
root.mainloop()

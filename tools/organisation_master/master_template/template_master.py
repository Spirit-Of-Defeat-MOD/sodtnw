"""Template Master: a starting point for a new master (copy this folder to tools/<your_master>, see README.md).

Everything shared (the theme, sounds, menu bar, File menu, ◂ Organisation Master, the status line, activity for To Do
Master, rr:// links, running from a copy so a git pull can replace the exe) comes from master_base.MasterApp:
fill in build() with the window's contents."""
import os
import sys
if __name__ == "__main__" and getattr(sys, "frozen", False):  # (the exe runs from a copy so a git pull can replace it)
	import run_copy
	run_copy.start("TemplateMaster")  # (the exe's name without .exe)

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
if not getattr(sys, "frozen", False):  # (running the .py: Organisation Master's shared code is next door)
	sys.path[:0] = [os.path.join(HERE, "..", "organisation_master", "Scripts"), os.path.join(HERE, "..", "culture_master")]

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

import master_base  # noqa: E402
import ui  # noqa: E402


class TemplateMaster(master_base.MasterApp):
	NAME = "Template Master"
	ICON = None  # (e.g. "template_master.ico", next to this file; build.bat builds it in)

	def build_menu(self, menu):
		tools = tk.Menu(menu, tearoff=0)
		tools.add_command(label="Say hello", command=lambda: self.set_status(f"Hello from {self.NAME}!"))
		menu.add_cascade(label="Tools", menu=tools)

	def build(self, body):
		sec = ui.Section(body, self.NAME, "template_master_main", None).place_in(fill="both")
		ttk.Label(sec.body, text=f"The mod: {self.mod_root}\n\nPut this master's contents here (build() in {os.path.basename(__file__)}).",
				  justify="left").pack(anchor="w")
		ttk.Button(sec.body, text="Pretend to save", command=lambda: self.saved(["common/example.txt"], "Saved (not really).")).pack(anchor="w", pady=8)
		self.set_status("Ready.")

	def open_target(self, link):
		self.set_status(f"Opened with {link}")


if __name__ == "__main__":
	master_base.run(TemplateMaster, __file__)

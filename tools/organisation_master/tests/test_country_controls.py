"""Regressions for accidental wheel edits and native tabs reappearing after theme switches."""
from pathlib import Path
import sys
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Scripts"))
from country_controls import SafeCombobox, PageStack
import ui


class CountryControls(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        ui.init(self.root)
        ui.load_themes(str(Path(__file__).resolve().parents[1] / "themes"))

    def tearDown(self):
        self.root.destroy()

    def test_pages_have_no_native_tab_strip_in_any_theme(self):
        book = PageStack(self.root)
        book.pack(fill="both", expand=True)
        pages = [ttk.Frame(book) for _ in range(3)]
        for page, title in zip(pages, ("Character", "Dual leaders", "Script")):
            book.add(page, text=title)
        for width in (360, 450, 600):
            self.root.geometry(f"{width}x500")
            for theme in ui.theme_names():
                ui.apply_theme(self.root, theme, fonts=False)
                for index, page in enumerate(pages):
                    book.select(index)
                    self.root.update()
                    self.assertEqual(book.select(), str(page))
                    self.assertEqual(book.index("current"), index)
                    self.assertEqual(page.winfo_y(), 0, theme)
                    self.assertLessEqual(page.winfo_width(), width)
                    self.assertEqual([p.winfo_ismapped() for p in pages], [p is page for p in pages])
        self.assertEqual(book.tab(pages[1], "text"), "Dual leaders")

    def test_wheel_does_not_change_editable_or_readonly_choices(self):
        for state in ("normal", "readonly"):
            box = SafeCombobox(self.root, state=state, values=("Democratic", "Communist"))
            box.pack(); box.current(0); self.root.update()
            for delta in (-120, 120):
                box.event_generate("<MouseWheel>", delta=delta)
                self.root.update()
                self.assertEqual(box.get(), "Democratic")
            box.destroy()

    def test_prefix_completion_and_deletion(self):
        box = SafeCombobox(self.root, complete=True)
        box.set_completion_values(("authoritarian", "democratic"))
        box.set("auth"); box.icursor("end")
        box._complete(SimpleNamespace(keysym="h", state=0))
        self.assertEqual(box.get(), "authoritarian")
        self.assertTrue(box.selection_present())
        box.set("auth"); box.icursor("end")
        box._complete(SimpleNamespace(keysym="BackSpace", state=0))
        self.assertEqual(box.get(), "auth")

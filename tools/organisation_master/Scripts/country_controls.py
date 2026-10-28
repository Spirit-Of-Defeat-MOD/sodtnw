"""Country inspector controls: intentional choices and page selectors without tab overflow."""
from tkinter import ttk


class SafeCombobox(ttk.Combobox):
    """The wheel never changes a saved-data field; editable choices complete prefixes."""
    def __init__(self, parent, *, complete=False, **kwargs):
        super().__init__(parent, **kwargs)
        self._choices = ()
        self.bind("<MouseWheel>", lambda event: "break")
        self.bind("<Button-4>", lambda event: "break")
        self.bind("<Button-5>", lambda event: "break")
        if complete:
            self.configure(postcommand=self._show_choices)
            self.bind("<KeyRelease>", self._complete)

    def set_completion_values(self, values):
        self._choices = tuple(values)
        self.configure(values=self._choices)

    def _show_choices(self):
        self.configure(values=self._choices)

    def _complete(self, event):
        if event.keysym in {"BackSpace", "Delete", "Left", "Right", "Up", "Down", "Home", "End", "Tab", "Return", "Escape"} or event.state & 0xC:
            return
        text = self.get()
        if not text or self.index("insert") != len(text):
            return
        match = next((value for value in self._choices if value.lower().startswith(text.lower())), None)
        if match and len(match) > len(text):
            self.set(match)
            self.selection_range(len(text), "end")
            self.icursor(len(text))


class PageStack(ttk.Frame):
    """Notebook-compatible page switching without native tabs or theme-engine chrome."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._pages = []
        self._titles = {}
        self._selected = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def add(self, page, *, text):
        self._pages.append(page)
        self._titles[str(page)] = text
        if self._selected is None:
            self.select(page)

    def tabs(self):
        return tuple(str(page) for page in self._pages)

    def index(self, page):
        if page == "current":
            page = self._selected
        if page == "end":
            return len(self._pages)
        if isinstance(page, int):
            return page
        return self.tabs().index(str(page))

    def tab(self, page, option=None):
        title = self._titles[str(self._pages[self.index(page)])]
        return title if option == "text" else {"text": title}

    def select(self, page=None):
        if page is None:
            return str(self._selected) if self._selected is not None else ""
        target = self._pages[self.index(page)]
        if target is not self._selected:
            if self._selected is not None:
                self._selected.grid_remove()
            target.grid(row=0, column=0, sticky="nsew")
            self._selected = target
            self.event_generate("<<NotebookTabChanged>>", when="tail")
        return str(target)

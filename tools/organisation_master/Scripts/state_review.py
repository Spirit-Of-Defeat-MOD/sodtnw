"""Culture state review reasons, portable snapshots, and the Selected task summary."""
import os
import re
import hashlib
import json
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk, simpledialog

from PIL import Image, ImageTk

import ui
import icons
import review_map

REASONS = ("Needs Minorities", "Unsure Placement", "Needs Lore Update")
PROJECT = "Culture System"
GROUP = "Review States"


class ReviewDialog(simpledialog.Dialog):
    def __init__(self, parent, name, sid, states=None):
        self.state_name, self.sid = name, sid
        self.states = states
        super().__init__(parent, title="Flag state for Review")

    def body(self, master):
        if self.states:
            ttk.Label(master, text="Review name").pack(anchor="w")
            self.review_name = tk.StringVar(master, value="Regional Cultures Review")
            ttk.Entry(master, textvariable=self.review_name, width=60).pack(fill="x", pady=(2, 8))
            listing = tk.Listbox(master, height=min(6, len(self.states)), font="TkDefaultFont")
            listing.pack(fill="x", pady=(0, 8))
            for state in self.states:
                listing.insert("end", f"{state['id']}: {state['name']}")
        else:
            ttk.Label(master, text=f"{self.state_name} (state {self.sid})", font="TkHeadingFont").pack(anchor="w", pady=(4, 8))
        ttk.Label(master, text="Select any reasons that apply:").pack(anchor="w")
        self.choices = {reason: tk.BooleanVar(master) for reason in REASONS}
        for reason, var in self.choices.items():
            ttk.Checkbutton(master, text=reason, variable=var).pack(anchor="w", pady=3)
        ttk.Label(master, text="Additional notes (optional)").pack(anchor="w", pady=(10, 4))
        self.note = tk.Text(master, width=60, height=5, wrap="word", font="TkDefaultFont")
        self.note.pack(fill="both", expand=True)
        return self.note

    def apply(self):
        self.result = ([reason for reason, var in self.choices.items() if var.get()],
                       self.note.get("1.0", "end-1c").strip())
        if self.states:
            self.result = (self.review_name.get().strip(), *self.result)

    def validate(self):
        return not self.states or bool(self.review_name.get().strip())


def ask_review(parent, name, sid):
    return ReviewDialog(parent, name, sid).result


def ask_group_review(parent, states):
    return ReviewDialog(parent, "Selected states", None, states).result


def state_id(task):
    match = re.fullmatch(r"culture_state_review:([1-9]\d*)", str((task or {}).get("link", "")))
    if match:
        return int(match[1])
    if str((task or {}).get("link", "")).startswith("culture_region_review:"):
        states = task.get("review_states") or []
        return states[0]["id"] if states else None
    return None


def review_ids(task):
    members = (task or {}).get("review_states") or []
    return list(dict.fromkeys(row["id"] for row in members)) if members else ([state_id(task)] if state_id(task) else [])


def approved(task, sid):
    return bool(((task or {}).get("review_approvals") or {}).get(str(sid), {}).get("approved"))


def all_approved(task):
    ids = review_ids(task)
    return bool(ids) and all(approved(task, sid) for sid in ids)


def fingerprint(data):
    """Compare composition, not translated names, artwork or presentation order."""
    if not isinstance(data, dict):
        return None
    def row(value, fields):
        return {key: value.get(key) for key in fields} if value else None
    content = {key: sorted((row(value, ("token", "strength", "majority")) for value in data.get(key, [])),
                           key=lambda value: str(value["token"])) for key in ("cultures", "religions")}
    content.update(migratory=row(data.get("migratory"), ("token", "strength", "band")),
                   order=row(data.get("order"), ("token", "strength")), low_population=bool(data.get("low_population")))
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def review_status(task, sid, current=None):
    approval = ((task or {}).get("review_approvals") or {}).get(str(sid), {})
    if approval.get("approved"):
        return "changed" if current and approval.get("fingerprint") and current != approval["fingerprint"] else "approved"
    baseline = next((row.get("snapshot") for row in (task or {}).get("review_states", []) if row["id"] == sid), None)
    baseline = baseline or (task or {}).get("review_snapshot")
    return "changed" if current and baseline and current != fingerprint(baseline) else "pending"


def snapshot(data, sid):
    import culture_master as cm
    sprites = {}
    for rel in (cm.F_GFX, cm.F_REL_GFX):
        try:
            sprites.update(cm.ModData.read_sprites(cm.TextFile(data.path(rel)).lines))
        except OSError:
            pass

    def entry(kind, token, strength, majority=False, labels=cm.STRENGTH_LABELS):
        node = data.nodes[kind].get(token)
        icon = sprites.get(cm.sprite_name(node), "") if node else ""
        return dict(token=token, name=node.label() if node else token, strength=strength,
                    strength_label=labels.get(strength, str(strength)), majority=majority,
                    parent=node.parent.label() if node and node.parent else "", icon=icon)

    out = dict(id=sid, name=data.loc.get(f"STATE_{sid}", f"State {sid}"), cultures=[], religions=[], migratory=None, order=None, low_population=sid in data.low_pop)
    for layer, kind, field in (("culture", "sub", "cultures"), ("religion", "religion", "religions")):
        comp = data.comps[layer].get(sid)
        if comp:
            for token in comp.order():
                row = entry(kind, token, comp.strengths[token], token == comp.majority)
                if out["low_population"] and row["strength"] == 1:
                    row["strength_label"] = "Absolute (low population)"
                out[field].append(row)
    if sid in data.migratory:
        token, strength, band = data.migratory[sid]
        out["migratory"] = entry("sub", token, strength, labels=cm.MIG_LABELS)
        out["migratory"].update(band=band, band_name=data.band_names.get(band, band or ""))
    if sid in data.orders:
        token, strength = data.orders[sid]
        out["order"] = entry("religion", token, strength, labels=cm.ORDER_LABELS)
    return out


class Loader:
    """Cache the parsed files between selections, invalidating when the mod changes."""
    def __init__(self, root):
        self.root, self.model, self.signature = root, None, None
        self.snapshots = {}

    def load(self, sid, fallback, size):
        import culture_master as cm
        sources = (cm.F_STATES, cm.F_ONACT, cm.F_REL_ONACT, cm.F_IDEAS, cm.F_REL_IDEAS,
                   cm.F_GFX, cm.F_REL_GFX, cm.F_MIG, cm.F_LOC, cm.F_REL_LOC, cm.F_MIG_LOC)
        signature = []
        for rel in sources:
            try:
                stat = os.stat(os.path.join(self.root, rel))
                signature.append((rel, stat.st_mtime_ns, stat.st_size))
            except OSError:
                signature.append((rel, None))
        try:
            if self.model is None or signature != self.signature:
                model = cm.ModData(self.root)
                if model.state_brace_problem:
                    raise ValueError(model.state_brace_problem)
                self.model, self.signature = model, signature
                self.snapshots.clear()
            if sid not in self.snapshots:
                self.snapshots[sid] = snapshot(self.model, sid)
            data, source = self.snapshots[sid], "Current saved mod data"
        except Exception:
            data, source = fallback, "Snapshot from when this review was flagged; current files could not be read"
        images = {}
        if data:
            rows = data.get("cultures", []) + data.get("religions", [])
            rows += [data[k] for k in ("migratory", "order") if data.get(k)]
            for row in rows:
                icon = row.get("icon")
                if not icon or icon in images:
                    continue
                try:
                    with Image.open(os.path.join(self.root, icon)) as image:
                        image = image.convert("RGBA")
                        image.thumbnail((size, size), Image.Resampling.LANCZOS)
                        images[icon] = image.copy()
                except (OSError, ValueError, Image.DecompressionBombError):
                    pass
        return data, source, images

    def load_review(self, sid, fallback, size, ids):
        data, source, images = self.load(sid, fallback, size)
        current = {}
        if source == "Current saved mod data":
            for member in ids:
                if member not in self.snapshots:
                    self.snapshots[member] = snapshot(self.model, member)
                current[member] = fingerprint(self.snapshots[member])
        return data, source, images, current


class StateReviewPanel(ttk.Frame):
    def __init__(self, parent, root, navigate=None, approve=None, app=None, invalidate=None):
        super().__init__(parent, padding=(0, 12))
        self.loader = Loader(root)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="state-review")
        self.future = self.job = None
        self.photos = []
        self.task = self.current_sid = None
        self.members = []
        self.navigate = navigate
        self.on_approve = approve
        self.on_invalidate = invalidate
        self.current = {}
        self.refresh_job = None
        self.display_key = None
        self._scale = None
        self._stacked = None
        self.section = ui.Section(self, "State review", "state_review_details", app, expand=False).place_in(fill="x")
        self.state_title = self.section.title
        self.state_title.configure(font="om_title", pady=5)
        self.progress = ttk.Progressbar(self.section.tools, length=ui.px(90), maximum=1,
                                        style="Review.Horizontal.TProgressbar")
        self.progress.pack(side="right", padx=8, pady=5)
        content = self.section.body
        self.state_row = ttk.Frame(content)
        self.state_row.pack(fill="x", pady=(0, 4))
        self.state_row.columnconfigure(2, weight=1)
        self.position = ttk.Label(self.state_row, style="Muted.TLabel")
        self.position.grid(row=0, column=0, padx=(0, 10))
        self.previous = ttk.Button(self.state_row, text="◀", width=3, style="Tool.TButton", command=lambda: self.step_state(-1))
        self.previous.grid(row=0, column=1)
        self.state_choice = ttk.Combobox(self.state_row, state="readonly", width=32, font="om_body",
                                         style="Review.TCombobox", postcommand=self.colour_choices)
        self.state_choice.grid(row=0, column=2, sticky="ew", padx=4)
        self.state_choice.bind("<<ComboboxSelected>>", self.choose_state)
        self.next = ttk.Button(self.state_row, text="▶", width=3, style="Tool.TButton", command=lambda: self.step_state(1))
        self.next.grid(row=0, column=3)
        self.open_button = ttk.Button(self.state_row, text="Open in Culture Master", command=self.open_state)
        self.open_button.grid(row=0, column=4, padx=(12, 0))
        self.review_actions = ttk.Frame(content)
        self.review_actions.pack(fill="x", pady=(0, 8))
        self.review_actions.columnconfigure(0, weight=1)
        self.approve_button = tk.Button(self.review_actions, text="Approve as is", font="om_bold", relief="solid",
            borderwidth=1, padx=10, pady=6, command=self.approve_state)
        self.approve_button.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.approve_button.bind("<Map>", lambda _event: self.after_idle(self.update_approval))
        self.reasons = ttk.Label(self.review_actions, style="ReviewReason.TLabel", justify="left")
        self.reasons.grid(row=0, column=0, sticky="w")
        self.body = body = ttk.Frame(content)
        body.pack(fill="x")
        self.trees, self.cards, self.card_titles, self.scrollbars = {}, {}, {}, {}
        for layer in ("Cultures", "Religions"):
            card = self.cards[layer] = ttk.Frame(body, style="ReviewCard.TFrame", borderwidth=1, relief="solid")
            title = self.card_titles[layer] = ttk.Label(card, text=layer, style="ReviewCardTitle.TLabel")
            title.pack(fill="x")
            table = ttk.Frame(card)
            table.pack(fill="both", expand=True, padx=8, pady=8)
            table.columnconfigure(0, weight=1)
            table.rowconfigure(0, weight=1)
            tree = self.trees[layer] = ttk.Treeview(table, columns=("group", "strength", "role"),
                height=1, selectmode="browse", style="StateReview.Treeview")
            for column, label, width, minimum in (("#0", "Culture" if layer == "Cultures" else "Religion", 170, 120),
                    ("group", "Group", 110, 75), ("strength", "Presence", 110, 90), ("role", "Role", 90, 70)):
                tree.heading(column, text=label)
                tree.column(column, width=ui.px(width), minwidth=ui.px(minimum), anchor="w")
            tree.grid(row=0, column=0, sticky="nsew")
            scroll = self.scrollbars[layer] = ttk.Scrollbar(table, command=tree.yview)
            scroll.grid(row=0, column=1, sticky="ns")
            tree.configure(yscrollcommand=lambda first, last, scroll=scroll: self.scroll_changed(scroll, first, last))
            horizontal = ttk.Scrollbar(table, command=tree.xview, orient="horizontal")
            horizontal.grid(row=1, column=0, sticky="ew")
            tree.configure(xscrollcommand=lambda first, last, scroll=horizontal: self.scroll_changed(scroll, first, last))
        self.extras_body = ttk.Frame(content)
        self.extras_body.pack(fill="x", pady=(10, 6))
        self.empty_extras = ttk.Label(self.extras_body, style="Muted.TLabel", justify="left")
        self.extras_ready = False
        self.extras = {}
        for key, title in (("migratory", "Migratory tribe"), ("order", "Cult / Order")):
            card = ttk.Frame(self.extras_body, padding=10, style="ReviewCard.TFrame", borderwidth=1, relief="solid")
            image = ttk.Label(card, style="ReviewCardText.TLabel")
            image.grid(row=0, column=0, rowspan=3, padx=(0, 10), sticky="n")
            ttk.Label(card, text=title, style="ReviewCardSmall.TLabel").grid(row=0, column=1, sticky="w")
            value = ttk.Label(card, style="ReviewCardValue.TLabel", justify="left")
            value.grid(row=1, column=1, sticky="w", pady=(3, 0))
            band = ttk.Label(card, style="ReviewCardSmall.TLabel", justify="left")
            band.grid(row=2, column=1, sticky="w", pady=(3, 0))
            card.columnconfigure(1, weight=1)
            self.extras[key] = dict(card=card, image=image, value=value, band=band, row=None)
        self.source = ttk.Label(content, style="Muted.TLabel", justify="left")
        self.source.pack(anchor="w", pady=(4, 0))
        self.map_panel = review_map.RegionalMap(content, root, lambda sid: self.show(self.task, sid))
        self.bind("<Configure>", self.layout)
        self.bind("<Destroy>", self.destroyed, add="+")
        ui.THEME_HOOKS.append(self.theme_changed)
        self.theme_changed()

    def theme_changed(self):
        style = ttk.Style(self)
        style.configure("StateReview.Treeview", rowheight=ui.px(40), font="om_body")
        style.configure("StateReview.Treeview.Heading", font="om_small_bold", padding=(ui.px(8), ui.px(6)))
        style.configure("ReviewCard.TFrame", background=ui.P["surface"], bordercolor=ui.P["border"])
        style.configure("ReviewCardTitle.TLabel", background=ui.P["header_background"],
            foreground=ui.P["header_foreground"], font="om_bold", padding=(ui.px(10), ui.px(7)))
        for name, font, color in (("Text", "om_body", ui.P["foreground"]),
                ("Small", "om_small", ui.P["muted"]), ("Value", "om_bold", ui.P["foreground"])):
            style.configure("ReviewCard" + name + ".TLabel", background=ui.P["surface"], foreground=color, font=font)
        style.configure("ReviewReason.TLabel", background=ui.P["header_background"],
            foreground=ui.P["header_foreground"], font="om_bold", padding=(ui.px(10), ui.px(6)))
        style.configure("Review.Horizontal.TProgressbar", background="#2a9b59", troughcolor=ui.P["surface"],
                        bordercolor=ui.P["border"], thickness=ui.px(7))
        self.progress.configure(length=ui.px(90))
        self._scale = ui.scale()
        for tree in self.trees.values():
            tree.tag_configure("majority", font="om_bold")
            ui.stripe(tree)
        self.refresh_extra_icons()
        self.update_approval()

    def layout(self, _event=None):
        if self._scale != ui.scale():
            self.theme_changed()
        width = max(1, self.winfo_width())
        stacked = width < ui.px(1000)
        if stacked != self._stacked:
            self._stacked = stacked
            for container, cards in ((self.body, list(self.cards.values())),):
                for col in (0, 1):
                    container.columnconfigure(col, weight=1 if col == 0 or not stacked else 0,
                                              uniform="review_cards" if not stacked else "")
                for index, card in enumerate(cards):
                    card.grid(row=index if stacked else 0, column=0 if stacked else index, sticky="nsew",
                        padx=(0, 0 if stacked or index else 12), pady=(0, 8 if stacked and index == 0 else 0))
        self.layout_extras(stacked)
        narrow = width < ui.px(720)
        self.open_button.grid(row=1 if narrow else 0, column=0 if narrow else 4,
            columnspan=4 if narrow else 1, sticky="ew", padx=(0 if narrow else 12, 0), pady=(6 if narrow else 0, 0))
        action_width = max(self.open_button.winfo_reqwidth(), self.approve_button.winfo_reqwidth())
        self.review_actions.columnconfigure(1, minsize=action_width + 12)
        self.reasons.configure(wraplength=max(80, width - action_width - ui.px(40)))
        for label in (self.state_title, self.source):
            label.configure(wraplength=max(120, width - 24))
        for part in self.extras.values():
            wrap = max(120, (width if stacked else width // 2) - ui.px(85))
            part["value"].configure(wraplength=wrap)
            part["band"].configure(wraplength=wrap)

    @staticmethod
    def scroll_changed(scroll, first, last):
        scroll.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            scroll.grid_remove()
        elif not scroll.winfo_manager():
            scroll.grid()

    def show(self, task, selected_sid=None):
        old_task, old_sid = self.task, self.current_sid
        same_review = bool(task and old_task and task.get("ref") == old_task.get("ref")
                           and task.get("link") == old_task.get("link"))
        self.display_key = None
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        if self.future:
            self.future.cancel()
            self.future = None
        if not same_review:
            self.photos = []
            for layer, tree in self.trees.items():
                tree.delete(*tree.get_children())
                self.card_titles[layer].configure(text=layer)
            self.current = {}
        self.task = task
        sid = selected_sid or state_id(task)
        self.members = (task or {}).get("review_states") or ([dict(id=sid, name=f"State {sid}")] if sid else [])
        if (selected_sid is None and old_task and task and old_task.get("ref") == task.get("ref")
                and old_sid in {row["id"] for row in self.members}):
            sid = old_sid
        self.current_sid = sid
        self.map_panel.set_review(task, sid)
        if not sid:
            self.pack_forget()
            return
        if not self.winfo_manager():
            self.pack(fill="x")
        self.state_choice.configure(values=[f"{row['id']}: {row.get('name', 'State')}" for row in self.members])
        index = next(i for i, row in enumerate(self.members) if row["id"] == sid)
        self.state_choice.current(index)
        self.position.configure(text=f"State {index + 1} of {len(self.members)}" if len(self.members) > 1 else "State")
        self.previous.state(["!disabled"] if index > 0 else ["disabled"])
        self.next.state(["!disabled"] if index + 1 < len(self.members) else ["disabled"])
        self.state_title.configure(text=self.members[index].get("name") or f"State {sid}")
        self.reasons.configure(text="Review focus   ·   " + ("  /  ".join(task.get("review_reasons") or []) or "General review"))
        self.source.configure(text="Loading saved state data…")
        # Keep the last composition and its geometry until the next one can be replaced in one Tk turn.
        if not same_review:
            for part in self.extras.values():
                part.update(row=None, photo=None)
                part["value"].configure(text="Loading…")
                part["band"].configure(text="")
                part["image"].configure(image="")
            self.extras_ready = False
        fallback = next((row.get("snapshot") for row in self.members if row["id"] == sid), None) or task.get("review_snapshot")
        self.future = self.pool.submit(self.loader.load_review, sid, fallback, ui.px(28), review_ids(task))
        self.job = self.after(40, self.poll)
        self.layout()
        self.update_approval()

    def approve_state(self):
        if self.on_approve and self.task and self.current_sid:
            self.on_approve(self.current_sid, self.status(self.current_sid) != "approved", self.current.get(self.current_sid))

    def status(self, sid):
        return review_status(self.task, sid, self.current.get(sid))

    def colours(self, status):
        dark = ui.THEME["t"].get("dark", False)
        if status == "approved":
            return ("#163d2a", "#c4f5d5") if dark else ("#d9f0df", "#166534")
        if status == "changed":
            return ("#163956", "#c8e7ff") if dark else ("#dbeeff", "#154e84")
        return ui.P["input_background"], ui.P["input_foreground"]

    def colour_choices(self):
        # ttk's Windows dropdown is a Tk listbox; colour each row without replacing keyboard navigation.
        popup = self.tk.call("ttk::combobox::PopdownWindow", str(self.state_choice))
        self.after_idle(lambda: self.paint_choices(popup))

    def paint_choices(self, popup):
        listing = str(popup) + ".f.l"
        if not self.winfo_exists() or not self.tk.call("winfo", "exists", listing):
            return
        for index, member in enumerate(self.members):
            status = self.status(member["id"])
            bg, fg = self.colours(status)
            selected = "#205f3a" if status == "approved" else "#205e94" if status == "changed" else ui.P["selection_background"]
            self.tk.call(listing, "itemconfigure", index, "-background", bg, "-foreground", fg,
                         "-selectbackground", selected, "-selectforeground", "#ffffff" if status != "pending" else ui.P["selection_foreground"])

    def update_approval(self):
        status = self.status(self.current_sid)
        yes, changed = status == "approved", status == "changed"
        dark = ui.THEME["t"].get("dark", False)
        green = "#7cdda0" if dark else "#166534"
        self.approve_button.configure(text="✓ Approved" if yes else "Approve Changes" if changed else "Approve as is",
            background="#167241" if yes else "#205e94" if changed else ui.P["button_background"],
            foreground="#ffffff" if yes or changed else ui.P["button_foreground"],
            activebackground="#205f3a" if yes else "#174c7a" if changed else ui.P["button_active"],
            activeforeground="#ffffff" if yes or changed else ui.P["button_foreground"],
            state="normal" if self.on_approve and self.task and self.future is None else "disabled")
        self.state_title.configure(foreground=green if yes else ("#82caff" if dark else "#154e84") if changed else ui.P["header_foreground"])
        ids = review_ids(self.task)
        total = sum(self.status(sid) == "approved" for sid in ids)
        self.section.count.configure(text=f"{total} / {len(ids)} approved" if ids else "",
                                     foreground=green if yes else ui.P["muted"])
        self.progress.configure(maximum=max(1, len(ids)), value=total)
        self.state_choice.configure(values=[("✓ " if self.status(row["id"]) == "approved" else "? " if self.status(row["id"]) == "changed" else "")
                                           + f"{row['id']}: {row.get('name', 'State')}" for row in self.members])
        index = next((i for i, row in enumerate(self.members) if row["id"] == self.current_sid), None)
        if index is not None:
            self.state_choice.current(index)
        bg, fg = self.colours(status)
        ttk.Style(self).map("Review.TCombobox", fieldbackground=[("readonly", bg)], foreground=[("readonly", fg)])
        self.map_panel.approved = {sid for sid in ids if self.status(sid) == "approved"}
        self.map_panel.changed = {sid for sid in ids if self.status(sid) == "changed"}
        self.map_panel.render()

    def layout_extras(self, stacked):
        present = [part["card"] for part in self.extras.values() if not self.extras_ready or part["row"]]
        for part in self.extras.values():
            if part["card"] not in present:
                part["card"].grid_remove()
        for col in (0, 1):
            self.extras_body.columnconfigure(col, weight=1 if col == 0 or not stacked and len(present) == 2 else 0,
                                             uniform="review_extras" if not stacked and len(present) == 2 else "")
        for index, card in enumerate(present):
            card.grid(row=index if stacked else 0, column=0 if stacked else index, sticky="nsew",
                      padx=(0, 12 if not stacked and len(present) == 2 and index == 0 else 0), pady=(0, 8 if stacked else 0))
        missing = [title + ": None recorded" for key, title in (("migratory", "Migratory tribe"), ("order", "Cult / Order"))
                   if self.extras_ready and not self.extras[key]["row"]]
        if missing:
            self.empty_extras.configure(text="   ·   ".join(missing), wraplength=max(120, self.winfo_width() - 24))
            self.empty_extras.grid(row=(len(present) if stacked else 1) if present else 0, column=0,
                                   columnspan=2, sticky="w", pady=(4, 0))
        else:
            self.empty_extras.grid_remove()

    def choose_state(self, _event=None):
        index = self.state_choice.current()
        if 0 <= index < len(self.members):
            self.show(self.task, self.members[index]["id"])

    def step_state(self, step):
        index = self.state_choice.current() + step
        if 0 <= index < len(self.members):
            self.show(self.task, self.members[index]["id"])

    def open_state(self):
        if self.navigate and self.current_sid:
            import master_links
            self.navigate(master_links.make("culture", "state", self.current_sid,
                          system=(self.task or {}).get("review_system") or "culture"))

    def refresh_extra_icons(self):
        for key, part in self.extras.items():
            photo = part.get("photo")
            if not photo:
                try:
                    photo = icons.image("team" if key == "migratory" else "open_book", ui.px(28))
                except (OSError, ValueError, KeyError, tk.TclError):
                    photo = None
            part["image"].configure(image=photo or "")

    def poll(self):
        self.job = None
        if not self.future.done():
            self.job = self.after(40, self.poll)
            return
        try:
            data, source, images, current = self.future.result()
        except Exception:
            data, source, images, current = None, "State data unavailable on this computer.", {}, {}
        self.future = None
        # Never compare the historical fallback with itself as if it were current data.
        self.current = current
        stale = [sid for sid in review_ids(self.task) if approved(self.task, sid) and self.status(sid) == "changed"]
        if stale and self.on_invalidate:
            self.on_invalidate(stale)
        self.update_approval()
        self.source.configure(text=source)
        display_key = (data, source, ui.scale())
        if data and display_key == self.display_key:
            self.refresh_job = self.after(5000, self.refresh)
            return
        self.display_key = display_key
        for tree in self.trees.values():
            tree.delete(*tree.get_children())
        if not data:
            for tree in self.trees.values():
                tree.configure(height=1)
                tree.insert("", "end", text="Data unavailable", values=("—", "—", "—"))
            for part in self.extras.values():
                part["value"].configure(text="Unavailable")
            self.refresh_job = self.after(5000, self.refresh)
            return
        if data.get("name"):
            self.state_title.configure(text=data["name"])
            if len(self.members) == 1 and not self.task.get("review_states"):
                self.members[0]["name"] = data["name"]
                self.state_choice.configure(values=[f"{self.current_sid}: {data['name']}"])
                self.state_choice.current(0)
        photos = {name: ImageTk.PhotoImage(image, master=self) for name, image in images.items()}
        self.photos = list(photos.values())
        for layer, field in (("Cultures", "cultures"), ("Religions", "religions")):
            tree = self.trees[layer]
            rows = data.get(field, [])
            self.card_titles[layer].configure(text=f"{layer}  ·  {len(rows)}")
            tree.configure(height=max(1, min(5, len(rows))))
            for row in rows:
                image = photos.get(row.get("icon"))
                tree.insert("", "end", text=row["name"], values=(row.get("parent") or "—", row["strength_label"],
                    "Majority" if row.get("majority") else "Minority"), tags=("majority",) if row.get("majority") else (),
                    **({"image": image} if image else {}))
            if not rows:
                tree.insert("", "end", text="No saved data", values=("—", "—", "—"))
            ui.stripe(tree)
        for key, part in self.extras.items():
            row = data.get(key)
            part["row"] = row
            part["photo"] = photos.get((row or {}).get("icon"))
            part["value"].configure(text=row["name"] + " · " + row["strength_label"] if row else "None recorded")
            part["band"].configure(text="Band: " + row["band_name"] if row and row.get("band_name") else "")
        self.refresh_extra_icons()
        self.extras_ready = True
        self.update_approval()
        self.layout()
        self.refresh_job = self.after(5000, self.refresh)

    def refresh(self):
        self.refresh_job = None
        if (self.task and self.winfo_ismapped() and not self.section.collapsed and self.future is None
                and not self.state_choice.instate(["pressed"])):
            fallback = next((row.get("snapshot") for row in self.members if row["id"] == self.current_sid), None) or self.task.get("review_snapshot")
            self.future = self.pool.submit(self.loader.load_review, self.current_sid, fallback, ui.px(28), review_ids(self.task))
            self.job = self.after(40, self.poll)
        else:
            self.refresh_job = self.after(5000, self.refresh)

    def destroyed(self, event):
        if event.widget is self:
            if self.refresh_job:
                self.after_cancel(self.refresh_job)
            if self.job:
                self.after_cancel(self.job)
            self.pool.shutdown(wait=False, cancel_futures=True)
            if self.theme_changed in ui.THEME_HOOKS:
                ui.THEME_HOOKS.remove(self.theme_changed)

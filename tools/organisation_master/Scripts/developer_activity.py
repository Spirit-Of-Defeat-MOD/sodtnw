"""Lead-only activity viewer, using access receipts and attributed saved changes."""
import datetime as dt
import hashlib
import json
import uuid
import tkinter as tk
from tkinter import ttk

import ui


def moment(value):
    try:
        return dt.datetime.fromisoformat(value).astimezone()
    except (ValueError, TypeError, AttributeError):
        return None


def value_text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def history_key(task, event):
    return hashlib.sha256(json.dumps([task.get("ref"), event], sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def changes(before, after, who):
    """Record changes without attribution in older data; ordinary task history already has it."""
    if not who:
        return []
    events = []
    for collection, key, master, noun in (("tasks", "ref", "To Do Master", "task"),
            ("ideas", "id", "Ideas", "idea"), ("idea_header_details", "id", "Ideas", "header details"),
            ("vcs", "id", "Dev VCs", "VC"),
            ("projects", "name", "To Do Master", "project"), ("devs", "name", "To Do Master", "developer")):
        old = {v[key]: v for v in before.get(collection, []) if key in v}
        new = {v[key]: v for v in after.get(collection, []) if key in v}
        for identity in dict.fromkeys([*old, *new]):
            a, b = old.get(identity), new.get(identity)
            if a == b:
                continue
            item = b or a
            fields = [k for k in dict.fromkeys([*(a or {}), *(b or {})])
                      if k not in ("updated", "history", "achievements") and (a or {}).get(k) != (b or {}).get(k)]
            if a is not None and b is not None and not fields:
                continue
            verb = "Created" if a is None else "Deleted" if b is None else "Updated"
            detail = "\n\n".join(f"{k}:\n{clip((a or {}).get(k))}\n→ {clip((b or {}).get(k))}" for k in fields)
            event = dict(id=uuid.uuid4().hex, when=dt.datetime.now().astimezone().isoformat(), who=who,
                master=master, action="changed", title=f"{verb} {noun}", target=str(item.get("title") or item.get("name") or identity), detail=detail)
            if collection == "tasks":
                event["target"] = f"{identity}  {item.get('title', '')}"
                event["history_keys"] = [history_key(item, h) for h in (b or a).get("history", [])
                    if b is None or h not in (a or {}).get("history", [])]
            events.append(event)
    return events


CLIP = 600  # (characters of a field's before / after kept in an event)
MERGE_WITHIN = 10 * 60  # (seconds: edits to the same thing by the same dev this close together are one event)
KEEP_DETAIL_DAYS = 30  # (older events keep who / what / when, not the text)
BIG_STATE = ("states", "map", "snapshot")  # (a state review's payload: in its task once imported)


def clip(value):
    text = value_text(value)
    return text if len(text) <= CLIP else text[:CLIP] + f"… (+{len(text) - CLIP} characters)"


def compact(data):
    """Keeps the shared activity log small (it's saved and live-synced with every change): a dev's edits to the same
    task / idea / VC within MERGE_WITHIN are one event (the latest text, how many edits), the text of old events and
    "opened" receipts older than KEEP_DETAIL_DAYS go, and imported review payloads are slimmed. Saved-work events
    (achievements count them) stay. True when something changed."""
    events = data.get("master_activity") or []
    now = dt.datetime.now().astimezone()
    out, last, changed = [], {}, False
    for event in events:
        when = moment(event.get("when"))
        old = when is not None and (now - when).days > KEEP_DETAIL_DAYS
        if old and event.get("action") == "opened":
            changed = True
            continue
        if isinstance(event.get("state"), dict) and any(k in event["state"] for k in BIG_STATE):
            event = dict(event, state={k: v for k, v in event["state"].items() if k not in BIG_STATE})
            changed = True
        if old and ("detail" in event or "state" in event):
            event = {k: v for k, v in event.items() if k not in ("detail", "state")}
            changed = True
        if isinstance(event.get("detail"), str) and len(event["detail"]) > CLIP * 4:
            event = dict(event, detail=event["detail"][:CLIP * 4 - 1] + "…")
            changed = True
        if event.get("action") == "changed" and when is not None:
            key = (event.get("who"), event.get("master"), event.get("title"), event.get("target"))
            prev = last.get(key)
            if prev is not None and (when - moment(out[prev]["when"])).total_seconds() <= MERGE_WITHIN:
                first = out[prev]
                event = dict(event, merged=first.get("merged", 1) + 1)
                keys = list(dict.fromkeys((first.get("history_keys") or []) + (event.get("history_keys") or [])))
                if keys:
                    event["history_keys"] = keys
                out[prev] = event  # (in the first one's place, with the latest text)
                changed = True
                continue
            last[key] = len(out)
        out.append(event)
    if changed:
        data["master_activity"] = out
    return changed


def entries(data):
    rows, seen = [], set()
    covered = {key for event in data.get("master_activity", []) for key in event.get("history_keys", [])}
    labels = {"opened": "Opened tool", "saved": "Saved work", "changed": "Updated",
              "portrait_unmarked": "Completed portrait review", "portrait_marked": "Flagged portrait",
              "state_review": "Flagged state for review"}
    for event in data.get("master_activity", []):
        if event.get("id") in seen:
            continue
        seen.add(event.get("id"))
        when = moment(event.get("when"))
        if not when or not event.get("who"):
            continue
        files = event.get("files") or []
        state = event.get("state") or {}
        target = event.get("target") or event.get("sprite") or state.get("name") or ", ".join(str(f) for f in files)
        detail = event.get("detail") or state.get("note") or ""
        rows.append(dict(when=when, who=event["who"], tool=event.get("master", ""),
            action=(event.get("title") or labels.get(event.get("action"), event.get("action", "")))
                + (f" ({event['merged']} edits)" if event.get("merged") else ""), target=target,
            detail=str(detail) + ("\n\nFiles:\n" + "\n".join(str(f) for f in files) if files else ""),
            access=event.get("action") == "opened"))
    for task in data.get("tasks", []):
        for event in task.get("history", []):
            if history_key(task, event) in covered:
                continue
            when = moment(event.get("when"))
            if not when or not event.get("who"):
                continue
            field = event.get("field", "created")
            detail = f"{field}:\n{value_text(event.get('old'))}\n→ {value_text(event.get('new'))}"
            if event.get("note"):
                detail += "\n\n" + event["note"]
            rows.append(dict(when=when, who=event["who"], tool="To Do Master", action="Created task" if field in ("created", "set") else "Changed " + field.replace("_", " "),
                target=f"{task.get('ref', '')}  {task.get('title', '')}", detail=detail, access=False))
    for idea in data.get("ideas", []):
        when = moment(idea.get("created"))
        if when and idea.get("by"):
            # New idea creation is already captured by a receipt; older ideas still appear.
            target = idea.get("title", "")
            if not any(r["tool"] == "Ideas" and r["action"] == "Created idea" and r["target"] == target for r in rows):
                rows.append(dict(when=when, who=idea["by"], tool="Ideas", action="Posted idea", target=target, detail=idea.get("text", ""), access=False))
        for comment in idea.get("comments", []):
            when = moment(comment.get("when"))
            if when and comment.get("by"):
                rows.append(dict(when=when, who=comment["by"], tool="Ideas", action="Commented on idea", target=idea.get("title", ""), detail=comment.get("text", ""), access=False))
    return sorted(rows, key=lambda r: r["when"], reverse=True)


class Activity:
    def __init__(self, parent, todo):
        self.todo = todo
        self.window = None
        self.section = ui.Section(parent, "Developer activity · leads", "todo_activity", todo.app, expand=False)
        ui.tool_button(self.section.tools, "View log…", self.open).pack(side="left", padx=2)
        area = ttk.Frame(self.section.body)
        area.pack(fill="x")
        self.summary = ttk.Treeview(area, columns=("access", "change"), height=4, selectmode="browse")
        for col, name, width in (("#0", "Developer", 100), ("access", "Last access", 95), ("change", "Last change", 95)):
            self.summary.heading(col, text=name)
            self.summary.column(col, width=ui.px(width), minwidth=ui.px(55))
        scrollbar = ttk.Scrollbar(area, command=self.summary.yview)
        self.summary.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.summary.pack(fill="x", expand=True)
        self.summary.bind("<Double-1>", lambda ev: self.open(self.summary.focus()))
        self.summary.tag_configure("online", background="#c8f0cf", foreground="#0d4d1c", font="om_bold")  # (🟢 online now)
        ttk.Label(self.section.body, text="🟢 What they're up to", font="om_bold").pack(anchor="w", pady=(6, 0))
        self.now_label = ttk.Label(self.section.body, text="", wraplength=ui.px(330), justify="left")
        self.now_label.pack(fill="x")
        ttk.Label(self.section.body, text="Recorded access and saved actions. Double-click a dev for their log. "
            "Lit up: online now (a tool open).", wraplength=ui.px(330), style="Muted.TLabel").pack(fill="x", pady=(4, 0))
        self.signature = None

    def refresh(self):
        todo = self.todo
        if not todo.is_lead():
            self.section.pack_forget()
            if self.window is not None:
                self.window.destroy()
                self.window = None
            return
        if todo.mode.get() in ("dev", "project"):
            self.section.place_in(fill="x", pady=(8, 0), before=todo.ms_section)
        else:
            self.section.pack_forget()
        signature = (getattr(todo, "_saved", None), todo.me.get())
        if self.signature == signature:
            return
        self.signature = signature
        self.rows = entries(todo.data)
        self.summary.delete(*self.summary.get_children())
        names = {d["name"] for d in todo.data.get("devs", [])}
        latest = {}
        for row in self.rows:
            names.add(row["who"])
            latest.setdefault(row["who"], {}).setdefault("access" if row["access"] else "change", row["when"])
        floor = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
        for name in sorted(names, key=lambda n: max(latest.get(n, {}).values(), default=floor), reverse=True):
            dates = latest.get(name, {})
            self.summary.insert("", "end", iid=name, text=name,
                values=tuple(dates[k].strftime("%d %b %H:%M") if k in dates else "Not recorded" for k in ("access", "change")))
        ui.stripe(self.summary)
        self.section.set_count(str(len(latest)))
        self.online_shown = None
        self.refresh_online()
        if self.window is not None:
            self.filter_rows()

    def refresh_online(self):
        """🟢 Who's online lit up in the list, and what they're up to (now_doing.py; every 10 s and after each refresh)."""
        import now_doing
        if not self.todo.is_lead() or not self.summary.get_children():
            return
        data, me = self.todo.data, self.todo.me.get()
        on = {}
        for name in self.summary.get_children():
            p = now_doing.online(data, name)
            if p is not None:
                on[name] = now_doing.describe(p)
        lines = [f"🟢 {name}{' (you)' if name == me else ''}: {text}" for name, text in on.items()]
        self.now_label.config(text="\n".join(lines) or "Nobody online right now.")
        if on.keys() == (self.online_shown or {}).keys():
            return
        self.online_shown = on
        for name in self.summary.get_children():
            tags = [t for t in self.summary.item(name, "tags") if t != "online"]
            self.summary.item(name, text=("🟢 " if name in on else "") + name, tags=tags + (["online"] if name in on else []))

    def open(self, developer=None):
        if not self.todo.lead_only("view developer activity"):
            return
        if self.window is not None:
            if developer:
                self.dev.set(developer)
                self.filter_rows()
            self.window.lift()
            return
        self.refresh()
        w = self.window = tk.Toplevel(self.todo)
        w.title("Developer activity · lead view")
        w.geometry(f"{ui.px(1100)}x{ui.px(700)}")
        w.minsize(ui.px(720), ui.px(460))
        def close():
            self.window = None
            w.destroy()
        w.protocol("WM_DELETE_WINDOW", close)
        outer = ttk.Frame(w, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Developer access & saved activity", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Access recording starts with this update. Existing task history is included. Times are local; activity appears after live sync.",
            wraplength=ui.px(1000), style="Muted.TLabel").pack(anchor="w", pady=(4, 10))
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 8))
        self.dev = tk.StringVar(value=developer or "All developers")
        self.tool = tk.StringVar(value="All tools")
        self.period = tk.StringVar(value="30 days")
        self.search = tk.StringVar()
        for label, var, values in (("Developer", self.dev, ["All developers"] + sorted({r["who"] for r in self.rows} | set(self.todo.dev_names()))),
                ("Tool", self.tool, ["All tools"] + sorted({r["tool"] for r in self.rows})),
                ("Period", self.period, ("7 days", "30 days", "90 days", "All time"))):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            ttk.Combobox(bar, textvariable=var, values=values, state="readonly", width=17).pack(side="left", padx=(0, 12))
            var.trace_add("write", lambda *_: self.filter_rows())
        search_row = ttk.Frame(outer)
        search_row.pack(fill="x", pady=(0, 8))
        ttk.Label(search_row, text="Search").pack(side="left", padx=(0, 8))
        ttk.Entry(search_row, textvariable=self.search).pack(side="left", fill="x", expand=True)
        self.search.trace_add("write", lambda *_: self.filter_rows())
        pw = ttk.PanedWindow(outer, orient="vertical")
        pw.pack(fill="both", expand=True)
        area = ttk.Frame(pw)
        pw.add(area, weight=3)
        columns = ("when", "who", "tool", "action", "target")
        tree = self.tree = ttk.Treeview(area, columns=columns, show="headings", selectmode="browse")
        for col, label, width in zip(columns, ("When", "Developer", "Tool", "Action", "Task / target"), (140, 100, 140, 170, 370)):
            tree.heading(col, text=label)
            tree.column(col, width=ui.px(width), minwidth=ui.px(65), stretch=col == "target")
        scroll = ttk.Scrollbar(area, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        horizontal = ttk.Scrollbar(area, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)
        detail_area = ttk.Frame(pw)
        pw.add(detail_area, weight=1)
        ttk.Label(detail_area, text="Selected activity details").pack(anchor="w", pady=(6, 4))
        self.detail = tk.Text(detail_area, height=7, wrap="word", state="disabled", font="om_body")
        detail_scroll = ttk.Scrollbar(detail_area, command=self.detail.yview)
        self.detail.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side="right", fill="y")
        self.detail.pack(fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", self.show_detail)
        self.count = ttk.Label(outer, style="Muted.TLabel")
        self.count.pack(anchor="w", pady=(6, 0))
        self.filter_rows()
        ui.theme_all(w)

    def filter_rows(self):
        if not self.todo.is_lead() or self.window is None:
            return
        days = {"7 days": 7, "30 days": 30, "90 days": 90}.get(self.period.get())
        cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=days) if days else None
        query = self.search.get().strip().casefold()
        self.filtered = [r for r in self.rows if (self.dev.get() == "All developers" or r["who"] == self.dev.get())
            and (self.tool.get() == "All tools" or r["tool"] == self.tool.get()) and (cutoff is None or r["when"] >= cutoff)
            and (not query or query in " ".join(str(v) for v in r.values()).casefold())]
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.filtered[:2000]):
            self.tree.insert("", "end", iid=str(index), values=(row["when"].strftime("%d %b %Y %H:%M"), row["who"], row["tool"], row["action"], row["target"]))
        ui.stripe(self.tree)
        self.count.configure(text=f"{len(self.filtered)} matching entries" + (" · showing latest 2,000; narrow the filters for older entries" if len(self.filtered) > 2000 else ""))
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.configure(state="disabled")

    def show_detail(self, _event=None):
        if not self.todo.is_lead():
            return
        selected = self.tree.selection()
        if selected:
            row = self.filtered[int(selected[0])]
            text = f"{row['who']} · {row['tool']} · {row['when'].strftime('%d %b %Y %H:%M:%S')}\n{row['action']}\n{row['target']}\n\n{row['detail']}"
            self.detail.configure(state="normal")
            self.detail.delete("1.0", "end")
            self.detail.insert("1.0", text)
            self.detail.configure(state="disabled")

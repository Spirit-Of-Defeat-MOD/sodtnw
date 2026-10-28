"""Reorder complete station song blocks without rebuilding their chance scripts."""
import re
import tkinter as tk

import ui

TOKENS = re.compile(r'"(?:[^"\\]|\\.)*"|[{}]|>=|<=|!=|[=<>]|[^\s{}=<>"#]+|#[^\n]*')


def reorder_song_blocks(lines, order):
    text = "\n".join(lines)
    tokens = [match for match in TOKENS.finditer(text) if not match[0].startswith("#")]
    spans = []
    depth = 0
    index = 0
    while index < len(tokens):
        token = tokens[index][0]
        if depth == 0 and token == "music" and index + 2 < len(tokens) and tokens[index + 1][0] == "=" and tokens[index + 2][0] == "{":
            start = tokens[index].start()
            line_start = text.rfind("\n", 0, start) + 1
            if not text[line_start:start].strip():
                start = line_start
            nesting = 1
            last = index + 3
            while last < len(tokens) and nesting:
                nesting += (tokens[last][0] == "{") - (tokens[last][0] == "}")
                last += 1
            if nesting:
                raise ValueError("The station file has an unclosed music block. Fix its braces before reordering.")
            end = tokens[last - 1].end()
            line_end = text.find("\n", end)
            line_end = len(text) if line_end < 0 else line_end
            if text[end:line_end].lstrip().startswith("#"):
                end = line_end  # Keep a closing-line comment with its song.
            spans.append((start, end))
            index = last
            continue
        depth += (token == "{") - (token == "}")
        if depth < 0:
            raise ValueError("The station file has an unmatched closing brace.")
        index += 1
    if depth or len(order) != len(spans) or sorted(order) != list(range(len(spans))):
        raise ValueError("The station file changed or has invalid blocks. Reload it before reordering.")
    blocks = [text[start:end] for start, end in spans]
    parts, previous = [], 0
    for (start, end), source in zip(spans, order):
        parts.extend((text[previous:start], blocks[source]))
        previous = end
    parts.append(text[previous:])
    return "".join(parts).split("\n")


class SongOrderDrag:
    def __init__(self, music):
        self.music, self.tree = music, music.song_tree
        self.drag = None
        self.line = tk.Canvas(self.tree, height=3, borderwidth=0, highlightthickness=0, takefocus=False)
        self.tree._drag_drop_overlay = self.line
        for event, handler in (("<ButtonPress-1>", self.press), ("<B1-Motion>", self.motion),
                ("<ButtonRelease-1>", self.release), ("<Escape>", self.cancel),
                ("<Unmap>", self.cancel), ("<FocusOut>", self.cancel)):
            self.tree.bind(event, handler, add="+")

    def press(self, event):
        self.cancel()
        page, tree = self.music, self.tree
        if page.song_sort.get() != "Order in the file" or not page.station or len(page.station.songs) < 2:
            return
        row = tree.identify_row(event.y)
        if (not row or not row.isdigit() or tree.identify_region(event.x, event.y) not in ("tree", "cell")
                or page.on_play_icon(tree, event) or event.state & 5):
            return
        selected = set(tree.selection()) if row in tree.selection() else {row}
        rows = [value for value in tree.get_children() if value in selected]
        self.drag = dict(x=event.x, y=event.y, rows=rows, active=False,
            mod=page.mod, token=page.station.token, count=len(page.station.songs))
        if len(rows) > 1:
            return "break"  # Keep a multi-selection together until it is dropped.

    def destination(self, event):
        tree = self.tree
        if not 0 <= event.x < tree.winfo_width() or not 0 <= event.y < tree.winfo_height():
            return None
        row = tree.identify_row(event.y)
        if row and row.isdigit():
            box = tree.bbox(row)
            after = event.y >= box[1] + box[3] / 2
            return int(row) + int(after), box[1] + (box[3] if after else 0)
        rows = tree.get_children()
        visible = [tree.bbox(row) for row in rows if tree.bbox(row)]
        if visible and event.y >= visible[-1][1] + visible[-1][3]:
            return self.drag["count"], min(tree.winfo_height() - 3, visible[-1][1] + visible[-1][3])
        return None

    def motion(self, event):
        drag = self.drag
        if not drag:
            return
        if not drag["active"] and abs(event.x-drag["x"]) + abs(event.y-drag["y"]) < ui.px(6):
            return
        if self.music.song_sort.get() != "Order in the file":
            self.cancel()
            return
        drag["active"] = True
        tree = self.tree
        if event.y < ui.px(35):
            tree.yview_scroll(-1, "units")
        elif event.y > tree.winfo_height() - ui.px(20):
            tree.yview_scroll(1, "units")
        ui.drag_wobble(tree, event, drag["rows"], origin=(drag["x"], drag["y"]))
        destination = self.destination(event)
        if destination:
            self.line.config(background=ui.P["copper"])
            self.line.place(x=1, y=destination[1], width=max(1, tree.winfo_width()-2), height=3)
            self.line.tk.call("raise", str(self.line))
        else:
            self.line.place_forget()
        return "break"

    def release(self, event):
        drag = self.drag
        if not drag or not drag["active"]:
            self.cancel()
            return
        destination = self.destination(event)
        self.cancel()
        page = self.music
        if (destination is None or page.song_sort.get() != "Order in the file" or page.mod is not drag["mod"]
                or not page.station or page.station.token != drag["token"] or len(page.station.songs) != drag["count"]):
            return "break"
        selected = sorted(int(row) for row in drag["rows"])
        remaining = [index for index in range(drag["count"]) if index not in selected]
        insertion = sum(index < destination[0] for index in remaining)
        order = remaining[:insertion] + selected + remaining[insertion:]
        if order == list(range(drag["count"])):
            return "break"
        try:
            lines = reorder_song_blocks(page.mod.text_lines(page.station.rel), order)
        except ValueError as error:
            from tkinter import messagebox
            messagebox.showerror("Song order", str(error), parent=page)
            return "break"
        page.write(page.station.rel, lines)
        page.mod.load()
        page.station = page.mod.stations.get(drag["token"])
        page.show_station()
        rows = [str(index) for index, old in enumerate(order) if old in selected]
        self.tree.selection_set(rows)
        if rows:
            self.tree.see(rows[0])
        page.status("Song order updated. Save to mod writes this order to the station file for the game.")
        getattr(page.app, "feedback", lambda *args: None)("success")
        return "break"

    def cancel(self, event=None):
        self.drag = None
        self.line.place_forget()
        wobble = getattr(self.tree, "_drag_wobble", None)
        if wobble is not None:
            wobble.stop()

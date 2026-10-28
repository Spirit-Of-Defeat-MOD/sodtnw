"""Music planning uses the existing live data; actual music stays in its own repositories."""
import copy
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
from tkinter import messagebox
from urllib.parse import urlsplit

import todo_sync
import ui

PLANS = "music_plans"
CATALOG = "music_station_catalog"
LOGOS = "planned_station_logos"


def normalise(plans):
    """Stable migration IDs let two PCs recognise the same older plan/song."""
    counts = {}
    for plan in plans:
        identity = str((plan.get("mod", ""), plan.get("token", ""), plan.get("title", "")))
        counts[identity] = counts.get(identity, 0) + 1
        plan.setdefault("id", "plan-" + hashlib.sha256(
            f"{identity}:{counts[identity]}".encode()).hexdigest()[:20])
        songs = []
        seen = {}
        for item in plan.get("songs", []):
            song = item if isinstance(item, dict) else {"title": str(item)}
            key = str((song.get("title", ""), song.get("artist", ""), song.get("link", "")))
            seen[key] = seen.get(key, 0) + 1
            song.setdefault("id", "song-" + hashlib.sha256(
                f"{plan['id']}:{key}:{seen[key]}".encode()).hexdigest()[:20])
            songs.append(song)
        plan["songs"] = songs


def safe_folder(parent, folder):
    if not folder or folder in (".", "..") or not re.fullmatch(r"[\w .-]+", folder) or folder[-1] in " .":
        raise ValueError("Invalid music mod folder")
    parent = Path(parent).resolve()
    target = (parent / folder).resolve()
    if target.parent != parent:
        raise ValueError("Music mod must be directly inside the mod folder")
    return target


def remote_url(value):
    """Only normal hosted Git URLs; never shell helpers, local paths or embedded passwords."""
    if re.fullmatch(r"git@[\w.-]+:[\w./-]+", value or ""):
        return value
    parsed = urlsplit(value or "")
    if (parsed.scheme in ("https", "ssh") and parsed.hostname and parsed.path.strip("/")
            and not parsed.password and (not parsed.username or parsed.scheme == "ssh")
            and not any(c.isspace() for c in value)):
        return value
    return ""


def run_git(folder, *args, timeout=120):
    result = subprocess.run(["git", "-C", str(folder), *args], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-1200:] or "Git failed")
    return result.stdout.strip()


def pull_music_mods(parent, repos, download=False):
    """One operation per repository; never reset, stash, overwrite a folder or resolve a merge."""
    results = []
    for folder, meta in repos.items():
        try:
            target = safe_folder(parent, folder)
            if download:
                if target.exists():
                    raise RuntimeError("Folder already exists; left untouched")
                url = remote_url(meta.get("remote", ""))
                if not url:
                    raise RuntimeError("No shareable repository URL yet")
                branch = meta.get("branch", "")
                if branch and (branch.startswith("-") or not re.fullmatch(r"[\w./-]+", branch)):
                    raise RuntimeError("Invalid repository branch")
                args = ["clone"] + (["--branch", branch] if branch else []) + ["--", url, str(target)]
                run_git(parent, *args, timeout=600)
                descriptor = target / "descriptor.mod"
                launcher = Path(parent) / (folder + ".mod")
                if descriptor.is_file() and not launcher.exists():
                    text = descriptor.read_text(encoding="utf-8-sig")
                    text = re.sub(r'(?m)^\s*path\s*=.*\n?', "", text)
                    launcher.write_text(text.rstrip() + f'\npath="{target.as_posix()}"\n', encoding="utf-8")
            else:
                # A surrounding repo is not the station mod's own repository.
                top = Path(run_git(target, "rev-parse", "--show-toplevel")).resolve()
                if top != target:
                    raise RuntimeError("This folder is not a music repository")
                if run_git(target, "status", "--porcelain"):
                    raise RuntimeError("Local changes present; save/commit them before pulling")
                run_git(target, "pull", "--ff-only", timeout=600)
            results.append((folder, True, "Downloaded" if download else "Updated"))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            results.append((folder, False, str(error)))
    return results


class MusicLive:
    def init_music_live(self):
        self._music_pulling = False
        self._music_repos = {}
        page = self.app.todo_page()
        shared = page.data.get(PLANS)
        normalise(self.plans)
        local = {"plans": self.plans, "music_mods": self.mod_meta}
        if shared is None:
            shared = local
        elif not self.app.config.get("music_live_initialised"):
            # First upgrade: import this developer's previously local-only plans once.
            shared = todo_sync.merge({}, shared, local)
        page.data[PLANS] = copy.deepcopy(shared)
        self.app.config["music_live_initialised"] = True
        self.app.save_config()
        self._music_base = copy.deepcopy(shared)
        self.plans = copy.deepcopy(shared.get("plans", []))
        self.mod_meta = copy.deepcopy(shared.get("music_mods", {}))
        self.catalog = copy.deepcopy(page.data.get(CATALOG, {}))
        self.fill_mods()
        self.save_plans()
        self.fill_plans()
        self.publish_stations()

    def publish_music_plans(self):
        if not hasattr(self, "_music_base"):
            return
        page = self.app.todo_page()
        normalise(self.plans)
        local = {"plans": self.plans, "music_mods": self.mod_meta}
        shared = todo_sync.merge(self._music_base, local, page.data.get(PLANS, self._music_base))
        self._music_base = copy.deepcopy(shared)
        page.data[PLANS] = copy.deepcopy(shared)
        if shared != local:
            # A deferred incoming update may have arrived while a plan edit was pending.
            # Keep existing plan objects alive for any editor which still references them.
            by_id = {plan["id"]: plan for plan in self.plans}
            combined = []
            for value in shared.get("plans", []):
                value = copy.deepcopy(value)
                plan = by_id.get(value["id"], {})
                plan.clear()
                plan.update(value)
                combined.append(plan)
            self.plans = combined
            self.mod_meta = copy.deepcopy(shared.get("music_mods", {}))
        if page.sync.ready:
            self.copy_plan_logos(Path(todo_sync.CLONE))
        page.save(undoable=False, feedback=False)

    def copy_plan_logos(self, destination):
        for plan in self.plans:
            rel = plan.get("logo", "")
            if not rel or not rel.startswith(LOGOS + "/") or Path(rel).name != rel[len(LOGOS) + 1:]:
                continue
            source = Path(self.plans_path()).parent / rel
            target = destination / rel
            if source.is_file() and source.resolve() != target.resolve():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    def plan_logo_path(self, plan):
        rel = (plan or {}).get("logo", "")
        if not rel or not rel.startswith(LOGOS + "/") or Path(rel).name != rel[len(LOGOS) + 1:]:
            return ""
        # Local selection takes precedence until its next sync; remote assets are copied on receipt.
        local = Path(self.plans_path()).parent / rel
        return str(local if local.is_file() else Path(todo_sync.CLONE) / rel)

    def receive_music_live(self):
        if not hasattr(self, "_music_base"):
            return
        page = self.app.todo_page()
        shared = page.data.get(PLANS, self._music_base)
        catalog = page.data.get(CATALOG, {})
        changed = shared != self._music_base
        if not changed and catalog == self.catalog:
            return
        selected = {self.plans[int(row)].get("id") for row in self.plan_tree.selection()
            if row.isdigit() and int(row) < len(self.plans)}
        was_plan = bool(self.cur_plan)
        if changed:
            self._music_base = copy.deepcopy(shared)
            self.plans = copy.deepcopy(shared.get("plans", []))
            self.mod_meta = copy.deepcopy(shared.get("music_mods", {}))
            self.cur_plan = None
            # Mirror to disk for offline use and older clients, without publishing it again.
            self.write_plans_file()
            for plan in self.plans:
                rel = plan.get("logo", "")
                if rel and rel.startswith(LOGOS + "/") and Path(rel).name == rel[len(LOGOS) + 1:]:
                    source = Path(todo_sync.CLONE) / rel
                    if source.is_file():
                        target = Path(self.plans_path()).parent / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
        self.catalog = copy.deepcopy(catalog)
        self.plan_tree.selection_remove(*self.plan_tree.selection())
        self.fill_plans()
        for i, plan in enumerate(self.plans):
            if plan.get("id") in selected and self.plan_tree.exists(str(i)):
                self.plan_tree.selection_add(str(i))
        self.fill_stations()
        if was_plan:
            # Tree selection notifications are queued; restore the active editor after them.
            self.after_idle(self.show_plan)

    def publish_stations(self):
        """Announce saved stations, including ones unrelated to a plan, without sending audio over live sync."""
        if not hasattr(self, "_music_base"):
            return
        page = self.app.todo_page()
        catalog = copy.deepcopy(page.data.get(CATALOG, {}))
        for root in self.rr_mods():
            mod = self.get_mod(root)
            if mod.pending_count():
                continue
            folder = os.path.basename(root)
            if root not in self._music_repos:
                try:
                    self._music_repos[root] = {
                        "remote": remote_url(run_git(root, "remote", "get-url", "origin", timeout=5)),
                        "branch": run_git(root, "branch", "--show-current", timeout=5)}
                except (OSError, RuntimeError, subprocess.SubprocessError):
                    self._music_repos[root] = {}
            for token, station in mod.stations.items():
                if not os.path.isfile(mod.path(station.rel)):
                    continue
                files = [station.rel]
                for name, _, _ in station.songs:
                    song = mod.songs.get(name)
                    if song:
                        files.extend([song.rel, "music/" + song.file])
                if station.art:
                    files.append(os.path.relpath(station.art, root).replace("\\", "/"))
                entry = dict(self._music_repos[root], mod=folder, token=token,
                    title=station.title or token, songs=len(station.songs),
                    files=sorted({rel for rel in files if os.path.isfile(mod.path(rel))}))
                old = catalog.get(folder + "|" + token)
                # An older checkout must not downgrade another developer's completed station.
                if old and (old.get("songs", 0) > entry["songs"] or any(
                        not (Path(root) / rel).is_file() for rel in old.get("files", []))):
                    continue
                catalog[folder + "|" + token] = entry
        if catalog != page.data.get(CATALOG, {}):
            page.data[CATALOG] = catalog
            page.save(undoable=False, feedback=False)
        self.catalog = copy.deepcopy(catalog)
        self.fill_stations()

    def missing_stations(self):
        catalog = dict(getattr(self, "catalog", {}))
        # Made plans from older clients can still advertise the missing station.
        for plan in self.plans:
            folder, token = plan.get("mod", ""), plan.get("token", "")
            if plan.get("status") == "Made" and folder and token and not folder.startswith("planned:"):
                catalog.setdefault(folder + "|" + token, dict(mod=folder, token=token,
                    title=plan.get("title", token), songs=len(plan.get("songs", []))))
        missing = {}
        for ident, entry in catalog.items():
            try:
                target = safe_folder(self.app.mod_dir, entry.get("mod", ""))
            except ValueError:
                continue
            mod = next((m for m in self._loaded.values() if Path(m.root).resolve() == target), None)
            station = mod.stations.get(entry.get("token")) if mod else None
            files_missing = any(not (target / rel).is_file() for rel in entry.get("files", []))
            if not station or files_missing or len(station.songs) < entry.get("songs", 0):
                missing[ident] = entry
        return missing

    def fill_missing_stations(self):
        self._missing_music = self.missing_stations()
        tree = self.st_tree
        tree.tag_configure("not_local", foreground=ui.P.get("muted", "#888888"))
        shown = {os.path.basename(m.root) for m in self.view_mods}
        all_mods = self.mod_var.get() == "★ All RR music mods" or not self.view_mods
        for ident, entry in self._missing_music.items():
            if not all_mods and entry["mod"] not in shown and self.mod_exists(entry["mod"]):
                continue
            text = entry["title"] + " — not downloaded"
            if tree.exists(ident):
                tree.item(ident, text=text, values=(entry.get("songs", ""), "Not local"), tags=("not_local",))
            else:
                tree.insert("", "end", iid=ident, text=text,
                    values=(entry.get("songs", ""), "Not local"), tags=("not_local",))
        existing = {e["mod"] for e in self._missing_music.values()
            if safe_folder(self.app.mod_dir, e["mod"]).exists()}
        absent = {e["mod"] for e in self._missing_music.values()} - existing
        self.pull_stations_button.config(text=f"Pull station updates ({len(existing)})")
        self.download_stations_button.config(text=f"Get missing music mods ({len(absent)})")
        self.pull_stations_button.state(["!disabled"] if existing and not self._music_pulling else ["disabled"])
        self.download_stations_button.state(["!disabled"] if absent and not self._music_pulling else ["disabled"])

    def pull_stations(self, download=False):
        if self._music_pulling:
            return
        self.flush_plan()
        repos = {}
        for entry in self.missing_stations().values():
            folder = entry["mod"]
            target = safe_folder(self.app.mod_dir, folder)
            if (not target.exists()) != download:
                continue
            repos[folder] = entry
        if not repos:
            return
        staged = [m.name for m in self.unsaved() if os.path.basename(m.root) in repos]
        if staged:
            messagebox.showinfo("Music Master", "Save or discard pending edits first: " + ", ".join(staged), parent=self)
            return
        self._music_pulling = True
        self.fill_stations()
        self.tk.call("tk", "busy", "hold", str(self))
        self.status("Downloading music mods…" if download else "Pulling music station updates…")
        results = []

        def work():
            results.extend(pull_music_mods(self.app.mod_dir, repos, download))

        worker = threading.Thread(target=work, daemon=True)
        worker.start()

        def poll():
            if not self.winfo_exists():
                return
            if worker.is_alive():
                self.after(150, poll)
                return
            self._music_pulling = False
            self.tk.call("tk", "busy", "forget", str(self))
            self.player.stop()
            for folder, ok, _ in results:
                if ok:
                    key = os.path.normcase(os.path.abspath(os.path.join(self.app.mod_dir, folder)))
                    self._loaded.pop(key, None)
            self.fill_mods()
            self.fill_stations()
            self.publish_stations()
            report = "\n".join(f"{folder}: {detail}" for folder, _, detail in results)
            self.status(f"Music: {sum(ok for _, ok, _ in results)} of {len(results)} repositories updated.")
            if any(not ok for _, ok, _ in results):
                messagebox.showwarning("Music Master", report, parent=self)
            else:
                messagebox.showinfo("Music Master", report, parent=self)
        self.after(150, poll)

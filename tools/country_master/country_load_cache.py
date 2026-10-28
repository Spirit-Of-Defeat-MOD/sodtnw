"""Validated source/parse cache for a single CountryData load; no executable cache format."""
import hashlib
import json
import os
import zlib


class SourceCache:
    def __init__(self, root, game, directory, entry_type, parser, reader):
        identity = os.path.normcase(os.path.abspath(root))
        if game:
            identity += "|" + os.path.normcase(os.path.abspath(game))
        self.path = os.path.join(directory, "sources_" + hashlib.sha256(identity.encode()).hexdigest()[:20] + ".json.z")
        self.entry_type, self.parser, self.reader = entry_type, parser, reader
        self.old, self.rows, self.parsed = {}, {}, {}
        self.dirty = False
        try:
            with open(self.path, "rb") as stream:
                cached = json.loads(zlib.decompress(stream.read()).decode("utf-8"))
            if cached.get("version") == 1 and isinstance(cached.get("files"), dict):
                self.old = cached["files"]
        except (OSError, ValueError, zlib.error, AttributeError, RecursionError):
            pass

    def record(self, path):
        if path in self.rows:
            return self.rows[path]
        stat = os.stat(path)
        signature = [stat.st_size, stat.st_mtime_ns]
        old = self.old.get(path)
        if isinstance(old, dict) and old.get("signature") == signature and isinstance(old.get("text"), str):
            row = dict(old)
        else:
            row = {"signature": signature, "text": self.reader(path)}
            self.dirty = True
        self.rows[path] = row
        return row

    def text(self, path):
        return self.record(path)["text"]

    @staticmethod
    def pack(entries):
        return [[e.key, e.op, SourceCache.pack(e.value) if e.block else e.value, e.first, e.last] for e in entries]

    def unpack(self, entries):
        if not isinstance(entries, list):
            raise ValueError("Invalid cached entries")
        result = []
        for row in entries:
            if not isinstance(row, list) or len(row) != 5 or not isinstance(row[3], int) or not isinstance(row[4], int):
                raise ValueError("Invalid cached entry")
            if (row[0] is not None and not isinstance(row[0], str)) or (row[1] is not None and not isinstance(row[1], str)):
                raise ValueError("Invalid cached key or operator")
            value = self.unpack(row[2]) if isinstance(row[2], list) else row[2]
            if not isinstance(value, (str, list)):
                raise ValueError("Invalid cached value")
            result.append(self.entry_type(row[0], row[1], value, row[3], row[4]))
        return result

    def entries(self, path):
        if path not in self.parsed:
            row = self.record(path)
            try:
                entries = self.unpack(row["entries"])
            except (KeyError, ValueError, TypeError, IndexError, RecursionError):
                entries = self.parser(row["text"])
                row["entries"] = self.pack(entries)
                self.dirty = True
            self.parsed[path] = entries
        return self.parsed[path]

    def save(self):
        if not self.dirty and self.rows.keys() == self.old.keys():
            return
        temporary = self.path + f".{os.getpid()}.tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            raw = json.dumps({"version": 1, "files": self.rows}, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
            with open(temporary, "wb") as stream:
                stream.write(zlib.compress(raw, 1))
            os.replace(temporary, self.path)
        except OSError:
            try:
                os.remove(temporary)
            except OSError:
                pass

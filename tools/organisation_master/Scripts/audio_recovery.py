"""Per-PC crash recovery; an OS lock distinguishes interrupted sessions from open workshops."""
import json
import os
from pathlib import Path
import shutil
import time
import uuid


class RecoverySession:
    def __init__(self, root, path=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = Path(path).resolve() if path else self.root / uuid.uuid4().hex
        if self.path.parent != self.root or not self.path.name.isalnum():
            raise ValueError("Invalid audio recovery folder")
        self.path.mkdir(exist_ok=True)
        self.handle = (self.path / "session.lock").open("a+b")
        self.handle.seek(0, 2)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            raise

    def save(self, data):
        if self.handle is None:
            return
        temporary = self.path / "session.json.tmp"
        payload = dict(data, version=1, updated=time.time())
        with temporary.open("w", encoding="utf-8") as writer:
            json.dump(payload, writer, ensure_ascii=False)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, self.path / "session.json")

    def read(self):
        data = json.loads((self.path / "session.json").read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("items"), dict):
            raise ValueError("Unsupported recovery record")
        return data

    def release(self):
        if self.handle is not None:
            self.handle.close()  # Closing releases the OS lock, including after a process crash.
            self.handle = None

    def cleanup(self):
        self.release()
        if self.path.parent != self.root or self.path.resolve().parent != self.root:
            raise ValueError("Recovery folder moved outside its root")
        shutil.rmtree(self.path, ignore_errors=True)


def recoverable(root):
    root = Path(root)
    if not root.is_dir():
        return []
    candidates = []
    for path in root.iterdir():
        if not path.is_dir() or not (path / "session.json").is_file():
            continue
        session = None
        try:
            session = RecoverySession(root, path)
            data = session.read()
            if data["items"]:
                candidates.append((session, data))
            else:
                session.release()
        except (OSError, ValueError, TypeError):
            if session is not None:
                session.release()
    return sorted(candidates, key=lambda entry: entry[1].get("updated", 0), reverse=True)


def find_download(folder):
    """A completed download can survive a crash before its metadata reached the UI."""
    folder = Path(folder)
    if not folder.is_dir():
        return ""
    files = [path for path in folder.glob("source.*") if path.suffix.lower() in
        (".ogg", ".opus", ".webm", ".m4a", ".mp4", ".mp3", ".flac", ".wav", ".aac")]
    return str(max(files, key=lambda path: path.stat().st_mtime_ns)) if files else ""

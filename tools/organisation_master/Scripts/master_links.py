"""Portable navigation links; parsing and file recognition never launch applications."""
import os
import re
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

MASTERS = {"culture": "Culture Master", "country": "Country Master", "music": "Music Master"}
KINDS = {"culture": {"state", "node"}, "country": {"country", "portrait", "ideology"}, "music": {"station", "plan"}}
try:  # (new masters register themselves: tools/<folder>/master.json "link" / "link_kinds")
    import masters as _masters
    for _m in _masters.discovered():
        if _m.get("link"):
            MASTERS[_m["link"]] = _m["name"]
            KINDS[_m["link"]] = set(_m.get("link_kinds") or [])
except Exception:
    pass


def parse(link):
    if not isinstance(link, str) or len(link) > 4096:
        raise ValueError("Invalid master link")
    url = urlsplit(link)
    if url.scheme != "rr" or url.netloc not in MASTERS or url.fragment:
        raise ValueError("Not a supported master link")
    parts = url.path.strip("/").split("/")
    if len(parts) != 2 or parts[0] not in KINDS[url.netloc]:
        raise ValueError("Unknown master link destination")
    kind, value = parts[0], unquote(parts[1])
    if not value or any(ord(c) < 32 for c in value):
        raise ValueError("Missing or invalid destination")
    query = parse_qs(url.query)
    if any(k not in ("system", "mod") or len(v) != 1 for k, v in query.items()):
        raise ValueError("Invalid master link options")
    system = query.get("system", ["culture"])[0]
    mod = query.get("mod", [""])[0]
    if system not in ("culture", "religion", "language") or any(c in mod for c in "/\\:") or mod in (".", ".."):
        raise ValueError("Invalid system or music mod")
    if kind == "state" and (not value.isascii() or not value.isdigit() or int(value) <= 0):
        raise ValueError("Invalid state number")
    if kind == "node" and not re.fullmatch(r"(group|culture|sub|rgroup|religion):[\w.\-]+", value):
        raise ValueError("Invalid culture or religion entry")
    if kind == "ideology" and not re.fullmatch(r"[\w.\-]+", value):
        raise ValueError("Invalid ideology")
    if kind == "country" and not re.fullmatch(r"[A-Z0-9]{3}", value):
        raise ValueError("Invalid country tag")
    if kind == "portrait":
        path = value.removeprefix("game:").replace("\\", "/")
        if path.startswith("/") or ":" in path or ".." in path.split("/"):
            raise ValueError("Portrait must be a sprite or relative image path")
    return dict(tool=url.netloc, master=MASTERS[url.netloc], kind=kind, value=value, system=system, mod=mod)


def make(tool, kind, value, **options):
    link = f"rr://{tool}/{kind}/{quote(str(value), safe='')}"
    if options:
        link += "?" + urlencode(options)
    parse(link)
    return link


def argument(argv):
    if "--open" not in argv:
        return None
    index = argv.index("--open") + 1
    return argv[index] if index < len(argv) else "rr://invalid"


def from_task(task):
    task = task or {}
    source = task.get("link") or ""
    if source.startswith("culture_region_review:"):
        states = task.get("review_states") or []
        if states:
            system = task.get("review_system")
            return make("culture", "state", states[0]["id"],
                        system=system if system in ("culture", "religion", "language") else "culture")
    if source.startswith("culture_state_review:"):
        sid = source.split(":", 1)[1]
        system = task.get("review_system")
        if system not in ("culture", "religion", "language"):
            match = re.search(r"\((culture|religion|language)\)", task.get("setter_note") or "")
            system = match.group(1) if match else "culture"
        return make("culture", "state", sid, system=system)
    if source.startswith("country_review:"):
        return make("country", "country", source.split(":", 1)[1])
    if source.startswith(("portrait_review:", "art_mark:")):
        return make("country", "portrait", source.split(":", 1)[1])
    if source.startswith("music_station:"):
        return make("music", "plan", source.split(":", 1)[1])
    if source.startswith("music_step:"):
        return make("music", "plan", source[len("music_step:"):].rsplit(":", 1)[0])
    return None


def from_file(link, root):
    if link.startswith("rr://"):
        parse(link)
        return link
    if re.match(r"https?://", link) or link.startswith("task:"):
        return None
    game = link.startswith("game:")
    name = link[5:] if game else link
    path = os.path.abspath(name if os.path.isabs(name) else os.path.join(root, name))
    try:
        rel = name.replace("\\", "/") if game else os.path.relpath(path, root).replace("\\", "/")
    except ValueError:  # An ordinary file on another Windows drive.
        return None
    if rel.startswith("history/states/") and rel.endswith(".txt"):
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as stream:
                text = re.sub(r"#[^\n]*", "", stream.read())
            match = re.search(r"\bid\s*=\s*(\d+)", text)
        except OSError:
            match = re.match(r"(\d+)", os.path.basename(path))
        if match:
            return make("culture", "state", match.group(1))
    match = re.match(r"(?:history/countries|common/characters)/([A-Z0-9]{3})(?:[ ._-]|$)", rel)
    if match:
        return make("country", "country", match.group(1))
    if rel.startswith("gfx/leaders/") and re.search(r"\.(?:dds|png|tga|jpg|jpeg)$", rel, re.I):
        return make("country", "portrait", ("game:" if game else "") + rel)
    # Music mods live next to RR. Inspect only a linked station definition in that mod folder.
    mod_root = os.path.dirname(os.path.dirname(path))
    if (os.path.basename(os.path.dirname(path)) == "music" and path.endswith(".txt")
            and os.path.dirname(mod_root) == os.path.dirname(os.path.abspath(root))):
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as stream:
                match = re.search(r'^\s*music_station\s*=\s*(?:"([^"]+)"|([^\s#{}]+))', stream.read(), re.M)
            if match:
                return make("music", "station", match.group(1) or match.group(2), mod=os.path.basename(mod_root))
        except OSError:
            pass
    return None

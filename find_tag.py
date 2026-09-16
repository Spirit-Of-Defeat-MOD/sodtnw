"""
find_tag.py — HoI4 vanilla tag finder for mod debugging

Searches the vanilla HoI4 install for files containing a given country tag,
skipping any paths covered by replace_path in the mod file (since those
vanilla files are never loaded by the game).

Usage:
    python find_tag.py <TAG>
    python find_tag.py GDC
    python find_tag.py SND

Edit the paths below if your setup differs.
"""

import os
import sys
import re

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MOD_FILE = os.path.join(SCRIPT_DIR, "sodtnw.mod")

VANILLA_DIR = r"C:/Program Files (x86)/Steam/steamapps/common/Hearts of Iron IV"

# File extensions to search inside
SEARCH_EXTENSIONS = {".txt", ".cfg"}

# ── Parse replace_path entries from the .mod file ─────────────────────────────

def get_replace_paths(mod_file: str) -> list[str]:
    replace_paths = []
    with open(mod_file, "r", encoding="utf-8") as f:
        for line in f:
            match = re.match(r'replace_path="(.+?)"', line.strip())
            if match:
                # Normalize to forward slashes for consistent comparison
                replace_paths.append(match.group(1).replace("\\", "/").rstrip("/"))
    return replace_paths


def is_covered_by_replace_path(filepath: str, vanilla_dir: str, replace_paths: list[str]) -> bool:
    """Return True if the file lives under any replace_path (so vanilla version is skipped by game)."""
    # Get path relative to vanilla dir, normalized
    rel = os.path.relpath(filepath, vanilla_dir).replace("\\", "/")
    for rp in replace_paths:
        if rel.startswith(rp + "/") or rel == rp:
            return True
    return False


# ── Search ────────────────────────────────────────────────────────────────────

def find_tag(tag: str, vanilla_dir: str, replace_paths: list[str]) -> list[tuple[str, int, str]]:
    """Walk vanilla dir, return (filepath, line_number, line_content) for each hit."""
    results = []
    for root, dirs, files in os.walk(vanilla_dir):
        # Skip hidden/system folders
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SEARCH_EXTENSIONS:
                continue
            filepath = os.path.join(root, filename)
            if is_covered_by_replace_path(filepath, vanilla_dir, replace_paths):
                continue
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, start=1):
                        if tag in line:
                            results.append((filepath, i, line.rstrip()))
            except OSError:
                pass  # skip unreadable files
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python find_tag.py <TAG>")
        print("Example: python find_tag.py GDC")
        sys.exit(1)

    tag = sys.argv[1].upper()

    if not os.path.exists(MOD_FILE):
        print(f"Error: could not find mod file at '{MOD_FILE}'")
        print("Make sure you're running this from your workspace root, or update MOD_FILE in the script.")
        sys.exit(1)

    if not os.path.exists(VANILLA_DIR):
        print(f"Error: vanilla HoI4 directory not found at '{VANILLA_DIR}'")
        print("Update VANILLA_DIR in the script to match your Steam install path.")
        sys.exit(1)

    print(f"Searching for tag: {tag}")
    print(f"Vanilla dir: {VANILLA_DIR}")

    replace_paths = get_replace_paths(MOD_FILE)
    print(f"Skipping {len(replace_paths)} replace_path(s) from {MOD_FILE}\n")

    results = find_tag(tag, VANILLA_DIR, replace_paths)

    if not results:
        print(f"No results found for '{tag}' in non-replaced vanilla paths.")
        return

    # Group by file for cleaner output
    from collections import defaultdict
    by_file = defaultdict(list)
    for filepath, lineno, content in results:
        by_file[filepath].append((lineno, content))

    print(f"Found '{tag}' in {len(by_file)} file(s):\n")
    for filepath, hits in by_file.items():
        rel = os.path.relpath(filepath, VANILLA_DIR).replace("\\", "/")
        print(f"  {rel}")
        for lineno, content in hits:
            print(f"    line {lineno}: {content.strip()}")
        print()


if __name__ == "__main__":
    main()

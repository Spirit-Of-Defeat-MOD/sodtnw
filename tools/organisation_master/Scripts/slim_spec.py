"""Used by the masters' build.bat: makes the exe start faster by leaving out files it never uses.

A onefile exe unpacks everything into a temp folder on every start, and on Windows each new file is checked by the
antivirus: the 600+ time zone files and 130+ translation files of Tcl (Python's tkinter) were most of the files and
most of the wait. The tools don't use time zones or Tk's translated dialog buttons (English is built in).

    python slim_spec.py build/OrganisationMaster.spec    (after pyi-makespec, before building from the spec)"""
import sys

SKIP = ("/tzdata/", "/msgs/")  # (inside _tcl_data / _tk_data)
MARK = "# slim_spec:"

FILTER = f'''{MARK} leave out Tcl's time zones and translations (faster start, see Scripts/slim_spec.py)
a.datas = [d for d in a.datas if not (str(d[0]).replace("\\\\", "/").startswith(("_tcl_data/", "_tk_data/", "tcl/", "tk/"))
                                      and any(s in "/" + str(d[0]).replace("\\\\", "/") for s in {SKIP!r}))]
'''


def slim(path):
	with open(path, encoding="utf-8") as f:
		text = f.read()
	if MARK in text:
		return False
	at = text.index("pyz = PYZ(")  # (right after the Analysis: the data list is final there)
	with open(path, "w", encoding="utf-8") as f:
		f.write(text[:at] + FILTER + text[at:])
	return True


if __name__ == "__main__":
	print("slim_spec:", "done" if slim(sys.argv[1]) else "already done")

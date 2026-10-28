"""Where Organisation Master's files are, now that its code lives in Scripts/.

TOOL: tools/organisation_master (next to OrganisationMaster.exe / organisation_master.py): sync.json, themes, backups,
and the art and sounds (sounds/, secret_assets/, icons/). They aren't built into the exes: every exe reads them from
this folder, so the repository keeps one copy. Culture / Country Master use the same scripts and find it next door
(tools/culture_master -> tools/organisation_master).
BUNDLE: kept for older code; the same folder as TOOL."""
import os
import sys

FROZEN = getattr(sys, "frozen", False)
SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def _tool():
	if not FROZEN:
		return os.path.dirname(SCRIPTS)
	here = os.path.dirname(os.path.abspath(sys.executable))
	for folder in (here, os.path.join(os.path.dirname(here), "organisation_master")):  # (Organisation Master's, or next door)
		if os.path.isdir(os.path.join(folder, "Scripts")) or os.path.isdir(os.path.join(folder, "sounds")):
			return folder
	return here


TOOL = _tool()
BUNDLE = TOOL

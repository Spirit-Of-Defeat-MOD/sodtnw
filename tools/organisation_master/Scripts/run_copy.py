"""The masters' exes run from a copy, so the exe in the repository is never locked.

Windows can't replace a running .exe: a git pull with a master open used to stop half way (the .py files it had
already replaced came over, the exe didn't), and the pull had to be cleaned up by hand. Now, started from the
repository, a master copies its exe to %LOCALAPPDATA%\\OrganisationMaster\\run (once per build) and runs that copy.
The copy sets sys.executable back to the repository's exe, so every folder worked out from it (the tool's files,
backups, shortcuts, the update check's "Restart now") still means the repository. Old copies are removed when they're
no longer running."""
import glob
import os
import shutil
import subprocess
import sys

RUN_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "OrganisationMaster", "run")
REPO_EXE = "RR_REPO_EXE"


def clean_env():
	"""The environment for another PyInstaller exe, without this one's own variables (it would think it's our child)."""
	return {k: v for k, v in os.environ.items() if not k.startswith(("_MEI", "_PYI"))}


def start(name):
	"""First thing a master's exe does. Started from the repository: copy, run the copy, exit. Running as the copy:
	sys.executable = the repository's exe, and old copies tidied away."""
	if not getattr(sys, "frozen", False):
		return
	repo = os.environ.get(REPO_EXE)
	if repo:
		os.environ.pop(REPO_EXE, None)  # (masters it opens start from the repository and make their own copy)
		sys.executable = repo
		for old in glob.glob(os.path.join(RUN_DIR, name + "-*.exe")):
			if os.path.normcase(old) != os.path.normcase(os.path.abspath(sys.argv[0])):
				try:
					os.remove(old)  # (one still open elsewhere is locked: it stays until next time)
				except OSError:
					pass
		return
	src = os.path.abspath(sys.executable)
	try:
		st = os.stat(src)
		dst = os.path.join(RUN_DIR, f"{name}-{st.st_size}-{int(st.st_mtime)}.exe")
		if not os.path.exists(dst):
			os.makedirs(RUN_DIR, exist_ok=True)
			tmp = dst + f".{os.getpid()}.tmp"
			shutil.copy2(src, tmp)
			os.replace(tmp, dst)
		env = clean_env()
		env[REPO_EXE] = src
		subprocess.Popen([dst, *sys.argv[1:]], env=env, cwd=os.path.dirname(src))
	except OSError:
		return  # (no copy possible: run from the repository as before)
	os._exit(0)

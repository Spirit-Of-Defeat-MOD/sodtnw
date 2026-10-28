"""🖼 GFX > ✨ Remini: restore and upscale a portrait on this PC with GFPGAN (TencentARC, https://github.com/TencentARC/GFPGAN,
Apache-2.0). The button's tooltip says so; the team calls it Remini after the phone app.

GFPGAN needs PyTorch, far too big for the exe: the first time, Remini asks and then sets up its own Python environment in
%LOCALAPPDATA%\\OrganisationMaster\\remini (a venv made with a Python 3.10-3.13 already on the PC; PyTorch CPU and GFPGAN
from PyPI, the GFPGAN v1.4 model from GitHub, facexlib's face models on the first run). After that a portrait takes a few
seconds. Scripts/remini_worker.py does the work inside that environment.

The result opens next to the original (side by side, or ⧉ overlaid: Space / click flips). ✏ Edit overlay: Remini's version
lies over the original - a Strength slider for how much of it shows, and a brush that rubs it out (🧽 Eraser, at a % level)
or paints it back (🖌 Restore); Ctrl+Z takes back a stroke. 💾 Save as PNG / ⬇ Use it in the mod (scaled back to the
original's size and format, the original copied to backups/remini first) use the edited result; 💾 Save overlay layer
saves Remini's version with the strength / rubbed-out parts as transparency, to lay over the original elsewhere."""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import urllib.request
from tkinter import filedialog, messagebox, ttk

import paths
import ui

APP_NAME = "Remini"
HOME = os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(), "OrganisationMaster", "remini")
VENV = os.path.join(HOME, "venv")
PY = os.path.join(VENV, "Scripts", "python.exe")
WEIGHTS = os.path.join(HOME, "GFPGANv1.4.pth")
WEIGHTS_URL = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
READY = os.path.join(HOME, "ready.json")
WORKER = os.path.join(paths.TOOL, "Scripts", "remini_worker.py")
# 🎭 Self swap ("FaceApp the portrait with itself"): InsightFace's inswapper_128 + ArcFace, as VisoMaster hosts them
SWAP_WORKER = os.path.join(paths.TOOL, "Scripts", "remini_swap.py")
SWAP_DIR = os.path.join(HOME, "models")
SWAP_READY = os.path.join(HOME, "swap_ready.json")
SWAP_MODELS = (("inswapper_128.fp16.onnx", "6d51a9278a1f650cffefc18ba53f38bf2769bf4bbff89267822cf72945f8a38b", 265),
			   ("w600k_r50.onnx", "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43", 166))
SWAP_URL = "https://github.com/visomaster/visomaster-assets/releases/download/v0.1.0/"
SWAP_TEXT = ("🎭 Self swap puts the original portrait's face back onto Remini's version (\"FaceApp it with itself\"), with the "
			 "face swap models VisoMaster uses (InsightFace's inswapper_128 and ArcFace). It runs on any PC's CPU.\n\n"
			 "It needs, once:\n• onnxruntime and onnx from PyPI - about 30 MB\n• inswapper_128 (265 MB) and ArcFace w600k_r50 "
			 "(166 MB) from VisoMaster's GitHub releases\n\n(InsightFace's swap model is for non-commercial use: fine for a free mod.)"
			 "\n\nSet it up now?")
TORCH_CPU = "https://download.pytorch.org/whl/cpu"
TORCH_GPU = "https://download.pytorch.org/whl/cu124"  # (NVIDIA: about a second a portrait instead of ~15)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TEXT = dict(text=True, encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))  # (pip / tqdm print progress bars)
TIP = ("Remini - GFPGAN (TencentARC) face restoration + upscaling, run on this PC.\n"
	   "Restores and upscales the picture you have picked (a portrait works best).")
SETUP_TEXT = ("Remini uses GFPGAN (TencentARC's face restoration), which needs a one-time setup on this PC:\n\n"
			  "• PyTorch (CPU) and GFPGAN's packages from PyPI - about 400 MB\n"
			  "• the GFPGAN v1.4 model from GitHub (TencentARC) - 348 MB\n"
			  "• facexlib's face detection models from GitHub on the first run - about 190 MB\n\n"
			  "About 2 GB on disk in %LOCALAPPDATA%\\OrganisationMaster\\remini (delete that folder to remove it).\n"
			  "It uses a Python 3.10-3.13 already installed on this PC. It takes a few minutes.\n\nSet it up now?")


def ready():
	return os.path.isfile(READY) and os.path.isfile(PY) and os.path.isfile(WEIGHTS)


def find_python():
	"""[command] of a Python that can run GFPGAN (3.11 first: its packages know it best), or None."""
	for cmd in (["py", "-3.11"], ["py", "-3.12"], ["py", "-3.10"], ["py", "-3.13"], ["python"], ["python3"]):
		try:
			out = subprocess.run(cmd + ["-c", "import sys; print(sys.version_info[:2] >= (3, 10) and sys.version_info[:2] <= (3, 13))"],
								 capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
			if out.returncode == 0 and out.stdout.strip() == "True":
				return cmd
		except (OSError, subprocess.SubprocessError):
			continue
	return None


def setup(say, gpu=False):
	"""The one-time setup (also Repair: steps already done are quick); say(text) reports each step. gpu: PyTorch for
	NVIDIA cards (~2.5 GB) instead of the CPU one. Raises RuntimeError with what went wrong."""
	os.makedirs(HOME, exist_ok=True)

	def run(cmd, what):
		say(what)
		p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=HOME, creationflags=NO_WINDOW, **TEXT)
		tail = []
		for line in p.stdout:
			line = line.rstrip()
			if line:
				tail = (tail + [line])[-12:]
				say(what + "\n" + line[-150:])
		if p.wait() != 0:
			raise RuntimeError(f"{what} failed:\n" + "\n".join(tail))
	if not os.path.isfile(PY):
		py = find_python()
		if py is None:
			raise RuntimeError("No Python 3.10-3.13 found on this PC. Install Python 3.11 from python.org, then try again.")
		run(py + ["-m", "venv", VENV], "Making Remini's Python environment...")
	pip = [PY, "-m", "pip", "install", "--disable-pip-version-check"]
	run(pip + ["--upgrade", "pip", "setuptools", "wheel"], "Updating pip...")
	if gpu:
		run(pip + ["--force-reinstall", "--no-deps", "torch", "torchvision", "--index-url", TORCH_GPU],
			"Downloading PyTorch for NVIDIA GPUs (~2.5 GB)...")
	elif not torch_info().get("cuda_build"):
		run(pip + ["torch", "torchvision", "--index-url", TORCH_CPU], "Downloading PyTorch (CPU, ~200 MB)...")
	run(pip + ["numpy<2", "opencv-python", "basicsr", "facexlib", "gfpgan", "--no-build-isolation"], "Downloading GFPGAN and its packages...")
	fix_basicsr(say)
	if not os.path.isfile(WEIGHTS):
		say("Downloading the GFPGAN v1.4 model (348 MB)...")
		tmp = WEIGHTS + ".part"

		def hook(blocks, size, total):
			if total > 0 and blocks % 200 == 0:
				say(f"Downloading the GFPGAN v1.4 model... {min(100, blocks * size * 100 // total)}%")
		urllib.request.urlretrieve(WEIGHTS_URL, tmp, hook)
		os.replace(tmp, WEIGHTS)
	run([PY, WORKER, WEIGHTS, "warmup"], "First run: facexlib downloads its face models...")
	with open(READY, "w", encoding="utf-8") as f:
		json.dump({"when": datetime.datetime.now().isoformat(timespec="seconds")}, f)
	say("Ready.")


def torch_info():
	"""{version, cuda (a GPU it can use), cuda_build} of Remini's PyTorch, or {} when it isn't there (a few seconds)."""
	if not os.path.isfile(PY):
		return {}
	try:
		out = subprocess.run([PY, "-c", "import torch, json; print(json.dumps({'version': torch.__version__, "
							  "'cuda': torch.cuda.is_available(), 'cuda_build': torch.version.cuda is not None}))"],
							 capture_output=True, timeout=120, creationflags=NO_WINDOW, **TEXT)
		return json.loads(out.stdout.strip().splitlines()[-1])
	except (OSError, subprocess.SubprocessError, ValueError, IndexError):
		return {}


def nvidia():
	"""This PC's NVIDIA card's name, or None."""
	try:
		out = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, timeout=10,
							 creationflags=NO_WINDOW, **TEXT)
		return out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else None
	except (OSError, subprocess.SubprocessError):
		return None


def folder_size():
	total = 0
	for root, _, files in os.walk(HOME):
		for f in files:
			try:
				total += os.path.getsize(os.path.join(root, f))
			except OSError:
				pass
	return total


def uninstall():
	"""Remini's folder goes (its Python environment, PyTorch, the models). True when it's gone."""
	shutil.rmtree(HOME, ignore_errors=True)
	return not os.path.exists(HOME)


def swap_ready():
	return ready() and os.path.isfile(SWAP_READY) and all(os.path.isfile(os.path.join(SWAP_DIR, n)) for n, _, _ in SWAP_MODELS)


def setup_swap(say):
	"""🎭 Self swap's extra setup (after Remini's): onnxruntime + onnx, and the two models (checked against VisoMaster's
	hashes)."""
	import hashlib
	if not ready():
		setup(say)
	p = subprocess.run([PY, "-m", "pip", "install", "--disable-pip-version-check", "onnxruntime", "onnx"], capture_output=True,
					   cwd=HOME, creationflags=NO_WINDOW, **TEXT)
	if p.returncode != 0:
		raise RuntimeError("Installing onnxruntime failed:\n" + p.stdout[-800:])
	os.makedirs(SWAP_DIR, exist_ok=True)
	for name, sha, mb in SWAP_MODELS:
		dst = os.path.join(SWAP_DIR, name)
		if os.path.isfile(dst):
			continue
		say(f"Downloading {name} ({mb} MB)...")

		def hook(blocks, size, total, name=name, mb=mb):
			if total > 0 and blocks % 200 == 0:
				say(f"Downloading {name} ({mb} MB)... {min(100, blocks * size * 100 // total)}%")
		urllib.request.urlretrieve(SWAP_URL + name, dst + ".part", hook)
		h = hashlib.sha256()
		with open(dst + ".part", "rb") as f:
			for chunk in iter(lambda: f.read(1 << 20), b""):
				h.update(chunk)
		if h.hexdigest() != sha:
			os.remove(dst + ".part")
			raise RuntimeError(f"{name} didn't match its checksum (a broken download?): try again.")
		os.replace(dst + ".part", dst)
	with open(SWAP_READY, "w", encoding="utf-8") as f:
		json.dump({"when": datetime.datetime.now().isoformat(timespec="seconds")}, f)
	say("Ready.")


def self_swap(identity, target, restore=True):
	"""(PIL result, faces) - identity's face (a path: the original portrait) onto target (a PIL image)."""
	from PIL import Image
	tmp = os.path.join(HOME, "tmp")
	os.makedirs(tmp, exist_ok=True)
	src, tgt, out = (os.path.join(tmp, n) for n in ("swap_identity.png", "swap_target.png", "swap_out.png"))
	Image.open(identity).convert("RGB").save(src)
	target.save(tgt)
	if os.path.exists(out):
		os.remove(out)
	p = subprocess.run([PY, SWAP_WORKER, SWAP_DIR, WEIGHTS, src, tgt, out] + ([] if restore else ["norestore"]), capture_output=True,
					   cwd=HOME, creationflags=NO_WINDOW, timeout=600, **TEXT)
	lines = [l for l in p.stdout.splitlines() if l.startswith(("ok ", "error "))]
	if not lines or lines[-1].startswith("error") or not os.path.isfile(out):
		raise RuntimeError((lines[-1][6:] if lines else "") or p.stderr.strip()[-600:] or "the swap didn't say why")
	got = Image.open(out)
	got.load()
	return got, int(lines[-1].split()[1])


def fix_basicsr(say):
	"""basicsr 1.4.2 imports torchvision.transforms.functional_tensor, which newer torchvision dropped."""
	out = subprocess.run([PY, "-c", "import importlib.util, os; print(os.path.dirname(importlib.util.find_spec('basicsr').origin))"],
						 capture_output=True, text=True, creationflags=NO_WINDOW)  # (found, not imported: importing it is what breaks)
	path = os.path.join(out.stdout.strip(), "data", "degradations.py")
	try:
		with open(path, encoding="utf-8") as f:
			text = f.read()
	except OSError:
		return
	if "functional_tensor" in text:
		with open(path, "w", encoding="utf-8") as f:
			f.write(text.replace("torchvision.transforms.functional_tensor", "torchvision.transforms.functional"))
		say("Patched basicsr for this torchvision.")


def upscale(src, scale=2):
	"""(PIL image of the result, faces found) for the picture at src (any format PIL reads: DDS, TGA, PNG...)."""
	from PIL import Image
	tmp = os.path.join(HOME, "tmp")
	os.makedirs(tmp, exist_ok=True)
	im = Image.open(src)
	im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" else "RGB")
	inp, out = os.path.join(tmp, "in.png"), os.path.join(tmp, "out.png")
	im.save(inp)
	if os.path.exists(out):
		os.remove(out)
	p = subprocess.run([PY, WORKER, WEIGHTS, str(scale), inp, out], capture_output=True, cwd=HOME, creationflags=NO_WINDOW, timeout=600, **TEXT)
	lines = [l for l in p.stdout.splitlines() if l.startswith(("ok ", "error "))]
	if not lines or lines[-1].startswith("error") or not os.path.isfile(out):
		raise RuntimeError((lines[-1][6:] if lines else "") or p.stderr.strip()[-600:] or "GFPGAN didn't say why")
	got = Image.open(out)
	got.load()
	return got, int(lines[-1].split()[1])


def copy_image(im):
	"""The picture onto Windows' clipboard: as PNG (keeps transparency: Photoshop, GIMP...) and as a bitmap (anything)."""
	import ctypes
	import io
	from ctypes import wintypes
	user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
	user32.OpenClipboard.argtypes = [wintypes.HWND]
	user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
	user32.SetClipboardData.restype = ctypes.c_void_p
	user32.RegisterClipboardFormatW.restype = ctypes.c_uint
	kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
	kernel32.GlobalAlloc.restype = ctypes.c_void_p
	kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
	kernel32.GlobalLock.restype = ctypes.c_void_p
	kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
	bmp, png = io.BytesIO(), io.BytesIO()
	im.convert("RGB").save(bmp, "BMP")
	im.save(png, "PNG")

	def put(fmt, data):
		h = kernel32.GlobalAlloc(0x0002, len(data))  # (GMEM_MOVEABLE: the clipboard owns it from now on)
		ctypes.memmove(kernel32.GlobalLock(h), data, len(data))
		kernel32.GlobalUnlock(h)
		user32.SetClipboardData(fmt, h)
	for _ in range(10):  # (another program may have the clipboard open for a moment)
		if user32.OpenClipboard(None):
			break
		import time
		time.sleep(0.05)
	else:
		raise OSError("the clipboard is busy")
	try:
		user32.EmptyClipboard()
		put(8, bmp.getvalue()[14:])  # (CF_DIB: the bitmap without its file header)
		put(user32.RegisterClipboardFormatW("PNG"), png.getvalue())
	finally:
		user32.CloseClipboard()


def paste_image():
	"""The picture on the clipboard (copied in Photoshop, a browser, a file copied in Explorer...), or None."""
	from PIL import Image, ImageGrab
	got = ImageGrab.grabclipboard()
	if isinstance(got, list):  # (files copied in Explorer: the first picture)
		for f in got:
			try:
				got = Image.open(f)
				break
			except OSError:
				continue
		else:
			return None
	return got.convert("RGBA") if got is not None else None


class Tooltip:
	"""A small note under a widget while the pointer rests on it."""

	def __init__(self, widget, text):
		self.widget, self.text, self.tip, self.job = widget, text, None, None
		widget.bind("<Enter>", lambda ev: self.schedule(), add="+")
		widget.bind("<Leave>", lambda ev: self.hide(), add="+")
		widget.bind("<ButtonPress>", lambda ev: self.hide(), add="+")

	def schedule(self):
		self.hide()
		self.job = self.widget.after(450, self.show)

	def show(self):
		self.job = None
		w = self.tip = tk.Toplevel(self.widget)
		w.overrideredirect(True)
		w.attributes("-topmost", True)
		tk.Label(w, text=self.text, justify="left", background=ui.P.get("surface", "#ffffe0"), foreground=ui.P.get("foreground", "#000000"),
				 relief="solid", borderwidth=1, padx=8, pady=5, font="om_small").pack()
		w.geometry(f"+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty() + self.widget.winfo_height() + 4}")

	def hide(self):
		if self.job:
			self.widget.after_cancel(self.job)
			self.job = None
		if self.tip is not None:
			self.tip.destroy()
			self.tip = None


def start(pane, path):
	"""✨ Remini on path: set up first if needed (asks), then the result window."""
	if not path or not os.path.isfile(path):
		path = filedialog.askopenfilename(parent=pane, title="✨ Remini: pick a picture", initialdir=os.path.join(pane.app.mod_root, "gfx", "leaders"),
										  filetypes=[("Pictures", "*.dds *.tga *.png *.jpg *.jpeg"), ("All files", "*.*")])
		if not path:
			return
	if ready():
		return Result(pane, path)
	if not messagebox.askyesno("✨ Remini (GFPGAN)", SETUP_TEXT, parent=pane):
		return
	SetupWindow(pane, lambda: Result(pane, path))


class SetupWindow(tk.Toplevel):
	def __init__(self, pane, then, gpu=False, swap=False):
		super().__init__(pane)
		self.gpu, self.swap = gpu, swap
		self._om_nonmodal = True
		self.title("✨ Remini: setting up GFPGAN")
		self.transient(pane.winfo_toplevel())
		self.geometry(f"{ui.px(620)}x{ui.px(220)}")
		f = ttk.Frame(self, padding=14)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text="✨ Setting up Remini (GFPGAN) on this PC - a few minutes, once.", font="om_bold").pack(anchor="w")
		self.bar = ttk.Progressbar(f, mode="indeterminate")
		self.bar.pack(fill="x", pady=8)
		self.bar.start(15)
		self.label = ttk.Label(f, text="Starting...", wraplength=ui.px(580), justify="left")
		self.label.pack(anchor="w", fill="x")
		self.state = {"text": "Starting..."}
		threading.Thread(target=self.work, daemon=True).start()
		self.then = then
		self.poll()

	def work(self):
		try:
			if self.swap:
				setup_swap(lambda t: self.state.update(text=t))
			else:
				setup(lambda t: self.state.update(text=t), gpu=self.gpu)
			self.state["done"] = True
		except Exception as ex:
			self.state["error"] = str(ex)

	def poll(self):
		if not self.winfo_exists():
			return
		self.label.config(text=self.state["text"])
		if "error" in self.state:
			self.bar.stop()
			messagebox.showerror("✨ Remini", "The setup didn't finish:\n\n" + self.state["error"][-1500:], parent=self)
			self.destroy()
		elif self.state.get("done"):
			self.destroy()
			self.then()
		else:
			self.after(250, self.poll)


class Settings(tk.Toplevel):
	"""Settings > ✨ Remini (GFPGAN): is it set up on this PC (and how: Python, CPU / GPU, model, size), Set up / Repair,
	⚡ Use the NVIDIA GPU, Uninstall."""

	def __init__(self, parent):
		super().__init__(parent)
		self._om_nonmodal = True
		self.title("✨ Remini (GFPGAN) on this PC")
		self.transient(parent.winfo_toplevel())
		self.resizable(False, False)
		f = ttk.Frame(self, padding=14)
		f.pack(fill="both", expand=True)
		ttk.Label(f, text="✨ Remini - GFPGAN (TencentARC) face restoration + upscaling", font="om_bold").pack(anchor="w")
		ttk.Label(f, text="Used from 🖼 GFX > ✨ Remini. It runs on this PC, in its own folder:\n" + HOME, style="Muted.TLabel",
				  wraplength=ui.px(520), justify="left").pack(anchor="w", pady=(2, 8))
		self.status = ttk.Label(f, text="Checking...", wraplength=ui.px(520), justify="left")
		self.status.pack(anchor="w", fill="x")
		bf = ttk.Frame(f)
		bf.pack(fill="x", pady=(12, 0))
		self.setup_btn = ttk.Button(bf, text="Set up", command=lambda: self.run_setup(False))
		self.setup_btn.pack(side="left")
		self.gpu_btn = ttk.Button(bf, text="⚡ Use the NVIDIA GPU (~2.5 GB)", command=lambda: self.run_setup(True))
		self.swap_btn = ttk.Button(bf, text="🎭 Set up Self swap (~430 MB)", command=self.run_swap_setup)
		self.remove_btn = ttk.Button(bf, text="🗑 Uninstall", command=self.remove)
		self.remove_btn.pack(side="left", padx=6)
		ttk.Button(bf, text="Close", command=self.destroy).pack(side="right")
		self.check()

	def check(self):
		"""Detects what's there (in the background: asking PyTorch takes a few seconds)."""
		for b in (self.setup_btn, self.remove_btn, self.gpu_btn, self.swap_btn):
			b.state(["disabled"])
		self.status.config(text="Checking...")
		box = {}

		def work():
			box.update(ready=ready(), swap=swap_ready(), venv=os.path.isfile(PY), model=os.path.isfile(WEIGHTS), torch=torch_info(), gpu=nvidia(),
					   size=folder_size() if os.path.isdir(HOME) else 0, python=find_python() if not os.path.isfile(PY) else None)
		th = threading.Thread(target=work, daemon=True)
		th.start()

		def wait():
			if not self.winfo_exists():
				return
			if th.is_alive():
				return self.after(200, wait)
			self.show(box)
		wait()

	def show(self, b):
		t = b["torch"]
		if b["ready"]:
			lines = ["✓ Set up and ready.", f"PyTorch {t.get('version', '?')} · runs on " + ("⚡ the GPU" if t.get("cuda") else "the CPU (~15 s a portrait)"),
					 "GFPGAN v1.4 model: " + ("there" if b["model"] else "missing"),
					 "🎭 Self swap: " + ("✓ set up" if b["swap"] else "not set up (Set up Self swap: ~430 MB more)")]
		elif b["venv"] or b["model"]:
			lines = ["⚠ Partly set up (a setup was stopped, or something's missing): Repair finishes it."]
		else:
			lines = ["Not set up on this PC.", "Set up downloads about 1 GB (PyTorch CPU, GFPGAN and its packages, the GFPGAN v1.4 and "
					 "face models) and needs a Python 3.10-3.13: " + (" ".join(b["python"]) + " found." if b["python"] else "none found - install Python 3.11 first.")]
		if b["gpu"]:
			lines.append(f"NVIDIA card: {b['gpu']}" + ("" if t.get("cuda") else " (not used yet: ⚡ makes it about 15× faster)"))
		if b["size"]:
			lines.append(f"On disk: {b['size'] / 1e9:.1f} GB")
		self.status.config(text="\n".join(lines))
		self.setup_btn.config(text="Repair" if b["venv"] or b["model"] else "Set up")
		self.setup_btn.state(["!disabled"])
		if b["size"]:
			self.remove_btn.state(["!disabled"])
		if b["ready"] and not b["swap"]:
			self.swap_btn.pack(side="left", padx=(0, 6), after=self.setup_btn)
			self.swap_btn.state(["!disabled"])
		else:
			self.swap_btn.pack_forget()
		if b["gpu"] and b["ready"] and not t.get("cuda"):
			self.gpu_btn.pack(side="left", padx=(0, 6), after=self.setup_btn)
			self.gpu_btn.state(["!disabled"])
		else:
			self.gpu_btn.pack_forget()

	def run_setup(self, gpu):
		text = ("Switch Remini to the NVIDIA GPU? It downloads PyTorch for CUDA from download.pytorch.org (about 2.5 GB) "
				"in place of the CPU one." if gpu else SETUP_TEXT)
		if not messagebox.askyesno("✨ Remini", text, parent=self):
			return
		SetupWindow(self, self.check, gpu=gpu)

	def run_swap_setup(self):
		if messagebox.askyesno("🎭 Self swap", SWAP_TEXT, parent=self):
			SetupWindow(self, self.check, swap=True)

	def remove(self):
		if not messagebox.askyesno("✨ Remini", "Uninstall Remini from this PC? Its folder goes, with its Python environment, "
							   "PyTorch and the models:\n\n" + HOME + "\n\n✨ Remini can set itself up again any time.", parent=self):
			return
		ok = uninstall()
		messagebox.showinfo("✨ Remini", "Remini is uninstalled." if ok else "Some files were in use: close anything using Remini and try again.",
							parent=self)
		self.check()


class Result(tk.Toplevel):
	"""The original and Remini's result: side by side or overlaid, zoom, save / use in the mod."""

	def __init__(self, pane, path, start=None, step="remini"):
		"""step "remini": the picture at path upscaled. step "swap": 🎭 the original (path)'s face put back onto start (the
		edited Remini picture) - the next overlay of the chain."""
		super().__init__(pane)
		self.step = step
		from PIL import Image
		self.pane, self.path = pane, path
		self._om_nonmodal = True
		self.title(f"{'✨ Remini' if step == 'remini' else '🎭 Self swap'}: {os.path.basename(path)}")
		self.geometry(f"{ui.px(1000)}x{ui.px(720)}")
		self.orig_size = Image.open(path).size  # (⬇ Use it in the mod: back to the file's own size)
		self.before = (start if start is not None else Image.open(path)).convert("RGBA")
		self.after_im, self.faces, self.zoom, self.showing, self._scale = None, 0, None, "after", 1
		self.mask = self.base_up = self._stroke = None  # (✏ Edit overlay: how much of Remini's shows, per pixel)
		self.mask_undo, self._view, self._redraw = [], None, None
		bar = ttk.Frame(self, padding=(8, 8, 8, 0))
		bar.pack(fill="x")
		self.mode = tk.StringVar(value=pane.app.config.get("remini_mode", "side"))
		for value, text in (("side", "◫ Side by side"), ("overlay", "⧉ Overlay"), ("edit", "✏ Edit overlay")):
			ttk.Radiobutton(bar, text=text, variable=self.mode, value=value, command=self.mode_changed, style="View.TRadiobutton").pack(side="left", padx=(0, 4))
		self.scale = tk.IntVar(value=2)
		if step == "remini":
			ttk.Label(bar, text="Upscale").pack(side="left", padx=(14, 2))
			for n in (2, 4):
				ttk.Radiobutton(bar, text=f"{n}×", variable=self.scale, value=n, command=self.run).pack(side="left")
		else:
			self.scale.set(1)
		ttk.Button(bar, text="Fit", width=4, command=lambda: self.set_zoom(None)).pack(side="right")
		ttk.Button(bar, text="1:1", width=4, command=lambda: self.set_zoom(1)).pack(side="right", padx=2)
		self.edit_bar = eb = ttk.Frame(self, padding=(8, 6, 8, 0))  # (✏ Edit overlay's tools: shown in that mode)
		self.strength = tk.IntVar(value=100)
		self.tool = tk.StringVar(value="erase")
		self.brush = tk.DoubleVar(value=40)  # (a double: Alt + right-drag changes it smoothly)
		self.level = tk.IntVar(value=50)
		ttk.Label(eb, text="Remini strength").pack(side="left")
		ttk.Scale(eb, from_=0, to=100, variable=self.strength, length=ui.px(120), command=lambda v: self.later_draw()).pack(side="left")
		self.strength_label = ttk.Label(eb, text="100%", width=5)
		self.strength_label.pack(side="left", padx=(2, 12))
		for value, text in (("erase", "🧽 Eraser"), ("restore", "🖌 Restore")):
			ttk.Radiobutton(eb, text=text, variable=self.tool, value=value, style="View.TRadiobutton").pack(side="left", padx=(0, 4))
		ttk.Label(eb, text="Level").pack(side="left", padx=(8, 0))
		ttk.Scale(eb, from_=5, to=100, variable=self.level, length=ui.px(90), command=lambda v: self.level_label.config(text=f"{self.level.get()}%")).pack(side="left")
		self.level_label = ttk.Label(eb, text="50%", width=5)
		self.level_label.pack(side="left")
		ttk.Label(eb, text="Brush").pack(side="left", padx=(8, 0))
		ttk.Scale(eb, from_=1, to=400, variable=self.brush, length=ui.px(90)).pack(side="left")
		ttk.Button(eb, text="↶ Stroke (Ctrl+Z)", command=self.undo_stroke).pack(side="left", padx=(10, 4))
		ttk.Button(eb, text="Reset", command=self.reset_edit).pack(side="left")
		ttk.Label(eb, text="Alt + right-drag: size / level · [ ] size · E / B / X · 1-0 level", style="Muted.TLabel").pack(side="left", padx=(10, 0))
		self.info = ttk.Label(self, text="", style="Muted.TLabel", padding=(8, 4))
		self.info.pack(anchor="w")
		self.canvas = tk.Canvas(self, highlightthickness=0, background=ui.P.get("input_background", "#ffffff"))
		self.canvas.pack(fill="both", expand=True, padx=8)
		self.canvas.bind("<Configure>", lambda ev: self.draw())
		self.canvas.bind("<MouseWheel>", lambda ev: self.set_zoom((self.zoom or self._scale or 1) * (1.15 if ev.delta > 0 else 1 / 1.15)))
		self.canvas.bind("<Button-1>", self.press)
		self.canvas.bind("<B1-Motion>", self.paint)
		self.canvas.bind("<ButtonRelease-1>", self.release)
		self.canvas.bind("<Motion>", self.brush_ring)
		self.bind("<space>", lambda ev: self.flip())
		self.bind("<Control-z>", lambda ev: self.undo_stroke())
		self.bind("<Control-Z>", lambda ev: self.undo_stroke())
		self.canvas.bind("<ButtonPress-3>", self.clip_menu)  # (right-click: copy / paste; Alt + right-drag sizes the brush)
		for key in ("<Control-c>", "<Control-C>"):
			self.bind(key, lambda ev: self.copy("result"))
		for key in ("<Control-v>", "<Control-V>"):
			self.bind(key, lambda ev: self.paste())
		# Photoshop's brush controls: Alt + right-drag (left / right: size, up / down: level), [ ] size, E eraser, B brush,
		# X swap, 1-0 level 10-100%
		self.canvas.bind("<Alt-ButtonPress-3>", self.size_start)
		self.canvas.bind("<Alt-B3-Motion>", self.size_drag)
		self.canvas.bind("<ButtonRelease-3>", self.size_end)
		self.bind("<bracketleft>", lambda ev: self.nudge_size(-1))
		self.bind("<bracketright>", lambda ev: self.nudge_size(1))
		for key, tool in (("e", "erase"), ("E", "erase"), ("b", "restore"), ("B", "restore")):
			self.bind(f"<Key-{key}>", lambda ev, t=tool: self.edit_key(lambda: self.tool.set(t)))
		for key in ("x", "X"):
			self.bind(f"<Key-{key}>", lambda ev: self.edit_key(lambda: self.tool.set("restore" if self.tool.get() == "erase" else "erase")))
		for n in range(10):
			self.bind(f"<Key-{n}>", lambda ev, n=n: self.edit_key(lambda: self.set_level(100 if n == 0 else n * 10)))
		buttons = ttk.Frame(self, padding=8)
		buttons.pack(fill="x")
		self.save_btn = ttk.Button(buttons, text="💾 Save as PNG...", command=self.save_png, state="disabled")
		self.save_btn.pack(side="left")
		self.layer_btn = ttk.Button(buttons, text="💾 Save overlay layer...", command=self.save_layer, state="disabled")
		self.layer_btn.pack(side="left", padx=(6, 0))
		self.use_btn = ttk.Button(buttons, text="⬇ Use it in the mod (original size, backup kept)", command=self.use, state="disabled")
		self.use_btn.pack(side="left", padx=6)
		self.swap_btn = ttk.Button(buttons, text="🎭 Self swap this →", command=self.next_swap, state="disabled")
		if step == "remini":
			self.swap_btn.pack(side="left", padx=(12, 0))
			Tooltip(self.swap_btn, "FaceApp it with itself: the original's face put back onto this edited version\n"
								   "(InsightFace's inswapper_128, as in VisoMaster; runs on the CPU), with its own overlay to edit.")
		ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")
		self.focus_set()
		if self.mode.get() == "edit":
			self.edit_bar.pack(fill="x", before=self.info)
		self.run()

	def run(self):
		self.after_im = None
		for btn in (self.save_btn, self.use_btn, self.layer_btn, self.swap_btn):
			btn.state(["disabled"])
		self.info.config(text=f"✨ GFPGAN is working on it ({self.scale.get()}×)... a few seconds (longer the first time)." if self.step == "remini"
						 else "🎭 Swapping the original's face back on... about 10-20 seconds on the CPU.")
		self.draw()
		box = {}
		scale = self.scale.get()

		def work():
			try:
				box["got"] = upscale(self.path, scale) if self.step == "remini" else self_swap(self.path, self.before)
			except Exception as ex:
				box["error"] = str(ex)
		th = threading.Thread(target=work, daemon=True)
		th.start()

		def wait():
			if not self.winfo_exists():
				return
			if th.is_alive():
				return self.after(200, wait)
			if "error" in box:
				self.info.config(text="✨ Remini couldn't do it: " + box["error"][-300:])
				return
			self.after_im, self.faces = box["got"]
			self.after_im = self.after_im.convert("RGBA")
			self.base_up = self.before.resize(self.after_im.size, Image.LANCZOS)
			self.reset_edit(draw=False)
			b, a = self.before.size, self.after_im.size
			self.info.config(text=f"{os.path.basename(self.path)}  ·  {b[0]}×{b[1]} → {a[0]}×{a[1]} px  ·  "
								  + (f"{self.faces} face{'s' if self.faces != 1 else ''} restored" if self.faces else "no face found: just upscaled")
								  + ("  ·  GFPGAN v1.4" if self.step == "remini" else "  ·  inswapper_128 + GFPGAN"))
			for btn in (self.save_btn, self.use_btn, self.layer_btn, self.swap_btn):
				btn.state(["!disabled"])
			self.draw()
		from PIL import Image
		wait()

	def next_swap(self):
		"""🎭 The next step: this (edited) result with the original's face put back on, in a window of its own."""
		start = self.final()
		if swap_ready():
			return Result(self.pane, self.path, start=start, step="swap")
		if messagebox.askyesno("🎭 Self swap", SWAP_TEXT, parent=self):
			SetupWindow(self, lambda: Result(self.pane, self.path, start=start, step="swap"), swap=True)

	def mode_changed(self):
		self.pane.app.config["remini_mode"] = self.mode.get()
		self.pane.app.save_config()
		if self.mode.get() == "edit":
			self.edit_bar.pack(fill="x", before=self.info)
		else:
			self.edit_bar.pack_forget()
		self.draw()

	# ---------- ✏ Edit overlay: Remini's version over the original ----------
	def effective(self):
		"""How much of Remini's version shows per pixel (L): the brushed mask times the strength."""
		k = self.strength.get() / 100
		return self.mask if k >= 0.999 else self.mask.point(lambda v: int(v * k))

	def final(self):
		"""The result as edited: Remini's version laid over the (upscaled) original."""
		from PIL import Image
		if self.after_im is None or self.mask is None:
			return self.after_im
		return Image.composite(self.after_im, self.base_up, self.effective())

	def reset_edit(self, draw=True):
		from PIL import Image
		if self.after_im is not None:
			if self.mask is not None and draw:
				self.mask_undo.append(self.mask.copy())
			self.mask = Image.new("L", self.after_im.size, 255)
		self.strength.set(100)
		if draw:
			self.draw()

	def later_draw(self):
		"""(drawn once things settle: sliders and the brush fire many events)"""
		self.strength_label.config(text=f"{self.strength.get()}%")
		if self._redraw is None:
			self._redraw = self.after(16, self._do_redraw)

	def _do_redraw(self):
		self._redraw = None
		self.draw()

	def to_image(self, x, y):
		"""Canvas point -> the picture's pixel (in the result's size), or None when off it."""
		if self._view is None:
			return None
		x0, y0, s, left, top = self._view
		ix, iy = (x - x0 + left) / s, (y - y0 + top) / s
		return (ix, iy) if 0 <= ix < self.mask.width and 0 <= iy < self.mask.height else None

	def press(self, ev):
		if self.mode.get() != "edit":
			return self.flip()
		if self.mask is None:
			return
		from PIL import Image
		self.mask_undo = (self.mask_undo + [self.mask.copy()])[-20:]
		self._base_mask = self.mask.copy()
		self._stroke = Image.new("L", self.mask.size, 0)
		self._last = self.to_image(ev.x, ev.y)
		self.paint(ev)

	def paint(self, ev):
		"""🧽 Rubs Remini's version out (down to the level's % gone) or 🖌 paints it back, soft-edged, along the stroke."""
		if self.mode.get() != "edit" or self._stroke is None:
			return
		from PIL import ImageChops, ImageDraw, ImageFilter
		pt = self.to_image(ev.x, ev.y)
		if pt is None:
			return
		r = self.brush.get() / 2
		d = ImageDraw.Draw(self._stroke)
		a = self._last or pt
		d.line([a, pt], fill=255, width=int(r * 2))
		for x, y in (a, pt):
			d.ellipse((x - r, y - r, x + r, y + r), fill=255)
		self._last = pt
		level = self.level.get() / 100
		soft = self._stroke.filter(ImageFilter.GaussianBlur(max(1, r / 3))).point(lambda v: int(v * level))
		self.mask = (ImageChops.subtract if self.tool.get() == "erase" else ImageChops.add)(self._base_mask, soft)
		self.later_draw()
		self.brush_ring(ev)

	def release(self, ev):
		self._stroke = None

	def brush_ring(self, ev, at=None):
		"""The brush's outline under the pointer (or where Alt + right-drag started), with its size and level."""
		c = self.canvas
		c.delete("ring")
		if self.mode.get() == "edit" and self._view is not None:
			x, y = at or (ev.x, ev.y)
			r = self.brush.get() / 2 * self._view[2]
			colour = "#ff4d6d" if self.tool.get() == "erase" else "#2e9d4a"
			c.create_oval(x - r, y - r, x + r, y + r, outline="#000000", width=3, tags="ring")
			c.create_oval(x - r, y - r, x + r, y + r, outline=colour, width=1.5, tags="ring")
			if at is not None or getattr(self, "_sizing", None):
				c.create_text(x, y - r - 6, anchor="s", text=f"{round(self.brush.get())} px · {self.level.get()}%", fill=colour,
							  font="om_small_bold", tags="ring")

	def edit_key(self, fn):
		if self.mode.get() == "edit":
			fn()
			self.canvas.event_generate("<Motion>", warp=False, x=self.canvas.winfo_pointerx() - self.canvas.winfo_rootx(),
									   y=self.canvas.winfo_pointery() - self.canvas.winfo_rooty())

	def set_level(self, v):
		self.level.set(v)
		self.level_label.config(text=f"{v}%")

	def nudge_size(self, way):
		"""[ / ]: like Photoshop, bigger steps the bigger the brush."""
		if self.mode.get() != "edit":
			return
		b = self.brush.get()
		step = 1 if b < 10 else 5 if b < 50 else 10 if b < 100 else 25
		self.brush.set(min(400, max(1, b + way * step)))
		self.edit_key(lambda: None)

	def size_start(self, ev):
		"""Alt + right-drag: the ring stays where you pressed and grows / shrinks as you drag (left-right: size,
		up-down: level), like Photoshop."""
		if self.mode.get() != "edit" or self._view is None:
			return
		self._sizing = (ev.x, ev.y, self.brush.get(), self.level.get())
		self.brush_ring(ev, at=(ev.x, ev.y))
		return "break"

	def size_drag(self, ev):
		s = getattr(self, "_sizing", None)
		if not s:
			return
		x, y, size, level = s
		self.brush.set(min(400, max(1, size + (ev.x - x) / self._view[2])))  # (screen pixels -> picture pixels: smooth)
		self.set_level(int(min(100, max(1, level - (ev.y - y) / 2))))
		self.brush_ring(ev, at=(x, y))
		return "break"

	def size_end(self, ev):
		if getattr(self, "_sizing", None):
			self._sizing = None
			self.brush_ring(ev)

	def undo_stroke(self):
		"""Ctrl+Z: the last brush stroke, Reset or paste taken back."""
		if self.mask_undo:
			step = self.mask_undo.pop()
			if isinstance(step, tuple):  # (a paste: the layer it replaced comes back)
				_, self.after_im, self.base_up, self.mask = step
			else:
				self.mask = step
			self.draw()

	# ---------- 📋 copy / paste, to work on it in another program ----------
	def clip_menu(self, ev):
		m = tk.Menu(self, tearoff=0)
		top = "Remini's version" if self.step == "remini" else "the swapped face"
		have = self.after_im is not None
		m.add_command(label="📋 Copy the result (as edited)    Ctrl+C", command=lambda: self.copy("result"),
					  state="normal" if have else "disabled")
		m.add_command(label=f"📋 Copy {top} only (the top layer)", command=lambda: self.copy("layer"),
					  state="normal" if have else "disabled")
		m.add_command(label="📋 Copy the original (the bottom layer)", command=lambda: self.copy("base"))
		m.add_separator()
		m.add_command(label="📥 Paste on top (it becomes the top layer)    Ctrl+V", command=self.paste)
		m.tk_popup(ev.x_root, ev.y_root)

	def copy(self, what):
		if what != "base" and self.after_im is None:
			return
		im = {"result": self.final, "layer": lambda: self.after_im, "base": lambda: self.base_up or self.before}[what]()
		try:
			copy_image(im)
		except OSError as ex:
			return messagebox.showerror("📋 Copy", f"Couldn't copy: {ex}", parent=self)
		self.info.config(text=f"📋 Copied ({im.width}×{im.height}). Edit it anywhere, copy it there, then right-click > 📥 Paste on top.")

	def paste(self):
		"""📥 The clipboard's picture as the top layer (in the result's size): the strength / eraser then work on it."""
		from PIL import Image
		im = paste_image()
		if im is None:
			return messagebox.showinfo("📥 Paste", "There's no picture on the clipboard. Copy one (in Photoshop: Ctrl+A, Ctrl+Shift+C "
										   "for everything you see), then paste here.", parent=self)
		size = self.after_im.size if self.after_im is not None else im.size
		if self.after_im is not None:
			self.mask_undo = (self.mask_undo + [("layer", self.after_im, self.base_up, self.mask)])[-20:]
		odd = abs(im.width / im.height - size[0] / size[1]) > 0.02
		self.after_im = im if im.size == size else im.resize(size, Image.LANCZOS)
		self.base_up = self.before.resize(size, Image.LANCZOS)
		self.mask = Image.new("L", size, 255)
		self.strength.set(100)
		for btn in (self.save_btn, self.use_btn, self.layer_btn, self.swap_btn):
			btn.state(["!disabled"])
		self.info.config(text=f"📥 Pasted on top ({im.width}×{im.height}" + (f", stretched to {size[0]}×{size[1]}: not the same shape!" if odd
							  else f" → {size[0]}×{size[1]}" if im.size != size else "") + "). Ctrl+Z takes it back.")
		self.draw()

	def save_layer(self):
		"""Remini's version with the strength / rubbed-out parts as transparency: to lay over the original elsewhere."""
		stem = os.path.splitext(os.path.basename(self.path))[0]
		dst = filedialog.asksaveasfilename(parent=self, title="Save the overlay layer", defaultextension=".png",
										   initialfile=f"{stem}_remini_overlay_{self.scale.get()}x.png", filetypes=[("PNG", "*.png")])
		if dst:
			from PIL import ImageChops
			layer = self.after_im.copy()
			layer.putalpha(ImageChops.multiply(self.after_im.getchannel("A"), self.effective()))
			layer.save(dst)
			self.pane.app.set_status(f"✨ Remini: overlay layer saved as {os.path.basename(dst)}.")

	def flip(self):
		if self.mode.get() == "overlay":
			self.showing = "before" if self.showing == "after" else "after"
			self.draw()

	def set_zoom(self, zoom):
		self.zoom = None if zoom is None else min(32, max(0.1, zoom))
		self.draw()

	def photo(self, im, box, scale):
		from PIL import Image, ImageTk
		size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
		out = im.resize(size, Image.NEAREST if scale > 1.5 else Image.LANCZOS)
		w, h = min(size[0], box[0]), min(size[1], box[1])
		return ImageTk.PhotoImage(out.crop(((size[0] - w) // 2, (size[1] - h) // 2, (size[0] - w) // 2 + w, (size[1] - h) // 2 + h)))

	def draw(self):
		c = self.canvas
		c.delete("all")
		W, H = c.winfo_width(), c.winfo_height()
		if W < 40:
			return
		muted = ui.P.get("muted", "#777777")
		self._photos = []
		# (both drawn at the same size on screen: the original is shown as big as the result)
		target = self.after_im.size if self.after_im is not None else (self.before.width * self.scale.get(), self.before.height * self.scale.get())
		self._view = None
		if self.mode.get() == "edit" and self.after_im is not None:
			im = self.final()
			box = (W - 20, H - 30)
			self._scale = self.zoom or min(box[0] / target[0], box[1] / target[1], 4)
			ph = self.photo(im, box, self._scale)
			self._photos.append(ph)
			size = (round(im.width * self._scale), round(im.height * self._scale))
			w, h = ph.width(), ph.height()
			x0, y0 = W / 2 - w / 2, (H - 18) / 2 - h / 2
			self._view = (x0, y0, self._scale, (size[0] - w) // 2, (size[1] - h) // 2)
			c.create_image(W / 2, (H - 18) / 2, image=ph)
			c.create_text(W / 2, H - 4, anchor="s", fill=muted, font="om_small",
						  text=f"EDITED  ·  Remini {self.strength.get()}%  ·  drag to {'rub it out' if self.tool.get() == 'erase' else 'paint it back'}")
			return
		if self.mode.get() == "overlay":
			im = self.final() if self.showing == "after" and self.after_im is not None else self.before
			box = (W - 20, H - 30)
			fit = min(box[0] / target[0], box[1] / target[1], 4)
			self._scale = self.zoom or fit
			ph = self.photo(im, box, self._scale * target[0] / im.width)
			self._photos.append(ph)
			c.create_image(W / 2, (H - 18) / 2, image=ph)
			c.create_text(W / 2, H - 4, anchor="s", fill=muted, font="om_small",
						  text=f"{'REMINI' if im is self.after_im else 'ORIGINAL'}  ·  click / Space flips")
			return
		half = W / 2
		box = (int(half - 16), H - 30)
		self._scale = self.zoom or min(box[0] / target[0], box[1] / target[1], 4)
		for i, (name, im) in enumerate((("ORIGINAL", self.before), ("REMINI", self.final()))):
			cx = half * i + half / 2
			if im is None:
				c.create_text(cx, H / 2, text="✨ working...", fill=muted, font="om_head")
			else:
				ph = self.photo(im, box, self._scale * target[0] / im.width)
				self._photos.append(ph)
				c.create_image(cx, (H - 18) / 2, image=ph)
			c.create_text(cx, H - 4, anchor="s", text=name, fill=muted, font="om_small")
		c.create_line(half, 8, half, H - 24, fill=ui.P.get("border", "#cccccc"))

	def save_png(self):
		stem = os.path.splitext(os.path.basename(self.path))[0]
		dst = filedialog.asksaveasfilename(parent=self, title="Save Remini's picture", defaultextension=".png",
										   initialfile=f"{stem}_{'remini_' + str(self.scale.get()) + 'x' if self.step == 'remini' else 'selfswap'}.png",
										   filetypes=[("PNG", "*.png")])
		if dst:
			self.final().save(dst)
			self.pane.app.set_status(f"✨ Remini: saved {os.path.basename(dst)}.")

	def use(self):
		"""Into the mod in place of the original: its size and format; the original goes to backups/remini first."""
		from PIL import Image
		ext = os.path.splitext(self.path)[1].lower()
		fmt = {".dds": "DDS", ".tga": "TGA", ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}.get(ext)
		if fmt is None:
			return messagebox.showinfo("✨ Remini", f"Can't write {ext} files: use 💾 Save as PNG.", parent=self)
		if not messagebox.askyesno("✨ Remini", f"Replace {os.path.basename(self.path)} in the mod with Remini's version, at its "
							   f"size ({self.orig_size[0]}×{self.orig_size[1]})?\n\nThe original is copied to "
							   "tools/organisation_master/backups/remini first.", parent=self):
			return
		backup = os.path.join(paths.TOOL, "backups", "remini", datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
		os.makedirs(backup, exist_ok=True)
		shutil.copy2(self.path, backup)
		out = self.final().resize(self.orig_size, Image.LANCZOS)
		original = Image.open(self.path)
		if "A" not in original.getbands() and original.mode != "P":
			out = out.convert("RGB")
		if fmt == "JPEG":
			out = out.convert("RGB")
		out.save(self.path, fmt)
		root = os.path.normcase(os.path.abspath(self.pane.app.mod_root))
		if os.path.normcase(os.path.abspath(self.path)).startswith(root):
			self.pane.app.log(os.path.relpath(self.path, self.pane.app.mod_root).replace("\\", "/"))
		self.pane.app.set_status(f"✨ Remini: {os.path.basename(self.path)} replaced (the original is in backups/remini).")
		getattr(self.pane.app, "feedback", lambda *_: None)("success")
		self.destroy()

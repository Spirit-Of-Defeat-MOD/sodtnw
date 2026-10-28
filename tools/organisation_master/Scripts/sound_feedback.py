"""Soft, synthesised UI sounds played from memory without blocking Tk."""
import array
import io
import json
import os
import math
import random
import sys
import threading
import time
import wave
import tkinter as tk
from tkinter import ttk
from functools import lru_cache
import paths  # (Scripts/paths.py: where the tool's files are)

try:
	import winsound
except ImportError:
	winsound = None


RATE = 22050
DURATIONS = {"click": 0.024, "open": 0.06, "close": 0.06, "select": 0.027, "select_owned": 0.07,
	"claim": 0.19, "success": 0.045, "complete": 0.11, "undo": 0.065, "womp": 0.34, "new_task": 0.15,
	"icon": 0.06, "dropdown_open": 0.012, "dropdown_select": 0.018, "priority_low": 0.025,
	"priority_normal": 0.035, "priority_high": 0.065, "priority_critical": 0.12, "ai": 0.095, "exit": 0.17,
	"brush": 0.11, "colour": 0.07, "switch": 0.05, "validation_ok": 0.13, "validation_problem": 0.055, "startup": 0.32,
	"reaction_like": 0.16, "reaction_super": 0.46, "reaction_dislike": 0.26, "theme_change": 0.26, "ghost": 0.7, "presence": 0.42}
RELIABLE = {"claim", "womp", "new_task", "ai", "dropdown_select", "priority_low", "priority_normal", "priority_high", "priority_critical",
	"brush", "colour", "switch", "validation_ok", "validation_problem", "startup", "reaction_like", "reaction_super", "reaction_dislike", "theme_change", "ghost", "presence"}


def sound_bytes(kind):
	"""Soft generated feedback, with a bundled voice clip for Super Want."""
	if kind == "reaction_super":
		try:
			with open(os.path.join(paths.BUNDLE, "sounds", "yes.wav"), "rb") as f:
				return f.read()
		except OSError:
			pass  # A melodic fallback if the optional voice asset is missing.
	duration = DURATIONS[kind]
	rng = random.Random(31)
	samples = array.array("h")
	previous = 0.0
	for n in range(int(RATE * duration)):
		t = n / RATE
		attack = min(1.0, t / 0.0015)
		tail = min(1.0, (duration - t) / 0.006)
		if kind == "presence":
			# 👋 a very light two-note ping (another dev opened a tool): high, soft, quickly gone.
			value = 0.0
			for start, frequency in ((0, 1318.5), (0.085, 1975.5)):
				u = t - start
				if u >= 0:
					value += 0.16 * min(1.0, u / 0.004) * math.sin(2 * math.pi * frequency * u) * math.exp(-u * 16)
		elif kind == "ghost":
			# A rounded, breathy oo vowel with a rising/falling pitch and gentle vibrato.
			phase = 2 * math.pi * (190*t + 30*duration/math.pi * (1-math.cos(math.pi*t/duration))) + .07*math.sin(2*math.pi*5*t)
			value = sum(weight * math.sin(harmonic*phase) for harmonic, weight in ((1,.65),(2,.24),(3,.07),(4,.025)))
			value *= math.sin(math.pi*t/duration)**1.3
		elif kind == "click":
			noise = rng.uniform(-1, 1)
			value = (0.55 * (noise - previous) + 0.45 * math.sin(2 * math.pi * 1550 * t)) * math.exp(-t * 210)
			previous = noise
		elif kind == "open":
			value = math.sin(2 * math.pi * (850 * t + 4500 * t * t)) * math.exp(-t * 65)
		elif kind == "close":
			u = (int(RATE * duration) - 1 - n) / RATE
			value = math.sin(2 * math.pi * (850 * u + 4500 * u * u)) * math.exp(-u * 65)
			attack = min(1.0, u / 0.0015)
			tail = min(1.0, (duration - u) / 0.006)
		elif kind == "select":
			value = 0.5 * math.sin(2 * math.pi * 720 * t) * math.exp(-t * 150)
		elif kind == "select_owned":
			value = sum(weight * math.sin(2 * math.pi * frequency * t) for frequency, weight in
						((660, 0.45), (825, 0.28), (990, 0.18))) * math.exp(-t * 65)
		elif kind == "claim":
			value = 0.0
			for start, frequency in ((0, 784), (0.045, 988), (0.09, 1175)):
				u = t - start
				if u >= 0:
					value += 0.65 * min(1.0, u / 0.002) * math.sin(2 * math.pi * frequency * u) * math.exp(-u * 40)
		elif kind == "womp":
			value = 0.0
			for start, frequency in ((0, 360), (0.17, 285)):
				u = t - start
				if 0 <= u < 0.17:
					phase = 2 * math.pi * (frequency * u - 430 * u * u)
					value += 0.75 * min(1.0, u / 0.009, (0.17 - u) / 0.025) * math.exp(-u * 5) * (math.sin(phase) + 0.25 * math.sin(phase * 2))
		elif kind in ("startup", "reaction_super", "theme_change"):
			value = 0.0
			notes = ((0, 659.25), (0.055, 523.25), (0.12, 1046.5)) if kind == "theme_change" else ((0, 523.25), (0.055, 659.25), (0.11, 783.99), (0.18, 1046.5))
			for start, frequency in notes:
				u = t - start
				if u >= 0:
					value += 0.55 * min(1.0, u / 0.003) * math.exp(-u * 45) * (
						math.sin(2 * math.pi * frequency * u) + 0.15 * math.sin(4 * math.pi * frequency * u))
		elif kind in ("new_task", "exit", "ai"):
			notes = {"new_task": ((0, 660), (0.04, 880), (0.08, 1320)),
					 "exit": ((0, 880), (0.045, 660), (0.09, 440)),
					 "ai": ((0, 950), (0.028, 1270), (0.056, 850))}[kind]
			value = 0.0
			for start, frequency in notes:
				u = t - start
				if u >= 0:
					value += 0.55 * min(1.0, u / 0.002) * math.sin(2 * math.pi * frequency * u) * math.exp(-u * (115 if kind == "ai" else 55))
		elif kind in ("dropdown_open", "dropdown_select"):
			value = 0.23 * math.sin(2 * math.pi * (1100 if kind == "dropdown_open" else 1400) * t) * math.exp(-t * 170)
		elif kind.startswith("priority_"):
			frequency, weight, pulses = {"priority_low": (580, 0.25, 1), "priority_normal": (760, 0.35, 1),
				"priority_high": (1050, 0.5, 2), "priority_critical": (1450, 0.65, 3)}[kind]
			value = 0.0
			for pulse in range(pulses):
				u = t - pulse * 0.035
				if u >= 0:
					value += weight * min(1.0, u / 0.002) * math.sin(2 * math.pi * frequency * u) * math.exp(-u * 95)
		elif kind == "icon":
			value = (0.55 * math.sin(2 * math.pi * 1800 * t) + 0.2 * math.sin(2 * math.pi * 2700 * t)) * math.exp(-t * 70)
		elif kind == "brush":
			previous = 0.85 * previous + 0.15 * rng.uniform(-1, 1)
			value = 1.7 * previous * math.sin(math.pi * t / duration) ** 2
		elif kind == "colour":
			value = 0.65 * math.sin(2 * math.pi * (2300 * t - 9000 * t * t)) * math.exp(-t * 75)
		elif kind == "switch":
			value = 0.0
			for start, frequency in ((0, 900), (0.025, 600)):
				u = t - start
				if u >= 0:
					value += min(1.0, u / 0.0015) * (0.5 * math.sin(2 * math.pi * frequency * u) + 0.3 * rng.uniform(-1, 1)) * math.exp(-u * 230)
		elif kind == "validation_ok":
			value = (0.5 * math.sin(2 * math.pi * 1046 * t) + 0.25 * math.sin(2 * math.pi * 1568 * t)) * math.exp(-t * 35)
		elif kind == "validation_problem":
			value = 0.65 * math.sin(2 * math.pi * 260 * t) * math.exp(-t * 95)
		elif kind == "reaction_like":
			value = (0.65 * math.sin(2 * math.pi * 1046.5 * t) + 0.25 * math.sin(2 * math.pi * 2093 * t)
					 + 0.1 * math.sin(2 * math.pi * 3139.5 * t)) * math.exp(-t * 24)
		elif kind == "reaction_dislike":
			# Original brassy incorrect-answer buzzer, without a spoken phrase.
			value = sum(weight * math.sin(2 * math.pi * frequency * harmonic * t)
				for frequency in (146.83, 207.65) for harmonic, weight in ((1, 0.23), (3, 0.13), (5, 0.07), (7, 0.035)))
			value *= min(1.0, t / 0.008, (duration - t) / 0.035)
		else:
			frequency = {"success": 1050, "complete": 1100, "undo": 780}[kind]
			value = math.sin(2 * math.pi * frequency * t) * math.exp(-t * 90)
			if kind == "complete" and t >= 0.045:
				u = t - 0.045
				value += min(1.0, u / 0.002) * math.sin(2 * math.pi * 1460 * u) * math.exp(-u * 70)
			elif kind == "undo":
				value = math.sin(2 * math.pi * (900 * t - 2400 * t * t)) * math.exp(-t * 65)
		samples.append(int(32767 * 0.16 * value * attack * tail))
	if sys.byteorder != "little":
		samples.byteswap()
	buf = io.BytesIO()
	with wave.open(buf, "wb") as wav:
		wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
		wav.writeframes(samples.tobytes())
	return buf.getvalue()


SOUNDS = {kind: sound_bytes(kind) for kind in DURATIONS}

THEME_BANKS = {
	"Classic": "clean", "Midnight": "clean", "Revolution Realised": "field", "Field Grey": "field",
	"Sons of Sorel": "field", "Arctic Station": "ice", "BurgSys": "industrial", "Soviet Terminal": "terminal",
	"Halloween": "horror", "Christmas": "festive", "Vaporwave": "vapor", "Rising Sun": "zen",
	"Andorran Dream": "imperial", "Stallonian Gambit": "cartoon",
}
# Playback speed, echo strength/delay, and timbre. Voices stay intelligible in each bank.
BANKS = {
	"field": (0.96, 0.06, 0.025, "wood"), "ice": (1.1, 0.14, 0.035, "glass"),
	"industrial": (0.92, 0.07, 0.025, "metal"), "terminal": (1.03, 0, 0, "digital"),
	"horror": (0.83, 0.22, 0.055, "ghost"), "festive": (1.08, 0.15, 0.035, "bells"),
	"vapor": (0.9, 0.24, 0.06, "chorus"), "zen": (1.0, 0.04, 0.025, "wood"),
	"imperial": (0.94, 0.13, 0.04, "regal"), "cartoon": (1.16, 0.12, 0.025, "bounce"),
}

SIGNATURES = {
	"field": ("latch", 330, (1, 4 / 3, 1.5), 0.34),
	"ice": ("glass", 1174.66, (1, 1.5, 2), 0.42),
	"industrial": ("metal", 130.81, (1, 1.414, 2), 0.44),
	"terminal": ("bits", 330, (1, 2, 1.5, 3), 0.36),
	"horror": ("ghost", 146.83, (1, 1.05946, 0.75, 1.414), 0.80),
	"festive": ("bells", 1046.5, (1, 1.25, 1.5, 2), 0.44),
	"vapor": ("pad", 220, (1, 1.2, 1.5, 1.8), 0.60),
	"zen": ("wood", 440, (1, 1.5, 4 / 3), 0.40),
	"imperial": ("brass", 196, (1, 1.5, 2, 2.5), 0.52),
	"cartoon": ("boing", 523.25, (1, 1.5, 2, 3), 0.43),
}
SIGNATURE_KINDS = {"startup", "exit", "theme_change", "click", "select", "select_owned", "open", "close", "dropdown_open", "dropdown_select", "success", "icon"}


def signature_sound(kind, bank):
	"""Different melodies and instruments for common UI actions, rather than filtered copies."""
	if kind == "close":
		with wave.open(io.BytesIO(signature_sound("open", bank)), "rb") as wav:
			samples = array.array("h", wav.readframes(wav.getnframes()))
		samples.reverse()  # Reversing complete samples also preserves byte order.
	else:
		style, root, melody, startup_duration = SIGNATURES[bank]
		short = kind not in ("startup", "exit", "theme_change")
		if kind == "startup":
			duration = startup_duration
			frequencies = [root * ratio for ratio in melody]
		elif kind == "exit":
			duration = startup_duration * 0.72
			frequencies = [root * ratio for ratio in reversed(melody[:3])]
		elif kind == "theme_change":
			duration = startup_duration * 0.85
			frequencies = [root * ratio for ratio in (melody[1], melody[0], melody[-1])]
		else:
			duration = {"click": 0.055, "select": 0.045, "select_owned": 0.105, "open": 0.10,
				"dropdown_open": 0.025, "dropdown_select": 0.035, "success": 0.095, "icon": 0.09}[kind]
			frequencies = [root * ratio for ratio in ((2, 2.5, 3) if kind == "select_owned" else (2, 3) if kind in ("open", "success") else (2,))]
		step = duration * (0.52 if style == "pad" else 0.6) / len(frequencies)
		rng = random.Random(103)
		samples = array.array("h")
		for n in range(int(duration * RATE)):
			t, value = n / RATE, 0.0
			for i, frequency in enumerate(frequencies):
				u = t - i * step
				if u < 0:
					continue
				phase = 2 * math.pi * frequency * u
				instrument = "metal" if short and style == "brass" else style
				if instrument == "brass":
					v = (math.sin(phase) + 0.45 * math.sin(phase * 2) + 0.23 * math.sin(phase * 3)) * min(1, u / 0.015) * math.exp(-u * 11)
				elif instrument == "ghost":
					phase += (0.8 if short else 2.5) * math.sin(u * 31) - (0 if short else 20 * u * u)
					v = (math.sin(phase) + 0.5 * math.sin(phase * 1.05946) + 0.22 * math.sin(phase * 3.03) + 0.12 * rng.uniform(-1, 1)) * min(1, u / (0.004 if short else 0.035)) * math.exp(-u * (45 if short else 6))
				elif instrument == "bits":
					v = sum(math.sin(phase * h) / h for h in (1, 3, 5)) / 1.5
					v = round(v * 12) / 12 * min(1, u / 0.002) * math.exp(-u * (90 if short else 26))
				elif instrument in ("bells", "glass"):
					v = (math.sin(phase) + 0.4 * math.sin(phase * 2.76) + 0.15 * math.sin(phase * 5.4)) * min(1, u / 0.002) * math.exp(-u * (65 if short else 18))
				elif instrument == "pad":
					v = (math.sin(phase) + 0.6 * math.sin(phase * 1.008)) * min(1, u / (0.005 if short else 0.04)) * math.exp(-u * (40 if short else 8))
				elif instrument == "boing":
					v = math.sin(phase + 4 * math.sin(u * 55)) * min(1, u / 0.002) * math.exp(-u * (65 if short else 20))
				elif instrument == "wood":
					v = (math.sin(phase) + 0.45 * math.sin(phase * 2.31)) * min(1, u / 0.002) * math.exp(-u * (100 if short else 32))
				else:
					v = (0.5 * math.sin(phase) + 0.35 * math.sin(phase * 3.71) + 0.25 * rng.uniform(-1, 1)) * min(1, u / 0.002) * math.exp(-u * (145 if short else 27))
				value += v / (1.5 if len(frequencies) > 1 else 1)
			gain = 0.07 if kind.startswith("dropdown_") else 0.13
			fade = min(1, t / 0.002, (duration - t) / 0.012)
			samples.append(round(max(-12000, min(12000, value * gain * 32767 * fade))))
		if sys.byteorder != "little":
			samples.byteswap()
	buf = io.BytesIO()
	with wave.open(buf, "wb") as wav:
		wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
		wav.writeframes(samples.tobytes())
	return buf.getvalue()


def sleigh_bells():
	"""A brief shake of several small, inharmonic bells for Christmas buttons."""
	duration = 0.16
	samples = array.array("h")
	for n in range(int(duration * RATE)):
		t, value = n / RATE, 0.0
		for start, strength in ((0, 1), (0.035, 0.7), (0.072, 0.4)):
			u = t - start
			if u >= 0:
				bell = sum(math.sin(2 * math.pi * f * u) * weight for f, weight in
					((1730, 0.34), (2390, 0.28), (3270, 0.2), (4510, 0.12), (5930, 0.06)))
				value += bell * strength * min(1, u / 0.0015) * math.exp(-u * 43)
		fade = min(1, (duration - t) / 0.015)
		samples.append(round(value * fade * 4800))
	if sys.byteorder != "little":
		samples.byteswap()
	buf = io.BytesIO()
	with wave.open(buf, "wb") as wav:
		wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
		wav.writeframes(samples.tobytes())
	return buf.getvalue()


def horror_scream():
	"""A short synthetic horror shriek with vocal harmonics, vibrato and a soft tail."""
	duration = 0.72
	rng = random.Random(666)
	samples = array.array("h")
	phase = 0.0
	for n in range(int(duration * RATE)):
		t = n / RATE
		frequency = (510 + 470 * min(1, t / 0.13) - 430 * max(0, t - 0.2)) * (1 + 0.045 * math.sin(t * 55))
		phase += 2 * math.pi * frequency / RATE
		voice = sum(math.sin(phase * h) * weight for h, weight in ((1, 0.46), (2, 0.3), (3, 0.2), (4, 0.13), (5, 0.08)))
		voice += 0.12 * rng.uniform(-1, 1)
		envelope = min(1, t / 0.035, (duration - t) / 0.2) * (0.88 + 0.12 * math.sin(t * 43))
		samples.append(round(voice * envelope * 6500))
	if sys.byteorder != "little":
		samples.byteswap()
	buf = io.BytesIO()
	with wave.open(buf, "wb") as wav:
		wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
		wav.writeframes(samples.tobytes())
	return buf.getvalue()


@lru_cache(maxsize=256)
def themed_sound(kind, bank):
	if kind == "ghost":
		return SOUNDS[kind]
	if bank == "festive" and kind == "click":
		return sleigh_bells()
	if bank == "horror" and kind == "reaction_dislike":
		return horror_scream()
	if bank == "festive" and kind == "reaction_super":
		try:
			with open(os.path.join(paths.BUNDLE, "sounds", "ho_ho_ho.wav"), "rb") as f:
				return f.read()
		except OSError:
			pass  # Keep the ordinary reaction available if the optional asset is missing.
	if bank not in BANKS:
		return SOUNDS[kind]
	if kind in SIGNATURE_KINDS:
		return signature_sound(kind, bank)
	with wave.open(io.BytesIO(SOUNDS[kind]), "rb") as wav:
		source = array.array("h", wav.readframes(wav.getnframes()))
		if sys.byteorder != "little":
			source.byteswap()
	speed, wet, delay, timbre = BANKS[bank]
	length = max(1, int(len(source) / speed))
	peak = max(map(abs, source), default=0)
	dry, previous = [], 0.0
	for n in range(length):
		t = n / RATE
		position = min(len(source) - 1, n * speed)
		index = int(position)
		v = source[index] + (source[min(index + 1, len(source) - 1)] - source[index]) * (position - index)
		if timbre == "digital":
			v = round(source[index - index % 3] / 192) * 192
		elif timbre in ("wood", "ghost", "chorus"):
			previous = 0.55 * previous + 0.45 * v
			v = previous
			if timbre != "wood":
				v *= 0.88 + 0.12 * math.sin(2 * math.pi * (7 if timbre == "ghost" else 2) * t)
		elif timbre == "metal":
			v *= 0.82 + 0.18 * math.sin(2 * math.pi * 85 * t)
		elif timbre == "bounce":
			v *= 0.8 + 0.2 * math.cos(2 * math.pi * 16 * t)
		if kind != "reaction_super" and timbre in ("glass", "bells", "regal"):
			frequency = {"glass": 2800, "bells": 3200, "regal": 660}[timbre]
			v += peak * 0.07 * math.sin(2 * math.pi * frequency * t) * min(1.0, t / 0.002) * math.exp(-t * 45)
		dry.append(v)
	echo = int(delay * RATE)
	length += echo * 2 if wet else 0
	output = array.array("h")
	for n in range(length):
		v = dry[n] if n < len(dry) else 0
		for repeat in (1, 2):
			index = n - echo * repeat
			if wet and 0 <= index < len(dry):
				v += dry[index] * wet ** repeat
		fade = min(1.0, n / (RATE * 0.001), (length - 1 - n) / (RATE * 0.004))
		output.append(round(max(-14000, min(14000, v * fade))))
	if sys.byteorder != "little":
		output.byteswap()
	buf = io.BytesIO()
	with wave.open(buf, "wb") as wav:
		wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
		wav.writeframes(output.tobytes())
	return buf.getvalue()


def at_volume(data, volume):
	"""A 16-bit WAV clip with its samples scaled (1.0 = as made)."""
	if volume >= 0.999:
		return data
	try:
		with wave.open(io.BytesIO(data), "rb") as w:
			params = w.getparams()
			frames = w.readframes(params.nframes)
		if params.sampwidth != 2:
			return data
		samples = array.array("h", frames)
		samples = array.array("h", (int(v * volume) for v in samples))
		out = io.BytesIO()
		with wave.open(out, "wb") as w:
			w.setparams(params)
			w.writeframes(samples.tobytes())
		return out.getvalue()
	except (wave.Error, EOFError, ValueError):
		return data


class SoundFeedback:
	def __init__(self, enabled, player=None, clock=time.monotonic, theme=None, volume=None):
		self.enabled = enabled
		self.volume = volume or (lambda: 1.0)
		self._scaled = {}
		self.theme = theme or (lambda: "Classic")
		self.player = player if player is not None else (
			(lambda data: winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)) if winsound else None)
		self.clock = clock
		self._busy = threading.Lock()
		self._pending = {kind: threading.Lock() for kind in RELIABLE}
		self._closing = False
		self._last = float("-inf")

	def clip(self, kind):
		data = themed_sound(kind if kind in SOUNDS else "success", THEME_BANKS.get(self.theme(), "clean"))
		vol = round(self.volume(), 2)
		key = (id(data), vol)
		if key not in self._scaled:
			if len(self._scaled) > 200:
				self._scaled.clear()
			self._scaled[key] = at_volume(data, vol)
		return self._scaled[key]

	def play(self, kind="success"):
		if self._closing:
			return False
		if kind in RELIABLE:
			return self.play_result(kind)
		if not self.enabled() or self.player is None or not self._busy.acquire(blocking=False):
			return False
		now = self.clock()
		interval = 0.015 if kind == "dropdown_open" else 0.035 if kind in ("click", "select", "icon") else 0.06 if kind in ("open", "close", "select_owned") else 0.12
		if now - self._last < interval:
			self._busy.release()
			return False
		self._last = now

		def run():
			try:
				if self.enabled():
					self.player(self.clip(kind))
			except Exception:
				pass  # Audio unavailable: the action still succeeds.
			finally:
				self._busy.release()

		try:
			threading.Thread(target=run, daemon=True).start()
		except RuntimeError:
			self._busy.release()
			return False
		return True

	def play_result(self, kind):
		"""Let an action result follow its click; coalesce duplicate pending results."""
		pending = self._pending[kind]
		if not self.enabled() or self.player is None or not pending.acquire(blocking=False):
			return False

		def run():
			try:
				with self._busy:
					if self.enabled() and not self._closing:
						self._last = self.clock()
						self.player(self.clip(kind))
			except Exception:
				pass
			finally:
				pending.release()

		try:
			threading.Thread(target=run, daemon=True).start()
		except RuntimeError:
			pending.release()
			return False
		return True

	def finish(self):
		"""Play the exit sound once; the UI polls the returned event before closing."""
		self._closing = True
		done = threading.Event()
		if not self.enabled() or self.player is None:
			done.set()
			return done
		def run():
			try:
				with self._busy:
					if self.enabled():
						self.player(self.clip("exit"))
			except Exception:
				pass
			finally:
				done.set()
		try:
			threading.Thread(target=run, daemon=True).start()
		except RuntimeError:
			done.set()
		return done


class SoundBindings:
	def play_startup(self):
		# Keep reloads and switching the open mod in the same window silent.
		if not getattr(self.root, "_startup_sound_played", False):
			self.root._startup_sound_played = True
			self.feedback("startup")

	def install_button_sounds(self):
		# A tag before the normal widget bindings also covers buttons in future dialogs.
		for event in ("<ButtonPress-1>", "<KeyPress-space>", "<KeyPress-Return>"):
			self.root.bind_class("OM.SoundButton", event, self.button_sound)
		self.root.bind_all("<Map>", self.prepare_button_sound, add="+")
		def walk(widget):
			self.prepare_button_sound(widget=widget)
			for child in widget.winfo_children():
				walk(child)
		walk(self.root)

	def prepare_button_sound(self, event=None, widget=None):
		w = widget if widget is not None else event.widget
		if isinstance(w, str):  # <Map> can hand over a path name (a combobox's list) instead of the widget # Globus
			return
		if getattr(self, "general_controls", False):
			if isinstance(w, ttk.Combobox):
				self.bind_dropdown_sound(w)
			elif isinstance(w, ttk.Treeview) and not getattr(w, "_sound_tree", False):
				w._sound_tree = True
				w.bind("<<TreeviewOpen>>", lambda ev: self.feedback("open"), add="+")
				w.bind("<<TreeviewClose>>", lambda ev: self.feedback("close"), add="+")
				w.bind("<ButtonPress-1>", lambda ev: setattr(ev.widget, "_sound_press", (ev.x, ev.y)), add="+")
				w.bind("<ButtonRelease-1>", self.tree_sound, add="+")
		if w.winfo_class() in ("TButton", "Button", "TCheckbutton", "Checkbutton", "TRadiobutton", "Radiobutton") or (
			w.winfo_class() == "Label" and getattr(w.master, "_om_bar", False)):
			if w.winfo_class() in ("TCheckbutton", "Checkbutton") and any(label in str(w.cget("text")) for label in ("Requires AI", "Needs AI")):
				w.sound_kind = lambda: "click" if w.tk.getboolean(w.getvar(w.cget("variable"))) else "ai"
			tags = w.bindtags()
			if "OM.SoundButton" not in tags:
				w.bindtags(("OM.SoundButton",) + tags)

	def button_sound(self, event):
		w = event.widget
		if (hasattr(w, "instate") and w.instate(("disabled",))) or str(w.cget("state")) == "disabled":
			return
		kind = getattr(w, "sound_kind", "click")
		self.feedback(kind() if callable(kind) else kind)

	def task_editor_sounds(self, container):
		for w in container.winfo_children():
			if isinstance(w, ttk.Combobox):
				self.bind_dropdown_sound(w)
			self.task_editor_sounds(w)

	def bind_dropdown_sound(self, widget):
		if getattr(widget, "_sound_dropdown", False):
			return
		widget._sound_dropdown = True
		for event in ("<ButtonPress-1>", "<KeyPress-F4>", "<Alt-KeyPress-Down>"):
			widget.bind(event, lambda ev: self.dropdown_sound(ev.widget), add="+")
		widget.bind("<<ComboboxSelected>>", lambda ev: self.dropdown_sound(ev.widget, selected=True), add="+")

	def tree_sound(self, event):
		w = event.widget
		x, y = getattr(w, "_sound_press", (event.x, event.y))
		if abs(x - event.x) + abs(y - event.y) > 6:
			return
		if w.identify_region(event.x, event.y) in ("tree", "cell") and w.identify_row(event.y) and "indicator" not in w.identify_element(event.x, event.y).lower():
			self.feedback("select")

	def dropdown_sound(self, widget, selected=False):
		if widget.instate(("disabled",)):
			return
		kind = "dropdown_select" if selected else "dropdown_open"
		if selected and getattr(widget, "sound_priority", False):
			kind = "priority_" + widget.get().lower() if widget.get() in ("Low", "Normal", "High", "Critical") else kind
		self.feedback(kind)


class SharedSoundSettings:
	"""One local preference for all three tools, with migration from the older config."""
	def __init__(self, directory=None):
		directory = directory or os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "OrganisationMaster")
		self.path = os.path.join(directory, "sounds.json")
		self.legacy = os.path.join(directory, "config.json")
		self._key = None
		self._enabled = True
		self._volume = 1.0

	def _read(self):
		path = self.path if os.path.exists(self.path) else self.legacy
		try:
			stat = os.stat(path)
			key = path, stat.st_mtime_ns, stat.st_size
			if key != self._key:
				with open(path, encoding="utf-8") as f:
					data = json.load(f)
				value = data.get("enabled" if path == self.path else "sound_feedback", True)
				self._enabled = value if isinstance(value, bool) else True
				vol = data.get("volume", 1.0) if path == self.path else 1.0
				self._volume = min(1.0, max(0.0, float(vol))) if isinstance(vol, (int, float)) else 1.0
				self._key = key
		except (OSError, ValueError, AttributeError):
			self._enabled, self._volume = True, 1.0

	def volume(self):
		"""0.0 - 1.0, shared by the three masters like the on / off setting."""
		self._read()
		return self._volume

	def set_volume(self, volume):
		self._write(enabled=self.enabled(), volume=min(1.0, max(0.0, float(volume))))

	def _write(self, **values):
		os.makedirs(os.path.dirname(self.path), exist_ok=True)
		temp = self.path + f".{os.getpid()}.tmp"
		with open(temp, "w", encoding="utf-8") as f:
			json.dump(values, f)
		os.replace(temp, self.path)
		self._key = None

	def enabled(self):
		self._read()
		return self._enabled

	def set(self, enabled):
		self._write(enabled=bool(enabled), volume=self.volume())


def volume_window(root, settings, test):
	"""Settings > Sound volume...: one slider for every master's sounds (saved on this PC as you move it)."""
	import tkinter as tk
	from tkinter import ttk
	old = getattr(root, "_volume_window", None)
	if old is not None and old.winfo_exists():
		old.lift()
		return old
	w = root._volume_window = tk.Toplevel(root)
	w.title("Sound volume")
	w.transient(root)
	w.resizable(False, False)
	f = ttk.Frame(w, padding=14)
	f.pack()
	ttk.Label(f, text="Sound volume", style="Head.TLabel").pack(anchor="w")
	ttk.Label(f, text="For the clicks, chimes and theme sounds in every master (the Radio and Music Master have their own).",
			  style="Muted.TLabel", wraplength=300, justify="left").pack(anchor="w", pady=(2, 8))
	row = ttk.Frame(f)
	row.pack(fill="x")
	value = tk.DoubleVar(w, value=round(settings.volume() * 100))
	shown = ttk.Label(row, text=f"{int(value.get())}%", width=5)
	state = {"job": None}

	def moved(_=None):
		shown.config(text=f"{int(value.get())}%")
		settings.set_volume(value.get() / 100)
		if state["job"]:
			w.after_cancel(state["job"])
		state["job"] = w.after(250, lambda: test("success"))  # (a sample once you stop moving it)
	ttk.Label(row, text="🔈").pack(side="left")
	ttk.Scale(row, from_=0, to=100, variable=value, command=moved, length=220).pack(side="left", padx=6)
	ttk.Label(row, text="🔊").pack(side="left")
	shown.pack(side="left", padx=(8, 0))
	if not settings.enabled():
		ttk.Label(f, text="(Sound feedback is off: tick it in Settings to hear them.)", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
	ttk.Button(f, text="Close", command=w.destroy).pack(anchor="e", pady=(10, 0))
	return w


class MasterSounds(SoundBindings):
	"""Culture / Country Master's shared controls, preference and graceful exit."""
	general_controls = True

	def __init__(self, root, menu, theme=None):
		self.root = root
		self._ready = False
		self._quitting = False
		self.sound_settings = SharedSoundSettings()
		self.sounds = SoundFeedback(self.sound_settings.enabled, theme=theme, volume=self.sound_settings.volume)
		settings = tk.Menu(menu, tearoff=0)
		self.sound_var = tk.BooleanVar(root, value=self.sound_settings.enabled())
		settings.configure(postcommand=lambda: self.sound_var.set(self.sound_settings.enabled()))
		settings.add_checkbutton(label="Sound feedback", variable=self.sound_var, command=self.toggle_sound)
		settings.add_command(label="Sound volume...", command=lambda: volume_window(root, self.sound_settings, self.feedback))
		menu.add_cascade(label="Settings", menu=settings)
		root._sound_feedback = self
		self.install_button_sounds()

	def feedback(self, kind="success"):
		if self._ready and not self._quitting:
			self.sounds.play(kind)

	def toggle_sound(self):
		self.sound_settings.set(self.sound_var.get())
		self.feedback()

	def close(self):
		if self._quitting:
			return
		self._quitting = True
		done = self.sounds.finish()
		deadline = time.monotonic() + 1.5
		def finish():
			if done.is_set() or time.monotonic() >= deadline:
				self.root.destroy()
			else:
				self.root.after(20, finish)
		finish()


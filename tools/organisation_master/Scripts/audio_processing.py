"""Portable yt-dlp setup and cancellable audio processing, independent of Tk."""
from array import array
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import urllib.parse
import urllib.request
import zipfile

EQ_FREQUENCIES = (31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)


class Cancelled(Exception):
    pass


class AudioJob:
    def __init__(self, progress=lambda text: None):
        self.progress = progress
        self.cancelled = threading.Event()
        self.process = None

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled("Cancelled")

    def cancel(self):
        self.cancelled.set()
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def run(self, args):
        self.check()
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        for key in list(env):
            if key.startswith(("_MEIPASS", "_PYI_")):
                del env[key]
        process = self.process = subprocess.Popen([str(x) for x in args], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        lines = []
        tail = deque(maxlen=25)
        try:
            # cancel() terminates this owned subprocess, unblocking the pipe read.
            if self.cancelled.is_set():
                process.terminate()
            for line in process.stdout:
                line = line.rstrip()
                lines.append(line)
                tail.append(line)
                if line.startswith("[download]"):
                    self.progress(line)
            code = process.wait()
            self.check()
            if code:
                raise RuntimeError("\n".join(tail) or f"Audio tool exited with code {code}")
            return "\n".join(lines)
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
            self.process = None


def tool_paths(folder):
    folder = Path(folder)
    return {name: str(folder / (name + ".exe")) if (folder / (name + ".exe")).is_file()
        else shutil.which(name) for name in ("yt-dlp", "ffmpeg", "ffprobe", "deno")}


def _request(url):
    return urllib.request.urlopen(urllib.request.Request(url,
        headers={"User-Agent": "OrganisationMaster-Audio", "Accept": "application/vnd.github+json"}), timeout=30)


def install_tools(folder, job, update=False):
    """Official release binaries, verified against the publisher's SHA-256 digest."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tools = tool_paths(folder)
    manifest_path = folder / "versions.json"
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    packages = (("yt-dlp/yt-dlp", "yt-dlp.exe", ("yt-dlp.exe",)),
        ("yt-dlp/FFmpeg-Builds", "ffmpeg-master-latest-win64-gpl.zip", ("ffmpeg.exe", "ffprobe.exe")),
        ("denoland/deno", "deno-x86_64-pc-windows-msvc.zip", ("deno.exe",)))
    manifest = {}
    for repo, asset_name, members in packages:
        if not update and all(tools.get(Path(name).stem) for name in members):
            continue
        job.check()
        job.progress("Checking " + repo + "…")
        with _request("https://api.github.com/repos/" + repo + "/releases/latest") as response:
            release = json.load(response)
        asset = next((a for a in release["assets"] if a["name"] == asset_name), None)
        if asset is None:
            raise RuntimeError("The official release does not contain " + asset_name)
        digest = asset.get("digest") or ""
        if not digest.startswith("sha256:"):
            raise RuntimeError("No publisher SHA-256 digest available for " + asset_name)
        if (previous.get(repo, {}).get("sha256") == digest[7:]
                and all((folder / member).is_file() for member in members)):
            continue
        with tempfile.TemporaryDirectory(prefix="setup-", dir=folder) as temporary:
            archive = Path(temporary) / asset_name
            checksum = hashlib.sha256()
            received = 0
            with _request(asset["browser_download_url"]) as response, archive.open("wb") as output:
                while True:
                    job.check()
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    checksum.update(chunk)
                    output.write(chunk)
                    received += len(chunk)
                    job.progress(f"Installing {repo}: {received / 1048576:.0f} / {asset['size'] / 1048576:.0f} MB")
            if checksum.hexdigest() != digest[7:]:
                raise RuntimeError("Download checksum did not match: " + asset_name)
            if archive.suffix == ".zip":
                with zipfile.ZipFile(archive) as source:
                    for name in members:
                        item = next((i for i in source.infolist() if Path(i.filename).name == name), None)
                        if item is None:
                            raise RuntimeError("Missing " + name + " in the official archive")
                        target = Path(temporary) / name
                        with source.open(item) as reader, target.open("wb") as writer:
                            shutil.copyfileobj(reader, writer)
                        os.replace(target, folder / name)
                    # Preserve the upstream build's licenses alongside its executables.
                    for item in source.infolist():
                        if Path(item.filename).name.upper().startswith(("LICENSE", "COPYING")):
                            name = repo.replace("/", "-") + "-" + Path(item.filename).name
                            (folder / name).write_bytes(source.read(item))
            else:
                os.replace(archive, folder / asset_name)
        manifest[repo] = dict(version=release["tag_name"], url=release["html_url"], sha256=digest[7:])
    if manifest:
        previous.update(manifest)
        manifest_path.write_text(json.dumps(previous, indent=2), encoding="utf-8")
    return tool_paths(folder)


def youtube_url(value):
    value = value.strip()
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in (
            "youtube.com", "www.youtube.com", "music.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"):
        raise ValueError("Enter a YouTube video link (youtube.com or youtu.be).")
    if parsed.username or parsed.password:
        raise ValueError("Invalid YouTube link")
    return value


def download_audio(url, destination, tools, job):
    url = youtube_url(url)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    args = [tools["yt-dlp"], "--ignore-config", "--no-playlist", "--no-colors", "--newline",
        "--no-plugin-dirs", "--no-remote-components", "--socket-timeout", "20", "--retries", "3",
        "--match-filters", "!is_live", "--format", "bestaudio/best", "--write-info-json",
        "--windows-filenames", "--ffmpeg-location", str(Path(tools["ffmpeg"]).parent),
        "--js-runtimes", "deno:" + tools["deno"], "--output", str(destination / "source.%(ext)s"), "--", url]
    job.progress("Downloading audio…")
    job.run(args)
    metadata_file = destination / "source.info.json"
    info = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.exists() else {}
    sources = [p for p in destination.glob("source.*") if p.suffix.lower() in (
        ".webm", ".m4a", ".mp4", ".mp3", ".ogg", ".opus", ".wav", ".flac", ".aac")]
    if not sources:
        raise RuntimeError("No audio was downloaded. Check that the video is available.")
    return str(max(sources, key=lambda p: p.stat().st_mtime_ns)), info


def probe_audio(source, tools, job):
    info = json.loads(job.run([tools["ffprobe"], "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,duration:stream_tags=title,artist:format=duration",
        "-of", "json", str(source)]))
    streams = info.get("streams", [])
    if not streams:
        raise ValueError("This file has no audio stream.")
    stream = streams[0]
    duration = float(info.get("format", {}).get("duration") or stream.get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Could not determine the track length.")
    return dict(stream, duration=duration)


def parse_time(value):
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Use seconds, m:ss or h:mm:ss for trim times.")
    numbers = [float(part) for part in parts]
    if any(not math.isfinite(n) or n < 0 for n in numbers) or any(n >= 60 for n in numbers[1:]):
        raise ValueError("Trim times must be valid, non-negative times.")
    return sum(n * 60 ** i for i, n in enumerate(reversed(numbers)))


def edit_settings(duration, start=0, end=None, gain=0, fade_in=0, fade_out=0,
        bass=0, treble=0, eq=None, noise=False, noise_reduction=12, noise_floor=-50,
        noise_type="white", noise_track=True):
    end = duration if end is None else end
    eq = [float(value) for value in (eq if eq is not None else [0] * len(EQ_FREQUENCIES))]
    values = [duration, start, end, gain, fade_in, fade_out, bass, treble, noise_reduction, noise_floor, *eq]
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Audio settings must be finite numbers.")
    if not 0 <= start < end <= duration + 0.02:
        raise ValueError("The start must be before the end, within the track's length.")
    if not -60 <= gain <= 24:
        raise ValueError("Gain must be between -60 and +24 dB.")
    length = end - start
    if min(fade_in, fade_out) < 0 or max(fade_in, fade_out) > length:
        raise ValueError("Fades must fit within the trimmed track.")
    if len(eq) != len(EQ_FREQUENCIES) or any(abs(value) > 12 for value in eq) or max(abs(bass), abs(treble)) > 12:
        raise ValueError("Each EQ band, bass and treble must be between -12 and +12 dB.")
    if not 0.01 <= noise_reduction <= 30 or not -80 <= noise_floor <= -20:
        raise ValueError("Noise reduction must be 0.01–30 dB and its noise floor -80 to -20 dB.")
    if noise_type not in ("white", "vinyl", "shellac"):
        raise ValueError("Choose white, vinyl or shellac noise.")
    return dict(start=start, end=end, gain=gain, fade_in=fade_in, fade_out=fade_out,
        bass=bass, treble=treble, eq=eq, noise=bool(noise), noise_reduction=noise_reduction,
        noise_floor=noise_floor, noise_type=noise_type, noise_track=bool(noise_track))


def convert_audio(source, destination, tools, job, settings, title="", artist=""):
    info = probe_audio(source, tools, job)
    settings = edit_settings(info["duration"], **settings)
    start, end, gain = (settings[key] for key in ("start", "end", "gain"))
    filters = [f"atrim=start={start:.6f}:end={end:.6f}", "asetpts=PTS-STARTPTS", "aresample=44100"]
    if settings["noise"]:
        filters.append(f"afftdn=nr={settings['noise_reduction']:.6f}:nf={settings['noise_floor']:.6f}"
            f":nt={settings['noise_type']}:tn={int(settings['noise_track'])}")
    if settings["bass"]:
        filters.append(f"bass=g={settings['bass']:.6f}:f=100:t=q:w=0.707")
    if settings["treble"]:
        filters.append(f"treble=g={settings['treble']:.6f}:f=3000:t=q:w=0.707")
    for frequency, boost in zip(EQ_FREQUENCIES, settings["eq"]):
        if boost:
            filters.append(f"equalizer=f={frequency}:t=o:w=1:g={boost:.6f}")
    filters.append(f"volume={gain:.6f}dB")
    if settings["fade_in"]:
        filters.append(f"afade=t=in:d={settings['fade_in']:.6f}")
    if settings["fade_out"]:
        filters.append(f"afade=t=out:st={end-start-settings['fade_out']:.6f}:d={settings['fade_out']:.6f}")
    filters.append("alimiter=limit=0.98:level=0:latency=1")
    filters.append(f"atrim=duration={end-start:.6f}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + ".partial.ogg")
    job.progress("Trimming and converting to Ogg Vorbis…")
    try:
        job.run([tools["ffmpeg"], "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(source),
            "-map", "0:a:0", "-vn", "-sn", "-dn", "-af", ",".join(filters), "-ar", "44100", "-ac", "2",
            "-c:a", "libvorbis", "-q:a", "5", "-map_metadata", "-1", "-metadata", "title=" + title,
            "-metadata", "artist=" + artist, "-f", "ogg", str(temporary)])
        converted = probe_audio(temporary, tools, job)
        if converted["codec_name"] != "vorbis" or int(converted["sample_rate"]) != 44100 or converted["channels"] != 2:
            raise RuntimeError("Conversion did not produce the expected Ogg Vorbis format.")
        job.check()
        os.replace(temporary, destination)
        return converted
    finally:
        temporary.unlink(missing_ok=True)


def waveform(source, tools, job, width=700):
    with tempfile.TemporaryDirectory(prefix="audio-wave-") as temporary:
        raw = Path(temporary) / "samples.raw"
        job.progress("Reading waveform…")
        job.run([tools["ffmpeg"], "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", str(source), "-map", "0:a:0", "-ac", "1", "-ar", "2000", "-f", "s16le", str(raw)])
        step = max(1, math.ceil(raw.stat().st_size / 2 / width))
        peaks = []
        with raw.open("rb") as reader:
            while chunk := reader.read(step * 2):
                job.check()
                samples = array("h")
                samples.frombytes(chunk)
                peaks.append(max(abs(n) for n in samples) / 32768)
        return peaks

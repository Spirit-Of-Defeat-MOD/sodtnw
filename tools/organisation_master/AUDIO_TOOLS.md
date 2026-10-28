# Music Master track workshop

Open **Download / edit audio** in a station's Songs section or in a planned station.
Selected planned tracks bring their YouTube links into the queue; with nothing selected,
the whole plan is offered. Download selected tracks or the entire queue. You can also
paste a new YouTube link or open an existing audio file.
After a batch finishes, the first successfully downloaded track opens for review.
Use **Previous track / Next track** to work through the queue; each track keeps its own
trim points, gain, fades and volume settings as you move between tracks.

Existing radio stations also have **Plan a song…** and a **Planned songs for this station**
queue. Enter a title, artist and YouTube link without uploading audio. These entries
live-sync with station plans; **Download queue…** sends them to the workshop.

Select a loaded track to adjust its title/artist, start/end times, gain and optional fades.
Drag either trim boundary on the waveform or type seconds, `m:ss` or `h:mm:ss`.
Preview the original or edited version; **Use playhead** copies the preview position
into a trim boundary. Ctrl/Shift select several queue entries to export or add them together.
Playback buttons sit directly above the waveform. Right-click anywhere on it to play or
seek to that source position; left dragging continues to set trim boundaries. Pause/Resume,
Stop and the moving playhead let you check cuts. The in-game volume slider directly below
the waveform adjusts preview loudness immediately and sets the station asset's volume.

Each track has a ten-band graphic EQ, bass/treble shelving controls, and an optional noise
reducer. Noise reduction offers strength, noise floor, white/vinyl/shellac profiles and
automatic floor tracking. **Preview edit** uses the same filters as the final export.
The scrollable editor keeps these controls reachable at larger text sizes.

The queue, completed downloads, local source copies and per-track settings autosave in
`audio_recovery/` on this PC. An interrupted session is offered when the workshop reopens;
**Recover session…** can restore it later. Active workshops are locked so another running
copy does not mistakenly recover them. Partial downloads can resume through yt-dlp.
Restoration does not silently import or save tracks to the mod: review them first.
A normal workshop close removes that session, while already staged imports remain staged.

In a station's main Songs list, choose **Order in the file** and drag a song (or a selection
of songs) to the insertion line. The complete song blocks move, preserving chance scripts
and inline comments. The new order is staged until **Save to mod**; **Discard** restores
the saved order. Other sort modes only change the display and do not allow file reordering.
Saving shows a scrollable receipt of created, updated and deleted files, including backups.

Exports use Ogg **Vorbis**, stereo, 44.1 kHz, quality 5, with a limiter to prevent clipping.
Audio gain changes the file; in-game volume writes the separate `.asset` volume value.
**Add selected to station** stages the `.ogg`, `.asset` and station entries. **Save to mod**
writes them using Music Master's normal backups. Closing the workshop preserves staged
imports. **Trim / levels** on a selected station song stages replacement audio and its
in-game volume, while keeping its current game name and station chance rules.

The first operation installs missing tools into `audio_tools/` next to Organisation Master.
No Python installation is needed for the packaged application. **Set up / update audio tools**
checks official releases and downloads only changed packages. Executables on PATH are also
recognised. Downloads are checked against their official release SHA-256 digests.

Sources and licenses:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp): official Windows standalone executable; Unlicense and bundled third-party licenses.
- [FFmpeg builds maintained by yt-dlp](https://github.com/yt-dlp/FFmpeg-Builds): `ffmpeg` and `ffprobe`; the selected build includes GPL components. License files from the archive are retained next to the binaries.
- [Deno](https://github.com/denoland/deno): official Windows JavaScript runtime for YouTube extraction; MIT license.
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html) and [Vorbis encoder](https://ffmpeg.org/ffmpeg-codecs.html#libvorbis).

Downloaded utilities and temporary audio are local to each PC and are not committed or
live-synced. Final music files travel with their music mod repository. Unavailable or
restricted videos show the downloader's error; the workshop does not read browser cookies.

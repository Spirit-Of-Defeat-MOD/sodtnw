# Sound assets and theme banks

Theme discovery sounds added 23 October 2026:

- `field_drum.wav`: an original synthesized single drum hit; mixer channels allow overlapping beats.
- `stallonian_secret.wav`: converted from the user-supplied `1473454535858061365.ogg`.
- `skeleton_jingle.wav`: converted from the user-supplied `spooky-scary-skeleton_WnTSX24.mp3`.

The two supplied clips retain their contents, converted to mono 22,050 Hz PCM WAV for reliable bundled playback.
These channels obey Sound feedback and stop on theme changes, without stopping the radio.

`yes.wav` is a short generic "Yes!", generated locally with the installed Microsoft Zira speech voice and trimmed
to remove silence. It is bundled into all three executables by their build scripts. Like and Dislike are original
synthesised sounds: a bell ding and a brassy incorrect-answer buzzer. Dislike has no spoken phrase.

The sound engine applies the active theme's bank to all feedback, including reactions and startup/exit sounds.
Startup, exit, button, task-selection, tab and dropdown sounds use distinct melodies and instruments for each bank;
other feedback uses themed variations of the original action sound. Clips are generated and cached in memory.
Switching themes plays a separate cue in the newly selected bank, including when following a shared theme change.
The initial theme application stays silent so launch plays only its startup sound.
Theme changes take effect on the next sound, and each master's own
theme override is respected. All banks follow the same shared Sound feedback toggle.

| Themes | Bank | Character |
| --- | --- | --- |
| Classic, Midnight | Clean | Original restrained sounds |
| Revolution Realised, Field Grey, Sons of Sorel | Field | Warm, damped mechanical feedback |
| Arctic Station | Ice | Glassy and bright, with a small echo |
| BurgSys | Industrial | Lower, metallic modulation |
| Soviet Terminal | Terminal | Quantised digital sounds and robotic voice |
| Halloween | Horror | Wavering ghost tones, creaks and a synthetic scream for Dislike |
| Christmas | Festive | Sleigh-bell button jingles; spoken "Ho ho ho" for Super Want |
| Vaporwave | Vapor | Slower, soft synth modulation and longer echo |
| Rising Sun | Zen | Soft, woody feedback |
| Andorran Dream | Imperial | Regal brass melodies and metallic button taps |
| Stallonian Gambit | Cartoon | Faster, higher and bouncy |

Unknown themes use the Clean bank. The engine and bank definitions live in `sound_feedback.py`.

`ho_ho_ho.wav` is generated locally with Microsoft Zira, lowered in pitch for the Christmas reaction, and bundled
into all three executables alongside `yes.wav`. Halloween's scream is synthesised in code at a restrained volume.

`midnight_chime.wav` uses the user-supplied bell-chime-2x.mp3.
`christmas_bell.wav` is a 1.8-second excerpt of the same clip, with an ending fade.

`zhgyv.wav` is the user-supplied zhgyv-oiftt.mp3, converted to stereo PCM for the Vaporwave sunset. Closing the effect stops this clip; the shared sound setting applies.

`andorran_intro.ogg` and `andorran_anthem.ogg` are the user-requested YouTube clips, downloaded from https://www.youtube.com/watch?v=EeLipPBTOv4 (Grunt Birthday Party Sound Effect, 4 seconds) and https://www.youtube.com/watch?v=kcisPq1NXhc (El Gran Carlemany, 120 seconds). They are bundled as 22.05 kHz stereo Ogg Vorbis and queued on one effect channel in that order. Dismissing the celebration stops the channel and its queued clip; the shared sound setting and volume apply.

BurgSys horror clips: `burg_demon.ogg` (9-second excerpt of **Scary Demon Haunting**) and `burg_laugh.ogg` (6-second excerpt of **Creepy Laugh**), both by **Adam Webb**, released as **Public Domain** on SoundBible. Sources: https://soundbible.com/1883-Scary-Demon-Haunting.html and https://soundbible.com/2052-Creepy-Laugh.html. Downloaded originals, converted to 22.05 kHz stereo Ogg Vorbis with short fades. These clips queue in order on a separate effect channel and stop on dismissal.

`santa_bells.ogg` and `santa_hoho.ogg` use the online recordings documented in CHRISTMAS_CREDITS.txt. The same credits are accessible by right-clicking the Christmas scoreboard.

Field Grey marching band instrument sounds (field_bugle.wav, field_cymbals.wav,
field_tuba.wav and field_horn.wav) are original locally synthesized stereo cues.
The military drum retains its existing field_drum sound and rapid-repeat behaviour.

Rising Sun cat animation:
Meow Sound — Alexander / Orange Free Sounds (2015), Public Domain as stated by source.
Source: https://orangefreesounds.com/meow-sound/
Download: https://www.orangefreesounds.com/wp-content/uploads/2015/01/Meow-sound.mp3
Converted to stereo 22.05 kHz Ogg Vorbis; a short single meow with gentle edge fades.

Milestone celebrations: `milestone_celebration.ogg` is a user-requested 32-second excerpt (00:10–00:42, with edge fades) of Kool & the Gang — Celebration, official artist video https://www.youtube.com/watch?v=3GwjfUFyY6M . Plays on its own effect channel, follows sound enable/volume settings, and stops when the celebration is dismissed.

`milestone_laser_zap.wav` is an original locally synthesized 0.42-second sci-fi chirp and soft cartoon puff for the Technology milestone gag. It plays once at the zap and follows the shared sound settings.

Mechanics milestone: `milestone_strain_a.wav` and `milestone_strain_b.wav` are original locally synthesized nasal duck effort/grunt cues with dry ratchet clicks (0.62s each). `milestone_bolt_seated.wav` is an original 0.28s metal seating clink. Four alternating effort cues play during tightening; the clink plays once as the bolt seats. All stop on dismissal and follow the shared sound enable/volume settings.

Technology milestone adds original synthesized `milestone_technology_pickup.wav` (metallic pickup click), `_hmm.wav` (nasal questioning duck chirp), `_charge.wav` (rising sci-fi charge), `_puff.wav` (soft filtered-noise soot puff) and `_blink.wav` (very light eye squeak). The pickup/inspection/charge/zap/puff cues play once at their animation beats; the tiny squeak accompanies each closed-eye blink. All follow shared sound settings and stop on dismissal.

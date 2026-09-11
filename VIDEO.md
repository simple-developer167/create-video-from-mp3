# Photo + music video

`create_video.py` combines one or more photos and audio into an H.264/AAC MP4. Add an
SRT to burn in lyrics. Video ends with the audio. No API key or additional Python
packages are required for video export; FFmpeg is a separate required program.

## Install FFmpeg

On Windows:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Reopen your terminal and check `ffmpeg -version`. On other systems, install an
FFmpeg build from your package manager with `libx264`, AAC, and libass support.
You can specify its full executable path with `--ffmpeg`.
Multiple-photo slideshows also require `ffprobe`, included in the Windows install;
it is found next to FFmpeg or on PATH, or supplied with `--ffprobe`.

## Create a video

```powershell
python create_video.py "song.mp3" "photo.jpg"
python create_video.py "song.mp3" "photo.jpg" --srt "song.srt"
python create_video.py "song.mp3" "photo.jpg" --srt "song.srt" --format portrait --theme neon
python create_video.py "song.mp3" "photo.jpg" --srt "song.srt" --seconds 15 -o preview.mp4
python create_video.py "song.mp3" "photo.jpg" --srt "song.srt" --overwrite
```

The default output is `song.mp4`. Existing output requires `--overwrite` and is
replaced only after a successful render. The supplied SRT is never changed.
Lyrics are included only when `--srt` is passed; run `create_lyric.py` first if
you need to generate them. A plain photo/audio video does not display captions.

## Multiple photos with crossfades

```powershell
python create_video.py "song.mp3" "01.jpg" "02.png" "03.jpg" --srt "song.srt" --karaoke --fade 2 -o slideshow.mp4
python create_video.py "song.mp3" --photos-dir "C:\Pictures\MySong" --srt "song.srt" --karaoke --fade 2 -o slideshow.mp4
```

If `first.jpg` or `first.png` is present, it becomes the opening photo (case-insensitive;
`first.jpg` wins if both exist). All remaining photos keep their previous order.
Without either filename, the current order is unchanged.

Each photo is used once. Explicit paths otherwise keep the order supplied. Folder input uses filename order
(case-insensitive), so use names like `01.jpg`, `02.jpg`, `03.jpg`. It includes
JPG/JPEG, PNG, WebP, BMP, TIFF, and PPM files in that folder, not subfolders.
Duplicate paths are rejected. Different files with identical content are not detected.

The full song is divided into equal slots. For a 6-minute song and 6 photos,
each slot is 60 seconds. A 2-second crossfade is centered at each boundary:
the first transition runs from 59 to 61 seconds. Neighboring photos overlap
during the transition; the last photo holds to the end, with no repetition.
Fades longer than a slot are shortened automatically. `--fade 0` uses cuts.

Photo transitions occur underneath the lyrics. The active SRT line and karaoke
highlight remain visible and keep their timing through each transition. Captions
still disappear normally during gaps in the SRT. The photos crossfade into one
another rather than fading the whole video to black.

`--seconds` previews the beginning of the full-song schedule; it does not squeeze
all the photos into the preview. Each input photo requires decoder/filter resources,
so start with a modest number of images for long or high-resolution videos.

## Karaoke highlighting

If your SRT incorrectly includes lyrics during an instrumental intro, use
`--lyrics-start 18` (replace 18 with the actual vocal start in seconds). This hides
cues ending before or at that time and clips a crossing cue's start; later cue
timestamps remain unchanged. For a clipped karaoke cue, estimated highlighting
restarts over the remaining cue duration. It does not detect singing or shift
all lyrics. For the most accurate result, correct the SRT's timestamps directly.

```powershell
python create_video.py "song.mp3" "photo.jpg" --srt "song.srt" --karaoke -o karaoke.mp4
python create_video.py "song.mp3" "photo.jpg" --srt "song.srt" --karaoke --karaoke-style step -o karaoke-step.mp4
```

With `--karaoke`, the full caption appears gray and progressively changes to the
selected theme color. The default `sweep` fills each word smoothly; `step`
changes each word's color instantly at its estimated start. Completed words
stay highlighted. Chinese text is highlighted character by character. The
effect is burned into the MP4, so the player does not need subtitle support.

**Timing is approximate:** ordinary SRT contains line start/end times, not word
times. This mode distributes each line's duration by character count, including
across multiple lines in a cue. It does not listen to the audio, detect syllables,
or account for pauses and held notes. Precise karaoke needs word/syllable alignment
or manually timed karaoke subtitles. Scripts without spaces other than Chinese
may highlight as a whole token. This is not a rapid blinking/strobe effect.

The original MP3 audio, including vocals, is retained. To sing over an instrumental,
supply an instrumental track aligned to the same timestamps. This command does
not remove vocals or create switchable vocal tracks.

Output is H.264 video with AAC audio in MP4. Use it with a machine that supports
that combination; check your machine's resolution and codec limits. This tool
does not export CD+G, MIDI, or proprietary karaoke-machine formats.

## Appearance

Default: landscape 1920x1080 at 30 fps, a photo cropped to fill, a 25% black
overlay, and bold warm-gold lyrics near the bottom with a dark outline and shadow.
Photos are still images with optional crossfades, without animated zooms or beat-reactive effects.

| Option | Choices / meaning |
| --- | --- |
| `--format` | `landscape` (1920x1080), `portrait` (1080x1920), `square` (1080x1080) |
| `--theme` | `gold` (default), `white`, or mint `neon` |
| `--font` | Installed font family; Windows default `Microsoft YaHei`, otherwise `sans-serif` |
| `--font-file` | Load a local TTF/OTF/TTC; also set `--font` to the family name inside that font |
| `--font-size` | Font size in output pixels, 12–200; default 56 |
| `--fit` | `cover` crops the edges to fill; `contain` keeps the full photo with black bars |
| `--dim` | Black overlay opacity, 0–1; default 0.25 |
| `--seconds` | Export just the beginning for a quick preview |
| `-o`, `--output` | Output MP4 in an existing directory |
| `--overwrite` | Replace an existing video after successful rendering |

For a bold Chinese look, the Windows default Microsoft YaHei works well. For
other looks, choose an installed font family and preview the result; missing
fonts or characters may trigger renderer fallback. No font files are bundled.
Chinese and other scripts require a font containing the relevant glyphs.
Long captions wrap automatically where supported by the renderer; for exact
line breaks, edit the SRT or reduce `--font-size` before rendering.

```powershell
python create_video.py "song.mp3" "photo.jpg" --srt "song.srt" --font "Microsoft YaHei" --font-size 64 --theme white
```

Captions are permanently burned into the MP4. Only basic numbered UTF-8 SRT
cues are accepted; formatting tags for bold/italic/underline are stripped in
favor of the selected consistent style. Preview before rendering a long song.
The encoder runs on CPU, so video rendering can take time.

## Rights

Use photos, recordings, lyrics, and fonts licensed for your intended video use.
Rights to one component do not automatically cover the others. FFmpeg and font
files are installed separately and retain their own licenses. See [LEGAL.md](LEGAL.md)
and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

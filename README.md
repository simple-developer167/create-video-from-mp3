# Create Video from MP3

Create local lyric SRT files and photo-based MP4 videos, with optional karaoke
highlighting and slideshow crossfades.

> **Copyright disclaimer:** This tool is intended for material you own, have
> permission to use, or may lawfully use under an applicable exception. It is
> not intended for unauthorized copying or distribution of copyrighted music,
> lyrics, photos, or other material. You are responsible for obtaining the
> necessary rights before processing or sharing content. The software license
> does not grant rights to third-party content. See [LEGAL.md](LEGAL.md).

Also create an MP4 from a photo and MP3, with optional styled lyrics:

```text
python create_video.py song.mp3 photo.jpg --srt song.srt --theme gold
python create_video.py song.mp3 photo.jpg --srt song.srt --karaoke -o karaoke.mp4
python create_video.py song.mp3 --photos-dir photos --srt song.srt --karaoke --fade 2 -o slideshow.mp4
```

See [the video guide](VIDEO.md) for FFmpeg setup, portrait videos, and font options.
Karaoke mode progressively highlights words (Chinese characters individually)
using estimated timing within each SRT cue. It retains the original audio vocals.
**This tool does not strip or remove vocals.** Karaoke mode adds lyric highlighting
only. For a backing-track video without vocals, provide a separate instrumental
audio file that matches the SRT timing.
Multiple photos are spread evenly across the song without repeating; crossfades
affect the photos while captions remain on top.
`first.jpg` (or `first.png`) is automatically shown first when present. Use
`--lyrics-start 18` to suppress captions before 18 seconds during an instrumental intro.

Generate a UTF-8 SRT file from an MP3 using local, free transcription. No paid API or account is required. Audio stays on your computer. The first run downloads the selected model; later runs can use the cached model offline.

Supports many languages, including Chinese, using [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Accuracy varies by language and recording; this tool does not promise support for every language or perfect lyrics. It transcribes singing into subtitle segments and filters common music captions. It has no GUI, translation mode, or karaoke word highlighting.

## Setup

Install Python 3.10 or newer (Python 3.11 or 3.12 recommended). From this directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe create_lyric.py "C:\Music\song.mp3"
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python create_lyric.py /path/to/song.mp3
```

A separate FFmpeg installation is normally unnecessary because faster-whisper uses PyAV's bundled libraries. Download or clone this repository and run commands from its directory.

The default output is `C:\Music\song.srt`. Existing SRT files are preserved by default; pass `--overwrite` to replace one after successful transcription. If transcription fails or finds no lyrics, the previous file stays intact. Output directories must already exist.

## Examples

After installing dependencies, use your virtual environment's Python for these commands:

```text
python create_lyric.py song.mp3
python create_lyric.py song.mp3 --language es -o lyrics.srt
python create_lyric.py "歌曲.mp3" --language zh
python create_lyric.py song.mp3 --model large-v3 --device cuda --compute-type float16
python create_lyric.py song.mp3 --offline
python create_lyric.py song.mp3 --model-dir .models
python create_lyric.py song.mp3 --keep-music-labels
python create_lyric.py song.mp3 --overwrite
python create_lyric.py --help
```

`--language auto` is the default. Set a supported language code such as `en`, `es`, `ja`, `ko`, `zh`, or `vi` when automatic detection is wrong. Output stays in the original language; this tool does not translate. Use a multilingual model (avoid `.en` models for other languages).

The default `small` model runs on CPU with int8 precision. `tiny` and `base` are lighter options; `medium` and `large-v3` require more resources. NVIDIA GPU execution requires compatible CUDA/cuDNN libraries; see the [faster-whisper installation documentation](https://github.com/SYSTRAN/faster-whisper#requirements) for current requirements. Its documentation also covers model downloads and supported devices.

## Command options

| Option | Behavior |
| --- | --- |
| `audio` | Required path to MP3 or another format supported by the decoder |
| `-o`, `--output` | SRT path; defaults to the input filename with `.srt` |
| `--language` | Language code, or `auto` (default) |
| `--model` | Model name or local directory; default `small` |
| `--device` | `cpu` (default), `cuda`, or `auto` |
| `--compute-type` | Precision; defaults to `int8` for CPU, backend default otherwise |
| `--model-dir` | Location for downloaded models |
| `--offline` | Require a cached or local model; do not download |
| `--vad` | Enable speech filtering; may miss singing |
| `--keep-music-labels` | Disable the default music-caption filter |
| `--overwrite` | Replace an existing SRT after successful transcription |

Progress is written to stderr; the completed output path is written to stdout.
Exit codes: `0` success, `1` processing failure or no lyrics, `2` invalid CLI
arguments, `130` interrupted transcription. A legacy Windows console may print
escaped characters in paths; this does not change UTF-8 subtitle contents.

## Troubleshooting

- **Chinese text looks garbled:** select UTF-8 in your subtitle player. The tool writes UTF-8 without a BOM. Chinese output can mix Simplified and Traditional characters; it does not normalize between them.
- **Music captions or invented text:** known labels are filtered automatically. Try `--vad`, select the language explicitly, or try a larger model, then review the result.
- **Slow CPU processing:** use `--model base` or `--model tiny`, with a possible accuracy tradeoff. GPU processing needs a compatible NVIDIA setup.
- **Model unavailable offline:** run once online with the same model and cache directory, or supply a downloaded model directory with `--model`.
- **Dependency not found:** install requirements using the same Python executable you use to run the tool.
- **Permission denied when saving:** close programs locking the SRT and choose an existing output directory you can write to.

## Limitations

Singing, instruments, long instrumental sections, and mixed languages can cause missing or invented lyrics and inaccurate timing. Review the generated SRT. Language coverage and accuracy vary; no model supports every language equally. Cues follow transcription segments, not guaranteed musical lyric lines or karaoke word highlighting.

Speech filtering is disabled by default because it may remove sung passages. Try `--vad` if instrumental sections produce unwanted text. This version performs transcription only; it does not separate vocals or align supplied lyrics.

Common standalone music descriptions such as `Zither Harp`, `[Music]`, `[instrumental]`, and `前奏` are removed automatically. Known bracketed labels within a lyric cue are also removed; remaining cues retain their timings and are renumbered. This is a limited text filter, not an audio classifier: unfamiliar descriptions can remain, and an actual lyric consisting solely of a listed label can be removed. Use `--keep-music-labels` to disable the filter. Lyric sentences containing words such as "music" and parenthetical vocals such as `(oh oh)` are preserved. Model prompts are not reliable instructions for suppressing all non-lyric captions.

## Tests

```text
python -m unittest discover -s tests -v
```

Tests use synthetic segments and a fake transcription backend, so they require no model downloads.

GitHub Actions is configured to run these tests on Windows and Linux with Python
3.10 and 3.12. Local validation has been performed on Windows with Python 3.12;
the CI matrix is not a claim of completed tests on every platform.

## License and contributions

The project uses the [MIT license](LICENSE). Dependencies and models retain their
own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Use audio and
lyrics only when you have the relevant rights or an applicable legal exception.
The software license does not grant rights to songs or generated lyric files.
See [licensing and responsible use](LEGAL.md) and [contributing](CONTRIBUTING.md).

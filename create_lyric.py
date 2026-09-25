"""Generate original-language SRT subtitles from local audio."""

import argparse
import math
import os
import re
from pathlib import Path
import sys
import tempfile


# Match labels, never arbitrary substrings inside sung sentences.
MUSIC_LABELS = {
    "zither harp", "music", "instrumental", "instrumental music",
    "instrumental intro", "instrumental interlude", "instrumental outro",
    "background music", "music playing", "applause",
    "音乐", "音樂", "纯音乐", "純音樂", "伴奏", "间奏", "間奏",
    "前奏", "尾奏", "掌声", "掌聲",
}
BRACKETED_LABEL = re.compile(r"\[[^\[\]]*\]|\([^()]*\)|（[^（）]*）|【[^【】]*】")


def is_music_label(text):
    normalized = " ".join(text.casefold().split()).strip(" .,!?:;。！？，：；♪♫🎵🎶")
    return normalized in MUSIC_LABELS


def lyrics_only(text):
    text = BRACKETED_LABEL.sub(
        lambda match: " " if is_music_label(match.group()[1:-1]) else match.group(), text)
    text = " ".join(text.split())
    if is_music_label(text) or not text.strip(" ♪♫🎵🎶"):
        return ""
    return text


def timestamp(milliseconds):
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render_srt(segments, keep_music_labels=False, lyrics_start=0):
    """Preserve model segments; normalize timestamps and remove empty cues."""
    cues = []
    previous_end = round(lyrics_start * 1000)
    for segment in segments:
        text = " ".join(segment.text.split())
        if not keep_music_labels:
            text = lyrics_only(text)
        if not text:
            continue
        if not all(math.isfinite(t) for t in (segment.start, segment.end)):
            raise ValueError("Transcription returned invalid timestamps")
        if segment.end <= lyrics_start:
            continue
        start = max(previous_end, round(segment.start * 1000), 0)
        end = max(start + 1, round(segment.end * 1000))
        cues.append(f"{len(cues) + 1}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n\n")
        previous_end = end
    return "".join(cues)


def save_srt(output, content, overwrite=False):
    """Publish a complete file, preserving existing files unless requested."""
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=output.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(content)
        except BaseException:
            temporary.close()
            temporary_path.unlink(missing_ok=True)
            raise
    try:
        if overwrite:
            os.replace(temporary_path, output)
        else:
            # A hard link publishes atomically and fails if output already exists.
            os.link(temporary_path, output)
    finally:
        temporary_path.unlink(missing_ok=True)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("audio", type=Path, help="MP3 or another supported audio file")
    result.add_argument("-o", "--output", type=Path, help="Output path (default: audio filename with .srt)")
    result.add_argument("--language", default="auto", help="Language code, e.g. en, es, ja; default: auto")
    result.add_argument("--lyrics-start", type=float, default=0,
                        help="Skip instrumental intro before this time in seconds; preserve original timestamps")
    result.add_argument("--model", default="small", help="Model name or local model directory (default: small)")
    result.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    result.add_argument("--compute-type", default="default", help="CTranslate2 precision; default: int8 on CPU, auto elsewhere")
    result.add_argument("--model-dir", type=Path, help="Directory for downloaded models")
    result.add_argument("--offline", action="store_true", help="Use cached/local models without downloading")
    result.add_argument("--vad", action="store_true", help="Enable speech filtering (can miss singing)")
    result.add_argument("--keep-music-labels", action="store_true",
                        help="Keep music descriptions normally removed from lyrics")
    result.add_argument("--overwrite", action="store_true",
                        help="Replace an existing SRT after successful transcription")
    return result


def main(argv=None):
    # Redirected Windows consoles may use a legacy encoding without Chinese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    arguments = parser()
    args = arguments.parse_args(argv)
    if not math.isfinite(args.lyrics_start) or args.lyrics_start < 0:
        arguments.error("--lyrics-start must be a finite nonnegative number")
    if args.lyrics_start > 0 and args.vad:
        arguments.error("Use --lyrics-start or --vad, not both: the transcription backend ignores VAD when clipping")
    audio = args.audio.resolve()
    output = (args.output or audio.with_suffix(".srt")).resolve()
    if not audio.is_file():
        arguments.error(f"Audio file does not exist: {audio}")
    if output == audio or (output.exists() and os.path.samefile(audio, output)):
        arguments.error("Output must not be the input audio file")
    if output.suffix.lower() != ".srt":
        arguments.error("Output filename must end in .srt")
    if output.exists() and not args.overwrite:
        arguments.error(f"Output already exists: {output}; use --overwrite to replace it")
    if not output.parent.is_dir():
        arguments.error(f"Output directory does not exist: {output.parent}")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("Install dependencies first: python -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    language = args.language.lower()
    compute_type = args.compute_type
    if compute_type == "default":
        compute_type = "int8" if args.device == "cpu" else "default"
    try:
        print(f"Loading model {args.model} on {args.device}...", file=sys.stderr)
        model = WhisperModel(args.model, device=args.device, compute_type=compute_type,
                             download_root=str(args.model_dir) if args.model_dir else None,
                             local_files_only=args.offline)
        segments, info = model.transcribe(str(audio), language=None if language == "auto" else language,
                                          task="transcribe", beam_size=5, vad_filter=args.vad,
                                          clip_timestamps=str(args.lyrics_start) if args.lyrics_start else "0",
                                          condition_on_previous_text=False)
        print(f"Language: {info.language}. Transcribing...", file=sys.stderr)
        def progress():
            for segment in segments:
                print(f"Processed through {segment.end:.1f}s", file=sys.stderr)
                yield segment
        content = render_srt(progress(), keep_music_labels=args.keep_music_labels, lyrics_start=args.lyrics_start)
        if not content:
            print("No lyrics detected; no output written.", file=sys.stderr)
            return 1
        save_srt(output, content, args.overwrite)
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

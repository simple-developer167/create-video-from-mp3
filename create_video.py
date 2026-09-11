"""Create an MP4 from photos, audio, and optional UTF-8 SRT lyrics."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


SIZES = {"landscape": (1920, 1080), "portrait": (1080, 1920), "square": (1080, 1080)}
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.ppm'}


def collect_photos(photos, directory=None):
    if directory is not None:
        if photos:
            raise ValueError('Use photo paths or --photos-dir, not both')
        if not directory.is_dir():
            raise ValueError(f'Photo directory does not exist: {directory}')
        photos = sorted((path for path in directory.iterdir()
                         if path.is_file() and path.suffix.lower() in PHOTO_EXTENSIONS),
                        key=lambda path: (path.name.casefold(), path.name))
    if not photos:
        raise ValueError('Provide at least one photo or a --photos-dir containing images')
    resolved = [path.resolve() for path in photos]
    if len(set(resolved)) != len(resolved):
        raise ValueError('Duplicate photo paths supplied; each photo should appear once')
    # Promote one designated opening image; preserve every other photo's order.
    first = next((path for name in ('first.jpg', 'first.png') for path in photos
                  if path.name.casefold() == name), None)
    if first is not None:
        photos = [first] + [path for path in photos if path != first]
    return photos


def slideshow_timing(duration, count, fade):
    """Center transitions on equal-sized slots without shortening the song."""
    if not math.isfinite(duration) or duration <= 0 or count < 1:
        raise ValueError('Slideshow requires a positive audio duration and photo count')
    if not math.isfinite(fade) or fade < 0:
        raise ValueError('Fade duration must be finite and nonnegative')
    slot = duration / count
    fade = min(fade, slot) if count > 1 else 0
    lengths = [slot + (fade / 2 if index > 0 else 0)
               + (fade / 2 if index < count - 1 else 0) for index in range(count)]
    offsets = [index * slot - fade / 2 for index in range(1, count)]
    return lengths, offsets, fade


def audio_duration(audio, ffmpeg, ffprobe=None):
    if ffprobe:
        executable = shutil.which(ffprobe)
    else:
        sibling = Path(ffmpeg).with_name('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
        executable = str(sibling) if sibling.is_file() else shutil.which('ffprobe')
    if not executable:
        raise ValueError('Multiple photos require ffprobe alongside FFmpeg, on PATH, or passed with --ffprobe')
    result = subprocess.run([executable, '-v', 'error', '-select_streams', 'a:0',
                             '-show_entries', 'stream=duration:format=duration', '-of', 'json', str(audio.resolve())],
                            check=True, capture_output=True, text=True)
    metadata = json.loads(result.stdout)
    if not metadata.get('streams'):
        raise ValueError('Input has no audio stream')
    value = metadata['streams'][0].get('duration')
    if value in (None, 'N/A'):
        value = metadata.get('format', {}).get('duration')
    duration = float(value)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Cannot determine a positive audio duration')
    return duration


def slideshow_graph(count, width, height, fit, dim, offsets, fade, subtitles=False, custom_font=False):
    if fit == 'cover':
        scale = f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}'
    else:
        scale = f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2'
    graph = [f'[{index}:v:0]{scale},setsar=1,fps=30,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[p{index}]'
             for index in range(count)]
    current = 'p0'
    if count > 1 and fade == 0:
        graph.append(''.join(f'[p{index}]' for index in range(count)) + f'concat=n={count}:v=1:a=0[slides]')
        current = 'slides'
    else:
        for index, offset in enumerate(offsets, 1):
            graph.append(f'[{current}][p{index}]xfade=transition=fade:duration={fade:.6f}:offset={offset:.6f}[mix{index}]')
            current = f'mix{index}'
    # Apply the caption layer only once, after every photo transition.
    overlay = f'[{current}]drawbox=color=black@{dim}:t=fill'
    if subtitles:
        overlay += ',ass=filename=lyrics.ass' + (':fontsdir=fonts' if custom_font else '')
    graph.append(overlay + ',format=yuv420p[video]')
    return ';\n'.join(graph)


def ass_time(value):
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2}),(\d{3})", value)
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    h, m, s, ms = map(int, match.groups())
    if m >= 60 or s >= 60:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def format_ass_time(ms):
    total = ms // 10
    seconds, cs = divmod(total, 100)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{seconds:02}.{cs:02}"


def karaoke_text(text, duration_cs, style='sweep'):
    """Estimate timing by text length; SRT supplies no per-word alignment."""
    cjk = '\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f'
    pieces = re.findall(r'\\N|[' + cjk + r']|\s+|[^\s\\' + cjk + r']+', text)
    units = []
    prefix = ''
    for piece in pieces:
        if piece != r'\N' and any(char.isalnum() for char in piece):
            units.append([prefix + piece, sum(char.isalnum() for char in piece)])
            prefix = ''
        elif units:
            units[-1][0] += piece
        else:
            prefix += piece
    if not units:
        return text
    total_weight = sum(weight for _, weight in units)
    elapsed_weight = previous = 0
    output = []
    tag = 'kf' if style == 'sweep' else 'k'
    for piece, weight in units:
        elapsed_weight += weight
        boundary = round(duration_cs * elapsed_weight / total_weight)
        output.append(f'{{\\{tag}{boundary - previous}}}{piece}')
        previous = boundary
    return ''.join(output)


def make_ass(srt, width, height, font, font_size, theme, karaoke=False, karaoke_style='sweep', lyrics_start=0):
    """Create fixed-resolution subtitle styles without executing SRT markup."""
    if not re.fullmatch(r"[\w .-]+", font):
        raise ValueError("Font family may contain letters, numbers, spaces, dots, underscores, and hyphens")
    colors = {"gold": "&H0086DFFF", "white": "&H00FFFFFF", "neon": "&H00E8FF9B"}
    margin = round(height * 0.12)
    header = (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Lyrics,{font},{font_size},{colors[theme]},&H00A0A0A0,&H00101018,&H80000000,"
        f"-1,0,0,0,100,100,1,0,1,3,2,2,{round(width * .08)},{round(width * .08)},{margin},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for block in re.split(r"\n\s*\n", srt.lstrip('\ufeff').replace('\r\n', '\n').strip()):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].isdigit():
            raise ValueError("Expected numbered SRT cues with timestamps and lyric text")
        times = lines[1].split(' --> ')
        if len(times) != 2:
            raise ValueError("Invalid SRT time range")
        start, end = map(ass_time, times)
        if end <= start:
            raise ValueError("SRT cue end must be after its start")
        threshold = round(lyrics_start * 1000)
        if end <= threshold:
            continue
        start = max(start, threshold)
        # Preserve line breaks; neutralize ASS commands in user-supplied lyrics.
        text = r'\N'.join(re.sub(r'</?(?:i|b|u)>', '', line, flags=re.I)
                          .replace('\\', '＼').replace('{', '｛').replace('}', '｝') for line in lines[2:])
        if karaoke:
            text = karaoke_text(text, max(1, end // 10 - start // 10), karaoke_style)
        events.append(f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(max(start // 10 * 10 + 10, end))},Lyrics,,0,0,0,,{text}\n")
    return header + ''.join(events)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio', type=Path)
    p.add_argument('photos', type=Path, nargs='*', help='One or more photos in playback order')
    p.add_argument('--photos-dir', type=Path, help='Use images from a folder in filename order (not recursive)')
    p.add_argument('--fade', type=float, default=1.0, help='Crossfade duration in seconds; 0 for cuts (default: 1)')
    p.add_argument('-o', '--output', type=Path, help='Output MP4; default: audio filename with .mp4')
    p.add_argument('--srt', type=Path, help='Optional SRT to burn into the video')
    p.add_argument('--lyrics-start', type=float, default=0,
                   help='Hide lyrics before this time in seconds; later cues keep their timestamps')
    p.add_argument('--karaoke', action='store_true', help='Highlight lyrics progressively using estimated word timing; requires --srt')
    p.add_argument('--karaoke-style', choices=('sweep', 'step'), default='sweep',
                   help='Smooth color sweep (default) or instant word-by-word color changes')
    p.add_argument('--format', choices=SIZES, default='landscape')
    p.add_argument('--theme', choices=('gold', 'white', 'neon'), default='gold')
    p.add_argument('--font', default='Microsoft YaHei' if os.name == 'nt' else 'sans-serif', help='Installed font family')
    p.add_argument('--font-file', type=Path, help='Optional TTF/OTF/TTC font to load; also set --font to its family name')
    p.add_argument('--font-size', type=int, default=56, help='Caption size in output pixels (default: 56)')
    p.add_argument('--fit', choices=('cover', 'contain'), default='cover', help='Crop to fill (default) or preserve entire photo with black bars')
    p.add_argument('--dim', type=float, default=0.25, help='Black overlay opacity from 0 to 1 (default: 0.25)')
    p.add_argument('--seconds', type=float, help='Limit duration for a quick preview')
    p.add_argument('--ffmpeg', default='ffmpeg', help='FFmpeg executable name or path')
    p.add_argument('--ffprobe', help='Optional ffprobe executable path for slideshow duration detection')
    p.add_argument('--overwrite', action='store_true')
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='backslashreplace')
    p = parser()
    args = p.parse_args(argv)
    if args.karaoke and not args.srt:
        p.error('--karaoke requires --srt')
    try:
        photos = collect_photos(args.photos, args.photos_dir)
    except ValueError as error:
        p.error(str(error))
    inputs = [args.audio, *photos] + [path for path in (args.srt, args.font_file) if path]
    for path in inputs:
        if not path.is_file():
            p.error(f"Input file does not exist: {path}")
    output = (args.output or args.audio.with_suffix('.mp4')).resolve()
    if output.suffix.lower() != '.mp4' or not output.parent.is_dir():
        p.error('Output must be an .mp4 file in an existing directory')
    if any(output == path.resolve() or (output.exists() and os.path.samefile(output, path)) for path in inputs):
        p.error('Output must not replace an input file')
    if output.exists() and not args.overwrite:
        p.error('Output already exists; pass --overwrite to replace it')
    if not 0 <= args.dim <= 1 or not 12 <= args.font_size <= 200:
        p.error('--dim must be between 0 and 1; --font-size must be between 12 and 200')
    if args.seconds is not None and not 0 < args.seconds < float('inf'):
        p.error('--seconds must be a finite positive number')
    if not math.isfinite(args.fade) or args.fade < 0:
        p.error('--fade must be a finite nonnegative number')
    if not math.isfinite(args.lyrics_start) or args.lyrics_start < 0:
        p.error('--lyrics-start must be a finite nonnegative number')
    executable = shutil.which(args.ffmpeg)
    if not executable:
        p.error('FFmpeg is missing. Install it (Windows: winget install --id Gyan.FFmpeg --exact), then reopen your terminal or pass --ffmpeg PATH')
    width, height = SIZES[args.format]
    try:
        duration = audio_duration(args.audio, executable, args.ffprobe) if len(photos) > 1 else None
        lengths, offsets, fade = slideshow_timing(duration, len(photos), args.fade) if duration else ([None], [], 0)
        if duration:
            print(f'{len(photos)} photos, {duration / len(photos):.2f}s per slot, {fade:.2f}s crossfades; no repeats.', file=sys.stderr)
        # Fixed relative asset names avoid Windows drive/quote escaping in filters.
        with tempfile.TemporaryDirectory(prefix='lyric-video-', dir=output.parent) as directory:
            work = Path(directory)
            if args.srt:
                (work / 'lyrics.ass').write_text(make_ass(args.srt.read_text(encoding='utf-8-sig'), width, height,
                                                        args.font, args.font_size, args.theme,
                                                        args.karaoke, args.karaoke_style, args.lyrics_start), encoding='utf-8')
                if args.karaoke:
                    print('Karaoke timing is estimated from SRT line durations; audio vocals are unchanged.', file=sys.stderr)
                if args.font_file:
                    (work / 'fonts').mkdir()
                    shutil.copyfile(args.font_file, work / 'fonts' / ('custom' + args.font_file.suffix))
            graph = slideshow_graph(len(photos), width, height, args.fit, args.dim,
                                    offsets, fade, bool(args.srt), bool(args.font_file))
            command = [str(Path(executable).resolve()), '-hide_banner', '-nostdin', '-y']
            for photo, length in zip(photos, lengths):
                command += ['-loop', '1', '-framerate', '30']
                if length is not None:
                    command += ['-t', f'{length:.6f}']
                command += ['-i', str(photo.resolve())]
            command += ['-i', str(args.audio.resolve()), '-filter_complex_threads', '1',
                       '-filter_complex', graph, '-map', '[video]', '-map', f'{len(photos)}:a:0',
                       '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'stillimage',
                       '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                       '-shortest', '-movflags', '+faststart']
            limit = min(args.seconds, duration) if args.seconds and duration else args.seconds or duration
            if limit:
                command += ['-t', str(limit)]
            command += ['render.mp4']
            print(f'Rendering {width}x{height} MP4...', file=sys.stderr)
            subprocess.run(command, cwd=work, check=True, stdout=sys.stderr)
            if args.overwrite:
                os.replace(work / 'render.mp4', output)
            else:
                os.link(work / 'render.mp4', output)
    except KeyboardInterrupt:
        print('Cancelled; existing output preserved.', file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        print(f'Video export failed: {error}', file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())

import contextlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import create_lyric


def segment(start, end, text):
    return SimpleNamespace(start=start, end=end, text=text)


class SrtTests(unittest.TestCase):
    def test_intro_cutoff_preserves_absolute_timestamps(self):
        result = create_lyric.render_srt([
            segment(0, 18, 'intro hallucination'),
            segment(17, 25, 'first lyric'),
            segment(30, 35, 'later lyric'),
        ], lyrics_start=18)
        self.assertNotIn('intro hallucination', result)
        self.assertIn('1\n00:00:18,000 --> 00:00:25,000', result)
        self.assertIn('2\n00:00:30,000 --> 00:00:35,000', result)

    def test_invalid_intro_cutoff_and_vad_conflict(self):
        for options in (['--lyrics-start', '-1'], ['--lyrics-start', 'nan'],
                        ['--lyrics-start', 'inf'], ['--lyrics-start', '18', '--vad']):
            with self.subTest(options=options), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                create_lyric.main(['missing.mp3', *options])

    def test_music_labels_removed_and_remaining_cues_renumbered(self):
        result = create_lyric.render_srt([
            segment(0, 23, "Zither Harp"),
            segment(23, 27, "[Music] Hello"),
            segment(27, 30, "[instrumental]"),
            segment(30, 33, "音乐"),
            segment(33, 36, "♪♫"),
            segment(36, 40, "Sing with me"),
        ])
        self.assertEqual(result, "1\n00:00:23,000 --> 00:00:27,000\nHello\n\n"
                         "2\n00:00:36,000 --> 00:00:40,000\nSing with me\n\n")

    def test_lyric_sentences_and_parenthetical_vocals_preserved(self):
        for text in ("I love music", "Play the zither harp", "(oh oh)", "我的音乐", "[stay with me]"):
            with self.subTest(text=text):
                self.assertEqual(create_lyric.lyrics_only(text), text)

    def test_music_filter_can_be_disabled(self):
        self.assertIn("Zither Harp", create_lyric.render_srt(
            [segment(0, 23, "Zither Harp")], keep_music_labels=True))

    def test_unicode_empty_cues_and_time_carry(self):
        result = create_lyric.render_srt([
            segment(0, 1, "  "),
            segment(59.9996, 62, "こんにちは\n世界"),
        ])
        self.assertEqual(result, "1\n00:01:00,000 --> 00:01:02,000\nこんにちは 世界\n\n")

    def test_overlapping_and_zero_duration_cues(self):
        result = create_lyric.render_srt([
            segment(-1, 1, "one"), segment(0.5, 1, "two")])
        self.assertIn("00:00:00,000 --> 00:00:01,000", result)
        self.assertIn("00:00:01,000 --> 00:00:01,001", result)

    def test_invalid_time(self):
        with self.assertRaises(ValueError):
            create_lyric.render_srt([segment(float("nan"), 1, "text")])

    def test_preserves_existing_file_and_can_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "song.srt"
            output.write_text("original", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                create_lyric.save_srt(output, "replacement")
            self.assertEqual(output.read_text(), "original")
            create_lyric.save_srt(output, "replacement", overwrite=True)
            self.assertEqual(output.read_text(), "replacement")
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_command_writes_original_language_srt(self):
        calls = {}

        class FakeModel:
            def __init__(self, name, **kwargs):
                calls["model"] = kwargs

            def transcribe(self, audio, **kwargs):
                calls["transcribe"] = kwargs
                return iter([segment(18, 23, "Hola mundo")]), SimpleNamespace(language="es")

        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "song.mp3"
            audio.touch()
            audio.with_suffix(".srt").write_text("previous lyrics", encoding="utf-8")
            with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=FakeModel)}):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    status = create_lyric.main([str(audio), "--language", "es", "--offline", "--overwrite", "--lyrics-start", "18"])
            self.assertEqual(status, 0)
            self.assertIn("Hola mundo", audio.with_suffix(".srt").read_text(encoding="utf-8"))
            self.assertEqual(calls["transcribe"]["task"], "transcribe")
            self.assertEqual(calls["transcribe"]["language"], "es")
            self.assertEqual(calls["transcribe"]["clip_timestamps"], "18.0")
            self.assertTrue(calls["model"]["local_files_only"])

    def test_failed_or_empty_transcription_preserves_existing_srt(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                audio = Path(directory) / "song.mp3"
                audio.touch()
                output = audio.with_suffix(".srt")
                output.write_text("previous lyrics", encoding="utf-8")

                class FakeModel:
                    def __init__(self, *args, **kwargs):
                        pass

                    def transcribe(self, *args, **kwargs):
                        def segments():
                            if fail:
                                yield segment(1, 3, "partial result")
                                raise RuntimeError("Transcription failed")
                        return segments(), SimpleNamespace(language="en")

                with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=FakeModel)}):
                    with contextlib.redirect_stderr(io.StringIO()):
                        status = create_lyric.main([str(audio), "--overwrite"])
                self.assertEqual(status, 1)
                self.assertEqual(output.read_text(encoding="utf-8"), "previous lyrics")

    def test_existing_srt_requires_overwrite_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "song.mp3"
            audio.touch()
            output = audio.with_suffix(".srt")
            output.write_text("original", encoding="utf-8")
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
                create_lyric.main([str(audio)])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("--overwrite", errors.getvalue())
            self.assertEqual(output.read_text(encoding="utf-8"), "original")

    def test_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "song.srt"
            audio.write_text("original")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                create_lyric.main([str(audio), "--overwrite"])
            self.assertEqual(audio.read_text(), "original")


if __name__ == "__main__":
    unittest.main()

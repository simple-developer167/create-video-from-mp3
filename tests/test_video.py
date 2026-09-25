import contextlib
import io
from pathlib import Path
import tempfile
import re
import unittest
from unittest.mock import patch

import create_video


class VideoTests(unittest.TestCase):
    def test_first_photo_priority_and_remaining_order(self):
        images = [Path('z.jpg'), Path('first.PNG'), Path('a.jpg')]
        self.assertEqual(create_video.collect_photos(images), [images[1], images[0], images[2]])
        both = images + [Path('FIRST.JPG')]
        self.assertEqual(create_video.collect_photos(both), [both[3], *images])
        self.assertEqual(create_video.collect_photos([images[0], images[2]]), [images[0], images[2]])

    def test_lyrics_start_removes_intro_without_shifting_later_cues(self):
        source = ('1\n00:00:00,000 --> 00:00:18,000\nIntro duplicate\n\n'
                  '2\n00:00:18,000 --> 00:00:25,000\nReal lyric\n')
        result = create_video.make_ass(source, 1920, 1080, 'Arial', 56, 'gold', lyrics_start=18)
        self.assertNotIn('Intro duplicate', result)
        self.assertIn('0:00:18.00,0:00:25.00', result)
        self.assertIn('Real lyric', result)

    def test_lyrics_start_clips_crossing_cue_and_karaoke_duration(self):
        source = '1\n00:00:16,000 --> 00:00:20,000\nHello world\n'
        result = create_video.make_ass(source, 1920, 1080, 'Arial', 56, 'gold', karaoke=True, lyrics_start=18)
        self.assertIn('0:00:18.00,0:00:20.00', result)
        self.assertEqual(sum(map(int, re.findall(r'\{\\kf(\d+)\}', result))), 200)

    def test_long_lines_wrap_at_phrases_with_language_spacing(self):
        english = "Beside the empty chair, I close my eyes, you're everywhere"
        self.assertEqual(create_video.wrap_line(english, 1612, 68, 1),
                         ['Beside the empty chair,', "I close my eyes, you're everywhere"])
        self.assertEqual(create_video.wrap_line('西安一轮明月 落在千年盛唐', 907, 68, 10),
                         ['西安一轮明月', '落在千年盛唐'])
        self.assertEqual(create_video.wrap_line('短句', 907, 68, 10), ['短句'])
        self.assertGreater(create_video.letter_spacing('你好', 68), create_video.letter_spacing('hello', 68))
        source = '1\n00:00:01,000 --> 00:00:04,000\n西安一轮明月 落在千年盛唐\n'
        result = create_video.make_ass(source, 1080, 1920, 'Arial', 68, 'gold', karaoke=True)
        self.assertIn(r'\fsp10}', result)
        self.assertEqual(result.count(r'\h\N'), 1)
        self.assertEqual(sum(map(int, re.findall(r'\{\\kf(\d+)\}', result))), 300)

    def test_cue_stretched_over_intro_starts_near_vocals(self):
        source = ('1\n00:00:00,000 --> 00:00:20,000\n北京一场晨光\n\n'
                  '2\n00:00:20,000 --> 00:00:23,000\n照亮万里城墙\n\n'
                  '3\n00:00:23,000 --> 00:00:26,000\n西安一轮明月\n')
        result = create_video.make_ass(source, 1920, 1080, 'Arial', 56, 'gold')
        self.assertIn('0:00:15.75,0:00:20.00', result)
        self.assertIn('0:00:20.00,0:00:23.00', result)
        kept = create_video.make_ass(source, 1920, 1080, 'Arial', 56, 'gold', trim_intros=False)
        self.assertIn('0:00:00.00,0:00:20.00', kept)

    def test_slideshow_durations_and_centered_transitions(self):
        lengths, offsets, fade = create_video.slideshow_timing(60, 3, 2)
        self.assertEqual(lengths, [21, 22, 21])
        self.assertEqual(offsets, [19, 39])
        self.assertEqual(sum(lengths) - 2 * fade, 60)
        self.assertEqual(create_video.slideshow_timing(60, 3, 0), ([20, 20, 20], [20, 40], 0))
        self.assertEqual(create_video.slideshow_timing(60, 1, 2), ([60], [], 0))

    def test_slideshow_clamps_long_fades_and_rejects_invalid_values(self):
        lengths, _, fade = create_video.slideshow_timing(3, 3, 10)
        self.assertEqual(fade, 1)
        self.assertEqual(sum(lengths) - 2 * fade, 3)
        for duration, count, fade in [(0, 3, 1), (10, 0, 1), (10, 3, -1), (float('nan'), 2, 1)]:
            with self.subTest(duration=duration, count=count, fade=fade), self.assertRaises(ValueError):
                create_video.slideshow_timing(duration, count, fade)

    def test_folder_photo_order_and_no_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('03.png', '01.JPG', '02.webp', 'notes.txt'):
                (root / name).touch()
            self.assertEqual([p.name for p in create_video.collect_photos([], root)], ['01.JPG', '02.webp', '03.png'])
            with self.assertRaises(ValueError):
                create_video.collect_photos([root / '03.png'], root)
            with self.assertRaises(ValueError):
                create_video.collect_photos([root / '03.png', root / '03.png'])

    def test_caption_layer_follows_all_transitions(self):
        graph = create_video.slideshow_graph(3, 1920, 1080, 'cover', 0.2, [19, 39], 2, True)
        self.assertEqual(graph.count('ass=filename'), 1)
        self.assertGreater(graph.index('ass=filename'), graph.rindex('xfade='))
        self.assertIn('[mix2]drawbox=', graph)

    def test_karaoke_chinese_characters_and_total_duration(self):
        result = create_video.karaoke_text('你好世界', 401)
        self.assertEqual(len(re.findall(r'\{\\kf\d+\}', result)), 4)
        self.assertEqual(sum(map(int, re.findall(r'\{\\kf(\d+)\}', result))), 401)
        self.assertEqual(re.sub(r'\{\\kf\d+\}', '', result), '你好世界')

    def test_karaoke_preserves_spaces_punctuation_and_line_breaks(self):
        text = 'Hello, world!\\N你好。'
        result = create_video.karaoke_text(text, 600, 'step')
        self.assertEqual(re.sub(r'\{\\k\d+\}', '', result), text)
        self.assertEqual(sum(map(int, re.findall(r'\{\\k(\d+)\}', result))), 600)
        self.assertEqual(len(re.findall(r'\{\\k\d+\}', result)), 4)

    def test_karaoke_is_opt_in_and_requires_subtitles(self):
        srt = '1\n00:00:01,000 --> 00:00:03,000\nHello world'
        self.assertNotIn('{\\kf', create_video.make_ass(srt, 1920, 1080, 'Arial', 56, 'gold'))
        self.assertIn('{\\kf', create_video.make_ass(srt, 1920, 1080, 'Arial', 56, 'gold', karaoke=True))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            create_video.main(['missing.mp3', 'missing.png', '--karaoke'])
        self.assertEqual(error.exception.code, 2)

    def test_chinese_and_markup_handling(self):
        source = '1\n00:00:01,000 --> 00:00:03,500\n你好世界\n{\\pos(1,2)}<b>Hello</b>\n'
        result = create_video.make_ass(source, 1080, 1920, 'Microsoft YaHei', 56, 'gold')
        self.assertIn('PlayResY: 1920', result)
        self.assertIn('0:00:01.00,0:00:03.50', result)
        self.assertIn('你好世界\\N', result)
        self.assertNotIn('{\\pos', result)
        self.assertNotIn('<b>', result)

    def test_invalid_subtitles_and_font_rejected(self):
        for source, font in [('bad text', 'Arial'), ('1\n00:00:04,000 --> 00:00:03,000\nHi', 'Arial'),
                             ('1\n00:00:01,000 --> 00:00:03,000\nHi', 'Arial,extra')]:
            with self.subTest(source=source, font=font), self.assertRaises(ValueError):
                create_video.make_ass(source, 1920, 1080, font, 56, 'gold')

    def test_existing_video_requires_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            audio, photo, output = [Path(directory) / name for name in ('song.mp3', 'photo.png', 'song.mp4')]
            for path in (audio, photo, output):
                path.write_bytes(b'original')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                create_video.main([str(audio), str(photo)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_bytes(), b'original')

    def test_failed_encoder_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            audio, photo, output = [Path(directory) / name for name in ('song.mp3', 'photo.png', 'song.mp4')]
            for path in (audio, photo, output):
                path.write_bytes(b'original')
            with patch('create_video.shutil.which', return_value='ffmpeg'), patch('create_video.subprocess.run', side_effect=OSError('encoder failed')):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(create_video.main([str(audio), str(photo), '--overwrite']), 1)
            self.assertEqual(output.read_bytes(), b'original')
            self.assertEqual(len(list(Path(directory).iterdir())), 3)


if __name__ == '__main__':
    unittest.main()

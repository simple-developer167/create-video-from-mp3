# Contributing

Keep this project a small command-line tool. For a substantial feature, open an
issue explaining the user-facing behavior before preparing a pull request.

## Development

Use Python 3.10 or newer. Follow the virtual environment setup in [README.md](README.md).
The unit tests themselves use only the standard library and a fake transcription
backend, so they run without faster-whisper or model downloads:

```text
python -m unittest discover -s tests -v
python create_lyric.py --help
```

For changes to transcription behavior, also run a real audio check using a
recording you have permission to use. State the model, language, device, and
result in the pull request. Unit tests do not establish transcription accuracy.

Preserve UTF-8 output, input-file protection, and the rule that unsuccessful
transcription leaves an existing SRT intact. Music-label filtering should avoid
removing matching words from longer lyric sentences. Document any new CLI flags
and add meaningful regression tests for behavior changes.

## Issues and pull requests

Include your operating system, Python and faster-whisper versions, command,
expected result, and actual result. Remove credentials and personal file paths.
Use short original or appropriately licensed test material; do not upload full
copyrighted songs or lyrics as examples without permission.

Contributions are submitted under the repository's [MIT license](LICENSE).
Only contribute material you have the right to submit under those terms.

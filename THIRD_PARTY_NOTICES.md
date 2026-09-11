# Third-party software and models

This source repository depends on third-party software installed separately.
The project's MIT license does not replace the licenses of those components.

| Component | Role | License reference |
| --- | --- | --- |
| faster-whisper | Direct Python dependency for transcription | [MIT, copyright SYSTRAN](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| OpenAI Whisper | Original models underlying the standard model choices | [Code and model weights: MIT](https://github.com/openai/whisper#license) |
| FFmpeg (separate executable) | Optional photo/audio MP4 rendering and libass subtitle rendering | [Build-dependent LGPL/GPL terms](https://ffmpeg.org/legal.html) |

Acknowledgments do not imply endorsement or affiliation with the upstream authors.

faster-whisper also installs transitive dependencies such as CTranslate2, PyAV,
ONNX Runtime, tokenizers, and Hugging Face Hub. This document is not a complete
bill of materials or a license audit of every transitive dependency. Consult
the installed distributions' license files and upstream repositories when
redistributing any of them. In particular, audio decoding involves FFmpeg
libraries, whose obligations depend on the actual build and included components;
see [FFmpeg's legal information](https://ffmpeg.org/legal.html).

Model names may resolve to converted model repositories. Check the actual model
card and license for the model you download, especially when using a custom
model directory. The standard upstream Whisper MIT statement is not a blanket
license for every third-party model.

Only this project's source, tests, and documentation are intended for this Git
repository. No dependency distributions, model weights, or song files are bundled.

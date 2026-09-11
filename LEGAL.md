# Licensing and responsible use

Reviewed September 10, 2026. This is a practical licensing review of the source
repository and general U.S. copyright information, not a legal opinion or a
guarantee for every jurisdiction or use case.

## Sharing this repository

The project's source and documentation are offered under the [MIT license](LICENSE).
Keep that license with redistributed copies. This repository installs external
dependencies rather than bundling their source, binaries, or model weights.
The core upstream licenses permit redistribution subject to their terms; this
review found no licensing barrier to publishing this source repository as prepared.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for upstream references and the
limits of this review. This project's license grants only rights its contributors
can grant; it does not relicense dependencies, model weights, audio, or song lyrics.

If you later distribute an executable, Docker image, dependency bundle, or model
archive, review every included component and preserve required notices. This
review is not clearance for those future distributions. Dependencies are resolved
at installation time, so their exact versions and terms may change.

## Audio and lyric files

This tool is not intended for unauthorized copying or distribution of copyrighted
material. Users are responsible for ensuring they have the necessary rights or
an applicable legal exception for the audio, lyrics, photos, and other material
they process and share. This disclaimer does not grant permission or replace
the rights holder's license.

A recording and the musical composition, including its lyrics, can have separate
copyright owners. The U.S. Copyright Office explains this distinction in
[What Musicians Should Know about Copyright](https://www.copyright.gov/engage/musicians/).
Automatically transcribing a song does not remove the underlying rights.

Use your own material, material licensed for your intended use, public-domain
material whose relevant rights have been checked, or material covered by an
applicable legal exception. Owning an MP3 is not by itself permission to publish
its lyrics. Publicly distributing a complete SRT of copyrighted lyrics may
require permission from the relevant rights holder. Local processing and
noncommercial use are not automatic copyright exemptions.

Fair use depends on the circumstances; there is no fixed safe word count or
percentage. See the [U.S. Copyright Office fair-use FAQ](https://www.copyright.gov/help/faq/faq-fairuse.html).
Other jurisdictions have different exceptions. Seek qualified legal advice for
uncertain uses or a commercial distribution of copyrighted lyric files.

No song recordings or full song transcriptions are included in this repository.
The ignore rules exclude common audio, subtitle, and model files. Review the
staged files before publishing: ignore rules do not stop a forced add or remove
files already tracked by Git.

## Privacy

The application passes local audio to a local transcription library. Its code
does not upload audio or use a paid transcription API. Installation and initial
model downloads require network access and expose normal request metadata to
package/model hosts. `--offline` prevents model downloads and requires the chosen
model to be available locally. Paths, language, and progress are printed to the
terminal; remove private details before sharing logs.

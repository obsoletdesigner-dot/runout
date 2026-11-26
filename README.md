# Runout

**English** · [Español](README.es.md)

To check out and download the latest release, see [RELEASE](https://github.com/obsoletdesigner-dot/runout/releases)

A metadata editor for audio masters that **never touches the audio**. It reads and edits WAV, AIFF, FLAC, MP3, M4A (AAC or ALAC), Ogg Vorbis and Opus files (see [Supported formats](#supported-formats)).

<img width="1322" height="832" alt="Captura de pantalla 2026-11-26 130524" src="https://github.com/user-attachments/assets/5f9b145f-c23c-41c2-931c-bb1d9ea2e402" />

In WAV files it writes every metadata layer at once:

- `id3 ` (ID3v2.3 by default, or v2.4): all text frames, credits, dates, sort orders, URLs, `COMM`, `USLT`, industry-standard `TXXX` frames (catalogue number, UPC/EAN, ISWC, release country, type and status, ReplayGain, MusicBrainz) and free `TXXX` fields. Four images are supported: front cover, back cover, artist photo and label logo. `TLEN` is computed from the audio. In v2.3, frames that only exist in v2.4 (`TMOO`, `TPRO`, `TSST`, `TDRL`, `TDEN`, `TDTG`) are stored as `TXXX`, the same way MusicBrainz Picard does it.
- `axml` (EBU Tech 3352, EBUCore): ISRC, title, artist, label, date, ISWC, UPC/EAN, catalogue number, language and rights. It is placed right before `data`. If the file already has an axml from another tool with more data, only the ISRC is changed and the rest is kept byte for byte.
- `LIST-INFO` (UTF-8, as BWF MetaEdit expects; Windows-1252 is available in Preferences): INAM, IART, IPRD, ICRD, IGNR, ICMT, ICOP, IENG, ISFT, ISRC (*Source*), ITRK, IKEY, ISBJ, IMED, ISRF, ITCH, IARL and ICMS. The ISRC code is never written to `INFO/ISRC`, because that field means *Source*. If the file already holds an ISRC code there (REAPER and Sound Forge do this), it is kept in sync with the track's ISRC.
- `bext` (BWF): description, originator, reference, date, time, loudness (EBU R128, version 2) and CodingHistory. TimeReference and UMID are shown but cannot be edited. If no field changes, `bext` is copied byte for byte.

Every field validates its format: ISRC, ISWC and UPC/EAN with check digits, ISO 639-3 language, ISO 3166-1 country, ISO 15924 script, real dates, BPM, musical key, URLs, ReplayGain, MusicBrainz UUIDs, ASCII and lengths in `bext`, and loudness ranges. A track with an invalid field cannot be saved. The full field list is in `docs/` (in Spanish).

Windows Explorer and the native Windows players do not read the cover embedded in a WAV. For them, the "Also save the cover as folder.jpg" option in Preferences (on by default) copies the cover as `folder.jpg` into the WAV folder.

If VLC does not show a new cover, it is VLC's cache: it stores covers per artist and album. Quit VLC and delete `%APPDATA%\vlc\art` on Windows, `~/Library/Caches/org.videolan.vlc/art` on macOS or `~/.cache/vlc/art` on Linux.

Images are converted to a plain RGB JPEG of at most 2 MB when they are larger than 2 MB, wider or taller than 3000 px, in CMYK, or progressive JPEGs.

## Supported formats

| Format | Extensions | Metadata written | What must stay identical (SHA-256) |
|---|---|---|---|
| WAV / BWF | `.wav`, `.wave` | `id3 `, `axml`, `LIST-INFO`, `bext` | `data` and `fmt ` chunks, every preserved chunk |
| AIFF / AIFF-C | `.aif`, `.aiff`, `.aifc` | `ID3 ` chunk (all ID3 fields and the four images) | `SSND` and `COMM` chunks |
| FLAC | `.flac` | Vorbis Comments and `PICTURE` blocks | every audio frame and the `STREAMINFO` block (which holds the MD5 of the decoded audio) |
| MP3 | `.mp3` | ID3v2 at the start of the file | everything after the ID3v2 tag (MPEG frames, Xing/LAME header, ID3v1 if present) |
| M4A | `.m4a` | iTunes `ilst` atoms and `----:com.apple.iTunes` fields, front cover | `mdat` payload, sample tables and chunk offsets relative to the audio |
| Ogg Vorbis / Opus | `.ogg`, `.oga`, `.opus` | Vorbis Comments and `METADATA_BLOCK_PICTURE` | every packet except the comment packet, and the granule position of every audio page |

The editor only shows the fields and image slots the selected files can store. With files of different formats selected, it shows the fields they have in common. Fields from other layers (`axml`, `LIST-INFO`, `bext`) only exist in WAV. In M4A only the front cover can be embedded, because the format has no image types. Unknown tags (Vorbis keys, `TXXX`, freeform atoms) are shown in Custom and kept.

**Why only these formats, for now.** Runout only saves a file when it can prove, with a hash, that the audio is byte for byte the one it had before. That needs, for each format, an exact definition of which bytes are "the audio" and a writer that copies them without going through a decoder. The formats above have that definition and are covered by the tests. The rest are left out until they can get the same guarantee:

- **WMA / ASF**: proprietary container with poorly documented metadata objects and DRM variants.
- **APE, WavPack, TTA, Musepack, DSF / DFF (DSD)**: their tags (APEv2, ID3 in DSF) are well known, but there is no audio-only verification for them yet, and they are not common in delivery to distributors.
- **RF64 / BW64 (WAV over 4 GB)**: they need 64-bit sizes and the `ds64` chunk, which the RIFF writer does not handle.
- **Chained or multiplexed Ogg** (several logical streams, Ogg FLAC, Speex, video): only single-stream Vorbis and Opus are accepted.
- **MP4 video, `.m4b`, `.mp4`**: they have more tracks than audio, and a tag change can move offsets of streams that are not hashed.

Files with another extension are simply not loaded. Files with a supported extension whose structure is not what Runout expects are shown as "Not usable" and never written.

## Zero-Touch Audio guarantee

1. A dedicated RIFF writer (`runout/core/riff.py` and `writer.py`) rebuilds the file into a temporary file. `fmt `, `data`, `bext`, `cue `, `LIST-adtl`, `iXML` and any unknown chunk are copied byte for byte.
2. `mutagen` **never opens the WAV**: it only builds and reads the ID3 tag bytes in memory.
3. Before anything is replaced, the temporary file is read back as an unknown file. Runout checks that the SHA-256 of `data` and `fmt ` is identical to the original, that the hash of every preserved chunk is unchanged, that the RIFF size equals the file size minus 8, that every offset is even, and that the ISRC and title read back are the ones written.
4. Only if everything matches is the file swapped in with `os.replace` (atomic). If anything fails, the temporary file is deleted and the original stays untouched.
5. Every save is recorded in `runout.log`, in the destination folder, together with the SHA-256 of `data`.

The other formats follow the same steps (`runout/core/formats/base.py`): hash of the audio part listed in the table above, a new file written to a temporary file in the destination folder, the same hash computed on the temporary file, the tags read back, and only then `os.replace`. FLAC and AIFF use their own block and chunk writers, and MP3 is rebuilt as a new ID3v2 tag followed by the original bytes. For M4A and Ogg, `mutagen` writes into a copy, never into the original, and the hash comparison decides whether that copy is used.

RF64/BW64 files (over 4 GB) and truncated WAVs are not supported. Runout marks them as "Not usable".

## Install and run (from source)

Python 3.10 or later is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt     # PySide6, mutagen, Pillow, pycountry
python main.py                 # or: python main.py "/path/to/album"
```

Workflow:

1. Drop the album folder or several audio files onto the window. Dropping a folder loads the supported files inside it, without going into subfolders.
2. Select one or more tracks (Ctrl+A for all). The editor on the right shows the cover, title and artist at the top, and its sections on the left: Album, Track, Credits, Identifiers, Web links, RIFF INFO, BWF (bext), Images and Custom.
   - Every change applies immediately to all selected tracks. There is no "Apply" button.
   - With several tracks selected, fields with different values show "(multiple values)" and only change if you type in them. Per-track fields (title, ISRC, track number, lyrics…) are locked.
   - An invalid field turns red with the reason, and its section gets a red dot. Language, country and script show their name in green when they are valid.
3. Track number, Title and ISRC can also be edited directly in the table. The ISRC is cleaned up automatically: `US-ABC-26-00001` becomes `USABC2600001`.
4. Or click **Import CSV** with the columns `track,title,isrc` (`pista,titulo,isrc` also works). Both `,` and `;` separators and both UTF-8 and Windows-1252 are accepted. Rows are matched by track number.
5. Choose the save mode in the bottom bar and click the button, which shows how many tracks will be written (Ctrl+S):
   - *Overwrite originals*: saves only the tracks with changes, always with the SHA-256 verification.
   - *Copies in the tagged/ subfolder*: writes copies of every track to `folder/tagged/` and leaves the originals untouched. Afterwards each row works with its copy in `/tagged`, and saving again updates that copy.

The Tags, Cover and AXML columns show what the file on disk contains (green ✔ or red ✘). Tags means ID3, Vorbis Comments or MP4 atoms, depending on the format. AXML only applies to WAV and shows "–" for the rest. Hovering over the file name shows its format and structure. The Status column summarises each track, with details on hover: grey ✔ no changes, amber ● unsaved changes, amber ▲ warnings, green ✔ saved and verified, red ✘ errors.

The status bar shows the result of each operation. The detailed log, with the SHA-256 of every file, opens with the **Log** button and opens by itself if something fails.

**Preferences** (Ctrl+, or ⌘,) holds the ID3 version, the LIST-INFO encoding, folder.jpg, the theme (light, dark or follow the system) and the language. The interface is available in English (default) and Spanish; a language change takes effect after a restart.

## Translations

Interface strings are written in English in the code, wrapped in `tr("...")`. Each extra language is a JSON file in `runout/locales/` that maps the English text to its translation, plus a `"_language_name"` entry with the language's own name, which is what Preferences shows. Language, country and script names come from the translations that pycountry already ships.

To add a language:

1. Copy `runout/locales/es.json` to `runout/locales/<code>.json` (for example `fr.json`) and change `_language_name`.
2. Translate the values. Anything left untranslated is shown in English.
3. Run `python tools/i18n_check.py`, which lists the missing or obsolete entries in each file (`--write` adds them empty or removes them).

The tests check that every catalogue is complete and that the placeholders (`%s`, `%d`…) match the original.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

`tests/make_test_wavs.py` builds synthetic WAVs with an odd-sized `data` chunk, `bext`, `cue `, `LIST-adtl`, `iXML`, an existing upper-case ID3 chunk, a third-party EBUCore `axml`, a wrong RIFF size, trailing garbage and a missing padding byte. `tests/test_ebucore_schema.py` validates the generated axml (ISRC only, extended, and the one inside a saved WAV) against the official EBU EBUCore 2012 schema (it needs `lxml`, which is in `requirements-dev.txt`). The schemas are not in the repository: the test downloads them the first time, checks their SHA-256 and stores them in `tests/.schemas/`. Without a network connection, that test is skipped. The tests check hashes, padding, RIFF size, chunk order, and that a forced corruption is detected without touching the original. `tests/test_formats.py` does the same for every other format with the files in `tests/fixtures/`: field round trip, unchanged audio hash, stable second save, kept custom tags and images, and detection of a byte changed inside the audio.

## Building executables with PyInstaller

PyInstaller does not cross-compile: each executable is built on its own operating system, with the virtual environment active and `pip install -r requirements-dev.txt`.

**Recommended: with the included spec** (it excludes unused Qt modules and reduces the size):

```bash
pyinstaller --noconfirm --clean runout.spec
```

The result is in `dist/`: `Runout.exe` on Windows, `Runout.app` on macOS and `Runout` on Linux.

**One-line equivalent, without the spec:**

```bash
# Windows (PowerShell or cmd)
pyinstaller --noconfirm --clean --windowed --onefile --name Runout --add-data "runout/locales/*.json;runout/locales" main.py

# macOS (builds dist/Runout.app)
pyinstaller --noconfirm --clean --windowed --name Runout --osx-bundle-identifier io.github.obsoletdesigner-dot.runout --add-data "runout/locales/*.json:runout/locales" main.py

# Linux
pyinstaller --noconfirm --clean --windowed --onefile --name Runout --add-data "runout/locales/*.json:runout/locales" main.py
```

The spec already uses the icon in `assets/` (`runout.ico` on Windows, `runout.icns` on macOS). With the one-line version, add `--icon assets/runout.ico` or `--icon assets/runout.icns`. The icons are regenerated with `python tools/make_icons.py`.

Notes per system:

- **macOS**: an unsigned app is opened the first time with right-click and *Open*. To distribute it to third parties, sign and notarise it (`codesign --deep --options runtime -s "Developer ID Application: …" dist/Runout.app`, then `xcrun notarytool submit`). Build on an Apple Silicon Mac for arm64 and on an Intel Mac for x86_64.
- **Windows**: some antivirus programs flag PyInstaller `.exe` files built with `--onefile`. If that happens, use folder mode (drop `--onefile`) or sign the executable.
- **Linux**: build on the oldest distribution you want to support, because the binary depends on its glibc. Qt's system libraries are required (on Debian/Ubuntu: `libegl1 libxkbcommon0 libgl1 libfontconfig1`).

## Automated builds (GitHub Actions)

The `.github/workflows/build.yml` workflow does the same as the steps above on Windows, macOS (Apple Silicon) and Linux: it installs the dependencies, runs the tests and builds with `runout.spec`.

- **On every push to `main` and every pull request**: the executables are kept as downloadable artifacts for 14 days, in the *Actions* tab, inside the run.
- **Manually**: *Actions → Build → Run workflow*. Same result.
- **To publish a release**: bump `__version__` in `runout/__init__.py`, commit, and create the matching tag:

  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```

  If the tag does not match `__version__`, the workflow stops. If it matches, it creates a release under *Releases* with `Runout-windows-x64.zip`, `Runout-macos-arm64.zip` and `Runout-linux-x64.tar.gz`.

In private repositories, Actions minutes are limited and every macOS minute counts as ten. In public repositories they are free.

## Project layout

```
main.py                     entry point
runout/core/                Qt-free core (usable and testable without the interface)
    riff.py                 RIFF parser (struct), streaming hashes
    writer.py               chunk plan, temporary file, atomic replace
    integrity.py            structural checks and SHA-256
    axml.py                 EBUCore / ISRC (keeps the rest of an existing XML)
    id3chunk.py             mutagen in memory only (keeps foreign frames)
    listinfo.py             LIST-INFO (keeps foreign subchunks)
    bext.py                 BWF bext (keeps TimeReference, UMID and reserved bytes)
    fields.py               registry of every field and where it goes in each layer
    validators.py           normalisation and validation for each field type
    cover.py                image preparation (RGB JPEG, max. 2 MB)
    reader.py               reads every layer
    isrc.py, csv_import.py, model.py
    formats/                one handler per format, with the common verified save
        base.py             fingerprint, temporary file, reread, atomic replace
        wav.py, id3file.py  WAV; MP3 and AIFF (ID3)
        flac.py, ogg.py     FLAC blocks; Ogg Vorbis and Opus
        vorbis.py, mp4.py   Vorbis Comments mapping; M4A atoms
runout/ui/                  PySide6 interface (table, section editor, theme and icons)
runout/i18n.py              translations (tr) and active language
runout/locales/             translation catalogues (es.json)
assets/                     app icon (png, ico, icns)
tools/make_icons.py         generates the icons
tools/i18n_check.py         checks the translation catalogues
.github/workflows/build.yml automated builds and releases
docs/                       full list of metadata fields per standard (in Spanish)
tests/                      synthetic WAVs, sample files of every format and tests
tests/fixtures/             short 440 Hz sine files (AIFF, FLAC, MP3, M4A, Ogg, Opus)
```

## License

Copyright © 2026 Daniel Rodilla Cahill

Runout is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. It is distributed WITHOUT ANY WARRANTY. The full text is in [`LICENSE`](LICENSE).

Dependencies and their licenses: mutagen (GPL-2.0-or-later), PySide6 (LGPL-3.0), Pillow (MIT-CMU), pycountry (LGPL-2.1). Validation schemas used only by the tests, which are downloaded when the tests run and are not redistributed:

- EBUCore (`EBU_CORE_20130107.xsd`) © European Broadcasting Union, under [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/). Source: [github.com/ebu/MXFTools](https://github.com/ebu/MXFTools), folder `EBUCoreSchema/`.
- `simpledc20021212.xsd` (Dublin Core Metadata Initiative) and `xml.xsd` (W3C), as published by the EBU in [github.com/ebu/OSCIED](https://github.com/ebu/OSCIED), folder `tools/EBUCore/schemas/`.

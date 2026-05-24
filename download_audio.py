#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    raise


def build_opts(
    output_dir: Path,
    *,
    audio_format: str,
    split_chapters: bool,
    quiet: bool,
) -> dict:
    # Split mode: one folder per video ``title [id]/``, short chapter filenames.
    # Non-split: single flat file as before.
    if split_chapters:
        video_folder = output_dir / "%(title)s [%(id)s]"
        outtmpl: dict[str, str] = {
            "default": str(video_folder / "_source.%(ext)s"),
            "chapter": str(
                video_folder / "%(section_number)03d - %(section_title)s.%(ext)s"
            ),
        }
    else:
        outtmpl = {
            "default": str(output_dir / "%(title)s [%(id)s].%(ext)s"),
        }
    opts: dict = {
        # Audio-only; do not fall back to combined video+audio ("best").
        "format": "bestaudio",
        "outtmpl": outtmpl,
        "noplaylist": True,
    }
    if quiet:
        opts["quiet"] = True
        opts["no_warnings"] = True

    postprocessors: list[dict] = []
    if audio_format == "mp3":
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",  # VBR / best for libmp3lame
            }
        )
    elif audio_format == "flac":
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "flac",
            }
        )
    elif audio_format == "opus":
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
            }
        )
    elif audio_format == "remux":
        # yt-dlp "best" extract: stream-copy into a conventional audio extension when
        # ffmpeg supports it (e.g. opus-in-webm -> .opus, aac -> .m4a). Uncommon codecs
        # may fall back to transcoding (see yt_dlp FFmpegExtractAudioPP).
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "best",
            }
        )
    if split_chapters:
        postprocessors.append({"key": "FFmpegSplitChapters"})
    if postprocessors:
        opts["postprocessors"] = postprocessors

    return opts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download highest-quality audio from a YouTube URL."
    )
    parser.add_argument(
        "url",
        help="YouTube (or yt-dlp supported) URL",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to save files (default: current directory)",
    )
    parser.add_argument(
        "--audio-format",
        choices=("native", "remux", "mp3", "flac", "opus"),
        default="native",
        metavar="FMT",
        help=(
            "Output: native (default, keep container e.g. webm). remux: same codec, "
            "common extension when possible (opus->.opus, aac->.m4a), stream-copy (needs ffmpeg). "
            "mp3/flac/opus: transcode with ffmpeg."
        ),
    )
    parser.add_argument(
        "--split-chapters",
        action="store_true",
        help=(
            "If the video has chapter metadata, split into one file per chapter after download "
            "(requires ffmpeg). Output layout: OUTPUT_DIR/<title [id]>/{_source + NNN - chapter}. "
            "If there are no chapters, a single full-length file is kept."
        ),
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Less console output",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    opts = build_opts(
        output_dir,
        audio_format=args.audio_format,
        split_chapters=args.split_chapters,
        quiet=args.quiet,
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([args.url])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

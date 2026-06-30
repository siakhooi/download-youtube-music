#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yt_dlp
    from yt_dlp.postprocessor import PostProcessor
    from yt_dlp.postprocessor.ffmpeg import ACODECS, FFmpegPostProcessor
    from yt_dlp.utils import prepend_extension
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    raise


def silenceremove_filter(*, threshold: str, min_duration: float) -> str:
    return (
        "silenceremove="
        f"start_periods=1:start_duration={min_duration}:start_threshold={threshold}:detection=rms:"
        f"stop_periods=1:stop_duration={min_duration}:stop_threshold={threshold}"
    )


_SILENCE_START_RE = re.compile(r"silence_start: ([\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end: ([\d.]+)")


class FFmpegSilenceRemovePP(FFmpegPostProcessor):
    def __init__(
        self,
        downloader=None,
        *,
        threshold: str = "-50dB",
        min_duration: float = 0.5,
    ):
        super().__init__(downloader)
        self.threshold = threshold
        self.min_duration = min_duration

    def _encode_args(self, filepath: str, af_filter: str) -> list[str]:
        ext = Path(filepath).suffix.lstrip(".").lower()
        codec = self.get_audio_codec(filepath)
        opts = ["-vn", "-af", af_filter]

        entry = ACODECS.get(codec) if codec else None
        if entry is None and ext:
            for key, value in ACODECS.items():
                target_ext, _, _ = value
                if ext in (key, target_ext):
                    entry = value
                    break

        if entry is None:
            entry = ACODECS["mp3"]

        _, encoder, extra = entry
        if encoder:
            opts.extend(["-acodec", encoder])
        opts.extend(extra)
        return opts

    def _audio_duration(self, filepath: str) -> float | None:
        try:
            return self._get_real_video_duration(filepath, fatal=False)
        except Exception:
            return None

    def _parse_silence_regions(self, stderr: str) -> list[tuple[float, float]]:
        regions: list[tuple[float, float]] = []
        current_start: float | None = None
        for line in stderr.splitlines():
            start_match = _SILENCE_START_RE.search(line)
            if start_match:
                current_start = float(start_match.group(1))
                continue
            end_match = _SILENCE_END_RE.search(line)
            if end_match and current_start is not None:
                regions.append((current_start, float(end_match.group(1))))
                current_start = None
        return regions

    def _silence_edges(
        self, filepath: str, duration: float | None
    ) -> tuple[float, float]:
        cmd = [
            self.executable,
            "-hide_banner",
            "-nostats",
            "-loglevel",
            "info",
            "-i",
            filepath,
            "-af",
            f"silencedetect=noise={self.threshold}:d={self.min_duration}",
            "-f",
            "null",
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        regions = self._parse_silence_regions(result.stderr)
        if not regions or duration is None:
            return 0.0, 0.0

        leading = 0.0
        trailing = 0.0
        start, end = regions[0]
        if start <= 0.05:
            leading = end
        last_start, last_end = regions[-1]
        if last_end >= duration - 0.05:
            trailing = duration - last_start

        if (
            len(regions) == 1
            and start <= 0.05
            and last_end >= duration - 0.05
        ):
            trailing = 0.0

        return leading, trailing

    def _trim_file(self, filepath: str) -> None:
        if not filepath or not os.path.isfile(filepath):
            return
        af_filter = silenceremove_filter(
            threshold=self.threshold,
            min_duration=self.min_duration,
        )
        before = self._audio_duration(filepath)
        start_trim, end_trim = self._silence_edges(filepath, before)
        temp_path = prepend_extension(filepath, "temp")
        self.to_screen(f'Trimming silence from "{filepath}"')
        self.run_ffmpeg(filepath, temp_path, self._encode_args(filepath, af_filter))
        os.replace(temp_path, filepath)
        after = self._audio_duration(filepath)
        if before is not None and after is not None:
            trimmed = before - after
            self.to_screen(
                f"  trimmed {trimmed:.1f}s "
                f"(start {start_trim:.1f}s, end {end_trim:.1f}s) "
                f"({before:.1f}s -> {after:.1f}s)"
            )
        else:
            self.to_screen("  trim complete (could not measure duration)")

    @PostProcessor._restrict_to(images=False)
    def run(self, info):
        paths: list[str] = []
        main_path = info.get("filepath")
        if main_path:
            paths.append(main_path)
        for chapter in info.get("chapters") or []:
            chapter_path = chapter.get("filepath")
            if chapter_path and chapter_path not in paths:
                paths.append(chapter_path)

        for path in paths:
            self._trim_file(path)
        return [], info


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
    parser.add_argument(
        "--trim-silence",
        action="store_true",
        help=(
            "Trim leading/trailing silence before saving (requires ffmpeg; re-encodes audio). "
            "Default detection: -50dB threshold, 0.5s minimum silence."
        ),
    )
    parser.add_argument(
        "--silence-threshold",
        default="-50dB",
        metavar="DB",
        help='Silence level in dBFS (default: "-50dB"). Lower values trim less.',
    )
    parser.add_argument(
        "--silence-min-duration",
        type=float,
        default=0.5,
        metavar="SEC",
        help="Seconds of continuous silence required to trim (default: 0.5).",
    )
    args = parser.parse_args()

    if args.trim_silence and not FFmpegSilenceRemovePP().available:
        print("ffmpeg is required for --trim-silence", file=sys.stderr)
        return 1

    output_dir: Path = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    opts = build_opts(
        output_dir,
        audio_format=args.audio_format,
        split_chapters=args.split_chapters,
        quiet=args.quiet,
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        if args.trim_silence:
            ydl.add_post_processor(
                FFmpegSilenceRemovePP(
                    ydl,
                    threshold=args.silence_threshold,
                    min_duration=args.silence_min_duration,
                ),
                when="post_process",
            )
        ydl.download([args.url])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

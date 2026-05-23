# download-youtube-music
Script to download youtube music


Download the best available audio-only stream from a YouTube URL.

## Requirements
Requires: pip install yt-dlp
Optional: ffmpeg on PATH (required for --audio-format mp3|flac, --split-chapters, and some sources).

Use --audio-format native (default) to keep the downloaded codec (e.g. opus in webm).
Use mp3 or flac to transcode with ffmpeg (lossy sources stay lossy; flac is still a lossless encode of the decoded PCM, not “higher quality” than the stream).

With --split-chapters, if the video provides chapter metadata, ffmpeg cuts one file per chapter (stream copy). If there are no chapters, you still get a single full-length file. The unsplit source file may remain on disk alongside the chapter files (same behavior as yt-dlp).

In split mode, files go under a subdirectory named from the video title and id (``%(title)s [%(id)s]``): the full download is saved as ``_source.%(ext)s``, and each chapter is ``NNN - section title.%(ext)s`` (no repeated video title in each chapter filename).

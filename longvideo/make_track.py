#!/usr/bin/env python3
"""Build a single 1080x1920 video track from the 12 Agnes clips with 0.3s
crossfades between sentences.

Each clip is extended by 0.4s and rendered slightly slower (for smoother motion).
The xfade chain uses offsets equal to the sentence start times, so the slot
boundaries stay exactly where the narration sentences start.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

WORK = pathlib.Path("/Users/xieyingfei/Documents/youtube-ai-video/longvideo")
ROOT = pathlib.Path.home() / "MoneyPrinterTurbo"
RAW = WORK / os.environ.get("MPT_RAW_DIR", "videos_raw")
EXT = WORK / os.environ.get("MPT_EXT_DIR", "clips_ext")
TRACK = WORK / os.environ.get("MPT_TRACK", "track_crossfade.mp4")
FPS = 30
XFADE = 0.3           # crossfade duration (seconds)
EXTRA_FRAMES = 12     # 0.4s slack so xfade never runs past the input
SLOWDOWN = 1.08       # >1 = slower playback, smoother motion


def main() -> int:
    EXT.mkdir(parents=True, exist_ok=True)
    frames = json.loads((WORK / "timeline.json").read_text(encoding="utf-8"))["frames"]
    starts = json.loads((WORK / "timeline.json").read_text(encoding="utf-8"))["starts"]
    ffmpeg = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    # 1) conform each raw clip to (slot + slack) frames, slightly slowed
    ext_files = []
    for i, f in enumerate(frames, 1):
        out = EXT / f"seg{i:02d}.mp4"
        n = f + EXTRA_FRAMES
        vf = (f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              f"setpts={SLOWDOWN}*PTS,fps={FPS},format=yuv420p")
        subprocess.run(
            [ffmpeg, "-y", "-stream_loop", "-1", "-i", str(RAW / f"seg{i:02d}.mp4"),
             "-vf", vf, "-frames:v", str(n), "-an", "-r", str(FPS), "-fps_mode", "cfr",
             "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-movflags", "+faststart", str(out)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        ext_files.append(out)
        print(f"ext {out.name}: {n} frames ({(f/FPS):.2f}s + 0.4s)", flush=True)

    # 2) xfade chain; offsets are the sentence start times
    inputs = []
    for f in ext_files:
        inputs += ["-i", str(f)]
    parts = []
    prev = "0:v"
    for k in range(1, len(ext_files)):
        out = f"x{k}"
        parts.append(
            f"[{prev}][{k}:v]xfade=transition=fade:duration={XFADE}:offset={starts[k]:.3f}[{out}]"
        )
        prev = out
    fc = ";".join(parts)
    cmd = [ffmpeg, "-y", *inputs, "-filter_complex", fc, "-map", f"[{prev}]",
           "-r", str(FPS), "-fps_mode", "cfr", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(TRACK)]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        print("FFMPEG FAILED:\n" + r.stderr.decode("utf-8", "ignore")[-3000:])
        return 1
    print(f"\ntrack -> {TRACK}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

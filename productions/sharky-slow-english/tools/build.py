#!/usr/bin/env python3
"""Build the sample: stills -> Ken Burns clips + narration + burned subtitles -> one mp4."""
import json, subprocess, pathlib, textwrap, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = json.loads((ROOT / "shots.json").read_text())["shots"]
VOICE = json.loads((ROOT / "voice.json").read_text())
W, H, FPS = 1920, 1080, 30
TMP = ROOT / "build"; TMP.mkdir(exist_ok=True)
FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
WORK = ROOT / "assets/work"; WORK.mkdir(parents=True, exist_ok=True)


def narrate(sid: str, text: str) -> pathlib.Path:
    aiff = WORK / f"{sid}.aiff"; wav = WORK / f"{sid}.wav"
    if not wav.exists():
        subprocess.run(["say", "-v", VOICE["voice"], "-r", str(VOICE["rate"]),
                        "-o", str(aiff), text], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff),
                        "-ac", "1", "-ar", "48000", str(wav)], check=True)
    return wav


def audio_len(p: pathlib.Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip())


def subtitle_png(sid: str, text: str) -> pathlib.Path:
    """Rounded bold caption, white with heavy outline, max 2 lines, bottom third."""
    out = TMP / f"{sid}_cap.png"
    if out.exists():
        return out
    img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = 74
    while size > 40:
        font = ImageFont.truetype(FONT, size)
        chars = int(W * 0.86 / (size * 0.55))
        lines = textwrap.wrap(text, chars)
        if len(lines) <= 2:
            break
        size -= 6
    font = ImageFont.truetype(FONT, size)
    lh = size * 1.18
    y = (300 - lh * len(lines)) / 2
    for line in lines:
        tw = d.textlength(line, font=font)
        d.text(((W - tw) / 2, y), line, font=font, fill="white",
               stroke_width=9, stroke_fill=(10, 20, 40, 255))
        y += lh
    img.save(out)
    return out


def clip(shot) -> pathlib.Path:
    sid = shot["id"]
    out = TMP / f"{sid}.mp4"
    if out.exists():
        return out
    wav = narrate(sid, shot["overlay"])
    dur = max(shot["target"], audio_len(wav) + 0.9)
    frames = int(dur * FPS)
    cap = subtitle_png(sid, shot["overlay"])
    still = ROOT / "assets" / "shots" / f"{sid}.png"
    # slow push-in; alternate direction per shot for rhythm
    zi = "min(1+0.0011*on,1.14)" if int(sid[1:]) % 2 else "if(lte(on,1),1.14,max(1.14-0.0011*on,1.0))"
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"zoompan=z='{zi}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[v0];"
          f"[v0][2:v]overlay=0:H-330:format=auto[v];"
          f"[1:a]aresample=48000,apad[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(still),
                    "-i", str(wav), "-i", str(cap),
                    "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-t", f"{dur:.3f}", "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(out)], check=True)
    print(f"  {sid} {dur:5.1f}s", flush=True)
    return out


def main():
    clips = [clip(s) for s in SHOTS]
    lst = TMP / "concat.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clips))
    final = ROOT / "output" / "sharky-sample.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(final)], capture_output=True, text=True)
    print(f"built {final}  {float(d.stdout) / 60:.2f} min")


if __name__ == "__main__":
    main()

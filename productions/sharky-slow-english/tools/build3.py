#!/usr/bin/env python3
"""v3 构建：一镜多刀 + 快镜头运动 + 程序化泡沫/水花粒子层。
参考片实测帧间差 4.54，v2 只有 0.53 —— 目标把每个镜头拆成约 2.2 秒一拍。"""
import json, math, subprocess, pathlib, textwrap, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = json.loads((ROOT / "shots.json").read_text())["shots"]
VOICE = json.loads((ROOT / "voice.json").read_text())
W, H, FPS = 1920, 1080, 30
UP = 2                          # 静帧先放大，给运镜留余量
BEAT = 2.2                      # 目标切镜间隔（秒），参考片实测 ~2.0
TMP = ROOT / "build3"; TMP.mkdir(exist_ok=True)
WORK = ROOT / "assets/work"; WORK.mkdir(parents=True, exist_ok=True)
FONT = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"

# 偏"湿"的镜头叠泡沫/水花粒子
WET = {"S05","S06","S07","S08","S11","S12","S16","S20","S22","S23","S24","C1","C2","C5","C6","C7"}
# 每一拍的取景中心（占画面比例）与推拉区间，交替出现制造"切"的错觉
FRAMES_ = [
    ((0.50, 0.50), (1.00, 1.38)),
    ((0.36, 0.46), (1.62, 1.24)),
    ((0.64, 0.52), (1.22, 1.62)),
    ((0.52, 0.38), (1.10, 1.46)),
    ((0.42, 0.60), (1.55, 1.14)),
    ((0.58, 0.44), (1.04, 1.42)),
]
# 手持感微旋转（弧度），每拍方向交替
TILT = [(+0.010, -0.004), (-0.008, +0.006), (+0.006, +0.009),
        (-0.010, -0.006), (+0.009, +0.003), (-0.006, -0.008)]


def audio_len(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return float(o.stdout.strip())


def narrate(sid, text):
    aiff, wav = WORK / f"{sid}.aiff", WORK / f"{sid}.wav"
    if not wav.exists():
        subprocess.run(["say", "-v", VOICE["voice"], "-r", str(VOICE["rate"]), "-o", str(aiff), text], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ac", "1", "-ar", "48000", str(wav)], check=True)
    return wav


def caption(sid, text):
    out = TMP / f"{sid}_cap.png"
    if out.exists():
        return out
    img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = 74
    while size > 40:
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
        d.text(((W - tw) / 2, y), line, font=font, fill="white", stroke_width=9, stroke_fill=(10, 20, 40, 255))
        y += lh
    img.save(out)
    return out


def particles():
    """预生成 60 帧白色气泡/水花循环（带 alpha），供叠加。"""
    seq = TMP / "part"
    if seq.exists() and len(list(seq.glob("*.png"))) == 60:
        return seq
    seq.mkdir(exist_ok=True)
    rnd = random.Random(11)
    N = 60
    bub = [dict(x=rnd.uniform(0, W), y=rnd.uniform(0, H), r=rnd.uniform(14, 46),
                sp=rnd.uniform(2.5, 7.0), ph=rnd.uniform(0, 6.28)) for _ in range(34)]
    for i in range(N):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        t = i / N
        for b in bub:
            y = (b["y"] - b["sp"] * i * 2) % (H + 120) - 60
            x = b["x"] + 26 * math.sin(b["ph"] + t * 18)
            r = b["r"]
            d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, 150), width=max(2, int(r / 9)))
            d.ellipse([x - r * .55, y - r * .55, x + r * .2, y + r * .2], fill=(255, 255, 255, 60))
        img = img.filter(ImageFilter.GaussianBlur(1.2))
        img.save(seq / f"{i:03d}.png")
    return seq


def beat_clip(shot, idx, dur, frame, cap, pseq):
    sid = shot["id"]
    out = TMP / f"{sid}_{idx}.mp4"
    if out.exists():
        return out
    (cx, cy), (z0, z1) = frame
    still = ROOT / "assets" / "shots" / f"{sid}.png"
    n = max(2, int(dur * FPS))
    a0, a1 = TILT[idx % len(TILT)]
    PW, PH = int(W * 1.10), int(H * 1.10)
    zv = (f"[0:v]scale={W*UP}:{H*UP}:force_original_aspect_ratio=increase,crop={W*UP}:{H*UP},"
          f"zoompan=z='{z0}+({z1}-{z0})*on/{n}':d={n}:s={PW}x{PH}:fps={FPS}"
          f":x='iw*{cx}-(iw/zoom)/2':y='ih*{cy}-(ih/zoom)/2',"
          f"rotate='{a0}+({a1}-{a0})*t/{dur:.4f}':ow=iw:oh=ih:fillcolor=black,"
          f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2[zv]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(still)]
    if sid in WET:
        cmd += ["-stream_loop", "-1", "-framerate", str(FPS), "-i", str(pseq / "%03d.png")]
        cmd += ["-i", str(cap)]
        fc = (zv + ";[1:v]format=rgba[pt];[zv][pt]overlay=0:0[ov];"
                   "[ov][2:v]overlay=0:H-330[v]")
    else:
        cmd += ["-i", str(cap)]
        fc = zv + ";[zv][1:v]overlay=0:H-330[v]"
    cmd += ["-t", f"{dur:.3f}", "-filter_complex", fc, "-map", "[v]", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True)
    return out


def main():
    pseq = particles()
    beats = []
    for si, shot in enumerate(SHOTS):
        sid = shot["id"]
        wav = narrate(sid, shot["overlay"])
        dur = max(shot["target"], audio_len(wav) + 0.9)
        cap = caption(sid, shot["overlay"])
        nbeat = max(1, round(dur / BEAT))
        bdur = dur / nbeat
        for b in range(nbeat):
            f = FRAMES_[(si * 3 + b) % len(FRAMES_)]
            beats.append(beat_clip(shot, b, bdur, f, cap, pseq))
        # 旁白音轨单独拼回（画面切拍不影响口播连续性）
        print(f"  {sid}: {nbeat} 拍 x {bdur:.2f}s", flush=True)

    lst = TMP / "beats.txt"
    lst.write_text("".join(f"file '{b}'\n" for b in beats))
    silent = TMP / "video_only.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(silent)], check=True)

    # 口播：把所有旁白按镜头时长排成一条音轨
    alist = TMP / "audio.txt"
    lines = []
    for shot in SHOTS:
        wav = WORK / f"{shot['id']}.wav"
        dur = max(shot["target"], audio_len(wav) + 0.9)
        pad = TMP / f"{shot['id']}_pad.wav"
        if not pad.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", f"apad=whole_dur={dur:.3f}",
                            "-ar", "48000", "-ac", "1", str(pad)], check=True)
        lines.append(f"file '{pad}'\n")
    alist.write_text("".join(lines))
    track = TMP / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(alist),
                    "-c", "copy", str(track)], check=True)

    final = ROOT / "output" / "sharky-sample-v3.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(track),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(final)], check=True)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(final)], capture_output=True, text=True)
    print(f"built {final}  {float(d.stdout)/60:.2f} min  ({len(beats)} 拍)")


if __name__ == "__main__":
    main()

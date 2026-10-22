#!/usr/bin/env python3
"""Build per-sentence images + exact-duration Ken Burns clips for the long video.

Pass 1 (already done) produced audio.mp3 + subtitle.srt. Here we:
  1. group the 33 subtitle cues back into the 12 script sentences,
  2. generate one matching image per sentence with the user's Agnes API,
  3. render one zoom clip per sentence whose duration equals that sentence's
     slot on the timeline (so picture changes exactly when the narration changes).
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path.home() / "MoneyPrinterTurbo"
WORK = pathlib.Path(__file__).resolve().parent
IMAGES = WORK / "images"
CLIPS = WORK / "clips"
FPS = 30
TARGET_TOTAL_SECONDS = 72.5  # > required (ceil(71.162)=72) + 0.1s margin, avoids clip looping

SENTENCES = [
    "清晨，智能音箱用温和的声音播报天气和日程，唤醒新的一天。",
    "出门前，手机地图根据实时路况，规划出最快的一条通勤路线。",
    "通勤路上，语音助手把当天新闻浓缩成三分钟的音频摘要。",
    "工作中，AI随手翻译外文邮件，还能自动起草得体的回复。",
    "写代码时，编辑器实时补全整段逻辑，让重复劳动降到最低。",
    "午餐后，AI根据口味和热量，推荐了一份附近餐厅的菜单。",
    "下班回家，智能门锁与灯光自动亮起，空调提前调到舒适温度。",
    "晚餐时，视频平台推荐的片子，正好符合全家人的口味。",
    "睡前，AI把白天拍的几百张照片，挑出最好的整理成相册。",
    "它还提醒老人按时服药，把体检报告里的指标讲成大白话。",
    "对孩子和长辈，一句自然的语音对话，就能完成复杂操作。",
    "人工智能不是遥远的未来，而是每天都在发生的细碎改变。",
]

PROMPTS = [
    "清晨的卧室，床头智能音箱发出柔和的光，窗外晨光和煦，写实电影感照片",
    "城市早高峰街道，上班族举着手机看导航地图，车流灯光，写实电影感照片",
    "地铁车厢里戴耳机听新闻的年轻人，手机屏幕显示音频波形，写实电影感照片",
    "办公室电脑屏幕上外文邮件与中文翻译对照，白领正在打字，写实电影感照片",
    "夜晚办公室，程序员屏幕上彩色代码与AI补全提示浮窗，写实电影感照片",
    "明亮餐厅里用手机扫码点餐，屏幕显示菜品与热量数字，写实电影感照片",
    "傍晚温馨客厅，智能门锁指示灯与暖色灯光自动亮起，写实电影感照片",
    "一家人在客厅沙发上看电视，屏幕显示推荐界面，温馨写实电影感照片",
    "夜晚卧室，暖色台灯下用平板浏览自动整理好的照片相册，写实电影感照片",
    "老年人手持药盒，手机弹出服药提醒，旁边有健康指标图表，写实电影感照片",
    "老人和小孩对着智能音箱自然说话，声波与对话气泡，温暖写实电影感照片",
    "城市夜景，居民楼窗户透出暖光，科技光点融入日常生活，电影感写实照片",
]

PUNCT = set("?,.、;:!…？！。，：；·\"'（）()《》【】—- ")


def norm(text: str) -> str:
    return "".join(ch for ch in text if ch not in PUNCT and not ch.isspace())


def read_cfg() -> tuple[str, str]:
    s = (ROOT / "config.toml").read_text(encoding="utf-8")

    def val(k):
        m = re.search(rf'^{re.escape(k)}\s*=\s*"(.*)"\s*$', s, re.M)
        return m.group(1) if m else ""

    return val("oneapi_base_url").rstrip("/"), val("oneapi_api_key")


def parse_srt(path: pathlib.Path):
    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        cues.append((start, " ".join(lines[2:])))
    return cues


def group_boundaries(cues):
    targets = [norm(s) for s in SENTENCES]
    groups, buf, cur_start = [], "", None
    ti = 0
    for start, text in cues:
        if cur_start is None:
            cur_start = start
        buf += norm(text)
        if ti < len(targets) and buf == targets[ti]:
            groups.append((cur_start, buf))
            buf, cur_start, ti = "", None, ti + 1
    if ti != len(targets) or buf:
        raise SystemExit(f"subtitle grouping failed: matched {ti}/{len(targets)} (leftover={buf!r})")
    return groups


def agnes_image(base: str, key: str, prompt: str, out: pathlib.Path) -> None:
    payload = json.dumps(
        {"model": "agnes-image-2.5-flash", "prompt": prompt, "n": 1, "size": "1080x1920"}
    ).encode()
    req = urllib.request.Request(
        base + "/images/generations",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                url = json.load(r)["data"][0]["url"]
            # Output URLs are public; sending Authorization makes the storage 401.
            dl = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(dl, timeout=180).read()
            out.write_bytes(data)
            print(f"  image ok ({len(data)//1024} KB) -> {out.name}")
            return
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt} failed: {type(e).__name__}: {e}")
            time.sleep(3 * attempt)
    raise SystemExit(f"image generation failed for prompt: {prompt}")


def make_clip(ffmpeg: str, image: pathlib.Path, frames: int, out: pathlib.Path) -> None:
    vf = (
        "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
        "zoompan=z='min(1+0.00045*on,1.13)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d=1:s=1080x1920:fps=30,format=yuv420p"
    )
    cmd = [
        ffmpeg, "-y", "-loop", "1", "-framerate", "30", "-i", str(image),
        "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print(f"  clip ok ({frames} frames = {frames/FPS:.2f}s) -> {out.name}")


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    base, key = read_cfg()
    if not key:
        raise SystemExit("oneapi_api_key missing in config.toml")

    task_id = (WORK / "pass1_taskid.txt").read_text().strip()
    srt = ROOT / "storage" / "tasks" / task_id / "subtitle.srt"
    cues = parse_srt(srt)
    groups = group_boundaries(cues)
    print(f"grouped {len(cues)} cues into {len(groups)} sentences")

    starts = [0.0] + [g[0] for g in groups[1:]]
    total = TARGET_TOTAL_SECONDS
    cum_frames = [0] + [int(starts[i] * FPS + 0.5) for i in range(1, len(starts))]
    cum_frames.append(int(total * FPS + 0.5))
    frames = [cum_frames[i + 1] - cum_frames[i] for i in range(len(groups))]
    for i, f in enumerate(frames, 1):
        print(f"  seg {i:2d}: start={starts[i-1]:6.3f}s  frames={f:4d}  dur={f/FPS:5.2f}s  {SENTENCES[i-1][:16]}...")

    ffmpeg = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    clips = []
    for i, (sent, prompt, f) in enumerate(zip(SENTENCES, PROMPTS, frames), 1):
        print(f"[{i}/{len(SENTENCES)}] {sent[:20]}...")
        img = IMAGES / f"seg{i:02d}.png"
        if not img.exists():
            agnes_image(base, key, prompt, img)
        clip = CLIPS / f"seg{i:02d}.mp4"
        make_clip(ffmpeg, img, f, clip)
        clips.append(clip)

    (WORK / "materials.txt").write_text(",".join(str(c) for c in clips), encoding="utf-8")
    (WORK / "timeline.json").write_text(
        json.dumps({"starts": starts, "frames": frames, "total": sum(frames) / FPS},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE: {len(clips)} clips, total {sum(frames)/FPS:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate real motion clips with Agnes `agnes-video-v2.0` (free) for each of the
12 script sentences, then conform every clip to its exact timeline slot.

Free-tier video RPM is 1, so creations are spaced out. State is kept in
video_tasks.json so the script can resume after a failure.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path.home() / "MoneyPrinterTurbo"
WORK = pathlib.Path(__file__).resolve().parent
RAW = WORK / "videos_raw"
CLIPS = WORK / "clips_video"
STATE = WORK / "video_tasks.json"
FPS_OUT = 30
FPS_SRC = 24
MIN_CREATE_GAP = 62  # seconds between task creations (free tier: 1 video RPM)

PROMPTS = [
    "Morning bedroom, a smart speaker on the nightstand glows softly and pulses gently, warm sunrise light through the window, slow cinematic push-in, realistic",
    "Busy city street in the morning, a commuter raises a phone showing a navigation map, traffic and car lights, subtle handheld camera drift, realistic",
    "Inside a subway car, a young commuter wearing earphones listens to the news, phone screen shows a moving audio waveform, gentle camera pan, realistic",
    "Office desk, computer screen shows a foreign-language email with a Chinese translation beside it, a professional types, slow camera move, realistic",
    "Night office, a programmer's screen filled with colorful code and an AI completion popup, screen glow on the desk, slow push-in, realistic",
    "Bright restaurant, a person scans a QR code and orders on a phone showing dishes and calorie numbers, warm light, gentle camera move, realistic",
    "Cozy living room at dusk, a smart lock indicator blinks and warm lights fade on automatically, curtains and lamps, slow camera dolly, realistic",
    "Family on a living room sofa watching TV, the screen shows a recommendation interface, warm cozy lighting, slow camera move, realistic",
    "Bedroom at night, a person browses an auto-organized photo album on a tablet under a warm lamp, soft glow, slow push-in, realistic",
    "An elderly person holds a pill organizer, a phone pops up a medication reminder beside health charts, warm home lighting, slow camera move, realistic",
    "An elderly person and a child talk naturally to a smart speaker, sound waves and chat bubbles appear, warm family scene, slow camera move, realistic",
    "City skyline at night, warmly lit windows in residential buildings, glowing tech particles drift through the streets, slow aerial push-in, cinematic realistic",
]

NEGATIVE = "cartoon, anime, low quality, blurry, distorted faces, extra limbs, text, watermark"


def cfg() -> tuple[str, str]:
    s = (ROOT / "config.toml").read_text(encoding="utf-8")

    def val(k):
        m = re.search(rf'^{re.escape(k)}\s*=\s*"(.*)"\s*$', s, re.M)
        return m.group(1) if m else ""

    return val("oneapi_base_url").rstrip("/").replace("/v1", ""), val("oneapi_api_key")


def api(method, url, key, payload=None):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:  # noqa: BLE001
        return "ERR", f"{type(e).__name__}: {e}"


def num_frames_for(seconds: float) -> int:
    """Smallest 8n+1 frame count whose duration at FPS_SRC covers `seconds`."""
    need = seconds * FPS_SRC
    n = math.ceil((need - 1) / 8)
    return 8 * n + 1


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def create_task(base, key, prompt, num_frames, tries=25):
    payload = {
        "model": "agnes-video-v2.0",
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "width": 720,
        "height": 1280,
        "num_frames": num_frames,
        "frame_rate": FPS_SRC,
    }
    for attempt in range(1, tries + 1):
        st, body = api("POST", f"{base}/v1/videos", key, payload)
        vid = body.get("video_id") if isinstance(body, dict) else None
        if st in (200, 201) and vid:
            return vid
        code = body.get("code") if isinstance(body, dict) else body
        print(f"    create attempt {attempt}: {st} {code}", flush=True)
        time.sleep(60)
    raise RuntimeError("could not create video task (queue full / rate limited)")


def poll(base, key, vid, timeout=900):
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(10)
        st, b = api("GET", f"{base}/agnesapi?video_id={vid}", key)
        status = str(b.get("status", "") if isinstance(b, dict) else "?").lower()
        if status in {"completed", "succeeded", "success", "done"}:
            return b.get("url")
        if status in {"failed", "error", "cancelled"}:
            raise RuntimeError(f"task failed: {json.dumps(b, ensure_ascii=False)[:200]}")
    raise TimeoutError(f"poll timed out for {vid}")


def download(url, dest: pathlib.Path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=300).read()
    dest.write_bytes(data)
    print(f"    downloaded raw ({len(data)//1024} KB)", flush=True)


def conform(ffmpeg, raw: pathlib.Path, frames: int, out: pathlib.Path):
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p"
    subprocess.run(
        [ffmpeg, "-y", "-stream_loop", "-1", "-i", str(raw), "-vf", vf,
         "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-movflags", "+faststart", str(out)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    base, key = cfg()
    if not key:
        raise SystemExit("no api key")
    timeline = json.loads((WORK / "timeline.json").read_text(encoding="utf-8"))
    frames = timeline["frames"]
    ffmpeg = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    state = load_state()
    last_create = 0.0
    for i, (prompt, slot_frames) in enumerate(zip(PROMPTS, frames), 1):
        seg = f"seg{i:02d}"
        raw = RAW / f"{seg}.mp4"
        clip = CLIPS / f"{seg}.mp4"
        if clip.exists() and raw.exists():
            print(f"[{i}/12] {seg} 已存在，跳过", flush=True)
            continue
        slot = slot_frames / FPS_OUT
        nf = num_frames_for(slot)
        print(f"[{i}/12] {seg} 槽位={slot:.2f}s num_frames={nf} ({nf/FPS_SRC:.2f}s)", flush=True)
        entry = state.get(seg, {})
        vid = entry.get("video_id")
        if not vid:
            gap = MIN_CREATE_GAP - (time.time() - last_create)
            if gap > 0:
                print(f"    限流等待 {gap:.0f}s", flush=True)
                time.sleep(gap)
            vid = create_task(base, key, prompt, nf)
            last_create = time.time()
            state[seg] = {"video_id": vid}
            save_state(state)
            print(f"    task created: {vid[-24:]}", flush=True)
        if not raw.exists():
            url = entry.get("url")
            if not url or not raw.exists():
                url = poll(base, key, vid)
                state[seg]["url"] = url
                save_state(state)
            download(url, raw)
        conform(ffmpeg, raw, slot_frames, clip)
        print(f"    conformed -> {clip.name} ({slot_frames} frames)", flush=True)

    (WORK / "materials_video.txt").write_text(
        ",".join(str(CLIPS / f"seg{i:02d}.mp4") for i in range(1, 13)), encoding="utf-8"
    )
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

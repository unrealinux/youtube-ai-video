#!/usr/bin/env python3
"""v2: image-to-video with anchored first frames + 30 inference steps.

Fixes from v1 feedback:
  * stiff motion      -> image-to-video + num_inference_steps=30 + 0.93x playback
  * floating phone    -> first frame anchors the composition, prompts avoid
                         close-up screens / floating devices / on-screen text
Each segment: fresh still -> i2v task -> poll -> download -> conform to slot.
Resumable via v2_state.json.
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
STILLS = WORK / "frames_v2"
RAW = WORK / "videos_raw_v2"
STATE = WORK / "v2_state.json"
FPS_SRC = 24
MIN_GAP = 62

NEG = ("cartoon, anime, illustration, text, subtitles, watermark, logo, floating objects, "
       "levitating phone, extra fingers, deformed hands, distorted face, morphing, "
       "duplicate limbs, low quality, blurry")

STILL_PROMPTS = [
    "Wide shot of a cozy bedroom at sunrise, a small fabric smart speaker on the nightstand glowing softly, warm morning light through sheer curtains, clean modern decor, realistic photograph",
    "Medium shot of a young woman in a coat walking along a city sidewalk in the morning, looking at a smartphone she holds in her hand, rain-washed street, traffic bokeh behind her, realistic photograph",
    "Wide shot inside a subway car, a young man wearing earphones sitting and holding a smartphone in one hand, relaxed posture, other passengers seated in the background, warm interior lighting, realistic photograph",
    "Medium shot from behind of an office worker at a desk typing on a laptop, documents and a coffee cup on the desk, soft daylight from a window, realistic photograph",
    "Wide shot of a dim home office at night, a developer sitting at a desk in front of the soft glow of a monitor, warm desk lamp, city lights outside the window, realistic photograph",
    "Wide shot inside a bright restaurant, a person holding a smartphone while deciding what to order, a plate and a glass on the table, friends nearby, warm light, realistic photograph",
    "Wide shot of a cozy living room at dusk, warm lights turned on, a floor lamp and a sofa with cushions, city view through the window, realistic photograph",
    "Medium shot of a family sitting together on a living room sofa watching television, warm cozy light, a bowl of popcorn on the table, realistic photograph",
    "Wide shot of a person sitting on a bed at night looking at a tablet, warm bedside lamp, soft shadows, realistic photograph",
    "Medium shot of an elderly woman in a bright kitchen holding a weekly pill organizer, a smartphone lying on the table, warm daylight, realistic photograph",
    "Wide shot of an elderly man and a small child sitting on a living room floor facing a fabric smart speaker on a low table, bookshelves behind them, warm daylight, realistic photograph",
    "Aerial wide shot of a city at night, warm lit windows in residential buildings, streets with gentle light trails, cinematic realistic photograph",
]

MOTION_PROMPTS = [
    "The speaker glow gently pulses, the curtains sway slightly, very slow camera push-in, realistic natural motion",
    "The woman walks steadily forward and glances at her phone, natural body motion, slight camera follow",
    "The man turns his head slightly and blinks, gentle breathing, subtle camera push-in, realistic",
    "The worker types naturally with slight shoulder movement, soft camera drift, realistic",
    "The developer types and reaches for the mouse, screen glow flickers softly, slow push-in, realistic",
    "The person looks at the phone and shifts slightly, gentle steam rises from the plate, subtle camera move",
    "Warm lights fade on, the curtains move gently, slow camera dolly forward, realistic",
    "Family members shift naturally and smile, slight camera drift, realistic",
    "The person swipes the tablet slowly, gentle head movement, warm lamp flicker, realistic",
    "The elderly woman lifts a pill and places it in the organizer, gentle hand motion, subtle camera move",
    "The elderly man and the child turn toward the speaker, gentle natural motion, slight camera push-in",
    "Slow aerial push-in over the city, subtle light trails moving, cinematic realistic",
]


def cfg():
    s = (ROOT / "config.toml").read_text(encoding="utf-8")

    def val(k):
        m = re.search(rf'^{re.escape(k)}\s*=\s*"(.*)"\s*$', s, re.M)
        return m.group(1) if m else ""

    return val("oneapi_base_url").rstrip("/"), val("oneapi_api_key")


def api(method, url, key, payload=None, timeout=90):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:  # noqa: BLE001
        return "ERR", f"{type(e).__name__}: {e}"


def num_frames_for(sec):
    n = math.ceil((sec * FPS_SRC - 1) / 8)
    return 8 * n + 1


def main() -> int:
    STILLS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    base, key = cfg()
    root = base.replace("/v1", "")
    frames = json.loads((WORK / "timeline.json").read_text(encoding="utf-8"))["frames"]
    ffmpeg = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    last_create = 0.0

    for i in range(1, 13):
        seg = f"seg{i:02d}"
        still = STILLS / f"{seg}.png"
        raw = RAW / f"{seg}.mp4"
        if raw.exists():
            print(f"[{i}/12] {seg} 已存在，跳过", flush=True)
            continue
        slot = frames[i - 1] / 30.0
        nf = num_frames_for(slot)
        print(f"[{i}/12] {seg} 槽位={slot:.2f}s num_frames={nf}", flush=True)
        ent = state.get(seg, {})

        # 1) fresh first frame (so its URL is valid for the video task)
        if not still.exists() or not ent.get("image_url"):
            st, b = api("POST", base + "/images/generations", key,
                        {"model": "agnes-image-2.5-flash", "prompt": STILL_PROMPTS[i - 1], "n": 1, "size": "720x1280"})
            if st != 200:
                print(f"    still failed: {st} {b}", flush=True)
                continue
            ent["image_url"] = b["data"][0]["url"]
            data = urllib.request.urlopen(
                urllib.request.Request(ent["image_url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=180
            ).read()
            still.write_bytes(data)
            state[seg] = ent
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    still ok ({len(data)//1024} KB)", flush=True)

        # 2) image-to-video task
        vid = ent.get("video_id")
        if not vid:
            gap = MIN_GAP - (time.time() - last_create)
            if gap > 0:
                time.sleep(gap)
            payload = {
                "model": "agnes-video-v2.0",
                "prompt": MOTION_PROMPTS[i - 1],
                "negative_prompt": NEG,
                "image": ent["image_url"],
                "mode": "ti2vid",
                "width": 720, "height": 1280,
                "num_frames": nf, "frame_rate": FPS_SRC,
                "num_inference_steps": 30,
            }
            for attempt in range(1, 20):
                st, b = api("POST", root + "/v1/videos", key, payload)
                vid = b.get("video_id") if isinstance(b, dict) else None
                if vid:
                    break
                print(f"    create {attempt}: {st} {b.get('code') if isinstance(b,dict) else b}", flush=True)
                time.sleep(60)
            if not vid:
                print("    give up on this segment", flush=True)
                continue
            last_create = time.time()
            ent["video_id"] = vid
            state[seg] = ent
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    task created: {vid[-20:]}", flush=True)

        # 3) poll + download
        url = ent.get("url")
        if not url:
            for _ in range(120):
                time.sleep(10)
                st, b = api("GET", f"{root}/agnesapi?video_id={vid}", key)
                s = str(b.get("status", "") if isinstance(b, dict) else "?").lower()
                if s in {"completed", "succeeded", "success", "done"}:
                    url = b.get("url"); break
                if s in {"failed", "error", "cancelled"}:
                    print(f"    FAILED: {json.dumps(b, ensure_ascii=False)[:200]}", flush=True); break
            if not url:
                print("    no url, skip", flush=True); continue
            ent["url"] = url; state[seg] = ent
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        d = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=300).read()
        raw.write_bytes(d)
        print(f"    downloaded {len(d)//1024} KB", flush=True)

    (WORK / "v2_done.txt").write_text("ok", encoding="utf-8")
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

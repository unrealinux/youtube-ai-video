#!/usr/bin/env python3
"""Agnes AI media driver for the "AI Bathroom, Made Real" production.

Wraps `agnes-ai-cli` with retries (Agnes returns transient 503 "image queue is
full"), downloads the finished asset, and appends a URL->file manifest row.

  agnes.py image <out.png> <prompt> [ref.png ...]
  agnes.py video <out.mp4> <ref.png> <prompt> [--frames N] [--fps N] [--size WxH]
  agnes.py fetch <out> <url>
  agnes.py selftest
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "manifest.jsonl"
RETRIES = int(os.environ.get("AGNES_RETRIES", "6"))
TRANSIENT = ("queue is full", "HTTP 503", "HTTP 502", "HTTP 429", "ECONNRESET",
             "fetch failed", "timed out", "Service Unavailable")


def api_key() -> str:
    key = os.environ.get("AGNES_API_KEY")
    if key:
        return key
    path = Path(os.environ.get("AGNES_KEY_FILE", Path.home() / ".config/agnes/key"))
    return path.read_text().strip()


def cli(*args: str) -> dict:
    """Run agnes-ai-cli and return its JSON. Retries transient failures."""
    env = {**os.environ, "AGNES_API_KEY": api_key()}
    last = ""
    for attempt in range(1, RETRIES + 1):
        proc = subprocess.run(
            ["npx", "-y", "agnes-ai-cli", *args, "--json"],
            capture_output=True, text=True, env=env, timeout=2400,
        )
        blob = proc.stdout.strip() or proc.stderr.strip()
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            # CLI prints progress lines before the JSON object; take the last one.
            data = None
            for chunk in reversed(blob.split("\n{")):
                try:
                    data = json.loads(("{" + chunk) if not chunk.startswith("{") else chunk)
                    break
                except json.JSONDecodeError:
                    continue
            if data is None:
                raise RuntimeError(f"agnes {' '.join(args)}: unparseable output:\n{blob}")
        if data.get("ok") is not False and not data.get("error"):
            return data
        last = json.dumps(data.get("error") or data)[:300]
        if attempt < RETRIES and any(t.lower() in last.lower() for t in TRANSIENT):
            wait = attempt * 15 + random.randint(0, 5)
            print(f"  retry {attempt}/{RETRIES} in {wait}s: {last}", file=sys.stderr)
            time.sleep(wait)
            continue
        raise RuntimeError(f"agnes {' '.join(args)} failed: {last}")
    raise RuntimeError(f"agnes {' '.join(args)} exhausted retries: {last}")


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=300) as r, open(out, "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
            if out.stat().st_size == 0:
                raise RuntimeError("empty download")
            return
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            if attempt == 3:
                raise RuntimeError(f"download failed {url}: {exc}") from exc
            time.sleep(5 * attempt)


def record(kind: str, source: str, out: Path, url: str) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    resolved = Path(out).resolve()
    shown = str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(out)
    with open(MANIFEST, "a") as f:
        f.write(json.dumps({
            "kind": kind, "source": source, "out": shown,
            "url": url, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }) + "\n")


def image_direct(out: Path, prompt: str, refs: list[str], model: str) -> None:
    """Call the Agnes image API directly.

    Needed for agnes-image-2.5-flash, which the pinned agnes-ai-cli does not know
    about, and because the CLI's upload bridge is an extra failure point. Reference
    images travel as inline data URLs, which the service accepts.
    """
    import base64
    import mimetypes
    import urllib.request

    body: dict = {"model": model, "prompt": prompt, "size": "1080x1920"}
    if refs:
        encoded = []
        for ref in refs:
            mime = mimetypes.guess_type(ref)[0] or "image/png"
            b64 = base64.b64encode(Path(ref).read_bytes()).decode()
            encoded.append(f"data:{mime};base64,{b64}")
        body["extra_body"] = {"image": encoded}
    req = urllib.request.Request(
        "https://apihub.agnes-ai.com/v1/images/generations",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
    )
    last = ""
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.load(r)
            url = data["data"][0]["url"]
            download(url, out)
            record(f"image:{model}", prompt, out, url)
            print(f"image -> {out}")
            return
        except Exception as exc:  # noqa: BLE001 - retry transport and 5xx alike
            last = str(exc)
            if attempt < RETRIES:
                wait = min(attempt * 15, 90)
                print(f"  retry {attempt}/{RETRIES} in {wait}s: {last[:120]}", file=sys.stderr)
                time.sleep(wait)
    raise RuntimeError(f"direct image failed: {last}")


def image(out: Path, prompt: str, refs: list[str]) -> None:
    if refs:
        args = ["image", "img2img", "--image", refs[0], "--prompt", prompt, "--size", "1080x1920"]
    else:
        args = ["image", "text2img", "--prompt", prompt, "--size", "1080x1920"]
    data = cli(*args)
    url = data["url"]
    download(url, out)
    record("image", prompt, out, url)
    print(f"image -> {out}")


def video(out: Path, ref: str, prompt: str, frames: int, fps: int, size: str) -> None:
    w, h = size.split("x")
    data = cli("video", "img2video", "--image", ref, "--prompt", prompt,
               "--num-frames", str(frames), "--frame-rate", str(fps),
               "--width", w, "--height", h)
    vid = data.get("videoId") or data.get("taskId")
    print(f"  submitted {vid}", file=sys.stderr)
    data = cli("video", "poll", vid, "--interval", "10", "--timeout", "1800")
    url = data.get("videoUrl") or data.get("url")
    if not url:
        raise RuntimeError(f"no videoUrl in {data}")
    download(url, out)
    record("video", prompt, out, url)
    print(f"video -> {out}")


def stills(only: list[str], workers: int, model: str) -> None:
    """Generate every missing shot still from shots.json."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    spec = json.loads((ROOT / "shots.json").read_text())
    anchor = str(ROOT / "assets/persona/persona-key-v1.png")
    todo = []
    for shot in spec["shots"]:
        if only and shot["id"] not in only:
            continue
        out = ROOT / "assets" / "shots" / f"{shot['id']}.png"
        if out.exists():
            print(f"skip {shot['id']} (exists)")
            continue
        prompt = " ".join([spec["persona"], shot["prompt"]] if shot.get("persona") else [shot["prompt"]])
        prompt = f"{prompt} {spec['env']}"
        refs = [anchor] if shot.get("persona") else []
        todo.append((shot["id"], out, prompt, refs))
    if not todo:
        print("nothing to do")
        return
    generate = (lambda o, p, r: image_direct(o, p, r, model)) if model else image
    print(f"generating {len(todo)} stills with {workers} workers" +
          (f" via {model}" if model else ""))
    failed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(generate, out, prompt, refs): sid for sid, out, prompt, refs in todo}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                fut.result()
            except Exception as exc:  # noqa: BLE001 - report and continue
                failed.append(sid)
                print(f"FAILED {sid}: {exc}", file=sys.stderr)
    if failed:
        print(f"\n{len(failed)} failed: {' '.join(sorted(failed))}\nre-run the same command to retry them")


def selftest() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "t.png"
        image(out, "A single red apple on a white table, product photo", [])
        head = out.read_bytes()[:8]
        assert head == b"\x89PNG\r\n\x1a\n", f"not a PNG: {head!r}"
        print(f"selftest PASS: {out.stat().st_size} bytes")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:]
    if cmd == "image":
        image(Path(rest[0]), rest[1], rest[2:])
    elif cmd == "video":
        opts = {"frames": 121, "fps": 24, "size": "720x1280"}
        args = list(rest)
        for flag in list(opts):
            if f"--{flag}" in args:
                i = args.index(f"--{flag}")
                opts[flag] = int(args[i + 1].split("x")[0]) if flag != "size" else args[i + 1]
                del args[i:i + 2]
        video(Path(args[0]), args[1], args[2], opts["frames"], opts["fps"], opts["size"])
    elif cmd == "stills":
        workers, model = 2, ""
        args = list(rest)
        for flag in ("--workers", "--model"):
            if flag in args:
                i = args.index(flag)
                if flag == "--workers":
                    workers = int(args[i + 1])
                else:
                    model = args[i + 1]
                del args[i:i + 2]
        stills(args, workers, model)
    elif cmd == "fetch":
        download(rest[1], Path(rest[0]))
    elif cmd == "selftest":
        selftest()
    else:
        print(__doc__)
        sys.exit(2)

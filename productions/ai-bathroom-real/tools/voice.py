#!/usr/bin/env python3
"""Gemini TTS voiceover for "AI Bathroom, Made Real".

Reads voice.json, writes one 24 kHz mono WAV per line to assets/voice/,
and records each line's real duration in assets/voice/timings.json.

  voice.py            generate every missing line
  voice.py A1 C2      generate only those ids
  voice.py --test A1  generate one line and print its duration
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RATE = 24000
BYTES_PER_SECOND = RATE * 2  # 16-bit mono


def api_key() -> str:
    key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_GENERATIVE_AI_API_KEY is not set")
    return key


def synth(text: str, model: str, voice: str, style: str) -> bytes:
    body = json.dumps({
        "contents": [{"parts": [{"text": f"{style}: {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }).encode()
    req = urllib.request.Request(
        API.format(model=model), data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key()},
    )
    last = ""
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
        except urllib.error.HTTPError as exc:
            last = exc.read().decode(errors="replace")[:300]
            if exc.code in (429, 500, 503) and attempt < 5:
                wait = attempt * 20
                print(f"  http {exc.code}, retry in {wait}s: {last[:120]}", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"TTS HTTP {exc.code}: {last}") from exc
        if "error" in data:
            raise RuntimeError(f"TTS error: {json.dumps(data['error'])[:300]}")
        return base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    raise RuntimeError(f"TTS exhausted retries: {last}")


def synth_say(text: str, voice: str, rate: int, out: Path) -> float:
    """macOS `say` fallback: writes the WAV directly and returns its duration."""
    import shutil
    import tempfile
    if not shutil.which("say"):
        raise RuntimeError("macOS `say` is not available")
    ffmpeg = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "line.aiff"
        subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text],
                       check=True, timeout=120)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(aiff),
                        "-ar", str(RATE), "-ac", "1", str(out)], check=True, timeout=120)
    with wave.open(str(out), "rb") as w:
        return w.getnframes() / w.getframerate()


def write_wav(pcm: bytes, out: Path) -> float:
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return len(pcm) / BYTES_PER_SECOND


def main() -> None:
    spec = json.loads((ROOT / "voice.json").read_text())
    out_dir = ROOT / "assets" / "voice"
    timings_path = out_dir / "timings.json"
    timings = json.loads(timings_path.read_text()) if timings_path.exists() else {}
    args = list(sys.argv[1:])
    test = "--test" in args
    engine = "gemini"
    if "--engine" in args:
        i = args.index("--engine")
        engine = args[i + 1]
        del args[i:i + 2]
    only = [a for a in args if not a.startswith("--")]
    say_voice = spec.get("sayVoice", "Samantha")
    say_rate = int(spec.get("sayRate", 195))

    total_target = 0.0
    for line in spec["lines"]:
        if only and line["id"] not in only:
            continue
        out = out_dir / f"{line['id']}.wav"
        if out.exists() and not test:
            timings.setdefault(line["id"], {})
            timings[line["id"]]["seconds"] = round(
                out.stat().st_size / (BYTES_PER_SECOND + 44), 3)
            total_target += line["target"]
            print(f"skip {line['id']} (exists)")
            continue
        if engine == "say":
            seconds = synth_say(line["text"], say_voice, say_rate, out)
        else:
            pcm = synth(line["text"], spec["model"], spec["voice"], spec["style"])
            seconds = write_wav(pcm, out)
        timings[line["id"]] = {"seconds": round(seconds, 3), "target": line["target"],
                               "text": line["text"]}
        total_target += line["target"]
        drift = seconds - line["target"]
        print(f"{line['id']}: {seconds:.2f}s (target {line['target']:.2f}s, {drift:+.2f}s)  {line['text'][:52]}")
        time.sleep(1.2)

    if len(timings) == len(spec["lines"]):
        spoken = sum(v["seconds"] for v in timings.values())
        print(f"\ntotal spoken {spoken:.2f}s vs target {spec['targetTotal']:.2f}s  ({spoken - spec['targetTotal']:+.2f}s)")
    out_dir.mkdir(parents=True, exist_ok=True)
    timings_path.write_text(json.dumps(dict(sorted(timings.items())), indent=2))


if __name__ == "__main__":
    main()

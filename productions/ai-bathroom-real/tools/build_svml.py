#!/usr/bin/env python3
"""Emit the Hypit composition for "AI Bathroom, Made Real" from the shot list
and the measured voiceover durations.

  build_svml.py            writes styles.svs, authors/main.svml, runs/build.svrun
  build_svml.py --dry-run  prints the timing plan without writing
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAD = {"persona": 1.1, "broll": 0.55, "silent": 0.0}
DEFAULT_SHOT = 1.0

MOTIONS = [
    ("m-push", '<visual:Pose at="start" scale="1.02" easing="ease-out"/>\n'
               '            <visual:Pose at="end" scale="1.12"/>'),
    ("m-pull", '<visual:Pose at="start" scale="1.12" easing="ease-out"/>\n'
               '            <visual:Pose at="end" scale="1.02"/>'),
    ("m-pan-l", '<visual:Pose at="start" x="34" scale="1.14" easing="ease-out"/>\n'
                '            <visual:Pose at="end" x="-34" scale="1.14"/>'),
    ("m-pan-r", '<visual:Pose at="start" x="-34" scale="1.14" easing="ease-out"/>\n'
                '            <visual:Pose at="end" x="34" scale="1.14"/>'),
    ("m-drift", '<visual:Pose at="start" y="26" scale="1.13" easing="ease-out"/>\n'
                '            <visual:Pose at="end" y="-26" scale="1.13"/>'),
]


def frame_count(seconds: float, fps: int) -> int:
    return max(1, round(seconds * fps))


def plan(fps: int) -> list[dict]:
    shots = json.loads((ROOT / "shots.json").read_text())["shots"]
    timings = json.loads((ROOT / "assets/voice/timings.json").read_text())
    rows, cursor = [], 0
    for i, shot in enumerate(shots):
        sid = shot["id"]
        if sid in timings:
            vo = timings[sid]["seconds"]
            kind = "persona" if shot.get("persona") else "broll"
            dur = max(vo + PAD[kind], DEFAULT_SHOT + PAD[kind])
        else:
            vo, dur = 0.0, DEFAULT_SHOT
        start_f = cursor
        end_f = cursor + frame_count(dur, fps)
        rows.append({
            "id": sid, "vo": vo, "dur": dur, "kind": "persona" if shot.get("persona") else "broll",
            "start_f": start_f, "end_f": end_f, "overlay": shot.get("overlay"),
            "motion": MOTIONS[i % len(MOTIONS)][0],
        })
        cursor = end_f
    return rows


def secs(frames: int, fps: int) -> str:
    return f"{frames}f"


def build(rows: list[dict], fps: int) -> tuple[str, str]:
    total_f = rows[-1]["end_f"]

    media_images = "\n".join(
        f'  <media:Image id="img-{r["id"]}" src="../assets/shots/{r["id"]}.png"/>' for r in rows)
    media_voice = "\n".join(
        f'  <media:Audio id="vo-{r["id"]}" src="../assets/voice/{r["id"]}.wav"/>'
        for r in rows if r["vo"])
    windows = "\n".join(
        f'    <time:Window id="win-{r["id"]}" from="{secs(r["start_f"], fps)}" until="{secs(r["end_f"], fps)}"/>'
        for r in rows)
    normalizes = "\n".join(
        f'  <mediaop:Normalize id="vonorm-{r["id"]}" source={{vo-{r["id"]}}} video="none" audio="default"\n'
        f'    span-authority="audio" clock={{clock}}/>'
        for r in rows if r["vo"])
    clips = "\n".join(
        f'    <visual:Clip id="clip-{r["id"]}" image={{img-{r["id"]}}} extent={{shotExtent}}\n'
        f'      during={{program.win-{r["id"]}}} frame={{full}} fit="cover" z="10" motion={{{r["motion"]}}}/>'
        for r in rows)
    audio_clips = "\n".join(
        f'    <audio:Clip id="acl-{r["id"]}" source={{vonorm-{r["id"]}.media}} during={{program.win-{r["id"]}}}/>'
        for r in rows if r["vo"])

    labelled = [r for r in rows if r["overlay"]]
    labels = "\n".join(
        f'  <text:Flow id="lbl-{r["id"]}" timeline={{program.timeline}} within={{labelFrame}}\n'
        f'    style={{labelStyle}} z="60" align="center" block-align="center"\n'
        f'    during={{program.win-{r["id"]}}}>{r["overlay"]}</text:Flow>'
        for r in labelled)
    label_tracks = "\n".join(
        f'    <film:Track source={{lbl-{r["id"]}.visual}}/>' for r in labelled)

    motions = "\n".join(
        f'  <visual:Motion id="{name}">\n            {poses}\n  </visual:Motion>'
        for name, poses in MOTIONS)

    svml = f'''<?svml using="@hypit/markup@1"?>
<svml>
  <import as="time" from="@hypit/timeline-author@1"/>
  <import as="space" from="@hypit/spatial@1"/>
  <import as="media" from="@hypit/media@1"/>
  <import as="mediaop" from="@hypit/media-operations@1"/>
  <import as="visual" from="@hypit/visual-track@1"/>
  <import as="audio" from="@hypit/audio-track@1"/>
  <import as="text" from="@hypit/text-fine@1"/>
  <import as="fonts" from="@hypit/fontsource@1"/>
  <import as="film" from="@hypit/film@1"/>
  <import as="html" from="@hypit/html-video@1"/>
  <import as="style" source="../styles.svs"/>

  <time:Clock id="clock" frame-rate="{fps}"/>
  <space:Canvas id="vertical" width="1080" height="1920"/>
  <space:Frame id="full" within={{vertical.bounds}} left="0px" top="0px" right="100%" bottom="100%"/>
  <space:Frame id="labelFrame" within={{vertical.bounds}} left="5%" top="6%" right="95%" bottom="36%"/>
  <space:Extent id="shotExtent" width="736" height="1312"/>

  <fonts:Face id="face" package="@fontsource-variable/inter" weight="800" style="normal"/>
  <media:FontStack id="font" primary={{face}}/>
  <text:Style id="labelStyle" recipe={{style.text.label}} font={{font}}>
    <text:Fill color="#FFE24B"/>
    <text:Shadow color="#000000" x="0" y="5" blur="9"/>
  </text:Style>

{motions}

{media_images}

{media_voice}

{normalizes}

  <time:Timeline id="program" clock={{clock}} end="{secs(total_f, fps)}">
{windows}
  </time:Timeline>

  <visual:Track id="picture" timeline={{program.timeline}}>
{clips}
  </visual:Track>

  <audio:Track id="voice" timeline={{program.timeline}}>
{audio_clips}
  </audio:Track>

{labels}

  <film:Film id="main" canvas={{vertical.canvas}} timeline={{program.timeline}} appearance={{style.film.main}}>
    <film:Track source={{picture.visual}}/>
    <film:Track source={{voice.audio}}/>
{label_tracks}
  </film:Film>

  <html:Video id="final" composition={{main.composition}} timeline={{program.timeline}}/>
</svml>
'''

    styles = '''<?svml using="@hypit/recipe@1"?>
<sheet version="1">
  film.main { background: #101014; }
  text.label { size: 68; weight: 800; line-height: 1.06; tracking: 0; }
</sheet>
'''

    run = '''<?svml using="@hypit/markup/run@1"?>

<svrun version="1">
  <author source="../authors/main.svml"/>
  <target output="final.video"/>
</svrun>
'''
    return svml, styles, run


def main() -> None:
    fps = 30
    rows = plan(fps)
    svml, styles, run = build(rows, fps)
    total = rows[-1]["end_f"] / fps
    spoken = sum(r["vo"] for r in rows)
    print(f"{len(rows)} shots, {total:.1f}s total, {spoken:.1f}s spoken, "
          f"{len([r for r in rows if r['overlay']])} overlays")
    for r in rows:
        print(f"  {r['id']:<3} {r['kind']:<8} vo {r['vo']:5.2f}s  shot {r['dur']:5.2f}s  "
              f"{r['start_f']:>5}–{r['end_f']:<5}f  {r['motion']:<7} {r['overlay'] or ''}")
    if "--dry-run" in sys.argv:
        return
    (ROOT / "styles.svs").write_text(styles)
    (ROOT / "authors").mkdir(exist_ok=True)
    (ROOT / "authors/main.svml").write_text(svml)
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs/build.svrun").write_text(run)
    print("\nwrote styles.svs, authors/main.svml, runs/build.svrun")


if __name__ == "__main__":
    main()

# Progress — AI Bathroom, Made Real

## State: delivered (v1)

Finished 96-second English vertical short at
`output/ai-bathroom-real.mp4` (1080×1920, 30 fps, 95.8 s, audio present).
Built as `bld_20261015T094007084Z_A8770748BA`, target Output `final.video`.

## What exists

| Path | What it is |
| --- | --- |
| `BRIEF.md` | the user's goal and settled choices |
| `TREATMENT.md` | the creative answer, including why the piece is stills-led |
| `SCRIPT.md` | the 32-shot English beat sheet |
| `shots.json` | shot list: persona/broll, image prompt, overlay label |
| `voice.json` | the 31 voiceover lines and the voice settings used |
| `authors/main.svml` | the whole composition (generated — do not hand-edit) |
| `runs/build.svrun` | one Run against `authors/main.svml` |
| `styles.svs` | the label typography and film background recipes |
| `tools/build_svml.py` | reads `shots.json` + voice timings, writes the SVML/SVS/Run |
| `tools/agnes.py` | Agnes image generation with retries, manifest and a direct-API path |
| `tools/voice.py` | Gemini TTS (`--engine gemini`) and macOS `say` (`--engine say`) |
| `assets/shots/*.png` | 32 generated stills (736×1312) |
| `assets/persona/` | the identity anchor used by every persona shot |
| `assets/voice/*.wav` | the 31 voiceover lines |
| `review/` | the opening-to-close frame grid and label checks actually used |

`authors/main.svml` is **generated**. Change `shots.json`, `voice.json`, or
`tools/build_svml.py`, re-run the builder, then `hypit build`.

## How to rebuild

```bash
python3 productions/ai-bathroom-real/tools/build_svml.py
hypit build productions/ai-bathroom-real/runs/build.svrun
hypit get <build-id> --output final.video --to productions/ai-bathroom-real/output/ai-bathroom-real.mp4
```

## Known limits

- **Voice is macOS `say`** (Samantha, rate 195). Clear but synthetic. The user's intended
  upgrade is a voice from the Voicebox app; regenerating `assets/voice/*.wav` and re-running
  the builder is the whole change — the composition does not move.
- **No AI video.** Agnes video is rate-limited to a paid tier; HypiHub has no credits; the Google
  key has no Veo models. The piece is designed to work without it (see TREATMENT.md).
- **The label stroke paint is unusable.** `text:Stroke` renders over the glyph interior and turns
  the label solid black regardless of `placement`. Labels therefore use `Fill` + `Shadow` only.
  Do not reintroduce a Stroke without re-testing.
- **Agnes congestion.** The image queue returned `503 / image queue is full` for hours. `tools/agnes.py`
  retries, and `image_direct` with `agnes-image-2.5-flash` plus a downscaled reference
  (`assets/persona/persona-anchor-small.png`) got through when the CLI's model did not.

## Open, not blocking

- `.gitignore` covers `*.mp4` but not the 57 MB of shot PNGs or `node_modules/`. Add patterns
  before committing if the media should stay out of history.
- Music was never added; the reference has no obvious bed either.
- Any still can be replaced by a moving clip later at the same Timeline position.

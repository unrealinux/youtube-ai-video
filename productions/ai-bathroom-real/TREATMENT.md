# Treatment — AI Bathroom, Made Real

## What the piece is

A 96-second English vertical short that keeps the reference's engine — *promise a makeover,
deliver a funny failure, hand the problem to the audience* — and rebuilds it as a stills-led
**"AI slideshow"** short: 32 generated photographs, each held on screen with its own slow camera
move, cut to a rapid voiceover, with the reference's loud label typography over the top.

## Why stills, not generated video

The selected services cannot reach AI video on this machine today (Agnes is rate-limited to a free
tier, HypiHub has no credits, the Google key has no Veo models). Rather than stop, the piece is
designed to be strong as stills: the reference's own energy comes mostly from **cuts, labels and
reaction shots**, not camera movement. Slow push/pull/pan on each still plus hard cuts reproduces
that rhythm at zero generation cost. Moving footage can be added later by replacing a still with a
video clip at the same Timeline position — the composition does not change.

## The director's choices

- **Persona.** One AI-generated woman, anchored to `assets/persona/persona-key-v1.png` and reused
  as an image reference for all 14 of her shots, so her face, freckles, auburn hair and denim shirt
  stay identical across the piece. She is cheerful and game, never winking at the camera; the comedy
  comes from her confidence running ahead of her competence.
- **The room.** Every shot repeats the same grimy 1990s bathroom (beige tiles, stained toilet,
  small window) so the improvised build reads as one continuous place.
- **The AI render** (`A2`) is deliberately glossy and perfect — a different visual world from every
  other shot. This contrast is the whole joke, so the cut between `A1` (her face) and `A2` (the
  render) is where the piece wins or loses.
- **Camera.** Each still gets one continuous move — push, pull, or lateral drift — varied in a fixed
  cycle so no two neighbours move the same way.
- **Labels.** Eleven beats carry a heavy Inter 800 label in yellow with a black outline and shadow,
  top-third, entered as a cut (no fade), matching the reference's CapCut-style text.
- **Voice.** Fast, dry, first-person. Every line is a claim, a complaint, or a verdict; no
  description. Silence is used once, at `C5`, where the concrete block lands.
- **Ending.** Verbatim in function to the reference: the result is shown, then immediately undercut,
  then the audience is asked for the fix.

## What is not solved here

- The voice is macOS `say`, so it is clear but synthetic. Swapping in a cloned/designed voice means
  regenerating `assets/voice/*.wav` and re-running the builder — no composition change.
- No lip sync. She is never shown mid-sentence in close-up; her shots are reactions and gestures,
  and the voiceover carries the words.

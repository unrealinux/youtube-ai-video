# Brief — AI Bathroom, Made Real (English clone)

## The user's goal

Produce a new vertical short that **clones the form and premise** of the reference
`references/bikin-kamar-mandi-ai/` ("Bikin Kamar Mandi AI Jadi Nyata", Irene Suwandi), but is its own
piece: **English language**, **an AI-generated virtual creator** (not the reference's real person),
**~95–100 seconds**, 1080×1920.

## Settled choices (user, this session)

| Choice | Value |
| --- | --- |
| Premise | Same: a creator tries to recreate an AI-designed space in real life; the build fails comedically and the ending asks the audience for suggestions |
| Language | English |
| On-camera person | AI-generated virtual creator with a consistent identity across shots |
| Length | ~95–100 s |
| Service | HypiHub (`hypihub.default`, OAuth) |
| Reference archive | `references/bikin-kamar-mandi-ai/` (source.mp4 + ANALYSIS.md + TIMELINE.md) |

## Intended viewer response

Entertainment through a counter-intuitive failure: the viewer expects a satisfying makeover and gets
a relatable, funny failure. The open ending ("how do I fix this?") invites comments.

## Constraints

- 9:16 vertical, 1080×1920, ~30 fps, English captions/overlays in the reference's loud label style.
- The reference's structure and beat timing are the guide; the person, words and props are new.
- No face/lip-sync model is available on the selected Endpoint: the creator appears in
  reaction/action shots, and speech is carried as voiceover narration (Voice Design).

## Paid scope — as executed

**Nothing was paid for.** The user refused HypiHub (no credits) and its alternatives were closed:
Agnes video is rate-limited to a Token Plan, HypiHub transcription returned HTTP 402, and the Google
key has no Veo video models. Actual routes used:

| Work | Route | Cost |
| --- | --- | --- |
| 32 shot stills | Agnes images (free tier, `agnes-image-2.1-flash` / `2.5-flash`) | $0 |
| Voiceover | macOS `say` (Samantha, rate 195) | $0 |
| Composition + render | Hypit, all 65 requests local (`html.local`, `media.local`) | $0 |
| Reference transcription | never obtained (HypiHub had no credits) | $0 |

The user's chain was: HypiHub → BYOK → Agnes → stills-only. The delivered piece is a stills-led
variant of the reference. A voice upgrade (Voicebox) was explicitly deferred to after v1.

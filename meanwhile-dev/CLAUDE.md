# meanwhile.dev: production tools

Every new episode uses Chatterbox and post.js by default; MMAudio only on request. They live in `tools/` and `assets/` at the
project root; copy them into each new `videos/<ep>/` folder when you set it up.
Setup notes and examples: `tools/ADDONS.md`.

## Narration: Chatterbox (`tools/narrate.py`)
- Write the script as `videos/<ep>/narration.json` and generate it with
  `python3 tools/narrate.py narration.json`. Don't use HeyGen unless I ask for Hugh.
- Narrator voice: `voices/narrator.wav` if it exists, otherwise Chatterbox's built-in voice.
- Narrator lines: exaggeration 0.4, cfg_weight 0.5. Dev's reactions ("Arreh? Uh-oh."):
  exaggeration 0.9–1.1, cfg_weight 0.3.
- `timing.py` must read line lengths from `assets/voice/lines.json`, never hard-coded durations.

## Sound effects: MMAudio (`tools/foley.py`)
- When I ask for it: after the first rough render, list cues of 8 s or less in `videos/<ep>/foley.json` for moments
  with on-screen motion (impacts, animals, textures). Run
  `python3 tools/foley.py foley.json --video <rough render>`.
- Keep `sfx.py` for exact beat hits; mix the foley files in from `assets/sfx/foley.json` (start times).
- Narration stays at least 17 dB above effects. Measure it before rendering.
- **MMAudio: OFF.** It is slow and RAM-heavy on this Mac, and its weights are non-commercial.
  Only use `tools/foley.py` when I ask for it on a specific moment, and then with
  `--variant small_44k` on a single cue of 5 s or less.

## Lens effects: pmndrs/postprocessing (`assets/post.js`)
- Add `"postprocessing": "https://cdn.jsdelivr.net/npm/postprocessing@6.35.5/build/index.js"`
  to the importmap (6.35.x matches three r160), and render with `post.render(t)` instead of
  `renderer.render(scene, camera)`.
- Use depth of field on every shot (bokeh 6–10, range on the scene's scale, e.g. 0.002 at carpet
  size), with rack focus on reveals. Bloom for glowing things. Chromatic aberration only for
  dizzy or woozy beats.
- Don't use `logarithmicDepthBuffer`, because it breaks depth of field.
- Check the storyboard stills with and without effects, and keep the brand teal background looking right.

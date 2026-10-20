# meanwhile.dev add-ons

Three free open-source tools wired for the Dev reels pipeline (`videos/<episode>/` with
`tools/timing.py`, `tools/sfx.py`, `assets/scene.js`). Copy the files into the project:

| File | Copy to | What it does |
|---|---|---|
| `tools/narrate.py` | `videos/<ep>/tools/` (or a shared `tools/`) | Narration with [Chatterbox](https://github.com/resemble-ai/chatterbox) |
| `tools/foley.py` | same | Sound effects that follow the picture, with [MMAudio](https://github.com/hkchengrex/MMAudio) |
| `assets/post.js` | `videos/<ep>/assets/` | Depth of field, bloom, vignette, chromatic aberration with [pmndrs/postprocessing](https://github.com/pmndrs/postprocessing) |
| `examples/` | anywhere | Sample `narration.json`, `foley.json`, and a demo page for `post.js` |

## 1. Narration: Chatterbox

A free, local narrator, so Dev no longer depends on the HeyGen allowance. It runs on Apple silicon (MPS).

```sh
pip install chatterbox-tts
python3 tools/narrate.py narration.json          # writes assets/voice/<id>.wav + assets/voice/lines.json
```

- **One voice for every episode:** record 10–20 s of a voice you have the rights to (yours, a friend's
  with permission) as `voices/narrator.wav` and set `"voice"` in `narration.json` (path relative to
  that file, e.g. `"../../voices/narrator.wav"` from `videos/<ep>/`). Don't clone Hugh
  or any other HeyGen voice.
- **Deadpan vs. panic:** `exaggeration` 0.3–0.5 for the dry narrator, 0.8–1.2 for Dev's
  "Arreh? Uh-oh." Lower `cfg_weight` to ~0.3 when you raise exaggeration, which keeps the pacing natural.
- **Only changed lines are regenerated.** Each line has a fixed seed, so re-running gives the same take;
  change `"seed"` on a line to get a different reading.
- `lines.json` holds each line's spoken length (silence trimmed). Have `timing.py` read it instead of
  hard-coded durations, so captions and beats move when a line gets longer:

  ```python
  import json
  LINES = json.load(open("assets/voice/lines.json"))
  dur = lambda i: LINES[i]["duration"]
  ```

- Chatterbox adds an inaudible watermark ("Perth") to everything it generates. It doesn't affect the sound.

## 2. Sound effects: MMAudio (optional, off by default)

> **Heavy on a Mac.** MMAudio is built for NVIDIA GPUs; on Apple silicon it runs on MPS, slowly, and
> the default `large_44k_v2` model needs ~6 GB of memory, which comes out of system RAM on a Mac.
> Use it only for a single hero moment, with `--variant small_44k` and a cue of 5 s or less.
> To uninstall: `rm -rf ~/MMAudio` (the code, its venv and the downloaded weights all live there).

MMAudio watches a stretch of the video and generates audio synced to what moves on screen:
the cat's swipe, the carpet fibres, the sneeze. It complements `sfx.py`, it doesn't replace it.
Keep the ffmpeg-synthesised hits for exact beats, and use MMAudio for texture.

```sh
git clone https://github.com/hkchengrex/MMAudio ~/MMAudio
cd ~/MMAudio && python3 -m venv .venv && .venv/bin/pip install torch torchvision torchaudio && .venv/bin/pip install -e .

# any quick render works; only the pictures are used
python3 tools/foley.py foley.json --video renders/preview.mp4
```

- Cues of up to ~8 s work best (that's what it was trained on). Split longer scenes.
- The default negative prompt (`speech, talking, voice, music`) stops it from inventing voices
  under the narration.
- `"video": false` on a cue makes it text-only, for sounds with nothing on screen to follow.
- It writes `assets/sfx/foley-<id>.wav` and `assets/sfx/foley.json` (start time per cue). To mix them
  in `sfx.py`, delay each one to its start:

  ```python
  import json
  for cue in json.load(open("assets/sfx/foley.json")).values():
      ms = int(cue["start"] * 1000)
      # ffmpeg filter input: f"adelay={ms}|{ms},volume=0.5"
  ```

  Then re-check the narration-over-effects margin as before. The ~17 dB margin from episode 3 is a good target.

> **Licence:** MMAudio's code is MIT, but its model weights are **CC-BY-NC 4.0 (non-commercial)**.
> That's fine for a hobby page. Once the page is monetised (bonuses, brand deals), switch these
> cues back to `sfx.py` or to a commercially licensed model.

## 3. Lens effects: pmndrs/postprocessing

Adds what a real camera does. Depth of field matters most for the scale gags: a shallow
focus is what makes a dust mite or a carpet fibre *feel* tiny.

Add to the importmap in `index.html` (6.35.x is the release line that supports three r160):

```json
"postprocessing": "https://cdn.jsdelivr.net/npm/postprocessing@6.35.5/build/index.js"
```

In `scene.js`, replace `renderer.render(scene, camera)` with `post.render(t)`:

```js
import { createPost } from './post.js';
const post = createPost(renderer, scene, camera, {
  dof: { focus: (t) => ({ target: t < 14 ? dev : cat, range: 0.3, bokeh: 8 }) },   // rack focus to the cat
  bloom: { intensity: 0.6 },                                                        // glowing pills, atoms
  chroma: { amount: (t) => (t > 58 ? 0.004 : 0.001) },                              // woozy at the end
});
```

- Every setting is a number or a function of `t`, so effects follow the beats. Rendering depends only on `t`,
  so HyperFrames frame-by-frame renders stay deterministic (tested: the same `t` gives identical pixels).
- `focus` takes either `target` (an Object3D to keep sharp) or `distance` (world units), plus `range`
  (in-focus depth, world units) and `bokeh` (blur strength; 6–10 shows at 1080×1920).
- For the shrinking episode the world is tiny (millimetres), so set `range` on that scale too, e.g.
  `range: 0.002` while Dev is in the carpet.
- If the renderer uses tone mapping, `post.js` re-applies it. A plain-colour `scene.background` comes
  out slightly darker than before (it now goes through tone mapping too); nudge the colour if the brand
  teal matters.
- Depth of field reads the depth buffer, so it doesn't work with `logarithmicDepthBuffer: true`
  (`post.js` warns if that's on). Scale the scene or move the camera near/far planes per beat instead.
- `examples/post-demo.html` shows it on stand-in shapes: serve the folder with `python3 -m http.server`,
  open `/examples/post-demo.html`, and add `?post=0` for the same frame without effects.

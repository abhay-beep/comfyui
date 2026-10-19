#!/usr/bin/env python3
"""Sound effects with MMAudio (hkchengrex/MMAudio): it watches a stretch of the reel and
generates audio that matches the motion on screen.

    python3 tools/foley.py foley.json --video renders/preview.mp4
    python3 tools/foley.py foley.json --video renders/preview.mp4 --only cat-hiss

foley.json:
    {
      "negative": "speech, talking, voice, music",     # default for every cue
      "cues": [
        {"id": "cat-hiss", "start": 12.8, "end": 15.2, "prompt": "a cat hissing and swiping"},
        {"id": "carpet",   "start": 16.0, "end": 23.0, "prompt": "rustling fibres, tiny footsteps"},
        {"id": "atom-hum", "start": 0, "end": 4, "prompt": "deep electric hum", "video": false}
      ]
    }

"video": false makes a cue text-only (nothing on screen to follow). Keep cues under ~8 s;
that is what MMAudio was trained on.

Writes <out>/foley-<id>.wav (44.1 kHz) plus <out>/foley.json with each cue's start time,
so tools/sfx.py can mix them in at the right place.

Setup once, in its own environment:
    git clone https://github.com/hkchengrex/MMAudio ~/MMAudio
    cd ~/MMAudio && python3 -m venv .venv && .venv/bin/pip install torch torchvision torchaudio && .venv/bin/pip install -e .
The model weights are CC-BY-NC 4.0 (non-commercial).
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

SR = 44100
MAX_LEN = 10.0


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cues", type=Path)
    ap.add_argument("--video", type=Path, help="a render of the reel (any quality; only its pictures are used)")
    ap.add_argument("--mmaudio", type=Path, default=Path(os.environ.get("MMAUDIO_DIR", "~/MMAudio")).expanduser())
    ap.add_argument("--python", help="interpreter with MMAudio installed (default: <mmaudio>/.venv/bin/python)")
    ap.add_argument("--variant", default="large_44k_v2")
    ap.add_argument("--out", type=Path, default=Path("assets/sfx"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="cue ids to regenerate")
    args = ap.parse_args()

    spec = json.loads(args.cues.read_text())
    demo = args.mmaudio / "demo.py"
    if not demo.exists():
        sys.exit(f"MMAudio not found at {args.mmaudio} (set --mmaudio or MMAUDIO_DIR)")
    py = args.python or str(args.mmaudio / ".venv/bin/python")
    if not Path(py).exists():
        py = sys.executable

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "foley.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    video_hash = hashlib.sha256(args.video.read_bytes()).hexdigest()[:16] if args.video else None

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, cue in enumerate(spec["cues"]):
            if args.only is not None and cue["id"] not in args.only:
                continue
            use_video = cue.get("video", True)
            if use_video and not args.video:
                sys.exit(f"{cue['id']}: needs --video (or set \"video\": false)")
            dur = round(cue["end"] - cue["start"], 3)
            if dur > MAX_LEN:
                print(f"warning: {cue['id']} is {dur}s; quality drops past ~8 s, consider splitting", file=sys.stderr)
            neg = cue.get("negative", spec.get("negative", "speech, talking, voice, music"))
            seed = cue.get("seed", 42 + i)
            key = hashlib.sha256(json.dumps([cue, neg, seed, args.variant, video_hash if use_video else None],
                                            sort_keys=True).encode()).hexdigest()[:16]
            wav = args.out / f"foley-{cue['id']}.wav"
            if not args.force and wav.exists() and manifest.get(cue["id"], {}).get("key") == key:
                continue

            cmd = [py, str(demo), "--variant", args.variant, "--duration", str(dur),
                   "--prompt", cue["prompt"], "--negative_prompt", neg, "--seed", str(seed),
                   "--output", str(tmp / cue["id"]), "--skip_video_composite"]
            if use_video:
                clip = tmp / f"{cue['id']}.mp4"
                run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", str(cue["start"]), "-t", str(dur),
                     "-i", str(args.video), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(clip)])
                cmd += ["--video", str(clip)]
            print(f"{cue['id']}: {cue['start']}-{cue['end']}s  {cue['prompt']}")
            run(cmd, cwd=args.mmaudio)

            flac = next((tmp / cue["id"]).glob("*.flac"))
            run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(flac),
                 "-t", str(dur), "-ar", str(SR), str(wav)])
            manifest[cue["id"]] = {"file": wav.name, "start": cue["start"], "duration": dur, "key": key}
            shutil.rmtree(tmp / cue["id"], ignore_errors=True)

    ids = {c["id"] for c in spec["cues"]}
    manifest = {k: v for k, v in manifest.items() if k in ids}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()

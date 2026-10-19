#!/usr/bin/env python3
"""Narration with Chatterbox (resemble-ai/chatterbox, MIT): one WAV per line.

    python3 tools/narrate.py narration.json            # only lines whose text/settings changed
    python3 tools/narrate.py narration.json --force    # everything
    python3 tools/narrate.py narration.json --only l03 l07

narration.json:
    {
      "voice": "voices/narrator.wav",      # optional 10-20 s reference clip; omit for the built-in voice
      "defaults": {"exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.8},
      "lines": [
        {"id": "l01", "text": "Dev took a shrinking pill."},
        {"id": "l02", "text": "Arreh? Uh-oh.", "exaggeration": 0.9, "cfg_weight": 0.3}
      ]
    }

Writes <out>/<id>.wav (44.1 kHz mono, silence trimmed) and <out>/lines.json with each
line's duration, so tools/timing.py can place captions and beats from real lengths.

Install once (Apple silicon runs on MPS):  pip install chatterbox-tts
"""
import argparse, hashlib, json, sys
from pathlib import Path

SR = 44100        # same rate as assets/bgm/bed.wav
PAD = 0.06        # seconds of silence kept around each trimmed line


def sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else json.dumps(p, sort_keys=True).encode())
    return h.hexdigest()[:16]


def trim(wav, sr, floor_db=-45.0):
    """Cut leading/trailing silence so a line's duration is its spoken length."""
    import torch
    frame = int(sr * 0.01)
    x = wav[0]
    n = x.shape[0] // frame
    if n == 0:
        return wav
    rms = x[: n * frame].reshape(n, frame).pow(2).mean(1).sqrt()
    loud = (20 * torch.log10(rms + 1e-9) > floor_db).nonzero()
    if len(loud) == 0:
        return wav
    a = max(0, int(loud[0]) * frame - int(PAD * sr))
    b = min(x.shape[0], (int(loud[-1]) + 1) * frame + int(PAD * sr))
    return wav[:, a:b]


def write_wav(path, wav, sr):
    """16-bit mono WAV via the stdlib (torchaudio >= 2.9 needs torchcodec just to save)."""
    import wave
    pcm = (wav[0].clamp(-1, 1) * 32767).round().short().numpy().tobytes()
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr); f.writeframes(pcm)


def load_model():
    import torch
    from chatterbox.tts import ChatterboxTTS
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    if device != "cuda":
        # checkpoints are saved from CUDA; map them onto this device (resemble-ai's example_for_mac.py)
        load = torch.load
        torch.load = lambda *a, **k: load(*a, **{"map_location": torch.device(device), **k})
    print(f"loading Chatterbox on {device}", file=sys.stderr)
    return ChatterboxTTS.from_pretrained(device=device)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path)
    ap.add_argument("--out", type=Path, default=Path("assets/voice"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="line ids to regenerate")
    args = ap.parse_args()

    spec = json.loads(args.script.read_text())
    base = args.script.parent
    voice = Path(base, spec["voice"]) if spec.get("voice") else None
    voice_hash = sha(voice.read_bytes()) if voice else "builtin"
    defaults = {"exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.8, **spec.get("defaults", {})}

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / "lines.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    todo = []
    for i, line in enumerate(spec["lines"]):
        p = {k: line.get(k, v) for k, v in defaults.items()}
        p["seed"] = line.get("seed", 1000 + i)
        key = sha(line["text"], p, voice_hash)
        wav_path = args.out / f"{line['id']}.wav"
        stale = manifest.get(line["id"], {}).get("key") != key or not wav_path.exists()
        if args.force or stale or (args.only and line["id"] in args.only):
            if args.only is None or line["id"] in args.only:
                todo.append((line, p, key, wav_path))

    if not todo:
        print("all lines up to date")
        return

    import torch, torchaudio
    model = load_model()
    for line, p, key, wav_path in todo:
        torch.manual_seed(p["seed"])
        wav = model.generate(
            line["text"],
            audio_prompt_path=str(voice) if voice else None,
            exaggeration=p["exaggeration"],
            cfg_weight=p["cfg_weight"],
            temperature=p["temperature"],
        )
        wav = trim(torchaudio.functional.resample(wav.cpu(), model.sr, SR), SR)
        write_wav(wav_path, wav, SR)
        dur = round(wav.shape[1] / SR, 3)
        manifest[line["id"]] = {"file": wav_path.name, "duration": dur, "text": line["text"], "key": key}
        print(f"{line['id']}: {dur:5.2f}s  {line['text'][:60]}")

    # drop lines that were removed from the script
    ids = {l["id"] for l in spec["lines"]}
    manifest = {k: v for k, v in manifest.items() if k in ids}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()

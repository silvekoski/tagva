import json
import os
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(__file__).parent / "out"
LIB = OUT / "sfx-library"

SOUNDS = {
    "blip": ("short clean digital UI blip, soft, high pitched, modern interface", 0.5),
    "lockon": ("futuristic targeting lock-on beep, two quick tones, clean UI", 0.6),
    "whoosh": ("fast airy whoosh transition, clean, modern motion graphics", 1.0),
    "whoosh-soft": ("soft subtle air swish, gentle, for text appearing on screen", 0.6),
    "riser": ("cinematic tension riser building up, bright synth swell into a hit", 2.0),
    "impact": ("deep cinematic logo reveal boom, sub bass hit with a shimmering tail", 3.0),
    "shimmer": ("sparkling glossy shimmer sweep, light airy chime, logo shine", 1.5),
    "typing": ("fast mechanical keyboard typing, short burst, close up", 1.5),
    "pop": ("satisfying soft pop click, clean UI element appearing", 0.5),
    "scribble": ("quick marker pen stroke underline on paper", 0.7),
    "counter": ("rapid digital counter ticking up, numbers rolling fast, electronic ticks", 3.5),
    "ding": ("bright positive success ding, clean notification", 1.0),
    "glitch": ("digital glitch stutter hit, electronic, short and punchy", 0.8),
    "shutter": ("camera shutter click, crisp", 0.5),
    "laser": ("smooth sci-fi laser beam scan, soft zap, clean", 1.2),
    "scan": ("electronic scanner sweep passing over, light hum", 1.0),
    "servo": ("mechanical gauge needle sweep, small servo whirr, then settles", 1.2),
    "lock": ("heavy metallic padlock snapping shut, solid click", 0.8),
    "hum": ("steady low electronic server hum with gpu cooling fans whirring", 5.0),
    "buzzer": ("negative error buzzer, short UI denied sound", 0.8),
    "chime": ("positive approval chime, two rising notes, clean UI", 1.0),
    "swell": ("uplifting short success synth swell, warm and bright", 2.0),
    "swarm": ("many small tiles flying in and clicking into place, cascading clicks", 2.5),
    "data": ("digital data stream transfer chirps, soft electronic bleeps", 2.5),
    "unroll": ("smooth paper unrolling swoosh", 1.0),
    "glass": ("crisp glass panels sliding apart, light shimmer, no breaking", 1.2),
    "pad": ("warm ambient synth pad outro, soft and wide, slowly fading out", 6.0),
}

# scene id -> [(seconds, sound, gain)]
CUES = {
    "m01-title": [(0.33, "lockon", 0.7), (0.63, "lockon", 0.6), (0.93, "lockon", 0.6), (1.23, "lockon", 0.6), (1.53, "lockon", 0.6), (1.83, "lockon", 0.7), (2.0, "riser", 0.8), (3.9, "impact", 1.0), (5.2, "shimmer", 0.6), (5.3, "whoosh-soft", 0.5), (7.4, "whoosh-soft", 0.4)],
    "m02-problem": [(0.3, "whoosh", 0.7), (0.8, "whoosh", 0.6), (1.25, "whoosh", 0.6), (1.85, "typing", 0.5), (2.2, "data", 0.25), (5.0, "pop", 0.7), (5.45, "pop", 0.7), (5.9, "pop", 0.8), (6.6, "scribble", 0.8)],
    "m03-seventy": [(0.0, "whoosh", 0.7), (0.4, "impact", 1.0), (0.05, "counter", 0.35), (1.05, "whoosh-soft", 0.6), (1.75, "pop", 0.4)],
    "m04-results": [(0.0, "whoosh", 0.7), (0.6, "pop", 0.7), (0.9, "pop", 0.7), (1.2, "pop", 0.7), (1.7, "shimmer", 0.4), (5.4, "whoosh", 0.6)],
    "m05-no-photos": [(0.0, "glitch", 0.9), (0.1, "whoosh-soft", 0.6)],
    "m06-counter": [(0.1, "swarm", 0.4), (0.4, "counter", 0.7), (3.95, "ding", 0.8), (3.95, "pop", 0.6)],
    "m07-one-camera": [(0.13, "shutter", 0.9), (0.6, "laser", 0.6), (1.0, "whoosh", 0.6), (1.85, "scan", 0.7), (2.6, "lockon", 0.9), (3.65, "whoosh-soft", 0.6)],
    "m08-custom-model": [(0.0, "glitch", 0.9), (0.1, "whoosh", 0.5), (1.53, "pop", 0.7), (2.33, "pop", 0.7), (3.13, "pop", 0.7), (2.0, "data", 0.4), (4.5, "data", 0.35), (5.0, "blip", 0.5), (5.2, "blip", 0.5), (5.4, "blip", 0.5), (5.6, "blip", 0.5), (7.6, "whoosh", 0.7), (8.3, "servo", 0.8), (9.4, "lock", 0.4), (9.5, "ding", 0.6)],
    "m09-gpus": [(0.0, "whoosh", 0.7), (0.4, "hum", 0.55), (1.5, "pop", 0.7), (1.85, "pop", 0.7), (2.2, "pop", 0.7), (2.6, "ding", 0.5)],
    "m10-run-table": [(1.1, "typing", 0.5), (2.33, "buzzer", 0.8), (4.1, "typing", 0.5), (5.33, "chime", 0.8), (7.1, "typing", 0.5), (8.33, "chime", 0.7), (10.0, "swell", 0.8), (10.0, "pop", 0.7), (11.0, "whoosh-soft", 0.5)],
    "m11-held-out": [(0.1, "swarm", 0.7), (2.4, "whoosh", 0.6), (3.2, "lock", 1.0), (3.7, "counter", 0.4), (7.2, "whoosh", 0.6), (7.6, "typing", 0.5), (9.0, "typing", 0.4), (10.3, "chime", 0.5)],
    "m12-dark-recall": [(0.25, "scan", 0.7), (0.87, "lockon", 0.8), (0.97, "lockon", 0.6), (1.07, "lockon", 0.6), (1.45, "whoosh", 0.6), (1.5, "counter", 0.4), (2.6, "ding", 0.7)],
    "m13-tiles": [(0.1, "unroll", 0.8), (1.5, "glass", 0.8), (3.45, "lockon", 0.7), (3.72, "lockon", 0.7), (4.0, "lockon", 0.7), (5.0, "counter", 0.4), (5.0, "swarm", 0.3), (6.1, "ding", 0.6)],
    "m14-ray": [(0.0, "swarm", 0.35), (0.45, "pop", 0.6), (1.13, "laser", 0.8), (2.2, "blip", 0.8), (2.8, "pop", 0.6), (3.47, "laser", 0.8), (4.6, "chime", 0.8), (5.3, "whoosh-soft", 0.6)],
    "m15-production": [(0.0, "whoosh", 0.6), (0.4, "whoosh", 0.5), (0.8, "whoosh", 0.5), (1.1, "data", 0.5)],
    "m16-next-device": [(0.0, "whoosh", 0.7), (1.3, "whoosh-soft", 0.5), (1.8, "pop", 0.6), (2.1, "pop", 0.6), (2.4, "pop", 0.6), (2.7, "pop", 0.6), (3.65, "whoosh-soft", 0.6)],
    "m17-close": [(0.0, "riser", 0.4), (0.25, "impact", 1.0), (1.6, "shimmer", 0.6), (1.7, "typing", 0.35), (2.4, "typing", 0.35), (2.5, "pad", 0.6), (6.3, "shimmer", 0.35)],
}


def generate(name: str) -> None:
    path = LIB / f"{name}.mp3"
    if path.exists():
        return
    text, seconds = SOUNDS[name]
    body = json.dumps({"text": text, "duration_seconds": seconds, "prompt_influence": 0.5}).encode()
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/sound-generation",
        data=body,
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        path.write_bytes(r.read())
    print("sound", name)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def mix(scene: str) -> None:
    video = OUT / f"{scene}.mp4"
    cues = CUES[scene]
    length = duration(video)
    inputs = [arg for _, s, _ in cues for arg in ("-i", str(LIB / f"{s}.mp3"))]
    chains = [f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={g},adelay={int(t * 1000)}:all=1[a{i}]" for i, (t, _, g) in enumerate(cues)]
    graph = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(len(cues))) + f"amix=inputs={len(cues)}:normalize=0,apad,atrim=0:{length},afade=t=out:st={length - 0.4}:d=0.4,alimiter=limit=0.89:level=disabled[out]"
    wav = OUT / "sfx" / f"{scene}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-ar", "48000", str(wav)], check=True)
    tmp = OUT / f"{scene}.tmp.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(tmp)], check=True)
    tmp.replace(video)
    alpha = OUT / f"{scene}-alpha.mov"
    if alpha.exists():
        tmp = OUT / f"{scene}-alpha.tmp.mov"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(alpha), "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "pcm_s16le", "-shortest", str(tmp)], check=True)
        tmp.replace(alpha)
    print("mixed", scene)


if __name__ == "__main__":
    LIB.mkdir(parents=True, exist_ok=True)
    (OUT / "sfx").mkdir(exist_ok=True)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(generate, SOUNDS))
    for scene in sys.argv[1:] or CUES:
        mix(scene)

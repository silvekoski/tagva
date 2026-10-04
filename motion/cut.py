import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "out"
FPS = 30
GAP = 0.8
TAIL = 1.5
SFX_GAIN = 0.4

SCENE_SECONDS = {"m01-title": 8, "m02-problem": 10, "m03-seventy": 5, "m04-results": 6, "m05-no-photos": 2, "m06-counter": 6, "m07-one-camera": 7, "m08-custom-model": 14, "m09-gpus": 6, "m10-run-table": 16, "m11-held-out": 12, "m12-dark-recall": 6, "m13-tiles": 8, "m14-ray": 8, "m15-production": 5, "m16-next-device": 8, "m17-close": 10}

# beat id, voiceover seconds, shots as (offset in the beat, kind, name)
BEATS = [
    ("01-cold-open", 25.8, [(0, "screen", "01-panorama-overview"), (7, "screen", "02-device-details"), (12, "screen", "04-device-documents"), (17.8, "scene", "m01-title")]),
    ("02-problem", 27.9, [(0, "scene", "m02-problem"), (10, "screen", "05-manual-task-page"), (22.3, "scene", "m03-seventy")]),
    ("03-one-button", 25, [(0, "screen", "06-dollhouse"), (7, "screen", "03-detection-boxes"), (14.5, "scene", "m04-results"), (20.5, "screen", "07-devices-table")]),
    ("04-synthetic-data", 51.5, [(0, "screen", "08-synthetic-dataset"), (4, "scene", "m05-no-photos"), (6, "plate", "rex615-front"), (17.5, "screen", "08-synthetic-dataset"), (26, "screen", "09-synthetic-dark-sample"), (38.2, "scene", "m06-counter"), (44.3, "scene", "m07-one-camera")]),
    ("05-custom-model", 49.6, [(0, "scene", "m08-custom-model"), (15.7, "scene", "m09-gpus"), (22.4, "scene", "m10-run-table"), (38.4, "screen", "03-detection-boxes")]),
    ("06-measured", 27.7, [(0, "scene", "m11-held-out"), (12, "screen", "07-devices-table"), (20.6, "scene", "m12-dark-recall")]),
    ("07-what-the-button-does", 57.6, [(0, "screen", "01-panorama-overview"), (9, "scene", "m13-tiles"), (17, "screen", "03-detection-boxes"), (19.5, "screen", "02-device-details"), (28.1, "scene", "m14-ray"), (36.1, "screen", "06-dollhouse"), (39.3, "screen", "05-manual-task-page"), (47, "screen", "07-devices-table")]),
    ("08-browser-and-production", 23.2, [(0, "screen", "10-browser-detection"), (10.3, "scene", "m15-production"), (15.3, "scene", "m16-next-device")]),
    ("09-yard-service", 50.7, [(0, "card", "yard-service-card"), (22.5, "screen", "06-dollhouse"), (30, "screen", "01-panorama-overview"), (36, "screen", "03-detection-boxes"), (40.8, "screen", "05-manual-task-page"), (44.3, "screen", "09-synthetic-dark-sample"), (47.5, "screen", "02-device-details")]),
    ("10-close", 8.6, [(0, "scene", "m17-close")]),
]


def build() -> None:
    starts, t = [], 0.0
    for _, seconds, _ in BEATS:
        starts.append(t)
        t += seconds + GAP
    total = starts[-1] + max(BEATS[-1][1] + TAIL, SCENE_SECONDS["m17-close"])
    shots = [(start + at, kind, name) for start, (_, _, beat_shots) in zip(starts, BEATS) for at, kind, name in beat_shots]

    inputs, video, audio = [], [], []

    def add(*args: str) -> int:
        inputs.extend(args)
        return sum(a == "-i" for a in inputs) - 1

    for i, (begin, kind, name) in enumerate(shots):
        end = shots[i + 1][0] if i + 1 < len(shots) else total
        dur = round((end - begin) * FPS) / FPS
        fade = f"fade=in:d=0.4,fade=out:st={dur - 0.3:.3f}:d=0.3"
        if kind == "scene":
            k = add("-i", str(OUT / f"{name}.mp4"))
            pad = max(dur - SCENE_SECONDS[name], 0)
            video.append(f"[{k}:v]trim=0:{dur:.3f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration={pad:.3f},fps={FPS},setsar=1,format=yuv420p[v{i}]")
            audio.append(f"[{k}:a]atrim=0:{dur:.3f},volume={SFX_GAIN},aformat=sample_rates=48000:channel_layouts=stereo,adelay={round(begin * 1000)}:all=1[s{i}]")
            continue
        bg = add("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(OUT / "backdrop.png"))
        if kind == "card":
            k = add("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(OUT / f"{name}.jpg"))
            video.append(f"[{k}:v]scale=1920:1080,setsar=1,{fade},format=yuv420p[v{i}]")
            continue
        if kind == "plate":
            k = add("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(ROOT / "public" / "img" / f"{name}.png"))
            fg = f"[{k}:v]scale=-2:760,format=rgba[f{i}]"
        else:
            k = add("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(ROOT / "public" / "screens" / f"{name}.jpg"))
            frames = round(dur * FPS)
            fg = f"[{k}:v]scale=2400:-2,zoompan=z='1+0.07*on/{frames}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1640x1012:fps={FPS}[f{i}]"
        video.append(f"{fg};[{bg}:v][f{i}]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,{fade},format=yuv420p[v{i}]")

    for start, (beat_id, _, _) in zip(starts, BEATS):
        k = add("-i", str(OUT / "voiceover" / f"{beat_id}.mp3"))
        audio.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={round(start * 1000)}:all=1[s{len(audio) + 1000}]")

    labels = [a[a.rindex("["):] for a in audio]
    graph = ";".join(video + audio)
    graph += ";" + "".join(f"[v{i}]" for i in range(len(shots))) + f"concat=n={len(shots)}:v=1:a=0[vout]"
    graph += ";" + "".join(labels) + f"amix=inputs={len(labels)}:normalize=0,atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    script = OUT / "cut-graph.txt"
    script.write_text(graph)
    subprocess.run(["ffmpeg", "-v", "error", "-stats", "-y", *inputs, "-filter_complex_script", str(script), "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-movflags", "+faststart", str(OUT / "tagva-pitch.mp4")], check=True)
    script.unlink()
    print(f"tagva-pitch.mp4: {total:.1f} s, {len(shots)} shots")


if __name__ == "__main__":
    build()

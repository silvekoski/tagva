import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "out" / "voiceover"
VOICE = "Hm0mJlZY3Pws7nTKAftG"
MODEL = "eleven_v4"
SETTINGS = {"stability": 0.35, "similarity_boost": 0.8}

# id, script start in seconds, slot length in seconds, text with v4 audio tags
BEATS = [
    ("01-cold-open", 0, 25, """[quietly, slow] This is a real substation... scanned with a Matterport camera.
[curious] Somewhere in this room are six protection relays.
[matter-of-fact] Today, a person finds every one of them by hand. [sighs] Open the panorama, find the device, read the label, type the tag, link the manual. [wearily] Cabinet... by cabinet.
<break time="0.6s" />
[warm, smiling] I'm team bob the builder... [laughs softly] a team of one. [proudly] This is Tagva."""),
    ("02-problem", 25, 30, """[confident] VEO scans substations, hydro plants and industrial sites into VEO three-sixty digital twins.
[lightly] The scan is the easy part. [serious] The hard part comes after: mapping every device to a tag, and to its documents. The manuals, drawings and maintenance reports.
[frustrated] That mapping is manual, it is slow, and it is easy to get wrong in a dark room full of glass doors.
[building excitement] VEO's own estimate: automate it... and about seventy percent of that work disappears."""),
    ("03-one-button", 55, 30, """[excited] Tagva turns a finished scan into a tagged digital twin... with one button.
[energetic] It finds each ABB Relion REX six-fifteen relay, reads its label, places a tag at its real 3D position, assigns it to the right cabinet, and links its manual and drawings.
[proudly] On VEO's sample site it found six of six relays... [emphasizing] with zero false positives.
[casually] One full run takes about four minutes on a laptop."""),
    ("04-synthetic-data", 85, 70, """[leaning in, excited] Now the part I'm most proud of. [slowly, with weight] The model never saw a real photograph during training. [whispers] Not one.
<break time="0.5s" />
[storytelling] VEO gave me one reference photo of the relay. I rectified it, built the front plate as a 3D object in Blender, and placed it inside a virtual cabinet.
[playful] Then a script takes over. [energetic, quick] It renders the plate from thousands of angles and distances. It changes the light, from a bright hall... [hushed] to near darkness. [quick] It adds glass reflections, cables hanging in front of the plate, motion blur, JPEG artifacts, worn labels and different LED states.
[delighted] And because Blender knows exactly where the plate is in every frame, it writes the bounding box for me. [impressed] Nine thousand images. [laughs] Zero hours of manual labeling.
[calm, precise] Every image is rendered for one camera, the Matterport Pro3 that VEO actually uses. So the training view and the real view match."""),
    ("05-custom-model", 155, 60, """[firm] This is not an off-the-shelf detector, and it is not a cloud vision API. [amused] No existing model knows what a REX six-fifteen is.
[confident] So I trained a custom one: a single-class YOLO detector at twelve eighty pixels, trained only on those renders. [serious] Even the confidence threshold was set from synthetic validation data, before I had looked at a single real result.
[casually] To train it, I rented two NVIDIA A one hundred GPUs from Verda. Each run took under an hour. [grinning] Three runs, one night, about twelve dollars of compute.
<break time="0.4s" />
[honest, slightly embarrassed] The first model failed. [sighs] It found all six relays, but it also fired on two things that were not relays.
[relieved] The second run added fifteen hundred dark and fifteen hundred occluded renders, and that one passed. [proudly] Six of six, zero false positives. That is the model running in Tagva today."""),
    ("06-measured", 215, 30, """[serious, sincere] I want to be clear about how that number was measured.
[deliberate] I cut the real scan into two hundred and six tiles with two hundred and fifty-one real relay boxes... and locked that set away. No training decision ever touched it.
[firm] The acceptance rule was fixed in advance: find every REX six-fifteen, with at most one false positive.
[quietly impressed] And on a darkened copy of those real tiles, the model still reached ninety-eight percent recall... [satisfied] with no false positives."""),
    ("07-what-the-button-does", 245, 75, """[brisk, energetic] Here is what the button does. Tagva reads the E fifty-seven file: eighteen scan positions, eight K panoramas, and a point cloud of almost two million points.
[explaining] It cuts each panorama into thirty-six perspective tiles, because a relay can be five pixels wide... or four hundred, and runs the detector on all six hundred and forty-eight of them.
[matter-of-fact] An OCR model then reads the device name and the cabinet label. No naming pattern is hard-coded, [knowingly] because VEO's naming changes from project to project.
[focused] Then it casts a ray from each box into the point cloud to find the panel in 3D, merges views of the same device from different scan positions into one tag, and assigns it to the nearest cabinet label. [precise] Anchor error: eight to twenty millimetres.
[warm] Each tag links to its manual. The project adds drawings and reports. [earnest] And Tagva does not hide doubt. Anything uncertain gets a review flag with a reason: low confidence, empty OCR, or OCR conflict. [reassuring] And a person makes the final call in the tag editor."""),
    ("08-browser-and-production", 320, 25, """[excited] The same custom model also runs in the browser, in Chrome with WebGPU: thirty-six tiles in under five seconds, [emphasizing] same six relays, same scores.
[confident] In production the tags go through the Matterport API into the VEO three-sixty viewer customers already use.
[playful, confident] And the next device type needs no photo campaign: one front plate in Blender... and one hour on a GPU."""),
    ("09-yard-service", 345, 65, """[mischievously] One more thing. [laughs] I made a game. [excited] It's called Yard Service, and it runs on the same scan and the same tag file.
[playful, storytelling] You play Leon, a VEO service technician. [dramatic] A radio call names a faulty device by the tag Tagva generated: REX six-fifteen at H zero five, SOLAR two.
[energetic] You drive the VEO van across the real yard. [amazed] The buildings, the containers, even the trees are placed from the scan data. You walk into the real switchgear house, open the real cabinet, and see the detector's boxes on the real panorama, with their confidence.
[quick, fun] You open the auto-linked manual, pick the right tool, fix the fault, [satisfied] and the game writes a maintenance record against that asset.
[hushed, playful] It works at night... because the model was trained for the dark. [excited] And when you stand in a blue ring, you drop into the real Tagva viewer. [warm, confident] Same tags. One source of truth."""),
    ("10-close", 410, 10, """[confident, warm] Scan the room. Press one button. Know every relay. [proudly] Tagva, at tagva dot bobs dot build. [smiling] Thanks for watching."""),
]


def speak(beat_id: str, text: str) -> Path:
    path = OUT / f"{beat_id}.mp3"
    if path.exists():
        return path
    body = json.dumps({"text": text, "model_id": MODEL, "voice_settings": SETTINGS}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_192",
        data=body,
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        path.write_bytes(r.read())
    return path


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def timeline() -> None:
    inputs = [arg for b in BEATS for arg in ("-i", str(OUT / f"{b[0]}.mp3"))]
    chains = [f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={b[1] * 1000}:all=1[a{i}]" for i, b in enumerate(BEATS)]
    graph = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(len(BEATS))) + f"amix=inputs={len(BEATS)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-b:a", "320k", str(OUT / "voiceover-full.mp3")], check=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:]
    for beat_id, start, slot, text in BEATS:
        if only and beat_id not in only:
            continue
        d = duration(speak(beat_id, text))
        flag = "OVER" if d > slot else "ok"
        print(f"{beat_id}: {d:5.1f} s of {slot} s slot at {start // 60}:{start % 60:02d} {flag}")
    timeline()

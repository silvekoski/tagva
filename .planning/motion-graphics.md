# Motion graphics

The `motion` directory holds the motion graphics M1 to M17 for the pitch video. Each graphic is a Remotion composition at 1920 × 1080 and 30 fps.

## Commands

- `npm run studio`: open Remotion Studio to preview and scrub each composition.
- `npm run render`: render all compositions to `out/<id>.mp4` (H.264, CRF 16).
- `node render.mjs m03-seventy m08-custom-model`: render only the named compositions.
- `node render.mjs --stills`: render two review frames for each composition to `out/stills`.

## README header

`readme-header` is a still at 1920 × 640. It uses the Backdrop, the logos and the sweep-02 markers of M1.

- `npx remotion still readme-header ../.github/readme-header.png`: render the header for the README.
- `npm run render` also writes it to `out/readme-header.png`.

## Overlays

M1, M4 and M12 also render to `out/<id>-alpha.mov` (ProRes 4444 with alpha). The `overlay` prop removes the background image. In the MP4, M1 uses the real sweep-02 panorama, M4 uses the panorama as a preview background, and M12 uses the darkened real tile.

## Sources

- Colors: the tokens in `viewer/src/index.css`, copied to `src/theme.ts`.
- Fonts: Geist Variable and Geist Mono Variable from `@fontsource-variable`, the same packages as the viewer.
- Icons: lucide-react, the same set as the viewer.
- Logos in `public/logos`:
  - Tagva: `viewer/src/assets/tagva-logo.svg`.
  - VEO: veo.fi, `VEO-logo_nega_CMYK.svg`.
  - Matterport: matterport.com header asset, recolored to white for the dark background.
  - Verda: the inline header SVG of verda.com, with the wordmark recolored to white.
  - NVIDIA wordmark, ABB and Blender: Wikimedia Commons.
  - NVIDIA eye: Simple Icons.
- Box positions: `data/tags/VEO-DEMO.json` (sweep-02 for M1, sweep-03 for M13) and the YOLO labels of the real and synthetic tiles. `src/data.json` holds the extracted values.
- Numbers: `.planning/detector-runs.md` and the pitch script.

## Scene notes

- M13 shifts the sweep-03 panorama by 1039 px. The tile borders then split the six relays into three tiles in row 2 (columns 3, 4 and 5).
- M8 draws the dial arc with the large-arc flag set to 0. A gauge of 180° or less never needs the large arc.

## Sound effects

`sfx.py` makes the sound effects with the ElevenLabs Sound Effects API (`/v1/sound-generation`). `SOUNDS` holds 27 prompts. `CUES` gives the start time and gain of each sound in each scene. The times come from the frame timings in the scene code.

- `ELEVENLABS_API_KEY=... python3 sfx.py`: generate each sound that is not in `out/sfx-library`, then mix each scene.
- `python3 sfx.py m03-seventy`: mix one scene again. The library is a cache, so the mix needs no API call.

The mix writes `out/sfx/<id>.wav`, puts AAC audio into `out/<id>.mp4` and PCM audio into `out/<id>-alpha.mov`. A limiter keeps the peaks at about -1 dBFS.

# Browser detector

The user asked on 2026-10-04 to run the model in the web browser, scope "detector only". The server pipeline stays the same. This is a deviation from the PRD sentence "The ML model weights are loaded by the pipeline service, not by the player", by the user's request.

## Export

```
.venv/bin/python -c "from ultralytics import YOLO; YOLO('models/rex615.pt').export(format='onnx', imgsz=1280, opset=17, simplify=True)"
```

The output is `models/rex615.onnx` (37 MB, git ignored). The API serves it at `/models/rex615.onnx` (the path of `REX_WEIGHTS` with the suffix `.onnx`). The model output is the raw head, `(1, 5, 33600)`: cx, cy, w, h and score of each candidate. The browser does the confidence filter and the NMS.

## Browser steps (`viewer/src/detect.ts`)

1. "Check this view" takes the loaded equirect panorama texture of the current sweep (8192 x 4096).
2. WebGL renders the 36 tiles of `pipeline/tiles.py` (1280 px, 60 deg FOV, 12 yaws, pitches -30, 0 and +30 deg) with the same math as `pipeline/sphere.py`.
3. onnxruntime-web 1.30 runs the model with WebGPU. When WebGPU is not available, it uses WebAssembly.
4. Each tile: confidence 0.25 or more, NMS at IoU 0.7. The boxes go to the panorama with the border sampling of `tile_box_to_pano`, then the NMS of `nms_pano` (intersection over the smaller area 0.6, uncut boxes first).
5. The viewer draws the boxes at or above `min_confidence` (0.85) in cyan.

The Vite server sends the COOP and COEP headers, so the WebAssembly fallback can use threads.

## Checks

- ONNX with this post-processing against Ultralytics on the 36 cube-face tiles of sweep-12: the same boxes and scores.
- Tiles from the equirect panorama against tiles from the cube faces: the boxes with a score of 0.88 or more match within 1 to 2 px, with the same scores. The 8192 px panorama has 22.7 px per degree, more than the 19.3 px per degree of a tile.
- Sweep-12 in Chrome with WebGPU on the M3 Pro: 36 tiles in 4.9 s, 6 plates (0.97, 0.96, 0.95, 0.95, 0.94, 0.90). The same steps in Python give the same 6 scores. Their anchors match w1 to w5 and e1 within 0.003 to 0.03 m. e2 has no box.

The browser path has no OCR, no anchors and no tag file. Those stay in the server pipeline.

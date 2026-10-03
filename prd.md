vaasaes-hackathon
========================

Deadline: 2026-10-04 (Sunday). The build order is the Technical Implementation list below. Build the later items only after the demo path works end to end: E57 read, tiles, detector, anchors, tag file, player.

# Step 1 Matterport Player demo

I received a .e57 Matterport file from the VEO team of an electrical room containing electrical units that need to be identified using machine learning. Since I don’t have the paid Matterport software, I’ll create a copy of the Matterport Player using Claude Code. The player does not need every Matterport feature. The minimum feature set is: equirectangular panorama view, jump between scan positions, and tag pins. Dollhouse / point cloud view and a tag editor for manual corrections are in scope and are built after the demo path works. The player is the testing environment where the front plates of ABB Relion REX615 devices are identified using ML. The software uses an existing OCR model to read labels from cabinets and device plates. The OCR model is not used to detect the REX615 devices. One button runs the full pipeline (see Pipeline below) on all scan images. The player then loads the new tag file. The player does not run detection while the user navigates.

The detector finds a box in a 2D panorama, but a Matterport tag needs a 3D point. For each detection, the pipeline casts a ray from the scan position through the box center into the E57 point cloud. The hit point is the tag anchor. The exact method depends on how the E57 is structured, which is checked first (see Technical Implementation, E57). If no point is found, the device gets no anchor and review is set to true. I’ll reserve separate time for this step.

The player loads three inputs:
- The .e57 point cloud from VEO, for geometry and navigation. Also includes photos.
- A tag file in JSON, produced by the pipeline (Step 4).
- The document folder, for the links in the tag file.

The ML model weights are loaded by the pipeline service, not by the player. The player holds no pipeline logic.

# Step 2: Creating synthetic data

Using Blender, Claude models the front plate of an ABB Relion REX615 device. The front plate is almost flat, so Claude rectifies the reference photo and uses it as the texture on a plane, with small extrusions for the buttons. Texture, lighting, and pixel scale matter more than geometry. There’s no need to model the back of the device, since the other parts are hidden behind the electrical panel. The device is also rendered inside different electrical panels. At this stage, various domain randomization techniques are used to prevent the model from overfitting to the reference photo: lighting, viewing angle, distance, dark scenes, reflections from cabinet glass, cables in front of the plate, blur, JPEG artifacts, and worn labels. The label text region and the LED states are also randomized, so the model learns the plate layout rather than one specific print. The relay is downscaled to the pixel size it has in a real panorama. The camera will always be a Matterport Pro 3, so the model does not need to be generalized across different cameras. The Pro 3 output is a stitched equirectangular panorama, and that projection distorts objects near the top and bottom edges. Each real panorama is reprojected to perspective tiles before detection, and Blender renders perspective views, so the training view and the inference view match. Claude automatically takes thousands of photos of the device using Blender’s API. Bounding boxes are exported directly from Blender to the next step, so there is no need to label the images manually at all. The reference photo comes from a different environment than the scanned site, which is the main sim-to-real risk. To measure it, crops of the real REX615 devices in the VEO E57 panoramas form a held-out test set that is never used for training or for tuning. There are too few real devices to split. Validation during training uses only a synthetic validation split. The real crops are evaluated once per training run and give the final number. Model the device with the Blender API from the rectified reference photo. Use a downloaded 3D model only if one is found quickly.

# Step 3: Training the Model

I have a lot of credits on Verda, so I’ll rent a graphics card from there to train the model. The detector is a single-class YOLO26 (s or m) at 1280 px, the smallest size that meets the real-scan recall target. A single-class detector of a flat object does not need eight hours: plan for several short runs (under an hour each) with different domain randomization settings, and measure each run on the held-out real crops from Step 2. Inference runs on this MacBook with an M3 Pro and 18 GB of unified memory with MPS. CoreML export is optional. We will use PP-OCRv5 to read the labels, so there is no need to train a custom OCR model.

# Step 4: Testing

I’ll test and demonstrate the model in the player from Step 1. The player allows you to save files to devices, so be sure to place at least the REX615 device manual in the correct location. The document lookup uses two keys: device_type (from the detector, always REX615 in this demo) selects the manual, and the project label selects the drawings and maintenance reports. The operator enters the project label in a text field before pressing the button. A plain folder structure is enough for the demo. VEO takes its documents from SharePoint, so I’ll keep the lookup simple. In the UI, you can navigate in a Google Street View-style interface and demonstrate how the model recognizes new ABB elements. Acceptance criteria for the demo: on the VEO sample scan, every REX615 is found (count recorded during the E57 check) and there is at most one false positive in total.

# Pipeline

The button runs these steps in order on every scan position:

1. Reproject each equirectangular panorama to perspective tiles (TODO: tile count and FOV, chosen after measuring the relay’s pixel size at the far end of a cabinet row in the sample E57).
2. Run the REX615 detector on every tile. Map each box back to panorama pixel coordinates. Merge duplicate boxes from overlapping tiles with NMS so there is at most one box per device per panorama.
3. Run PP-OCRv5 text detection on the same tiles to find cabinet labels. Map label boxes back to panorama coordinates and NMS them the same way.
4. Run PP-OCRv5 recognition on each device box (device name) and on each cabinet label box.
5. Cast a ray from the scan position through the center of each device box and each cabinet label box into the point cloud. The hit points are the 3D anchors.
6. Merge detections of the same device across scan positions: anchors within merge_radius (default 0.2 m) become one device. The device keeps every box and takes the highest confidence. Merge cabinet label anchors the same way.
7. Assign each device to the cabinet whose label anchor is nearest in 3D. A device with no cabinet label within cabinet_radius (default 2 m) goes to a tag named "unassigned". A cabinet with a label but no devices still gets a tag with an empty device list.
8. Look up documents: device_type selects the manual, the project label selects drawings and reports.
9. Set review and review_reasons. The threshold is a slider in the player. The player recomputes low_confidence from confidence live. The other reasons come from the pipeline run. Reasons:
   - low_confidence: confidence below review_threshold
   - empty_ocr
   - no_anchor
   - few_observations: seen from only one scan position when neighboring positions exist
   - anchor_variance: observations spread more than merge_radius
   - ocr_conflict: different name texts across observations
   - ambiguous_cabinet: two cabinet labels within 20 % of the same distance
10. Write the tag file and reload it in the player.

# Requirements

- One action starts detection. The operator presses one button. The solution then finds the devices, reads the labels, and links the documents. It does not search while the operator navigates.
- The target device is the ABB Relion REX615 protection relay. VEO confirmed that one device is enough. The model covers the front plate.
- The solution is not a live tool. VEO scans the whole site first. The solution processes the scan data after the scan is complete.  
- There is no fixed tag naming schema. Tag names and label shapes change from project to project. The solution does not hard-code a name pattern.
- VEO always uses the Matterport Pro3 camera.
- In production, the solution uploads the tags to the Matterport portal through the Matterport API. In the demo, my own player replaces the portal.
- Document types are manuals, cabinet and device drawings, maintenance reports, and inspection reports. VEO stores them in SharePoint. The demo uses a local folder structure.
- The sample scan is a best case for lighting. Real sites can be very dark. The training data and the tests include dark conditions.
- The review threshold is adjustable by the operator, not fixed in code.
- The player can show a dollhouse / point cloud view and has a tag editor for manual corrections of review-flagged devices. Both are in scope and are built after the demo path works end to end.

# Data format

File fields:
- project: project label entered by the operator
- site: site name, entered by the operator next to the project label (defaults to the project label)
- review_threshold: confidence below which review is true
- merge_radius: distance in meters for merging anchors of the same device
- cabinet_radius: maximum distance in meters from a device to its cabinet label

Tag fields (one tag per cabinet, plus one "unassigned" tag if needed):
- id: unique tag identifier
- cabinet: cabinet name read by OCR from the cabinet label
- anchor: 3D position of the cabinet label in scan coordinates (x, y, z)
- path: site, cabinet
- devices: list of devices, see below (may be empty)

Device fields (one entry per REX615 in the cabinet):
- device_id: unique device identifier
- name: text from the device label (OCR output)
- device_type: REX615 (from the detector class, not from OCR)
- boxes: list of bounding boxes, one per scan image where the detector found the device. Each box has scan_position, x, y, width, and height in pixels.
- anchor: 3D position of the device in scan coordinates (x, y, z). Null when the ray hit nothing.
- confidence: three decimal probability from the ML model
- documents: list of document links attached to this device
- review: true when review_reasons is not empty
- review_reasons: list from low_confidence, empty_ocr, no_anchor, few_observations, anchor_variance, ocr_conflict, ambiguous_cabinet

# Open questions

- Perspective tiling: how many tiles per panorama and at what FOV? Measure the relay’s pixel size in the sample E57 first.
- Dark sites: is there a real dark-site panorama or photo from VEO to anchor the Blender lighting range? If not, ask for one.
- E57 structure: per-scan clouds or one merged cloud? Decides the anchor method, see Technical Implementation.
- Point cloud density on cabinet fronts: check the E57 before trusting the ray cast. If the cloud is sparse or the glass doors scattered the LiDAR, fall back to a plane fit per cabinet.
- REX615 count in the sample scan: record it during the E57 check. It is the denominator for the acceptance criterion.

# Technical Implementation

Build in this order.

1. E57: pye57 reads scan poses and points. The images2D nodes give the panoramas. Open3D processes the point cloud. First check: does the file have one scan node per position (per-scan clouds) or a single merged cloud? Count the REX615 devices, measure the relay's pixel size at the far end of a cabinet row, and check cloud density on cabinet fronts.
2. Projection: overlapping perspective tiles per panorama. FOV and tile count come from the measurement in item 1. Boxes map back to panorama pixels. NMS across tile overlaps.
3. Synthetic data: Blender, Cycles, bpy, in Blender's Python. Randomize camera, light, occlusion, reflection, wear, blur, label text, and LED states. Render perspective tiles that match inference. Export YOLO labels. Hold out a synthetic validation split.
4. Detector: YOLO26 s or m, one class, 1280 px, the smallest that meets the real-scan recall target. Training: Ultralytics on one Verda A100, several short runs. Validation uses the synthetic split only. The real crops are test-only and are scored once per run.
5. Inference: offline batch on the M3 Pro with MPS. CoreML export is optional.
6. Anchor: if per-scan clouds, project each scan's points into its panorama and take the median depth inside the box center. If merged cloud, take the nearest point to the ray within a tolerance set from the density check in item 1. Fit a plane per cabinet when points are sparse or the glass scattered the LiDAR.
7. Merge: cluster observations across scans within merge_radius (default 0.2 m). One cluster is one device. Keep all observations and the VEO field names.
8. OCR: PP-OCRv5. Text detection on the tiles finds cabinet labels. Recognition runs on rectified, upscaled, full-resolution crops of device boxes and cabinet labels. The detector gives the device type. OCR gives only the name and cabinet text.
9. Cabinets: nearest label anchor in 3D within cabinet_radius (default 2 m). Fallback if labels sit high above the devices: distance along the row axis, ignoring height.
10. Review: the full reason set from Pipeline step 9. The player recomputes low_confidence from the slider. The pipeline writes the other reasons.
11. Documents: local folders `docs/devices/<device_type>/` and `docs/projects/<project>/`.
12. API: FastAPI, Python 3.12. POST runs the pipeline and writes the tag file. GET serves it. The service loads the model weights.
13. Viewer: Vite, TypeScript, Three.js. Panorama spheres, scan hotspots, tag billboards, project and site text fields, run button, review threshold slider. It holds no pipeline logic.
14. Tag editor: edit the name, cabinet, and anchor of review-flagged devices. Clear review_reasons. Save the tag file back through the API.
15. Dollhouse: Open3D-downsampled point cloud rendered as a Three.js point material with the same tag billboards.


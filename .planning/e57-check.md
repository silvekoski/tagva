# E57 check

Date: 2026-10-03. File: `cloud_0.e57` (2.3 GB, ASTM E57 1.0, Matterport Pro3).

## Structure

- 18 data3D nodes, `Sweep 0` to `Sweep 17`. Sweep 0 is outside the container. Sweeps 1 to 17 are inside.
- Each sweep has its own structured cloud: 6 480 000 points, a grid of 1800 rows x 3600 columns, with color. About 20% of the cells are invalid (`cartesianInvalidState` 2).
- Points are in the sweep local frame. `world = R_sweep @ local + t_sweep`.
- Grid mapping in the local frame (verified on 100% of valid points): elevation `= (row - 900) * 0.1 deg`, azimuth `= (col + 0.5) * 0.1 deg`, with `azimuth = atan2(y, x)`. See `pipeline/scan.py:local_dirs_to_grid`.
- 108 images2D nodes: 6 cube faces per sweep (`Skybox 0` to `Skybox 5`), linked by `associatedData3DGuid`. Each face is a 4096 x 4096 JPEG pinhole image with a focal length of 2048 px (90 deg FOV).
- Face camera convention (color correlation 0.997 to 0.999 against the points): `cam = R_img^T (world - t_img)`, the camera looks along -z, `u = 2048 + 2048 x / -z`, `v = 2048 - 2048 y / -z`.
- The blob `fileOffset` points to a 16-byte blob section header. `pye57.libe57.BlobNode.read` handles this.

## Anchor method

Per-scan clouds, so the anchor uses the first branch of Technical Implementation item 6: project the box center into the sweep grid and take the median range. See `pipeline/anchor.py`.

## Room

The room is about 7 m x 12 m (x from -9 to -2.2, y from -7.1 to 5, z up, floor at about 0).

- West lineup: 5 ABB UniGear panels, front at x = -5.7, y from -6.3 to -1.3. Each panel has one relay on the LV compartment at z = 1.87 m, and an engraved white nameplate (for example "H03 METERING") lower on the door.
- East side: 2 ELCON cabinets (Cerdex displays, no relays) and one VEO cabinet with two 615-series relays and an orange tape label "OT1".
- Cabinet labels: engraved nameplates on the switchgear, orange tape on the VEO and ELCON cabinets. Some orange tapes are notes, not labels (for example "KOKOOJA KISKO EI MOMENTISSA").

## REX615 count

6 targets (the acceptance denominator), confirmed with the user on 2026-10-03:

| id | center (x, y, z) m | nearest sweep |
| --- | --- | --- |
| w1 | -5.701, -5.87, 1.87 | 10 (0.84 m) |
| w2 | -5.704, -4.78, 1.87 | 11 (0.86 m) |
| w3 | -5.707, -3.78, 1.87 | 12 (0.85 m) |
| w4 | -5.708, -2.78, 1.87 | 13 (0.85 m) |
| w5 | -5.712, -1.78, 1.87 | 14 (0.91 m) |
| e1 | -2.766, -5.92, 1.75 | 7 (0.63 m) |

Hard negative: e2 at (-2.763, -5.92, 1.43), a narrow 615-series plate with F1 to F4 only. A detection on e2 is a false positive.

The plate is about 0.26 m x 0.18 m (wide REX615 HMI). The centers above are approximate (from an orthophoto) and are refined for the real test set.

## Pixel size and tiles

Relay width in a 1280 px tile with a 60 deg FOV (focal 1108 px), per visible sweep:

- Nearest sweep: 260 to 400 px.
- At least 5 sweeps per device: 90 px or more.
- Far end of the row (4 to 6.6 m, 50 to 80 deg off the plate normal): 5 to 50 px.

Each device is visible from 12 to 15 sweeps, so the far views are not necessary for recall. The detector must find a device at 30 px width or more.

Decision: 1280 px tiles, 60 deg FOV, 12 yaws (30 deg steps), pitches -30, 0 and +30 deg. That gives 36 tiles per sweep and 648 tiles in total. A test proves that each object up to 24 deg wide between -45 and +45 deg elevation fits fully in at least one tile (`tests/test_tiles.py`). The largest view of a device (e1 from 0.63 m) is 23.5 deg wide.

Tiles sample the cube faces directly (`pipeline/sphere.py:sample_cube`), so they keep the native resolution. Matterport stores the panorama as a cube map, so this is the reprojection of the panorama. Box coordinates are in the equirect frame of the panorama.

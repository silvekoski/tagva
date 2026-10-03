# OCR

Date: 2026-10-03, updated 2026-10-04. Module: `pipeline/ocr.py`. Configuration: `pipeline/ocr-stoplist.json`. Tests: `tests/test_ocr.py`.

## Models

PaddleOCR 3.7, PP-OCRv5, CPU. The module uses `paddleocr.TextDetection` and `paddleocr.TextRecognition` (PaddleX predictors). A numpy input is BGR. The predictor changes it to RGB.

Defaults:

- Text detection: `PP-OCRv5_mobile_det`, `limit_side_len` 1280, `limit_type` max. A 1280 px tile is not resized.
- Recognition: `PP-OCRv5_server_rec`.

Model files go to `~/.paddlex/official_models/` on first use. Sizes on disk:

| Model | Size |
| --- | --- |
| PP-OCRv5_mobile_det | 4.8 MB |
| PP-OCRv5_server_det | 84 MB |
| PP-OCRv5_server_rec | 81 MB |
| PP-OCRv5_mobile_rec | 16 MB |
| en_PP-OCRv5_mobile_rec | 7.7 MB |

The default pair needs 86 MB. All five models need 195 MB.

## Text detection speed

Machine: M3 Pro, 11 cores, CPU only. Other agents used the CPU at the same time, so the absolute numbers are high. The load average was 5.8 to 6.6 during the benchmark. Input: 1280 px tiles of sweep 12, one tile per call.

| Model | MKLDNN | Time per tile | 648 tiles | Max RSS |
| --- | --- | --- | --- | --- |
| PP-OCRv5_mobile_det | on (default) | 0.87 s | 9.4 min | 1.8 GB |
| PP-OCRv5_mobile_det | off | 0.81 s | 8.7 min | 1.9 GB |
| PP-OCRv5_server_det | off | 10.1 s | 1.8 h | 9.9 GB |
| PP-OCRv5_server_det | on (default) | 79 s | 14 h | 9.4 GB |

A full sweep (36 tiles) with the mobile model took 0.88 to 1.38 s per tile at load averages from 9 to 26. The server model took 28 s per tile on the full sweep 12. The server model is not usable here. It is 12 to 90 times slower, and it needs about 10 GB of the 18 GB of shared memory.

Recall on sweep 12: the server model gave 81 pano text boxes, the mobile model gave 113. Both found the nameplates H02, H03 and H04, and the tapes OKK1 and TSK2. The server boxes missed OT1. The mobile boxes missed TSK1 with the server recognizer (the English recognizer reads it as T5K1).

Decision: `PP-OCRv5_mobile_det`.

## Worker processes and full run speed

Date: 2026-10-04. Machine: M3 Pro, 11 cores, CPU only for Paddle. The input is the real scan and the ground truth boxes of `tests/test_run.py:TruthDetector`, because the detector weights do not exist yet.

### One process

A Paddle CPU predictor uses one core on this machine. The user CPU time was equal to the wall time. These settings did not change the speed of the text detection (12 tiles of sweep 12):

| Setting | Time per tile |
| --- | --- |
| Default (`cpu_threads` 10, MKLDNN on) | 0.85 s |
| `cpu_threads` 1 | 0.87 s |
| MKLDNN off | 0.85 s |
| `batch_size` 4 | 1.39 s |
| 2 or 4 predictors in Python threads | 0.85 s and 0.88 s |

MKLDNN is not available on arm64, so the flag has no effect. The threads do not run in parallel.

In one process, sweep 12 took 31.2 s for the text detection (36 tiles) and 8.5 s for the labels. A full run took about 18 minutes.

### Worker processes

`Ocr(workers=N)` starts N spawn processes. Each process has its own predictors (`Models`). `detect` sends one tile per task, `recognize` sends batches of `REC_BATCH` = 8 crops, and `reads` sends one view per task. `workers=0` runs the predictors in the calling process. The default is half the cores plus one (6 here). The env var `REX_OCR_WORKERS` overrides it.

Sweep 12, text detection of 36 tiles, while two Blender render processes also ran:

| Workers | Text detection | Labels |
| --- | --- | --- |
| 1 (no pool) | 31.2 s | 8.5 s |
| 4 | 13.3 s | 5.4 s |
| 5 | 11.9 s | 6.8 s |
| 6 | 8.1 s to 9.8 s | 3.6 s to 4.7 s |
| 7 | 14.1 s | 4.0 s |
| 8 | 15.7 s | 4.7 s |

Decision: 6 workers. More workers are slower, because the efficiency cores and the other load share the CPU.

### Order of work in `run.py`

For each sweep, the main process renders the tiles. The text detection runs in the worker processes while the main process runs the detector. Then the main process renders the device and label views and releases the cube faces. The recognition of the views runs in the background while the main process renders the tiles of the next sweep. Only one sweep of cube faces is in memory at a time.

`Ocr.labels` is now `label_views` (needs the faces) followed by `Ocr.read_labels` (needs only the views).

### Detector time

YOLO26 with untrained weights from the Ultralytics yaml (the same compute as trained weights), 36 tiles at 1280 px, MPS, batch 8: YOLO26s 4.65 s per sweep, YOLO26m 7.19 s per sweep. In sequence, this adds 84 s to 130 s to a run. In the new order, the detector runs at the same time as the text detection (about 8 s per sweep), so it adds almost no time.

### Full runs

The full run time includes the start of the worker processes (about 10 s to 14 s).

| Code | Workers | Detector | Other load | Time |
| --- | --- | --- | --- | --- |
| Before this change | 1 | ground truth | other agents | about 18 min |
| Pool, steps in sequence | 6 | ground truth | 2 Blender renders | 274.5 s |
| Final | 6 | ground truth | none (`test_run_pipeline_real_ocr`) | 180.0 s |
| Final | 6 | ground truth + YOLO26s on MPS | none (load 6 to 9) | 196.6 s and 230.3 s |
| Final | 4 | ground truth + YOLO26s on MPS | none (load 9) | 253.1 s |

In the 274.5 s run, the stage sums were: tile rendering 42.3 s, text detection 157.5 s, recognition 73.7 s. The final code hides the recognition behind the tile rendering of the next sweep.

### Memory

Each worker holds both models. The text detection of a 1280 px tile needs about 800 MB of activations. The default Paddle allocator also reserves about 690 MB for each predictor at load. `pipeline/ocr.py` sets `FLAGS_use_system_allocator` = 1. With this flag, one process with both models went from 1597 MB to 1275 MB after a sweep, at the same speed (0.727 s against 0.743 s per tile).

System memory in use (active, wired and compressed pages) during a run of three sweeps: 6 workers add 6.9 GB, 4 workers add 4.9 GB. The pool lives for one run. `run_pipeline` shuts it down at the end, and the memory goes back to the level before the run. The API does not cache the `Ocr` instance for this reason.

### Changes that were not used

- `limit_side_len` 960: the text detection is about 0.56 times the time, and all 10 true labels were still found. But the number of sweeps that read each label fell (TSK2 from 7 to 2, H05 SOLAR2 from 3 to 2), and the correct label observations fell from 40 to 31. The label filter needs 2 sweeps, so this margin is too small.
- Text detection on fewer tile rows: all true label observations are between -3 and +40 degrees of elevation. The 0 degree row contains all of them except OKK1 from sweeps 3 and 4. But other sites can have labels high above the devices (see the PRD row-axis fallback), so all 36 tiles stay.
- A prefilter for tiles with no text: the gain is small, because a full detection at low resolution costs about 0.25 of a tile, and small text in an otherwise empty tile is lost.

## Recognition accuracy

Method: mobile text detection on sweeps 7, 10, 11, 12, 13 and 14. Then `Ocr.labels` with each recognizer on the same boxes. This comparison used an earlier version of the filters, so only the ratios between the models are valid. A result is correct when it is equal to a true label with the spaces removed. True labels (from the images): H01 PT1, H02 STATION TRANSFORMER, H03 METERING, H04 SOLAR 1, H05 SOLAR 2, OKK1, TSK1, TSK2, OT1, VLK.

| Recognizer | Correct labels | Other accepted texts | Time for 6 sweeps |
| --- | --- | --- | --- |
| PP-OCRv5_server_rec | 26 | 27 | 59 s |
| PP-OCRv5_mobile_rec | 21 | 34 | 88 s |
| en_PP-OCRv5_mobile_rec | 24 | 40 | 84 s |

The server recognizer also reads the handwritten "S" of TSK1 and TSK2 better. The mobile recognizers read it as "5". On 113 single line crops, the server recognizer took 7.7 s and the mobile recognizer took 13.6 s.

Decision: `PP-OCRv5_server_rec`.

## Results per sweep (final code, default models)

Method: the text detection boxes of each sweep went to a cache file once. Then `Ocr.labels` ran on the cached boxes. Two runs of the final code gave the same output. With the final code, the server recognizer gave 27 correct labels and 27 other texts. The recognizer read each of the 10 true labels correctly from at least one sweep.

| Sweep | Correct | Other accepted texts |
| --- | --- | --- |
| 7 | OT1, VLK | AS, VECO |
| 10 | H01 PT1, H02 STATION TRANSFORMER, OKK1, TSK1, TSK2, VLK | H02 STATION TRANGFORMER, LOT1, EI MOMENTISSA, VEOVECOS, 4013 HOI UI, LCONTR, LANEVA |
| 11 | H02 STATIONTRANSFORMER, H03 METERING, OKK1, OT1, TSK1, TSK2 | AR, KOKO MATKAN, H01 PTI, ME MEPNSSA, VEOVE |
| 12 | H02 STATION TRANSFORMER, H03 METERING, H04 SOLAR1, OKK1, TSK2 | 071, LOLO MATRANN, KOKOOJA WISKO EIMOMERISSA, VEOVE, 81 |
| 13 | H03 METERING, H04 SOLAR1, H05 SOLAR2, OKK1, TSK2 | OT, EI MOMEUTISSA, DADA101 023, ASS, XWE, LANNITIN, HO |
| 14 | H04 SOLAR1, H05 SOLAR2, OKK1 | CONT |

On the same cached boxes, the code before the review fixes gave 25 correct labels and 30 other texts. The main change is the side space of a multi-line view (see the label pipeline below). On sweep 12, the old view cut the "1" of "H04 SOLAR 1".

The other texts are of three types:

- Misreads of a true label (071, LOT1, OT, H01 PTI, TRANGFORMER, HO). The recognizer reads a true label the same from most sweeps, so the merge step can select the most frequent text.
- Handwritten notes on the orange tapes ("KOKOOJA KISKO EI MOMENTISSA", "KOKO MATKAN"). The generic filter cannot find them. The recognizer reads them differently from each sweep.
- Other print: the VEO logo (VEOVE, VECO), a manufacturer plate (LAMMINNEVA KX.27482), a serial number (9ADA181-023), sticker fragments.

## Device names

The REX615 front plates in this scan have no user text. The label strips next to the function keys are empty. So the correct device name is "" for each device.

Method: a box from the corners in `eval/real-devices.json`, projected into the nearest sweep (w1 from sweep 10, w2 from 11, w3 from 12, w4 from 13, w5 from 14, e1 and the hard negative e2 from 7). Each box at 0.9, 1.0 and 1.1 times its size, so 21 views. Then `box_view`, `Ocr.read` and `device_name`, the same calls as `pipeline/run.py`.

Before the review fixes, 6 of the 21 views gave a name: "XEAD" (w1, a misread of READY), "FU" (w2, two views, a misread of an F key), "MEAD" (w2), "TCU" (e1, a misread of PICKUP) and "PICKUPTRIP" (e2, two words read as one). The earlier claim of 8 good views of 9 was not correct. With the final code, all 21 views give "". The fixes:

- A stop word of 5 or more letters matches at edit distance 2 (XEAD, MEAD for READY).
- A join of stop words is a stop word (PICKUPTRIP).
- A stop word with letters and digits matches with one other digit or with one character missing (F23 for F13, 14 for F14).
- `name_min_score` 0.85: `device_name` uses only lines with a score of 0.85 or more. The misreads FU (0.77, 0.79) and TCU (0.61) have low scores. Without this limit, 3 of the 21 views give a name. A real name with a low score gives "", so the review step flags the device with empty_ocr. A wrong name is not flagged.

Tests: `test_device_name_real_blank_plates` uses the lines of the w1 and w2 views.

## Pipeline for cabinet labels

`Ocr.labels(faces, boxes, pano_width, pano_height)` is `label_views` followed by `Ocr.read_labels`. It takes the NMS pano text boxes of one sweep and returns `(block box, detection score, text, text score)` for each cabinet label:

1. `group_lines` joins stacked line boxes of one plate (horizontal overlap of 50 % or more of the narrower box, vertical gap of at most one line height). Example: "H03" and "METERING" become one block.
2. `box_view` renders each block at `LABEL_VIEW_WIDTH` = 320 px. A view of 640 px or more is too blurred for the text detection. Then the reader lost "H05", or read "SOLAR 2" as "SOLAR R2". A block with two or more lines gets `LABEL_PAD` = 1 line height of space on the left and the right, because a text box is sometimes one character too narrow. The view width increases by the same ratio, so the text keeps its pixel size. Side space on single-line views made the result worse: the recognizer read the text next to the label as part of it (25 correct labels became 20 with half a line height on all views).
3. The recognizer reads a block with one line as one crop (batch). A block with more lines goes through `Ocr.reads`: text detection in the view, then lines in reading order. Polygons in the same row that are near each other become one line.
4. `label_text` removes stop words and joins the lines in upper case. The result is "" for a badge, a sticker or device print. Such a block has a line of only stop words, or it has as many stop words as other words.
5. `is_cabinet_label` keeps the text when three conditions are true. The score is at least `min_score`. The text has letters or digits that are not stop words. The text has at most `max_words` words.

On sweep 12, the label step took 8.3 s with the default models. The earlier path (one recognition per line box) read "H03" and "METERING" as two labels, and "STATION TRANSFORMER" as "STAON RANSFOMER".

## Label noise

Date: 2026-10-04. Code: `pipeline/merge.py:vote_text`, `pipeline/cabinets.py:agrees` and `confirmed`, `pipeline/run.py`.

The filter of one line cannot find notes, logos and print. The recognizer reads a handwritten note differently from each sweep, but it reads a true label the same from most sweeps. So the rules use the agreement between sweeps. There is no name pattern and no word list for this site.

1. `text_key`: compare texts with the spaces removed and in lower case. `vote_text` selects the text that the most sweeps read, then the largest text score sum. Of its variants, the one with the most words wins ("H04 SOLAR 1" over "H04 SOLAR1").
2. `agrees`: two texts agree when they are equal after `text_key` and the OCR confusions of `CONFUSABLE` (O and 0, I and 1, ...), with one edit for each 8 characters. Example: "0T1" agrees with "OT1", "H01 PTI" agrees with "H01 PT1".
3. `confirmed`: a label group stays when 2 or more sweeps read a text that agrees with the voted text. A label that only one sweep reads stays only when it is within `review.NEIGHBOR_RADIUS` (4 m) of that sweep and no other sweep in that radius has line of sight to the label anchor in its depth grid.

Results on the full real run (real OCR, ground truth detector):

| | Before | After |
| --- | --- | --- |
| Cabinet tags | 44 label groups | 14 tags |
| True labels in the tags | 10 of 10 | 10 of 10 |
| Other tags | 34 | 4: 200, 2075A20761, LAMMINNEVA KX 27482, VEOVE |
| w3 | the note tape | H03 METERING |

Assignment: w1 H01 PT1, w2 H02 STATION TRANSFORMER, w3 H03 METERING, w4 H04 SOLAR1, w5 H05 SOLAR2, e1 OT1, and the non-target e2 OT1. The images show no other label on the VEO cabinet. The 4 other tags have no devices. Three of them are print that 2 sweeps read the same (a manufacturer plate, a logo misread, a number). 2075A20761 is a serial number that only one sweep sees.

The note tapes sit on the strip between the relay compartment and the door, so they are nearer to the relay than the nameplate. Example: for w1, the note "EI MOMENTISSA" is 0.4 m away and "H01 PT1" is 0.5 m away. So the notes must be removed before the nearest-label step.

The confusable mapping raised the support of OT1 from 3 to 5 sweeps and of H01 PT1 from 2 to 3 sweeps. It raised no other group to 2 sweeps.

Rules that were not used:

- A threshold on the mean text score and the number of agreeing sweeps: no threshold separates the groups. True labels: TSK1 (score 0.67, 3 sweeps), H01 PT1 (0.99, 2 sweeps). Other text: LAMMINNEVA KX 27482 (0.99, 2 sweeps), VEOVE (0.78, 2 sweeps), 200 (0.90, 2 sweeps).
- A group that is a part of a larger group: groups with anchors within `merge_radius` are already one group (single linkage), and on this scan no kept group is a part of another kept group.

## Filters

All values are in `pipeline/ocr-stoplist.json`:

- `min_score` 0.6: minimum recognition score of a line.
- `min_chars` 2: minimum number of letters and digits in a line after the filter removes the stop words.
- `max_words` 3: maximum number of words in a cabinet label. This is a tuning value for each site. The longest label in this scan has 3 words. A label with 4 words (for example "H05 SOLAR 2 SPARE") is rejected. A larger value lets more note tapes through, because many notes have 4 words.
- `name_min_score` 0.85: minimum recognition score of a line for `device_name`.
- `fuzzy_min_length` 4, `fuzzy_long_length` 5: limits for misreads of alphabetic stop words. A token is a misread at edit distance 1 from an alphabetic stop word of 4 or more letters, and at edit distance 2 from one of 5 or more letters.
- Other misreads (fixed rules in `stopped`): the same text after the filter changes the OCR confusions O/0, I/1, L/1, S/5, Z/2 and B/8 to digits (only for stop words of 2 or more characters, so "1" is not "L"). A join of stop words. A stop word of 3 or more characters with one character missing. A stop word with letters and digits with one other digit. A short token with letters and digits does not match a stop word with a different letter, so H10 to H16, Q12, B12 and TR1 are labels.
- `plate_print`: the fixed print of the 615 front plate and LCD menu words. `device_name` removes these words.
- `not_label`: manufacturer print, front plate print, function keys, switch print (LOCAL, REMOTE) and sticker words. `label_text` and `is_cabinet_label` use these words.

A line with a letter that is not Latin is noise (the multilingual recognizer returns Chinese characters for symbols).

There is no name pattern in the code. Known limits of the generic filter:

- It rejects the tokens F0 to F26 and most other tokens F and two digits (F1 to F16 are stop words, and one other digit is a misread). It rejects the label "F17 FEEDER", and `device_name` gives "FEEDER" for it.
- It rejects the tokens 10 to 16, 61, 65 and 15 (F10 to F16 or 615 with one character missing), and 2-character tokens such as AB or ES (ABB or ESC with one character missing).
- A stop word that is also a common name word is removed: LINE and GROUP from device names, CONTROL from device names and labels. MAIN is not a stop word, so "MAIN INCOMER" stays.
- The single-character stop words R and L do not match "1".

## Integration notes

- `pipeline/run.py` uses `Ocr.detect`, `label_views` with `Ocr.read_labels`, and `Ocr.reads` with `device_name` for device boxes. A test fake must have these methods.
- Compare label texts with the spaces removed. The recognizer sometimes drops a space: "H02 STATIONTRANSFORMER", "H04 SOLAR1".
- `Ocr.read` returns one line for the full view when the text detection finds no text.
- `box_view` crops a square tile with `render_tile` and caps the size at `VIEW_MAX_SIZE` = 2048 px to limit memory.
- `box_view` gives a box of zero width or height a size of one pixel at the native focal length, so a degenerate box does not stop the run.

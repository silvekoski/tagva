# OCR

Date: 2026-10-03. Module: `pipeline/ocr.py`. Configuration: `pipeline/ocr-stoplist.json`. Tests: `tests/test_ocr.py`.

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

`Ocr.labels(faces, boxes, pano_width, pano_height)` takes the NMS pano text boxes of one sweep and returns `(block box, detection score, text, text score)` for each cabinet label:

1. `group_lines` joins stacked line boxes of one plate (horizontal overlap of 50 % or more of the narrower box, vertical gap of at most one line height). Example: "H03" and "METERING" become one block.
2. `box_view` renders each block at `LABEL_VIEW_WIDTH` = 320 px. A view of 640 px or more is too blurred for the text detection. Then the reader lost "H05", or read "SOLAR 2" as "SOLAR R2". A block with two or more lines gets `LABEL_PAD` = 1 line height of space on the left and the right, because a text box is sometimes one character too narrow. The view width increases by the same ratio, so the text keeps its pixel size. Side space on single-line views made the result worse: the recognizer read the text next to the label as part of it (25 correct labels became 20 with half a line height on all views).
3. The recognizer reads a block with one line as one crop (batch). A block with more lines goes through `Ocr.read`: text detection in the view, then lines in reading order. Polygons in the same row that are near each other become one line.
4. `label_text` removes stop words and joins the lines in upper case. The result is "" for a badge, a sticker or device print. Such a block has a line of only stop words, or it has as many stop words as other words.
5. `is_cabinet_label` keeps the text when three conditions are true. The score is at least `min_score`. The text has letters or digits that are not stop words. The text has at most `max_words` words.

On sweep 12, the label step took 8.3 s with the default models. The earlier path (one recognition per line box) read "H03" and "METERING" as two labels, and "STATION TRANSFORMER" as "STAON RANSFOMER".

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

- `pipeline/run.py` uses `Ocr.labels` when the reader has it, and `Ocr.read` with `device_name` for device boxes.

- Compare label texts with the spaces removed. The recognizer sometimes drops a space: "H02 STATIONTRANSFORMER", "H04 SOLAR1".
- `Ocr.read` returns one line for the full view when the text detection finds no text.
- `box_view` crops a square tile with `render_tile` and caps the size at `VIEW_MAX_SIZE` = 2048 px to limit memory.
- `box_view` gives a box of zero width or height a size of one pixel at the native focal length, so a degenerate box does not stop the run.
- The pytest marker `slow` is not registered. pytest shows a warning.

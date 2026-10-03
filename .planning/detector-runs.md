# Detector runs

Each run trains on synthetic data only. The real test set (`data/real-test`, 206 tiles, 251 target boxes) is scored once per run. It tunes nothing.

## Confidence floor

The device floor `min_confidence` comes from the synthetic validation split only. The decision was made on 2026-10-04, before the first device-level real result.

Run r1-base-s, synthetic validation, box level:

| Confidence | Precision | Recall |
| --- | --- | --- |
| 0.22 (F1 max) | 0.9877 | 0.9785 |
| 0.50 | 0.9938 | 0.9648 |
| 0.70 | 0.9968 | 0.9532 |
| 0.80 | 0.9984 | 0.9352 |
| 0.85 | 1.0000 | 0.9044 |

A device takes the highest score of all its boxes, and each device has 12 to 16 boxes in this scan. So false positive boxes add up at device level. The floor is the first confidence with no false positive box in the synthetic validation split: 0.85. The default `review_threshold` is 0.90, so a device between 0.85 and 0.90 gets a review flag.

## Runs

| Run | Data | Model | Epochs | Synthetic mAP50 | Real recall at 0.85 (tiles) | Real false positives at 0.85 (tiles) |
| --- | --- | --- | --- | --- | --- | --- |
| r1-base-s | base, 6000 images | YOLO26s | 40 | 0.994 | 1.000 | 0 |

## Device-level acceptance (PRD Step 4)

| Run | Targets found | False positives | Result | Run time |
| --- | --- | --- | --- | --- |
| r1-base-s | 6 / 6 (anchor error 0.010 to 0.019 m, confidence 0.971 to 0.976) | 2: e2 (0.858, 7 boxes) and a box at z = 0.54 m near TSK2 (0.877, 2 boxes) | FAIL | 231 s |

Both false positives of r1 are above the floor by less than 0.03 and get the review reason `low_confidence`. The floor stays at 0.85: a change after this result would tune on the real test set.

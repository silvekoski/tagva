import os
from pathlib import Path

import cv2
import pytest

ultralytics = pytest.importorskip("ultralytics")

WEIGHTS = Path(os.environ.get("REX_TEST_YOLO", "models/yolo26n.pt"))


@pytest.mark.skipif(not WEIGHTS.is_file(), reason="set REX_TEST_YOLO to a stock YOLO .pt file")
def test_detector_output_shape():
    from pipeline.detect import Detector

    bus = cv2.imread(str(Path(ultralytics.__file__).parent / "assets" / "bus.jpg"))
    det = Detector(WEIGHTS, imgsz=640)
    out = det([bus] * 9 + [bus[:200, :200].copy()])
    assert len(out) == 10
    assert all(isinstance(b, list) for b in out)
    assert len(out[0]) >= 1
    for (x0, y0, x1, y1), score in out[0]:
        assert all(isinstance(v, float) for v in (x0, y0, x1, y1, score))
        assert 0 <= x0 < x1 <= bus.shape[1] and 0 <= y0 < y1 <= bus.shape[0] and 0.05 <= score <= 1
    assert det.device in ("mps", "cpu")

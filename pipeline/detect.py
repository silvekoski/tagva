import torch
from ultralytics import YOLO

BATCH = 8


class Detector:
    def __init__(self, weights, device=None, conf=0.05, imgsz=1280):
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model = YOLO(str(weights))
        self.conf = conf
        self.imgsz = imgsz

    def __call__(self, images):
        """images: list of BGR uint8 tiles -> list (one per image) of list of ((x0, y0, x1, y1), score)"""
        out = []
        for i in range(0, len(images), BATCH):
            results = self.model.predict(
                list(images[i:i + BATCH]), imgsz=self.imgsz, conf=self.conf, classes=[0], device=self.device, verbose=False
            )
            for r in results:
                xyxy = r.boxes.xyxy.cpu().numpy().tolist()
                scores = r.boxes.conf.cpu().numpy().tolist()
                out.append([(tuple(b), s) for b, s in zip(xyxy, scores)])
        return out

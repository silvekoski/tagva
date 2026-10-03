import type { Device } from "./types";

export const REASON_LABELS: Record<string, string> = {
  low_confidence: "Low confidence",
  empty_ocr: "No name from OCR",
  no_anchor: "No 3D anchor",
  few_observations: "Seen from one scan position only",
  anchor_variance: "Observations spread too far",
  ocr_conflict: "Different names across observations",
  ambiguous_cabinet: "Two cabinets at similar distance",
};

export const REASONS = Object.keys(REASON_LABELS);

export function reviewReasons(device: Device, threshold: number) {
  const rest = device.review_reasons.filter((r) => r !== "low_confidence");
  return device.confidence < threshold ? ["low_confidence", ...rest] : rest;
}

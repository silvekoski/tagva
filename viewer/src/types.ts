export interface Point3 {
  x: number;
  y: number;
  z: number;
}

export interface Sweep {
  id: string;
  index: number;
  name: string;
  position: [number, number, number];
  rotation: number[][];
  pano: string;
}

export interface Manifest {
  source: string;
  pano_width: number;
  pano_height: number;
  sweeps: Sweep[];
  cloud?: { points: number; xyz: string; rgb: string };
}

export interface Box {
  scan_position: string;
  x: number;
  y: number;
  width: number;
  height: number;
  confidence?: number;
  ocr_text?: string;
}

export interface DocLink {
  title: string;
  kind: string;
  url: string;
}

export interface Device {
  device_id: string;
  name: string;
  device_type: string;
  boxes: Box[];
  anchor: Point3 | null;
  confidence: number;
  documents: DocLink[];
  review: boolean;
  review_reasons: string[];
}

export interface Tag {
  id: string;
  cabinet: string;
  anchor: Point3 | null;
  path: string[];
  devices: Device[];
}

export interface TagFile {
  project: string;
  site: string;
  review_threshold: number;
  merge_radius: number;
  cabinet_radius: number;
  min_confidence?: number;
  scan?: string;
  generated_at?: string;
  tags: Tag[];
}

export interface RunStatus {
  run_id: string;
  project: string;
  state: "running" | "done" | "failed";
  step: string;
  progress: number;
  message: string;
}

export type BoxXyxy = [number, number, number, number];

export interface SynthPlate {
  kind: string;
  labeled: boolean;
  box: BoxXyxy | null;
  width_px: number | null;
  distance_m: number | null;
  off_normal_deg: number | null;
  visible: number | null;
  drop_reason: string | null;
}

export interface SynthImage {
  path: string;
  thumb: string;
  name: string;
  split: "train" | "val";
  width: number;
  height: number;
  boxes: BoxXyxy[];
  dark?: boolean;
  fov_deg?: number;
  camera_z?: number;
  jpeg_quality?: number;
  plates?: SynthPlate[];
}

export interface SynthSetSummary {
  name: string;
  profile: string | null;
  count: number;
  train: number;
  val: number;
}

export interface SynthSet {
  name: string;
  profile: string | null;
  count: number;
  images: SynthImage[];
}

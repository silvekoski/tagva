import * as THREE from "three";
import type { InferenceSession, Tensor } from "onnxruntime-web";
import type { Box, Manifest } from "./types";

export const MIN_CONFIDENCE = 0.85;
const MODEL_URL = "/models/rex615.onnx";
const TILE_SIZE = 1280;
const TILE_FOV = Math.PI / 3;
const TILE_YAWS = 12;
const TILE_PITCHES = [-30, 0, 30].map((d) => (d * Math.PI) / 180);
const TILE_CONFIDENCE = 0.25;
const TILE_IOU = 0.7;
const PANO_OVERLAP = 0.6;
const EDGE_MARGIN = 2;
const BORDER_SAMPLES = 16;

type Vec = [number, number, number];

interface Spec {
  yaw: number;
  pitch: number;
}

interface Candidate {
  box: Box;
  score: number;
  edge: boolean;
}

export interface Detection {
  box: Box;
  score: number;
}

export interface DetectResult {
  detections: Detection[];
  seconds: number;
  backend: string;
  tiles: number;
}

const cross = (a: Vec, b: Vec): Vec => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = (a: Vec): Vec => {
  const n = Math.hypot(a[0], a[1], a[2]);
  return [a[0] / n, a[1] / n, a[2] / n];
};

function basis({ yaw, pitch }: Spec) {
  const f: Vec = [Math.cos(pitch) * Math.cos(yaw), Math.cos(pitch) * Math.sin(yaw), Math.sin(pitch)];
  const r = unit(cross(f, [0, 0, 1]));
  return { f, r, up: cross(r, f) };
}

function specs(): Spec[] {
  return TILE_PITCHES.flatMap((pitch) => Array.from({ length: TILE_YAWS }, (_, k) => ({ yaw: (2 * Math.PI * k) / TILE_YAWS, pitch })));
}

function pixelDir(b: ReturnType<typeof basis>, x: number, y: number): Vec {
  const t = Math.tan(TILE_FOV / 2);
  const sx = (x / TILE_SIZE) * 2 - 1;
  const sy = (y / TILE_SIZE) * 2 - 1;
  return unit([0, 1, 2].map((i) => b.f[i] + sx * t * b.r[i] - sy * t * b.up[i]) as Vec);
}

function equirect(d: Vec, w: number, h: number) {
  const lon = Math.atan2(d[1], d[0]);
  const lat = Math.asin(Math.max(-1, Math.min(1, d[2])));
  return { u: ((Math.PI - lon) / (2 * Math.PI)) * w, v: ((Math.PI / 2 - lat) / Math.PI) * h };
}

function tileBoxToPano(spec: Spec, [x0, y0, x1, y1]: number[], w: number, h: number): Box {
  const b = basis(spec);
  const points: [number, number][] = [];
  for (let i = 0; i < BORDER_SAMPLES; i++) {
    const t = i / (BORDER_SAMPLES - 1);
    points.push([x0 + (x1 - x0) * t, y0], [x1, y0 + (y1 - y0) * t], [x1 - (x1 - x0) * t, y1], [x0, y1 - (y1 - y0) * t]);
  }
  const cu = equirect(pixelDir(b, (x0 + x1) / 2, (y0 + y1) / 2), w, h).u;
  let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
  for (const [x, y] of points) {
    const { u, v } = equirect(pixelDir(b, x, y), w, h);
    const uu = cu + ((((u - cu + w / 2) % w) + w) % w) - w / 2;
    left = Math.min(left, uu);
    right = Math.max(right, uu);
    top = Math.min(top, v);
    bottom = Math.max(bottom, v);
  }
  return { scan_position: "", x: ((left % w) + w) % w, y: top, width: right - left, height: bottom - top };
}

function tileNms(boxes: number[][], scores: number[]) {
  const order = scores.map((_, i) => i).sort((a, b) => scores[b] - scores[a]);
  const kept: number[] = [];
  const area = (b: number[]) => (b[2] - b[0]) * (b[3] - b[1]);
  for (const i of order) {
    const a = boxes[i];
    const clash = kept.some((k) => {
      const b = boxes[k];
      const iw = Math.min(a[2], b[2]) - Math.max(a[0], b[0]);
      const ih = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
      if (iw <= 0 || ih <= 0) return false;
      return (iw * ih) / (area(a) + area(b) - iw * ih) >= TILE_IOU;
    });
    if (!clash) kept.push(i);
  }
  return kept;
}

function panoIntersection(a: Box, b: Box, w: number) {
  let best = 0;
  for (const shift of [-w, 0, w]) {
    const iw = Math.min(a.x + a.width, b.x + shift + b.width) - Math.max(a.x, b.x + shift);
    const ih = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
    if (iw > 0 && ih > 0) best = Math.max(best, iw * ih);
  }
  return best;
}

function panoNms(cands: Candidate[], w: number): Detection[] {
  const order = [...cands].sort((a, b) => Number(a.edge) - Number(b.edge) || b.score - a.score);
  const groups: Detection[] = [];
  for (const c of order) {
    const g = groups.find(
      (k) => panoIntersection(c.box, k.box, w) / Math.max(Math.min(c.box.width * c.box.height, k.box.width * k.box.height), 1e-9) >= PANO_OVERLAP,
    );
    if (g) g.score = Math.max(g.score, c.score);
    else groups.push({ box: c.box, score: c.score });
  }
  return groups;
}

const vertexShader = /* glsl */ `
void main() {
  gl_Position = vec4(position.xy, 0.0, 1.0);
}`;

const fragmentShader = /* glsl */ `
uniform sampler2D tex;
uniform vec3 f;
uniform vec3 r;
uniform vec3 up;
uniform float t;
uniform float size;
const float PI = 3.141592653589793;
void main() {
  float sx = (gl_FragCoord.x / size * 2.0 - 1.0) * t;
  float sy = (gl_FragCoord.y / size * 2.0 - 1.0) * t;
  vec3 d = normalize(f + sx * r - sy * up);
  float lon = atan(d.y, d.x);
  float lat = asin(clamp(d.z, -1.0, 1.0));
  vec2 uv = vec2((PI - lon) / (2.0 * PI), (PI / 2.0 - lat) / PI);
  gl_FragColor = vec4(textureLod(tex, uv, 0.0).rgb, 1.0);
}`;

export class BrowserDetector {
  private session: Promise<{ session: InferenceSession; backend: string; ort: typeof import("onnxruntime-web/webgpu") }> | null = null;
  private readonly target = new THREE.WebGLRenderTarget(TILE_SIZE, TILE_SIZE, { depthBuffer: false });
  private readonly material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    depthTest: false,
    depthWrite: false,
    uniforms: {
      tex: { value: null },
      f: { value: new THREE.Vector3() },
      r: { value: new THREE.Vector3() },
      up: { value: new THREE.Vector3() },
      t: { value: Math.tan(TILE_FOV / 2) },
      size: { value: TILE_SIZE },
    },
  });
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.Camera();
  private readonly pixels = new Uint8Array(TILE_SIZE * TILE_SIZE * 4);
  private readonly input = new Float32Array(3 * TILE_SIZE * TILE_SIZE);

  constructor(private readonly renderer: THREE.WebGLRenderer, private readonly manifest: Manifest) {
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.material);
    quad.frustumCulled = false;
    this.scene.add(quad);
  }

  private load(progress: (text: string) => void) {
    this.session ??= (async () => {
      progress("Loading the browser model");
      const ort = await import("onnxruntime-web/webgpu");
      ort.env.wasm.numThreads = self.crossOriginIsolated ? Math.min(8, navigator.hardwareConcurrency || 4) : 1;
      const res = await fetch(MODEL_URL);
      if (!res.ok) throw new Error(`model: HTTP ${res.status}`);
      const model = new Uint8Array(await res.arrayBuffer());
      if ("gpu" in navigator) {
        try {
          return { session: await ort.InferenceSession.create(model, { executionProviders: ["webgpu"] }), backend: "WebGPU", ort };
        } catch {
          // WebGPU is present but the session failed: fall back to WebAssembly.
        }
      }
      return { session: await ort.InferenceSession.create(model, { executionProviders: ["wasm"] }), backend: "WebAssembly", ort };
    })();
    this.session.catch(() => (this.session = null));
    return this.session;
  }

  private renderTile(texture: THREE.Texture, spec: Spec) {
    const b = basis(spec);
    const u = this.material.uniforms;
    u.tex.value = texture;
    u.f.value.set(...b.f);
    u.r.value.set(...b.r);
    u.up.value.set(...b.up);
    const previous = this.renderer.getRenderTarget();
    this.renderer.setRenderTarget(this.target);
    this.renderer.render(this.scene, this.camera);
    this.renderer.readRenderTargetPixels(this.target, 0, 0, TILE_SIZE, TILE_SIZE, this.pixels);
    this.renderer.setRenderTarget(previous);
    const plane = TILE_SIZE * TILE_SIZE;
    for (let i = 0; i < plane; i++) {
      this.input[i] = this.pixels[4 * i] / 255;
      this.input[plane + i] = this.pixels[4 * i + 1] / 255;
      this.input[2 * plane + i] = this.pixels[4 * i + 2] / 255;
    }
  }

  async detect(texture: THREE.Texture, progress: (text: string, fraction?: number) => void): Promise<DetectResult> {
    const { session, backend, ort } = await this.load(progress);
    const { pano_width: w, pano_height: h } = this.manifest;
    const start = performance.now();
    const cands: Candidate[] = [];
    const all = specs();
    for (const [k, spec] of all.entries()) {
      progress(`Detecting in the browser (${backend}): tile ${k + 1} of ${all.length}`, k / all.length);
      this.renderTile(texture, spec);
      const feeds = { [session.inputNames[0]]: new ort.Tensor("float32", this.input, [1, 3, TILE_SIZE, TILE_SIZE]) };
      const out = (await session.run(feeds))[session.outputNames[0]] as Tensor;
      const data = out.data as Float32Array;
      const n = out.dims[2];
      const boxes: number[][] = [];
      const scores: number[] = [];
      for (let i = 0; i < n; i++) {
        const s = data[4 * n + i];
        if (s < TILE_CONFIDENCE) continue;
        const cx = data[i], cy = data[n + i], bw = data[2 * n + i], bh = data[3 * n + i];
        boxes.push([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]);
        scores.push(s);
      }
      out.dispose();
      for (const i of tileNms(boxes, scores)) {
        const b = boxes[i];
        const edge = Math.min(b[0], b[1]) <= EDGE_MARGIN || Math.max(b[2], b[3]) >= TILE_SIZE - EDGE_MARGIN;
        cands.push({ box: tileBoxToPano(spec, b, w, h), score: scores[i], edge });
      }
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    return { detections: panoNms(cands, w), seconds: (performance.now() - start) / 1000, backend, tiles: all.length };
  }
}

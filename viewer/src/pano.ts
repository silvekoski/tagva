import * as THREE from "three";
import { scanUrl } from "./api";
import { DepthGrid } from "./depth";
import { CAMERA_HEIGHT, toThree } from "./geo";
import type { Box, Manifest, Sweep } from "./types";

const MAX_BOXES = 16;
const SPHERE_RADIUS = 5;
const FADE_MS = 700;
const CACHE_SIZE = 2;
const NEARBY = 6;
const OCCLUSION_MARGIN = 0.3;

const vertexShader = /* glsl */ `
varying vec3 vWorld;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`;

const fragmentShader = /* glsl */ `
#define MAX_BOXES ${MAX_BOXES}
uniform sampler2D tex0;
uniform sampler2D tex1;
uniform vec3 origin0;
uniform vec3 origin1;
uniform float mixT;
uniform vec2 size;
uniform vec4 boxes[MAX_BOXES];
uniform vec3 boxColors[MAX_BOXES];
uniform int boxCount;
varying vec3 vWorld;
const float PI = 3.141592653589793;

vec2 panoUv(vec3 t) {
  vec3 d = normalize(vec3(t.x, -t.z, t.y));
  float lon = atan(d.y, d.x);
  float lat = asin(clamp(d.z, -1.0, 1.0));
  return vec2((PI - lon) / (2.0 * PI), (PI / 2.0 - lat) / PI);
}

void grads(vec2 uv, out vec2 gx, out vec2 gy) {
  gx = dFdx(uv);
  gy = dFdy(uv);
  gx.x -= floor(gx.x + 0.5);
  gy.x -= floor(gy.x + 0.5);
}

vec3 samplePano(sampler2D tex, vec2 uv) {
  vec2 gx, gy;
  grads(uv, gx, gy);
  return textureGrad(tex, uv, gx, gy).rgb;
}

void main() {
  vec2 uv1 = panoUv(vWorld - origin1);
  vec3 c = samplePano(tex1, uv1);
  if (mixT < 1.0) c = mix(samplePano(tex0, panoUv(vWorld - origin0)), c, mixT);
  vec2 gx, gy;
  grads(uv1, gx, gy);
  vec2 px = uv1 * size;
  vec2 perPx = vec2(length(vec2(gx.x, gy.x)), length(vec2(gx.y, gy.y))) * size;
  for (int i = 0; i < MAX_BOXES; i++) {
    if (i >= boxCount) break;
    vec4 b = boxes[i];
    float lx = mod(px.x - b.x, size.x);
    float ly = px.y - b.y;
    if (lx > b.z || ly < 0.0 || ly > b.w) continue;
    float e = min(min(lx, b.z - lx) / perPx.x, min(ly, b.w - ly) / perPx.y);
    if (e < 3.0) c = e < 1.0 ? vec3(0.0) : boxColors[i];
  }
  gl_FragColor = vec4(c, 1.0);
}`;

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const ease = (t: number) => t * t * (3 - 2 * t);

export interface PanoBox {
  box: Box;
  color: THREE.Color;
}

export class PanoView {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(75, 1, 0.05, 1000);
  yaw = 0;
  pitch = 0;
  sweep: Sweep | null = null;
  depth: { id: string; grid: DepthGrid } | null = null;
  onLoading: (sweep: Sweep | null) => void = () => {};
  onChange: () => void = () => {};

  private readonly material: THREE.ShaderMaterial;
  private readonly sphere: THREE.Mesh;
  private readonly rings = new Map<string, THREE.Mesh>();
  private readonly cache = new Map<string, Promise<THREE.Texture>>();
  private readonly live = new Set<THREE.Texture>();
  readonly maxTexture: number;
  private fade: { from: THREE.Vector3; to: THREE.Vector3; start: number } | null = null;
  private jumpToken = 0;

  constructor(private readonly renderer: THREE.WebGLRenderer, readonly manifest: Manifest) {
    this.maxTexture = renderer.capabilities.maxTextureSize;
    const blank = new THREE.DataTexture(new Uint8Array([40, 40, 40, 255]), 1, 1);
    blank.needsUpdate = true;
    this.material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      side: THREE.BackSide,
      depthTest: false,
      depthWrite: false,
      uniforms: {
        tex0: { value: blank },
        tex1: { value: blank },
        origin0: { value: new THREE.Vector3() },
        origin1: { value: new THREE.Vector3() },
        mixT: { value: 1 },
        size: { value: new THREE.Vector2(manifest.pano_width, manifest.pano_height) },
        boxes: { value: Array.from({ length: MAX_BOXES }, () => new THREE.Vector4()) },
        boxColors: { value: Array.from({ length: MAX_BOXES }, () => new THREE.Color()) },
        boxCount: { value: 0 },
      },
    });
    this.sphere = new THREE.Mesh(new THREE.SphereGeometry(SPHERE_RADIUS, 96, 48), this.material);
    this.sphere.renderOrder = -1;
    this.sphere.frustumCulled = false;
    this.scene.add(this.sphere);

    const ringGeometry = new THREE.RingGeometry(0.17, 0.24, 48).rotateX(-Math.PI / 2);
    for (const s of manifest.sweeps) {
      const ring = new THREE.Mesh(
        ringGeometry,
        new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85, depthTest: false }),
      );
      ring.position.copy(this.floorPoint(s));
      this.rings.set(s.id, ring);
      this.scene.add(ring);
    }
  }

  floorPoint(s: Sweep) {
    return toThree([s.position[0], s.position[1], s.position[2] - CAMERA_HEIGHT + 0.02]);
  }

  private texture(s: Sweep): Promise<THREE.Texture> {
    let p = this.cache.get(s.id);
    if (p) this.cache.delete(s.id);
    else {
      const q: Promise<THREE.Texture> = this.loadTexture(s).then((t) => ((t.userData.source = q), t));
      p = q;
    }
    this.cache.set(s.id, p);
    p.catch(() => this.cache.delete(s.id));
    while (this.cache.size > CACHE_SIZE + 1) this.cache.delete(this.cache.keys().next().value!);
    return p;
  }

  private prune() {
    const u = this.material.uniforms;
    for (const t of this.live) {
      if (t === u.tex0.value || t === u.tex1.value || this.cache.get(t.userData.sweep) === t.userData.source) continue;
      t.dispose();
      this.live.delete(t);
    }
  }

  private async loadTexture(s: Sweep) {
    const res = await fetch(scanUrl(s.pano));
    if (!res.ok) throw new Error(`Panorama ${s.id}: HTTP ${res.status}`);
    const blob = await res.blob();
    const w = Math.min(this.manifest.pano_width, this.maxTexture);
    const opts: ImageBitmapOptions =
      w < this.manifest.pano_width ? { resizeWidth: w, resizeHeight: w / 2, resizeQuality: "high" } : {};
    const bitmap = await createImageBitmap(blob, opts);
    const t = new THREE.Texture(bitmap);
    t.flipY = false;
    t.wrapS = THREE.RepeatWrapping;
    t.colorSpace = THREE.NoColorSpace;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    t.onUpdate = () => bitmap.close();
    t.userData.sweep = s.id;
    t.needsUpdate = true;
    this.live.add(t);
    return t;
  }

  async jump(s: Sweep, animate = true) {
    if (this.sweep?.id === s.id) return;
    const token = ++this.jumpToken;
    this.onLoading(s);
    let tex: THREE.Texture;
    try {
      tex = await this.texture(s);
    } finally {
      if (token === this.jumpToken) this.onLoading(null);
    }
    if (token !== this.jumpToken) return;
    const u = this.material.uniforms;
    const to = toThree(s.position);
    const from = this.sweep ? this.camera.position.clone() : to.clone();
    u.tex0.value = u.tex1.value;
    u.origin0.value.copy(from);
    u.tex1.value = tex;
    u.origin1.value.copy(to);
    this.sweep = s;
    this.prune();
    this.depth = null;
    DepthGrid.load(scanUrl(`depth/${s.id}.npz`), s.rotation).then(
      (grid) => {
        if (this.sweep?.id !== s.id) return;
        this.depth = { id: s.id, grid };
        this.onChange();
      },
      () => {},
    );
    if (animate && !prefersReducedMotion() && from.distanceTo(to) > 0) {
      this.fade = { from, to, start: performance.now() };
      u.mixT.value = 0;
    } else {
      this.fade = null;
      u.mixT.value = 1;
      this.camera.position.copy(to);
    }
    this.onChange();
  }

  setBoxes(items: PanoBox[]) {
    const u = this.material.uniforms;
    const n = Math.min(items.length, MAX_BOXES);
    for (let i = 0; i < n; i++) {
      const b = items[i].box;
      u.boxes.value[i].set(b.x, b.y, b.width, b.height);
      u.boxColors.value[i].copy(items[i].color);
    }
    u.boxCount.value = n;
  }

  lookAtPixel(u: number, v: number) {
    const { pano_width: w, pano_height: h } = this.manifest;
    this.yaw = Math.PI - (u / w) * 2 * Math.PI;
    this.pitch = Math.PI / 2 - (v / h) * Math.PI;
    this.onChange();
  }

  look(dYaw: number, dPitch: number) {
    this.yaw += dYaw;
    this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch + dPitch));
    this.onChange();
  }

  zoom(factor: number) {
    this.camera.fov = Math.max(25, Math.min(100, this.camera.fov * factor));
    this.camera.updateProjectionMatrix();
    this.onChange();
  }

  get animating() {
    return this.fade !== null;
  }

  update(now: number) {
    if (this.fade) {
      const t = Math.min(1, (now - this.fade.start) / FADE_MS);
      this.camera.position.lerpVectors(this.fade.from, this.fade.to, ease(t));
      this.material.uniforms.mixT.value = ease(t);
      if (t >= 1) this.fade = null;
    }
    const c = Math.cos(this.pitch);
    const dir = toThree([c * Math.cos(this.yaw), c * Math.sin(this.yaw), Math.sin(this.pitch)]);
    this.camera.lookAt(this.camera.position.clone().add(dir));
    this.sphere.position.copy(this.camera.position);
    for (const [id, ring] of this.rings) ring.visible = this.isNearby(id);
  }

  occluded(p: THREE.Vector3) {
    if (!this.depth || this.fade) return false;
    const v = p.clone().sub(this.camera.position);
    const r = this.depth.grid.range(v);
    return r > 0 && v.length() > r + OCCLUSION_MARGIN;
  }

  isNearby(id: string) {
    const ring = this.rings.get(id);
    return (
      !!ring &&
      this.sweep !== null &&
      id !== this.sweep.id &&
      ring.position.distanceTo(this.camera.position) < NEARBY &&
      !this.occluded(ring.position)
    );
  }
}

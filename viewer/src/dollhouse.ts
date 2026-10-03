import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { scanUrl } from "./api";
import { toThree } from "./geo";
import type { Manifest } from "./types";

const POINT_SIZE = 0.02;

const vertexShader = /* glsl */ `
uniform float scale;
uniform float pointSize;
varying vec3 vColor;
varying float vHeight;
void main() {
  vColor = color;
  vHeight = position.y;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = max(1.0, pointSize * scale / -mv.z);
  gl_Position = projectionMatrix * mv;
}`;

const fragmentShader = /* glsl */ `
uniform float cut;
varying vec3 vColor;
varying float vHeight;
void main() {
  if (vHeight > cut) discard;
  gl_FragColor = vec4(vColor, 1.0);
}`;

export class Dollhouse {
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(55, 1, 0.05, 500);
  readonly controls: OrbitControls;
  status = "";
  private loaded: Promise<void> | null = null;
  private readonly material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    vertexColors: true,
    uniforms: { scale: { value: 1 }, pointSize: { value: POINT_SIZE }, cut: { value: 2.6 } },
  });

  constructor(dom: HTMLElement, private readonly manifest: Manifest, private readonly onChange: () => void) {
    this.scene.background = new THREE.Color(0x15181c);
    const grid = new THREE.GridHelper(40, 40, 0x3a414a, 0x262b31);
    this.scene.add(grid);
    const c = new THREE.Vector3();
    for (const s of manifest.sweeps) c.add(toThree(s.position));
    c.divideScalar(Math.max(1, manifest.sweeps.length)).setY(1);
    this.controls = new OrbitControls(this.camera, dom);
    this.controls.target.copy(c);
    this.camera.position.copy(c).add(new THREE.Vector3(6, 9, 8));
    this.controls.update();
    this.controls.addEventListener("change", onChange);
    this.controls.enabled = false;
  }

  get cut() {
    return this.material.uniforms.cut.value as number;
  }

  set cut(v: number) {
    this.material.uniforms.cut.value = v;
    this.onChange();
  }

  resize(width: number, height: number) {
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.material.uniforms.scale.value = height / (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2));
  }

  load() {
    this.loaded ??= this.fetchCloud().catch((e) => {
      this.status = `The point cloud did not load: ${(e as Error).message}`;
      this.onChange();
    });
    return this.loaded;
  }

  private async fetchCloud() {
    const cloud = this.manifest.cloud;
    if (!cloud) {
      this.status = "This scan has no point cloud yet. The view shows the scan positions and tags only.";
      return;
    }
    this.status = `Loading ${cloud.points.toLocaleString("en-US")} points`;
    this.onChange();
    const [xyzRes, rgbRes] = await Promise.all([fetch(scanUrl(cloud.xyz)), fetch(scanUrl(cloud.rgb))]);
    if (!xyzRes.ok || !rgbRes.ok) throw new Error(`HTTP ${xyzRes.ok ? rgbRes.status : xyzRes.status}`);
    const xyz = new Float32Array(await xyzRes.arrayBuffer());
    const rgb = new Uint8Array(await rgbRes.arrayBuffer());
    const n = Math.min(xyz.length / 3, rgb.length / 3);
    for (let i = 0; i < n * 3; i += 3) {
      const y = xyz[i + 1];
      xyz[i + 1] = xyz[i + 2];
      xyz[i + 2] = -y;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(xyz.subarray(0, n * 3), 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(rgb.subarray(0, n * 3), 3, true));
    this.scene.add(new THREE.Points(geometry, this.material));
    this.status = "";
    this.onChange();
  }

  key(e: KeyboardEvent) {
    if (e.shiftKey && e.key.startsWith("Arrow")) return this.pan(e.key);
    const offset = this.camera.position.clone().sub(this.controls.target);
    const s = new THREE.Spherical().setFromVector3(offset);
    const step = 0.08;
    if (e.key === "ArrowLeft") s.theta -= step;
    else if (e.key === "ArrowRight") s.theta += step;
    else if (e.key === "ArrowUp") s.phi -= step;
    else if (e.key === "ArrowDown") s.phi += step;
    else if (e.key === "+" || e.key === "=") s.radius *= 0.85;
    else if (e.key === "-" || e.key === "_") s.radius /= 0.85;
    else return false;
    s.phi = Math.max(0.05, Math.min(Math.PI / 2 - 0.02, s.phi));
    s.radius = Math.max(1, Math.min(60, s.radius));
    this.camera.position.copy(this.controls.target).add(new THREE.Vector3().setFromSpherical(s));
    this.controls.update();
    return true;
  }

  private pan(key: string) {
    const forward = this.controls.target.clone().sub(this.camera.position).setY(0);
    if (forward.lengthSq() < 1e-9) return false;
    forward.normalize().multiplyScalar(0.05 * this.camera.position.distanceTo(this.controls.target));
    const right = new THREE.Vector3(-forward.z, 0, forward.x);
    const move = { ArrowUp: forward, ArrowDown: forward.clone().negate(), ArrowRight: right, ArrowLeft: right.clone().negate() }[key];
    if (!move) return false;
    this.controls.target.add(move);
    this.camera.position.add(move);
    this.controls.update();
    return true;
  }
}

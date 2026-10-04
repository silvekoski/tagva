import * as THREE from "three";
import { raycast } from "./api";
import { BrowserDetector, type DetectResult, type Detection } from "./detect";
import { h } from "./dom";
import { Dollhouse } from "./dollhouse";
import { panoDir, panoPixel, toThree } from "./geo";
import { Overlay, type Marker } from "./overlay";
import { PanoView } from "./pano";
import { deviceLabel, isReview } from "./review";
import type { Box, Device, Manifest, Point3, Sweep, Tag, TagFile } from "./types";

export type Mode = "pano" | "dollhouse";

export interface Selection {
  tag: Tag;
  device?: Device;
}

export interface PlayerState {
  file: TagFile | null;
  threshold: number;
  showAll: boolean;
  selection: Selection | null;
}

export interface PlayerEvents {
  select(tag: Tag, device?: Device): void;
  sweep(sweep: Sweep): void;
  mode(mode: Mode): void;
  status(text: string, ms?: number): void;
  escape(target: HTMLElement): void;
}

const BOX_COLORS = {
  review: new THREE.Color(1, 0.69, 0.13),
  ok: new THREE.Color(0.24, 0.86, 0.52),
  browser: new THREE.Color(0.2, 0.85, 1),
};
const CSS_COLOR = { review: "var(--review)", ok: "var(--ok)", browser: "var(--browser)" };
const ARIA = {
  pano: "Panorama view. Drag, or use the arrow keys, to look around. Use the wheel, a pinch, or the plus and minus keys to zoom.",
  dollhouse:
    "Dollhouse view. Drag, or use the arrow keys, to orbit. Right-drag, or use Shift and the arrow keys, to pan. Use the wheel, a pinch, or the plus and minus keys to zoom.",
};
const LAYERS = "[role=dialog], [role=listbox], [role=menu], [data-radix-popper-content-wrapper]";

export const boxCenter = (b: Box, width: number) => ({ u: (b.x + b.width / 2) % width, v: b.y + b.height / 2 });

export class Player {
  readonly sweepById: Map<string, Sweep>;
  mode: Mode = "pano";
  private state: PlayerState = { file: null, threshold: 0.9, showAll: false, selection: null };
  private readonly renderer: THREE.WebGLRenderer;
  private readonly pano: PanoView;
  private readonly doll: Dollhouse;
  private readonly overlay: Overlay;
  private readonly detector: BrowserDetector;
  private readonly browserBoxes = new Map<string, Detection[]>();
  private placing: ((p: Point3 | null | undefined) => void) | null = null;
  private frame = 0;
  private readonly cleanup: (() => void)[] = [];

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly stage: HTMLElement,
    overlayRoot: HTMLElement,
    readonly manifest: Manifest,
    private readonly events: PlayerEvents,
  ) {
    this.sweepById = new Map(manifest.sweeps.map((s) => [s.id, s]));
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.pano = new PanoView(this.renderer, manifest);
    this.doll = new Dollhouse(canvas, manifest, () => this.requestRender());
    this.overlay = new Overlay(overlayRoot);
    this.detector = new BrowserDetector(this.renderer, manifest);
    this.pano.onChange = () => this.requestRender();
    this.pano.onLoading = (s) => events.status(s ? `Loading the panorama for ${s.id}` : "");
    canvas.setAttribute("aria-label", ARIA.pano);
    if (this.pano.maxTexture < manifest.pano_width) {
      events.status(`The GPU texture limit is ${this.pano.maxTexture} px. The panoramas show at a reduced resolution.`, 8000);
    }
    const resize = new ResizeObserver(() => this.requestRender());
    resize.observe(stage);
    this.cleanup.push(() => resize.disconnect());
    this.bindPointer();
    this.bindKeys();
    this.buildMarkers();
  }

  get sweep() {
    return this.pano.sweep;
  }

  get cut() {
    return this.doll.cut;
  }

  set cut(v: number) {
    this.doll.cut = v;
  }

  dispose() {
    cancelAnimationFrame(this.frame);
    for (const f of this.cleanup) f();
    this.doll.controls.dispose();
    this.renderer.dispose();
  }

  update(next: Partial<PlayerState>) {
    this.state = { ...this.state, ...next };
    this.buildMarkers();
    this.updateBoxes();
  }

  private requestRender() {
    if (!this.frame) this.frame = requestAnimationFrame((t) => this.draw(t));
  }

  private draw(now: number) {
    this.frame = 0;
    const { canvas, renderer, pano, doll, stage } = this;
    const w = stage.clientWidth;
    const hgt = stage.clientHeight;
    if (!w || !hgt) return;
    const ratio = renderer.getPixelRatio();
    if (canvas.width !== Math.round(w * ratio) || canvas.height !== Math.round(hgt * ratio)) {
      renderer.setSize(w, hgt, false);
      pano.camera.aspect = w / hgt;
      pano.camera.updateProjectionMatrix();
      doll.resize(w, hgt);
    }
    const camera = this.mode === "pano" ? pano.camera : doll.camera;
    if (this.mode === "pano") pano.update(now);
    renderer.render(this.mode === "pano" ? pano.scene : doll.scene, camera);
    this.overlay.update(camera, w, hgt);
    if (this.mode === "pano" && pano.animating) this.requestRender();
  }

  private drawNow() {
    cancelAnimationFrame(this.frame);
    this.draw(performance.now());
  }

  sweepBoxes() {
    const sid = this.pano.sweep?.id;
    const { file, showAll, threshold } = this.state;
    if (!sid || !showAll) return [];
    const devices = (file?.tags ?? []).flatMap((t) => t.devices);
    return [
      ...devices.flatMap((d) => {
        const kind = isReview(d, threshold) ? ("review" as const) : ("ok" as const);
        return d.boxes
          .filter((b) => b.scan_position === sid)
          .map((box) => ({ box, kind, score: box.confidence ?? d.confidence, label: deviceLabel(d) }));
      }),
      ...(this.browserBoxes.get(sid) ?? []).map((x) => ({ box: x.box, kind: "browser" as const, score: x.score, label: "Browser detection" })),
    ];
  }

  private updateBoxes() {
    this.pano.setBoxes(this.sweepBoxes().map(({ box, kind }) => ({ box, color: BOX_COLORS[kind] })));
    this.requestRender();
  }

  private boxLabels(): Marker[] {
    const sweep = this.pano.sweep;
    if (!this.state.showAll || this.mode !== "pano" || !sweep) return [];
    const origin = toThree(sweep.position);
    const { pano_width: w, pano_height: hh } = this.manifest;
    return this.sweepBoxes().map(({ box, kind, score, label }) => ({
      pos: origin.clone().add(panoDir(box.x, box.y, w, hh)),
      el: h("span", { class: "box-label", style: `--box-color: ${CSS_COLOR[kind]}`, title: label }, score.toFixed(2)),
    }));
  }

  private buildMarkers() {
    const { file, threshold } = this.state;
    const pano = this.pano;
    const ms: Marker[] = this.boxLabels();
    for (const t of file?.tags ?? []) {
      if (t.anchor && t.id !== "tag-unassigned") {
        const n = t.devices.length;
        const pos = toThree(t.anchor);
        ms.push({
          pos,
          occluded: () => this.mode === "pano" && pano.occluded(pos),
          el: h(
            "button",
            {
              type: "button",
              class: "pin cabinet",
              "data-key": t.id,
              "aria-label": `Cabinet ${t.cabinet}, ${n} ${n === 1 ? "device" : "devices"}`,
              onclick: () => this.events.select(t),
            },
            h("span", { class: "pin-label" }, t.cabinet),
          ),
        });
      }
      for (const d of t.devices) {
        if (!d.anchor) continue;
        const review = isReview(d, threshold);
        const pos = toThree(d.anchor);
        ms.push({
          pos,
          occluded: () => this.mode === "pano" && pano.occluded(pos),
          el: h(
            "button",
            {
              type: "button",
              class: `pin device ${review ? "review" : "ok"}`,
              "data-key": d.device_id,
              "aria-label": `Device ${deviceLabel(d)} in ${t.cabinet}, ${review ? "needs review" : "OK"}`,
              onclick: () => this.events.select(t, d),
            },
            h("span", { class: "pin-badge", "aria-hidden": "true" }, review ? "!" : "✓"),
            h("span", { class: "pin-label" }, deviceLabel(d)),
          ),
        });
      }
    }
    for (const s of this.manifest.sweeps) {
      ms.push(
        this.mode === "pano"
          ? {
              pos: pano.floorPoint(s),
              radius: 0.24,
              visible: () => pano.isNearby(s.id),
              el: h("button", { type: "button", class: "hotspot", "aria-label": `Go to scan position ${s.id}`, onclick: () => this.goTo(s) }),
            }
          : {
              pos: pano.floorPoint(s),
              el: h(
                "button",
                { type: "button", class: "sweep-dot", "aria-label": `Enter the panorama at ${s.id}`, onclick: () => this.goTo(s) },
                String(s.index),
              ),
            },
      );
    }
    this.overlay.set(ms);
    const sel = this.state.selection;
    const key = sel?.device?.device_id ?? sel?.tag.id;
    for (const el of this.overlay.root.querySelectorAll<HTMLElement>(".pin")) el.classList.toggle("selected", el.dataset.key === key);
    this.requestRender();
  }

  async goTo(s: Sweep, look?: { u: number; v: number }) {
    if (this.mode !== "pano") this.setMode("pano");
    try {
      await this.pano.jump(s);
    } catch (e) {
      this.events.status(`The panorama for ${s.id} did not load: ${(e as Error).message}`, 8000);
      return;
    }
    if (look) this.pano.lookAtPixel(look.u, look.v);
    this.events.sweep(s);
    this.updateBoxes();
    if (this.state.showAll) this.buildMarkers();
    this.drawNow();
    const focused = document.activeElement as HTMLElement | null;
    if (!focused || focused === document.body || (this.overlay.root.contains(focused) && focused.hidden)) this.canvas.focus();
  }

  async start(sweep: Sweep) {
    try {
      await this.pano.jump(sweep, false);
      this.events.sweep(sweep);
      this.requestRender();
    } catch (e) {
      this.events.status(`The panorama for ${sweep.id} did not load: ${(e as Error).message}`);
    }
  }

  showBox(b: Box) {
    const s = this.sweepById.get(b.scan_position);
    if (s) this.goTo(s, boxCenter(b, this.manifest.pano_width));
  }

  face(tag: Tag, device?: Device) {
    const { pano, manifest } = this;
    if (this.mode !== "pano" || !pano.sweep) return;
    const here = pano.sweep.id;
    const box = device?.boxes.find((b) => b.scan_position === here);
    if (box) {
      const c = boxCenter(box, manifest.pano_width);
      return pano.lookAtPixel(c.u, c.v);
    }
    const anchor = device ? device.anchor : tag.anchor;
    if (anchor) {
      const p = panoPixel(toThree(anchor).sub(pano.camera.position), manifest.pano_width, manifest.pano_height);
      return pano.lookAtPixel(p.u, p.v);
    }
    const other = device?.boxes[0];
    if (other) this.showBox(other);
  }

  flush() {
    this.drawNow();
  }

  setMode(m: Mode) {
    if (m === this.mode) return;
    this.mode = m;
    this.doll.controls.enabled = m === "dollhouse";
    this.stage.classList.toggle("dollhouse", m === "dollhouse");
    this.canvas.setAttribute("aria-label", ARIA[m]);
    if (m === "dollhouse") {
      if (this.placing) this.finishPlacing(undefined);
      const loading = this.doll.load();
      this.events.status(this.doll.status);
      loading.then(() => this.mode === "dollhouse" && this.events.status(this.doll.status));
    } else this.events.status("");
    this.events.mode(m);
    this.buildMarkers();
  }

  placeAnchor() {
    return new Promise<Point3 | null | undefined>((resolve) => {
      this.placing?.(undefined);
      if (this.mode !== "pano") this.setMode("pano");
      this.placing = resolve;
      this.stage.classList.add("placing");
      this.events.status("Click the panorama to place the anchor, or press Enter to place it at the view center. Press Escape to cancel.");
    });
  }

  cancelPlacing() {
    if (this.placing) this.finishPlacing(undefined);
  }

  private finishPlacing(p: Point3 | null | undefined) {
    const done = this.placing;
    this.placing = null;
    this.stage.classList.remove("placing");
    this.events.status("");
    done?.(p);
  }

  private async placeAt(clientX: number, clientY: number) {
    const sweep = this.pano.sweep;
    if (!sweep) return this.finishPlacing(undefined);
    const rect = this.canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, this.pano.camera);
    const { u, v } = panoPixel(ray.ray.direction, this.manifest.pano_width, this.manifest.pano_height);
    this.events.status("Looking up the scan point");
    try {
      const res = await raycast(sweep.id, u, v);
      this.finishPlacing(res.anchor);
    } catch (e) {
      this.events.status(`Raycast failed: ${(e as Error).message}`, 6000);
      this.finishPlacing(undefined);
    }
  }

  async detectInBrowser(
    floor: number,
    progress: (text: string, fraction?: number) => void,
  ): Promise<{ sweep: Sweep; found: Detection[]; result: DetectResult }> {
    const sweep = this.pano.sweep;
    const texture = this.pano.currentTexture();
    if (this.mode !== "pano" || !sweep || !texture) throw new Error("Open a panorama first.");
    const result = await this.detector.detect(texture, progress);
    const found = result.detections.filter((x) => x.score >= floor).sort((a, b) => b.score - a.score);
    this.browserBoxes.set(sweep.id, found);
    this.updateBoxes();
    if (this.state.showAll) this.buildMarkers();
    return { sweep, found, result };
  }

  private listen<K extends keyof HTMLElementEventMap>(
    target: HTMLElement,
    type: K,
    fn: (e: HTMLElementEventMap[K]) => void,
    opts?: AddEventListenerOptions,
  ) {
    target.addEventListener(type, fn, opts);
    this.cleanup.push(() => target.removeEventListener(type, fn, opts));
  }

  private bindPointer() {
    const { canvas, stage, pano } = this;
    const pointers = new Map<number, { x: number; y: number }>();
    let down: { x: number; y: number } | null = null;
    let moved = false;
    let pinch = 0;
    const spread = () => {
      const [a, b] = [...pointers.values()];
      return Math.hypot(a.x - b.x, a.y - b.y);
    };
    this.listen(canvas, "pointerdown", (e) => {
      if (this.mode !== "pano") return;
      canvas.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.size === 1) {
        down = { x: e.clientX, y: e.clientY };
        moved = false;
        stage.classList.add("dragging");
      } else {
        moved = true;
        pinch = spread();
      }
    });
    this.listen(canvas, "pointermove", (e) => {
      const prev = pointers.get(e.pointerId);
      if (!prev || this.mode !== "pano") return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.size === 1) {
        if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) moved = true;
        const k = THREE.MathUtils.degToRad(pano.camera.fov) / canvas.clientHeight;
        pano.look((e.clientX - prev.x) * k, (e.clientY - prev.y) * k);
      } else if (pointers.size === 2) {
        const d = spread();
        if (d > 0 && pinch > 0) pano.zoom(pinch / d);
        pinch = d;
      }
    });
    const up = (e: PointerEvent) => {
      if (!pointers.delete(e.pointerId)) return;
      if (pointers.size === 0) {
        stage.classList.remove("dragging");
        if (!moved && down && this.placing && e.type === "pointerup") this.placeAt(e.clientX, e.clientY);
        down = null;
      }
    };
    this.listen(canvas, "pointerup", up);
    this.listen(canvas, "pointercancel", up);
    this.listen(
      canvas,
      "wheel",
      (e) => {
        if (this.mode !== "pano") return;
        e.preventDefault();
        pano.zoom(Math.exp(e.deltaY * 0.001));
      },
      { passive: false },
    );
  }

  private bindKeys() {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      const { canvas, pano } = this;
      if (e.key === "Escape") {
        if (t.closest?.(LAYERS)) return;
        if (this.placing) this.finishPlacing(undefined);
        else this.events.escape(t);
        return;
      }
      if (!(t === document.body || t === canvas || this.overlay.root.contains(t))) return;
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (this.mode === "dollhouse") {
        if (this.doll.key(e)) e.preventDefault();
        return;
      }
      if (this.placing && t === canvas && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        const r = canvas.getBoundingClientRect();
        this.placeAt(r.left + r.width / 2, r.top + r.height / 2);
        return;
      }
      const step = THREE.MathUtils.degToRad(pano.camera.fov) / 12;
      const actions: Record<string, () => void> = {
        ArrowLeft: () => pano.look(step, 0),
        ArrowRight: () => pano.look(-step, 0),
        ArrowUp: () => pano.look(0, step),
        ArrowDown: () => pano.look(0, -step),
        "+": () => pano.zoom(0.85),
        "=": () => pano.zoom(0.85),
        "-": () => pano.zoom(1 / 0.85),
        _: () => pano.zoom(1 / 0.85),
      };
      const action = actions[e.key];
      if (action) {
        e.preventDefault();
        action();
      }
    };
    window.addEventListener("keydown", onKey);
    this.cleanup.push(() => window.removeEventListener("keydown", onKey));
  }
}

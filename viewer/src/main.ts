import * as THREE from "three";
import { getRun, getScan, getTags, putTags, raycast, startRun } from "./api";
import { $, h } from "./dom";
import { BrowserDetector, MIN_CONFIDENCE, type Detection } from "./detect";
import { Dollhouse } from "./dollhouse";
import { panoDir, panoPixel, toThree } from "./geo";
import { Overlay, type Marker } from "./overlay";
import { deviceLabel, Panel } from "./panel";
import { PanoView } from "./pano";
import { reviewReasons } from "./review";
import type { Box, Device, Manifest, Point3, Sweep, Tag, TagFile } from "./types";

const REVIEW_COLOR = new THREE.Color(1, 0.69, 0.13);
const OK_COLOR = new THREE.Color(0.24, 0.86, 0.52);
const BROWSER_COLOR = new THREE.Color(0.2, 0.85, 1);
const CSS_COLOR = { review: "var(--review)", ok: "var(--ok)", browser: "var(--browser)" };

const canvas = $<HTMLCanvasElement>("stage-canvas");
const stage = $("stage");
const stageStatus = $("stage-status");
const projectInput = $<HTMLInputElement>("project");
const siteInput = $<HTMLInputElement>("site");
const runButton = $<HTMLButtonElement>("run");
const detectButton = $<HTMLButtonElement>("detect-browser");
const showBoxesButton = $<HTMLButtonElement>("show-boxes");
const runStatus = $("run-status");
const thresholdInput = $<HTMLInputElement>("threshold");
const cutInput = $<HTMLInputElement>("cut-height");

let statusTimer = 0;
function say(text: string, ms = 0) {
  clearTimeout(statusTimer);
  stageStatus.textContent = text;
  stageStatus.hidden = !text;
  if (ms) statusTimer = window.setTimeout(() => say(""), ms);
}

function showRun(text: string, progress?: number) {
  runStatus.hidden = false;
  $("run-text").textContent = text;
  const bar = $<HTMLProgressElement>("run-progress");
  bar.hidden = progress === undefined;
  if (progress !== undefined) bar.value = progress;
}

async function boot() {
  let manifest: Manifest;
  try {
    manifest = await getScan();
  } catch (e) {
    say(`The scan did not load (${(e as Error).message}). Start the API on port 8000 and reload the page.`);
    return;
  }
  start(manifest);
}

function start(manifest: Manifest) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const pano = new PanoView(renderer, manifest);
  const doll = new Dollhouse(canvas, manifest, () => requestRender());
  const overlay = new Overlay($("overlay"));
  const browserDetector = new BrowserDetector(renderer, manifest);
  const browserBoxes = new Map<string, Detection[]>();
  let showAll = false;
  const sweepById = new Map(manifest.sweeps.map((s) => [s.id, s]));

  let file: TagFile | null = null;
  let threshold = Number(thresholdInput.value);
  let mode: "pano" | "dollhouse" = "pano";
  let placing: ((p: Point3 | null | undefined) => void) | null = null;
  let returnFocus: HTMLElement | null = null;

  if (pano.maxTexture < manifest.pano_width) {
    say(`The GPU texture limit is ${pano.maxTexture} px. The panoramas show at a reduced resolution.`, 8000);
  }

  let frame = 0;
  function requestRender() {
    if (!frame) frame = requestAnimationFrame(draw);
  }
  function draw(now: number) {
    frame = 0;
    const w = stage.clientWidth;
    const hgt = stage.clientHeight;
    if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(hgt * renderer.getPixelRatio())) {
      renderer.setSize(w, hgt, false);
      pano.camera.aspect = w / hgt;
      pano.camera.updateProjectionMatrix();
      doll.resize(w, hgt);
    }
    const camera = mode === "pano" ? pano.camera : doll.camera;
    if (mode === "pano") pano.update(now);
    renderer.render(mode === "pano" ? pano.scene : doll.scene, camera);
    overlay.update(camera, w, hgt);
    if (mode === "pano" && pano.animating) requestRender();
  }
  pano.onChange = requestRender;
  pano.onLoading = (s) => (s ? say(`Loading the panorama for ${s.id}`) : say(""));
  new ResizeObserver(requestRender).observe(stage);

  const isReview = (d: Device) => reviewReasons(d, threshold).length > 0;
  const findDevice = (id: string) => {
    for (const t of file?.tags ?? []) for (const d of t.devices) if (d.device_id === id) return { tag: t, device: d };
    return null;
  };

  function sweepBoxes() {
    const sid = pano.sweep?.id;
    if (!sid) return [];
    const selected = panel.selection?.device;
    const devices = showAll ? (file?.tags ?? []).flatMap((t) => t.devices) : selected ? [selected] : [];
    return [
      ...devices.flatMap((d) => {
        const kind = isReview(d) ? ("review" as const) : ("ok" as const);
        return d.boxes.filter((b) => b.scan_position === sid).map((box) => ({ box, kind, score: box.confidence ?? d.confidence, label: deviceLabel(d) }));
      }),
      ...(browserBoxes.get(sid) ?? []).map((x) => ({ box: x.box, kind: "browser" as const, score: x.score, label: "Browser detection" })),
    ];
  }

  function boxLabels(): Marker[] {
    if (!showAll || mode !== "pano" || !pano.sweep) return [];
    const origin = toThree(pano.sweep.position);
    return sweepBoxes().map(({ box, kind, score, label }) => ({
      pos: origin.clone().add(panoDir(box.x, box.y, manifest.pano_width, manifest.pano_height)),
      el: h("span", { class: "box-label", style: `--box-color: ${CSS_COLOR[kind]}`, title: label }, score.toFixed(2)),
    }));
  }

  function buildMarkers() {
    const ms: Marker[] = [...boxLabels()];
    for (const t of file?.tags ?? []) {
      if (t.anchor && t.id !== "tag-unassigned") {
        const n = t.devices.length;
        const pos = toThree(t.anchor);
        ms.push({
          pos,
          occluded: () => mode === "pano" && pano.occluded(pos),
          el: h(
            "button",
            {
              type: "button",
              class: "pin cabinet",
              "data-key": t.id,
              "aria-label": `Cabinet ${t.cabinet}, ${n} ${n === 1 ? "device" : "devices"}`,
              onclick: () => select(t),
            },
            h("span", { class: "pin-label" }, t.cabinet),
          ),
        });
      }
      for (const d of t.devices) {
        if (!d.anchor) continue;
        const review = isReview(d);
        const pos = toThree(d.anchor);
        ms.push({
          pos,
          occluded: () => mode === "pano" && pano.occluded(pos),
          el: h(
            "button",
            {
              type: "button",
              class: `pin device ${review ? "review" : "ok"}`,
              "data-key": d.device_id,
              "aria-label": `Device ${deviceLabel(d)} in ${t.cabinet}, ${review ? "needs review" : "OK"}`,
              onclick: () => select(t, d),
            },
            h("span", { class: "badge", "aria-hidden": "true" }, review ? "!" : "✓"),
            h("span", { class: "pin-label" }, deviceLabel(d)),
          ),
        });
      }
    }
    for (const s of manifest.sweeps) {
      if (mode === "pano") {
        ms.push({
          pos: pano.floorPoint(s),
          radius: 0.24,
          visible: () => pano.isNearby(s.id),
          el: h("button", {
            type: "button",
            class: "hotspot",
            "aria-label": `Go to scan position ${s.id}`,
            onclick: () => goTo(s),
          }),
        });
      } else {
        ms.push({
          pos: pano.floorPoint(s),
          el: h("button", { type: "button", class: "sweep-dot", "aria-label": `Enter the panorama at ${s.id}`, onclick: () => goTo(s) }, String(s.index)),
        });
      }
    }
    overlay.set(ms);
    markSelected();
    requestRender();
  }

  function markSelected() {
    const key = panel.selection?.device?.device_id ?? panel.selection?.tag.id;
    for (const el of overlay.root.querySelectorAll(".pin")) el.classList.toggle("selected", (el as HTMLElement).dataset.key === key);
    for (const el of document.querySelectorAll("#tag-list button")) {
      if ((el as HTMLElement).dataset.key === key) el.setAttribute("aria-current", "true");
      else el.removeAttribute("aria-current");
    }
  }

  function buildTagList() {
    const list = $("tag-list");
    const empty = $("tag-empty");
    const project = projectInput.value.trim();
    empty.hidden = !!file?.tags.length;
    empty.textContent = !project
      ? "Enter a project label to load its tags."
      : file
        ? "The tag file has no tags."
        : `No tags for ${project} yet. Press Run detection.`;
    list.replaceChildren(
      ...(file?.tags ?? []).map((t) =>
        h(
          "li",
          {},
          h("button", { type: "button", class: "link cabinet-link", "data-key": t.id, onclick: () => select(t, undefined, true) }, `${t.cabinet} (${t.devices.length})`),
          t.devices.length
            ? h(
                "ul",
                {},
                t.devices.map((d) => {
                  const review = isReview(d);
                  return h(
                    "li",
                    {},
                    h(
                      "button",
                      {
                        type: "button",
                        class: `link ${review ? "review" : "ok"}`,
                        "data-key": d.device_id,
                        "aria-label": `${deviceLabel(d)}, ${review ? "needs review" : "OK"}`,
                        onclick: () => select(t, d, true),
                      },
                      h("span", { class: "badge", "aria-hidden": "true" }, review ? "!" : "✓"),
                      deviceLabel(d),
                    ),
                  );
                }),
              )
            : null,
        ),
      ),
    );
    markSelected();
  }

  function buildSweepList() {
    $("sweep-list").replaceChildren(
      ...manifest.sweeps.map((s) =>
        h("li", {}, h("button", { type: "button", class: "link", "data-sweep": s.id, onclick: () => goTo(s) }, `${s.id}`)),
      ),
    );
  }

  function markSweep() {
    for (const el of document.querySelectorAll<HTMLElement>("#sweep-list button")) {
      if (el.dataset.sweep === pano.sweep?.id) el.setAttribute("aria-current", "location");
      else el.removeAttribute("aria-current");
    }
  }

  function updateCounts() {
    const devices = (file?.tags ?? []).flatMap((t) => t.devices);
    $("device-count").textContent = String(devices.length);
    $("review-count").textContent = String(devices.filter(isReview).length);
  }

  function updateBoxes() {
    const colors = { review: REVIEW_COLOR, ok: OK_COLOR, browser: BROWSER_COLOR };
    pano.setBoxes(sweepBoxes().map(({ box, kind }) => ({ box, color: colors[kind] })));
    requestRender();
  }

  function setParam(key: string, value: string) {
    const url = new URL(location.href);
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
    history.replaceState(null, "", url);
  }

  async function goTo(s: Sweep, look?: { u: number; v: number }) {
    if (mode !== "pano") setMode("pano");
    try {
      await pano.jump(s);
    } catch (e) {
      say(`The panorama for ${s.id} did not load: ${(e as Error).message}`, 8000);
      return;
    }
    if (look) pano.lookAtPixel(look.u, look.v);
    setParam("sweep", s.id);
    markSweep();
    updateBoxes();
    if (showAll) buildMarkers();
    if (panel.selection && !panel.editing) panel.render();
    cancelAnimationFrame(frame);
    draw(performance.now());
    const focused = document.activeElement as HTMLElement | null;
    if (!focused || focused === document.body || (overlay.root.contains(focused) && focused.hidden)) canvas.focus();
  }

  const boxCenter = (b: Box) => ({ u: (b.x + b.width / 2) % manifest.pano_width, v: b.y + b.height / 2 });

  function face(tag: Tag, device?: Device) {
    if (mode !== "pano" || !pano.sweep) return;
    const here = pano.sweep.id;
    const box = device?.boxes.find((b) => b.scan_position === here);
    if (box) return pano.lookAtPixel(boxCenter(box).u, boxCenter(box).v);
    const anchor = device ? device.anchor : tag.anchor;
    if (anchor) {
      const p = panoPixel(toThree(anchor).sub(pano.camera.position), manifest.pano_width, manifest.pano_height);
      return pano.lookAtPixel(p.u, p.v);
    }
    const other = device?.boxes[0];
    if (other && sweepById.has(other.scan_position)) goTo(sweepById.get(other.scan_position)!, boxCenter(other));
  }

  function select(tag: Tag, device?: Device, turn = false) {
    if (!panel.selection) returnFocus = document.activeElement as HTMLElement | null;
    panel.show(tag, device);
    markSelected();
    updateBoxes();
    if (turn) face(tag, device);
  }

  function closePanel() {
    const key = panel.selection?.device?.device_id ?? panel.selection?.tag.id;
    panel.hide();
    markSelected();
    updateBoxes();
    cancelAnimationFrame(frame);
    draw(performance.now());
    const back =
      (returnFocus?.isConnected && !returnFocus.hidden && returnFocus) ||
      document.querySelector<HTMLElement>(`#overlay [data-key="${key}"]:not([hidden]), #tag-list [data-key="${key}"]`) ||
      canvas;
    back.focus();
    returnFocus = null;
  }

  const panel = new Panel($("panel"), {
    file: () => file!,
    threshold: () => threshold,
    currentSweep: () => (mode === "pano" ? (pano.sweep?.id ?? null) : null),
    showBox: (b) => {
      const s = sweepById.get(b.scan_position);
      if (s) goTo(s, boxCenter(b));
    },
    openTag: (t) => select(t),
    openDevice: (t, d) => select(t, d),
    close: closePanel,
    cancel: () => {},
    placeAnchor: () =>
      new Promise((resolve) => {
        placing?.(undefined);
        if (mode !== "pano") setMode("pano");
        placing = resolve;
        stage.classList.add("placing");
        say("Click the panorama to place the anchor, or press Enter to place it at the view center. Press Escape to cancel.");
      }),
    save: async (next) => {
      const keep = panel.selection?.device?.device_id;
      const saved = await putTags(next);
      setFile(saved);
      const found = keep ? findDevice(keep) : null;
      if (found) {
        panel.editing = false;
        panel.show(found.tag, found.device);
      }
      say("The tag file is saved.", 4000);
    },
  });

  function finishPlacing(p: Point3 | null | undefined) {
    const done = placing;
    placing = null;
    stage.classList.remove("placing");
    say("");
    done?.(p);
  }

  async function placeAt(clientX: number, clientY: number) {
    if (!pano.sweep) return finishPlacing(undefined);
    const rect = canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, pano.camera);
    const { u, v } = panoPixel(ray.ray.direction, manifest.pano_width, manifest.pano_height);
    say("Looking up the scan point");
    try {
      const res = await raycast(pano.sweep.id, u, v);
      finishPlacing(res.anchor);
    } catch (e) {
      say(`Raycast failed: ${(e as Error).message}`, 6000);
      finishPlacing(undefined);
    }
  }

  function setFile(f: TagFile | null) {
    file = f;
    if (f) {
      threshold = f.review_threshold;
      thresholdInput.value = String(threshold);
      $("threshold-value").textContent = threshold.toFixed(2);
      siteInput.value = f.site;
    }
    const sel = panel.selection;
    if (sel) {
      const found = sel.device ? findDevice(sel.device.device_id) : null;
      const tag = found?.tag ?? f?.tags.find((t) => t.id === sel.tag.id);
      if (found) panel.selection = found;
      else if (tag && !sel.device) panel.selection = { tag };
      else panel.hide();
      if (!panel.editing) panel.render();
    }
    buildMarkers();
    buildTagList();
    updateCounts();
    updateBoxes();
  }

  let loadToken = 0;
  async function loadTags(project: string) {
    const token = ++loadToken;
    if (!project) return setFile(null);
    try {
      const f = await getTags(project);
      if (token === loadToken) setFile(f);
    } catch (e) {
      if (token === loadToken) {
        setFile(null);
        say(`The tags did not load: ${(e as Error).message}`, 8000);
      }
    }
  }

  function setMode(m: typeof mode) {
    mode = m;
    $("mode-pano").setAttribute("aria-pressed", String(m === "pano"));
    $("mode-dollhouse").setAttribute("aria-pressed", String(m === "dollhouse"));
    doll.controls.enabled = m === "dollhouse";
    $("cut").hidden = m !== "dollhouse" || !manifest.cloud;
    stage.classList.toggle("dollhouse", m === "dollhouse");
    canvas.setAttribute(
      "aria-label",
      m === "pano"
        ? "Panorama view. Drag, or use the arrow keys, to look around. Use the wheel, a pinch, or the plus and minus keys to zoom."
        : "Dollhouse view. Drag, or use the arrow keys, to orbit. Right-drag, or use Shift and the arrow keys, to pan. Use the wheel, a pinch, or the plus and minus keys to zoom.",
    );
    if (m === "dollhouse") {
      if (placing) finishPlacing(undefined);
      const loading = doll.load();
      say(doll.status);
      loading.then(() => mode === "dollhouse" && say(doll.status));
    } else say("");
    buildMarkers();
    if (panel.selection && !panel.editing) panel.render();
  }

  $("mode-pano").addEventListener("click", () => setMode("pano"));
  $("mode-dollhouse").addEventListener("click", () => setMode("dollhouse"));
  cutInput.addEventListener("input", () => {
    doll.cut = Number(cutInput.value);
    $("cut-value").textContent = Number(cutInput.value).toFixed(1);
  });

  thresholdInput.addEventListener("input", () => {
    threshold = Number(thresholdInput.value);
    $("threshold-value").textContent = threshold.toFixed(2);
    buildMarkers();
    buildTagList();
    updateCounts();
    updateBoxes();
    if (panel.selection && !panel.editing) panel.render();
  });

  let projectTimer = 0;
  projectInput.addEventListener("input", () => {
    const project = projectInput.value.trim();
    if (file && siteInput.value === file.site) siteInput.value = "";
    siteInput.placeholder = project;
    setParam("project", project);
    clearTimeout(projectTimer);
    projectTimer = window.setTimeout(() => loadTags(project), 400);
  });

  $("run-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const project = projectInput.value.trim();
    if (!project) {
      showRun("Enter a project label first.");
      projectInput.focus();
      return;
    }
    runButton.disabled = true;
    showRun("Starting the run", 0);
    try {
      const { run_id } = await startRun({ project, site: siteInput.value.trim() || project, review_threshold: threshold });
      for (;;) {
        const r = await getRun(run_id);
        if (r.state === "failed") {
          showRun(`The run failed: ${r.message || r.step}`);
          break;
        }
        if (r.state === "done") {
          await loadTags(project);
          const n = (file?.tags ?? []).reduce((s, t) => s + t.devices.length, 0);
          showRun(`The run is complete. ${n} ${n === 1 ? "device" : "devices"} loaded.`, 1);
          break;
        }
        showRun(`${r.step || "Running"}: ${Math.round(r.progress * 100)} %`, r.progress);
        await new Promise((res) => setTimeout(res, 1000));
      }
    } catch (err) {
      showRun(`The run did not complete: ${(err as Error).message}`);
    } finally {
      runButton.disabled = false;
    }
  });

  detectButton.addEventListener("click", async () => {
    const sweep = pano.sweep;
    const texture = pano.currentTexture();
    if (mode !== "pano" || !sweep || !texture) {
      showRun("Open a panorama first.");
      return;
    }
    detectButton.disabled = true;
    try {
      const floor = file?.min_confidence ?? MIN_CONFIDENCE;
      const res = await browserDetector.detect(texture, (text, fraction) => showRun(text, fraction));
      const found = res.detections.filter((x) => x.score >= floor).sort((a, b) => b.score - a.score);
      browserBoxes.set(sweep.id, found);
      updateBoxes();
      if (showAll) buildMarkers();
      const scores = found.map((x) => x.score.toFixed(2)).join(", ");
      showRun(
        `Browser detection on ${sweep.id}: ${found.length} REX615 ${found.length === 1 ? "plate" : "plates"}${scores ? ` (${scores})` : ""} ` +
          `above ${floor.toFixed(2)}, ${res.tiles} tiles in ${res.seconds.toFixed(1)} s with ${res.backend}. The boxes are cyan.`,
        1,
      );
    } catch (err) {
      showRun(`Browser detection failed: ${(err as Error).message}`);
    } finally {
      detectButton.disabled = false;
    }
  });

  showBoxesButton.addEventListener("click", () => {
    showAll = !showAll;
    showBoxesButton.setAttribute("aria-pressed", String(showAll));
    updateBoxes();
    buildMarkers();
    const sid = pano.sweep?.id;
    if (showAll && sid) {
      const n = sweepBoxes().length;
      say(`${n} detected ${n === 1 ? "box" : "boxes"} on ${sid}. Orange needs review, green is OK, cyan is from the browser.`, 6000);
    }
  });

  const pointers = new Map<number, { x: number; y: number }>();
  let down: { x: number; y: number } | null = null;
  let moved = false;
  let pinch = 0;
  const spread = () => {
    const [a, b] = [...pointers.values()];
    return Math.hypot(a.x - b.x, a.y - b.y);
  };
  canvas.addEventListener("pointerdown", (e) => {
    if (mode !== "pano") return;
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
  canvas.addEventListener("pointermove", (e) => {
    const prev = pointers.get(e.pointerId);
    if (!prev || mode !== "pano") return;
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
      if (!moved && down && placing && e.type === "pointerup") placeAt(e.clientX, e.clientY);
      down = null;
    }
  };
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  canvas.addEventListener(
    "wheel",
    (e) => {
      if (mode !== "pano") return;
      e.preventDefault();
      pano.zoom(Math.exp(e.deltaY * 0.001));
    },
    { passive: false },
  );

  window.addEventListener("keydown", (e) => {
    const t = e.target as HTMLElement;
    if (e.key === "Escape") {
      if (placing) finishPlacing(undefined);
      else if (panel.selection && !(panel.editing && $("panel").contains(t))) closePanel();
      return;
    }
    if (!(t === document.body || t === canvas || overlay.root.contains(t))) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (mode === "dollhouse") {
      if (doll.key(e)) e.preventDefault();
      return;
    }
    if (placing && t === canvas && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      placeAt(r.left + r.width / 2, r.top + r.height / 2);
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
  });

  buildSweepList();
  buildMarkers();
  buildTagList();

  const params = new URLSearchParams(location.search);
  const centroid = manifest.sweeps.reduce((c, s) => c.add(toThree(s.position)), new THREE.Vector3()).divideScalar(manifest.sweeps.length);
  const first =
    sweepById.get(params.get("sweep") ?? "") ??
    manifest.sweeps.reduce((a, b) => (toThree(a.position).distanceTo(centroid) <= toThree(b.position).distanceTo(centroid) ? a : b));
  pano.jump(first, false).then(() => {
    markSweep();
    requestRender();
  }, (e) => say(`The panorama for ${first.id} did not load: ${(e as Error).message}`));

  const project = params.get("project");
  if (project) {
    projectInput.value = project;
    siteInput.placeholder = project;
    loadTags(project);
  }
}

boot();
